"""Read rounds from round_links_new.csv and collect each one.

Each row has the round id plus verification_link and scoring_link.
Pass a count to read only that many rows from the top of the file:

    python collect_round.py 3

The six reveal files are downloaded into downloads/<round_id>/ and uploaded
to the Hugging Face model repo for that round's chromosome. Fill HF_REPOS and
set HF_TOKEN before running. Each collected round is then upserted into the
Supabase public.rounds table. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
Collected objects are also printed and written to rounds.jsonl.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from huggingface_hub import HfApi

LINKS_PATH = Path(__file__).with_name("round_links_new.csv")
OUT_PATH = Path(__file__).with_name("rounds.jsonl")
DOWNLOADS = Path(__file__).with_name("downloads")
ENV_PATH = Path(__file__).with_name(".env")
# Scoring for this round was not finished, so it is never collected.
SKIP_ROUNDS = {"2026-09-25T23:53:00+00:00"}
# One Hugging Face model repo per chromosome. Fill these with your repo ids,
# for example "your-name/minos-chr20".
HF_REPOS = {
    "chr14": "eliteminer/minos_ch14",
    "chr15": "eliteminer/minos_ch15",
    "chr16": "eliteminer/minos_ch16",
    "chr17": "eliteminer/minos_ch17",
    "chr18": "eliteminer/minos_ch18",
    "chr19": "eliteminer/minos_ch19",
    "chr20": "eliteminer/minos_ch20",
    "chr21": "eliteminer/minos_ch21",
    "chr22": "eliteminer/minos_ch22",
}


def load_env(path: Path = ENV_PATH) -> None:
    """Load KEY=VALUE lines from .env. Existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def read_links(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rank_one(leaderboard: dict, commitments: list[dict]) -> dict | None:
    """Scoring fields for the rank-1 miner only."""
    winner = next(
        (entry for entry in leaderboard.get("entries", []) if entry.get("rank") == 1),
        None,
    )
    if winner is None:
        return None

    commitment = next(
        (row for row in commitments if row.get("hotkey") == winner.get("hotkey")),
        {},
    )
    return {
        "hotkey": winner.get("hotkey"),
        "uid": winner.get("uid"),
        "tool_name": winner.get("tool_name") or commitment.get("tool_name"),
        "config_hash": commitment.get("config_hash"),
        "rank": winner.get("rank"),
        "status": winner.get("status"),
        "combined_final": winner.get("combined_final"),
        "snp_final": winner.get("snp_final"),
        "indel_final": winner.get("indel_final"),
        "weight": winner.get("weight"),
        "incentive": winner.get("incentive"),
        "emission": winner.get("emission"),
        "eligible": winner.get("eligible"),
        "participation_count": winner.get("participation_count"),
        "validator_count": winner.get("validator_count"),
        "submitted_at": winner.get("submitted_at"),
        "scored_at": winner.get("scored_at"),
    }


def combine(verification: dict, leaderboard: dict) -> dict:
    commitments = verification.get("commitments", [])
    round_info = leaderboard.get("round", {})
    reveal = verification.get("reveal") or {}

    return {
        "round_id": verification.get("round_id") or round_info.get("round_id"),
        "status": round_info.get("status") or verification.get("round_status"),
        "region": round_info.get("region"),
        "window_id": verification.get("window_id"),
        "selected_position": verification.get("selected_position"),
        "draw": verification.get("draw"),
        "file_hashes": verification.get("file_hashes"),
        "files": reveal.get("files"),
        "chain": verification.get("chain"),
        "timing": {
            "start_time": round_info.get("start_time"),
            "submission_end_time": round_info.get("submission_end_time"),
            "scoring_end_time": round_info.get("scoring_end_time"),
            "score_finalization_time": round_info.get("score_finalization_time"),
        },
        "counts": {
            "submissions": round_info.get("submission_count"),
            "scored": round_info.get("scored_submission_count"),
            "scores": round_info.get("score_count"),
            "identity_revealed": round_info.get("identity_revealed"),
            "is_finalized": round_info.get("is_finalized"),
        },
        "rank_1": rank_one(leaderboard, commitments),
    }


def collect_from_links(verification_url: str, scoring_url: str) -> dict:
    verification = fetch_json(verification_url)
    leaderboard = fetch_json(scoring_url)
    return combine(verification, leaderboard)


def chromosome(region: str | None) -> str:
    if not region or ":" not in region:
        raise ValueError(f"region has no chromosome: {region}")
    return region.split(":", 1)[0]


def folder_name(round_id: str) -> str:
    """Windows folder names cannot contain ':'. The same name is used on Hugging Face."""
    return round_id.replace(":", "-")


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=300) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def download_round_files(collected: dict) -> Path:
    """Download the six reveal files into downloads/<round_id>/."""
    name = folder_name(collected["round_id"])
    folder = DOWNLOADS / name
    folder.mkdir(parents=True, exist_ok=True)
    for item in collected.get("files") or []:
        destination = folder / item["name"]
        print(f"  download {item['name']}", file=sys.stderr, flush=True)
        download_file(item["url"], destination)
    return folder


def upload_round_folder(collected: dict, folder: Path) -> str:
    """Upload downloads/<round_id>/ into the chromosome's Hugging Face model repo."""
    chrom = chromosome(collected.get("region"))
    repo_id = HF_REPOS.get(chrom, "").strip()
    if not repo_id:
        raise ValueError(f"no Hugging Face repo configured for {chrom}")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError("set HF_TOKEN to a Hugging Face token that can write the model repo")

    remote_folder = folder.name
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)
    print(f"  upload {remote_folder} -> {repo_id}", file=sys.stderr, flush=True)
    api.upload_folder(
        folder_path=str(folder),
        path_in_repo=remote_folder,
        repo_id=repo_id,
        repo_type="model",
    )
    return f"https://huggingface.co/{repo_id}/tree/main/{remote_folder}"


def round_row(collected: dict) -> dict:
    """Flatten one collected round into a public.rounds row."""
    draw = collected.get("draw") or {}
    hashes = collected.get("file_hashes") or {}
    chain = collected.get("chain") or {}
    timing = collected.get("timing") or {}
    counts = collected.get("counts") or {}
    winner = collected.get("rank_1") or {}
    return {
        "round_id": collected.get("round_id"),
        "status": collected.get("status"),
        "region": collected.get("region"),
        "window_id": collected.get("window_id"),
        "selected_position": collected.get("selected_position"),
        "draw_block_height": draw.get("block_height"),
        "draw_block_hash": draw.get("block_hash"),
        "file_hash_bam": hashes.get("bam"),
        "file_hash_truth_vcf": hashes.get("truth_vcf"),
        "file_hash_mutations_vcf": hashes.get("mutations_vcf"),
        "files": collected.get("files") or [],
        "chain_network": chain.get("network"),
        "chain_netuid": chain.get("netuid"),
        "start_time": timing.get("start_time"),
        "submission_end_time": timing.get("submission_end_time"),
        "scoring_end_time": timing.get("scoring_end_time"),
        "score_finalization_time": timing.get("score_finalization_time"),
        "submission_count": counts.get("submissions"),
        "scored_count": counts.get("scored"),
        "score_count": counts.get("scores"),
        "identity_revealed": counts.get("identity_revealed"),
        "is_finalized": counts.get("is_finalized"),
        "rank_1_hotkey": winner.get("hotkey"),
        "rank_1_uid": winner.get("uid"),
        "rank_1_tool_name": winner.get("tool_name"),
        "rank_1_config_hash": winner.get("config_hash"),
        "rank_1_status": winner.get("status"),
        "rank_1_combined_final": winner.get("combined_final"),
        "rank_1_snp_final": winner.get("snp_final"),
        "rank_1_indel_final": winner.get("indel_final"),
        "rank_1_weight": winner.get("weight"),
        "rank_1_incentive": winner.get("incentive"),
        "rank_1_emission": winner.get("emission"),
        "rank_1_eligible": winner.get("eligible"),
        "rank_1_participation_count": winner.get("participation_count"),
        "rank_1_validator_count": winner.get("validator_count"),
        "rank_1_submitted_at": winner.get("submitted_at"),
        "rank_1_scored_at": winner.get("scored_at"),
        "huggingface": collected.get("huggingface"),
    }


def round_in_database(round_id: str) -> bool:
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        return False
    query = urllib.parse.quote(round_id, safe="")
    request = urllib.request.Request(
        f"{base}/rest/v1/rounds?round_id=eq.{query}&select=round_id",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return bool(json.load(response))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False


def round_on_huggingface(collected: dict) -> bool:
    chrom = chromosome(collected.get("region"))
    repo_id = HF_REPOS.get(chrom, "").strip()
    expected = {item["name"] for item in collected.get("files") or []}
    if not repo_id or not expected:
        return False
    try:
        entries = HfApi().list_repo_tree(
            repo_id=repo_id,
            path_in_repo=folder_name(collected["round_id"]),
            repo_type="model",
            token=os.environ.get("HF_TOKEN"),
        )
    except Exception:
        return False
    present = {getattr(entry, "path", "").rsplit("/", 1)[-1] for entry in entries}
    return expected.issubset(present)


def save_round(collected: dict) -> None:
    """Upsert one round into Supabase. Re-running the same round_id updates the row."""
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        raise ValueError("set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")

    request = urllib.request.Request(
        f"{base}/rest/v1/rounds?on_conflict=round_id",
        data=json.dumps(round_row(collected)).encode(),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        response.read()


def main() -> None:
    load_env()
    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if count is not None and count < 1:
        raise SystemExit("count must be at least 1")

    rows = [row for row in read_links(LINKS_PATH) if row["round"] not in SKIP_ROUNDS]
    if count is not None:
        rows = rows[:count]

    collected_rows = []
    for index, row in enumerate(rows, start=1):
        round_id = row["round"]
        verification_status = row.get("verification_status") or "200"
        scoring_status = row.get("scoring_status") or "200"
        if verification_status != "200" or scoring_status != "200":
            print(
                f"{index}/{len(rows)} skip {round_id} "
                f"verification={verification_status} scoring={scoring_status}",
                file=sys.stderr,
                flush=True,
            )
            continue
        try:
            collected = collect_from_links(row["verification_link"], row["scoring_link"])
            if round_in_database(collected["round_id"]) and round_on_huggingface(collected):
                print(
                    f"{index}/{len(rows)} skip {collected['round_id']} already uploaded",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            folder = download_round_files(collected)
            collected["huggingface"] = upload_round_folder(collected, folder)
            save_round(collected)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError, OSError) as error:
            print(f"{index}/{len(rows)} fail {round_id} {error}", file=sys.stderr, flush=True)
            continue
        collected_rows.append(collected)
        print(f"{index}/{len(rows)} {collected['round_id']} {collected['huggingface']}", file=sys.stderr, flush=True)

    print(json.dumps(collected_rows, indent=2))
    with OUT_PATH.open("w", encoding="utf-8") as handle:
        for collected in collected_rows:
            handle.write(json.dumps(collected) + "\n")


if __name__ == "__main__":
    main()
