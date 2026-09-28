"""Add scored rounds newer than the newest row in round_links_9_01_9_25.csv."""

from __future__ import annotations

import csv
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import check_round_links as links

PATH = Path(__file__).with_name("round_links_9_01_9_25.csv")
FIELDS = [
    "round",
    "verification_link",
    "scoring_link",
    "verification_status",
    "scoring_status",
]


def scoring_body(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 200:
                return None
            return json.load(response)
    except Exception:
        return None


def is_scored(payload: dict) -> bool:
    info = payload.get("round") or {}
    return (
        info.get("status") == "completed"
        and info.get("is_finalized") is True
        and (info.get("scored_submission_count") or 0) > 0
    )


def locate_next(previous: datetime) -> datetime | None:
    expected = previous + links.STEP
    offsets = [0]
    for delta in range(1, 9):
        offsets.extend((delta, -delta))
    for offset in offsets:
        moment = expected + timedelta(minutes=offset)
        if links.scoring_status(moment) == "200":
            return moment
    return None


def main() -> None:
    with PATH.open(newline="", encoding="utf-8") as handle:
        existing = list(csv.DictReader(handle))
    known = {row["round"] for row in existing}
    newest = max(datetime.fromisoformat(row["round"]) for row in existing)

    added = []
    cursor = newest
    while True:
        found = locate_next(cursor)
        if found is None or found <= cursor:
            break
        key = links.round_id(found)
        _, scoring_link = links.links(key)
        payload = scoring_body(scoring_link)
        if payload is None or not is_scored(payload):
            print(f"skip {key} not scored", flush=True)
            break
        if key not in known:
            record = links.row_for(found, scoring="200")
            added.append(record)
            print(f"add {key} verification={record['verification_status']}", flush=True)
        cursor = found

    if not added:
        print("no new scored rounds")
        return

    added.sort(key=lambda row: row["round"], reverse=True)
    rows = added + existing
    temporary = PATH.with_suffix(PATH.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(PATH)
    print(f"added {len(added)} rounds, now {len(rows)}")


if __name__ == "__main__":
    main()
