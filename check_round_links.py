"""Check verification and scoring links for each Minos round.

Rounds are 72 minutes apart. From 2026-09-25 back through 2026-09-20 the
start time sometimes shifts by a minute or two, so a miss searches the
previous 71 minutes for the real round.

Writes round_links.csv:
round, verification_link, scoring_link, verification_status, scoring_status
"""

from __future__ import annotations

import csv
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.theminos.ai"
STEP = timedelta(minutes=72)
# Last round on 2026-09-25. Earlier rounds are this time minus N * 72 minutes,
# plus small shifts when the chain clock moved.
START = datetime(2026, 9, 25, 23, 53, tzinfo=timezone.utc)
FIRST_DAY = datetime(2026, 9, 20, tzinfo=timezone.utc)
OUT_PATH = Path(__file__).with_name("round_links.csv")
TIMEOUT = 30
WORKERS = 4


def round_id(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def links(round_key: str) -> tuple[str, str]:
    encoded = urllib.parse.quote(round_key, safe="")
    verification = f"{API}/verification/round/{encoded}"
    scoring = f"{API}/scoring/rounds/{encoded}/leaderboard"
    return verification, scoring


def http_status(url: str) -> str:
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                response.read(1)
                return str(response.status)
        except urllib.error.HTTPError as error:
            if error.code in (403, 429, 503) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            return str(error.code)
        except Exception as error:
            if attempt < 5:
                time.sleep(2 ** attempt)
                continue
            return f"error: {error}"
    return "error: retries exhausted"


def scoring_status(moment: datetime) -> str:
    _, scoring = links(round_id(moment))
    return http_status(scoring)


def locate(expected: datetime) -> datetime | None:
    """Return the round at `expected`, or the latest real round up to 71 minutes earlier."""
    if scoring_status(expected) == "200":
        return expected
    # The clock usually slips only a few minutes. Check those before a wide scan.
    near = [expected - timedelta(minutes=delta) for delta in range(1, 9)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        near_status = list(pool.map(scoring_status, near))
    near_hits = [moment for moment, status in zip(near, near_status) if status == "200"]
    if near_hits:
        return max(near_hits)
    far = [expected - timedelta(minutes=delta) for delta in range(9, 72)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        far_status = list(pool.map(scoring_status, far))
    far_hits = [moment for moment, status in zip(far, far_status) if status == "200"]
    if not far_hits:
        return None
    return max(far_hits)


def row_for(moment: datetime, scoring: str | None = None) -> dict[str, str]:
    key = round_id(moment)
    verification, scoring_link = links(key)
    return {
        "round": key,
        "verification_link": verification,
        "scoring_link": scoring_link,
        "verification_status": http_status(verification),
        "scoring_status": scoring if scoring is not None else http_status(scoring_link),
    }


def collect() -> list[dict[str, str]]:
    rows = []
    cursor = START
    while cursor >= FIRST_DAY:
        found = locate(cursor)
        if found is None:
            rows.append(row_for(cursor, scoring="404"))
            print(f"missing {round_id(cursor)}", flush=True)
            cursor -= STEP
            continue
        if found.astimezone(timezone.utc) < FIRST_DAY:
            break
        record = row_for(found, scoring="200")
        rows.append(record)
        print(
            f"{record['round']} verification={record['verification_status']} scoring=200",
            flush=True,
        )
        cursor = found - STEP
    return rows


def main() -> None:
    rows = collect()
    try:
        handle = OUT_PATH.open("w", newline="", encoding="utf-8")
    except PermissionError:
        handle = OUT_PATH.with_name("round_links_new.csv").open("w", newline="", encoding="utf-8")
    with handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "round",
                "verification_link",
                "scoring_link",
                "verification_status",
                "scoring_status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    broken = [
        row
        for row in rows
        if row["verification_status"] != "200" or row["scoring_status"] != "200"
    ]
    print(f"wrote {len(rows)} rows to {OUT_PATH}")
    print(f"links not 200: {len(broken)}")
    for row in broken:
        print(
            f"  {row['round']} verification={row['verification_status']} "
            f"scoring={row['scoring_status']}"
        )


if __name__ == "__main__":
    main()
