"""Write round_links_new.csv for 2026-09-01 through 2026-09-19.

Walks backward from the earliest round in round_links_old.csv. Rounds already
listed there are left out.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import check_round_links as links

OLD_PATH = Path(__file__).with_name("round_links_old.csv")
OUT_PATH = Path(__file__).with_name("round_links_new.csv")
FIRST_DAY = datetime(2026, 9, 1, tzinfo=timezone.utc)
# Earliest round already stored. The walk starts one step before it.
ANCHOR = datetime(2026, 9, 20, 0, 48, tzinfo=timezone.utc)


def old_round_ids() -> set[str]:
    with OLD_PATH.open(newline="", encoding="utf-8") as handle:
        return {row["round"] for row in csv.DictReader(handle)}


def collect() -> list[dict[str, str]]:
    known = old_round_ids()
    rows: list[dict[str, str]] = []
    cursor = ANCHOR - links.STEP
    while cursor >= FIRST_DAY:
        found = links.locate(cursor)
        if found is None:
            print(f"missing {links.round_id(cursor)}", flush=True)
            cursor -= links.STEP
            continue
        if found < FIRST_DAY:
            break
        key = links.round_id(found)
        if key in known or found >= ANCHOR:
            cursor = found - links.STEP
            continue
        record = links.row_for(found, scoring="200")
        rows.append(record)
        print(f"{key} verification={record['verification_status']}", flush=True)
        cursor = found - links.STEP
    rows.sort(key=lambda row: row["round"], reverse=True)
    return rows


def main() -> None:
    rows = collect()
    with OUT_PATH.open("w", newline="", encoding="utf-8") as handle:
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


if __name__ == "__main__":
    main()
