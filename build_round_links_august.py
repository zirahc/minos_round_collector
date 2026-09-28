"""Write rounds_links_august.csv for August 2026.

Walks backward from the earliest September round, 2026-09-01T00:08:00+00:00.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import check_round_links as links

OUT_PATH = Path(__file__).with_name("rounds_links_august.csv")
FIRST_DAY = datetime(2026, 8, 1, tzinfo=timezone.utc)
ANCHOR = datetime(2026, 9, 1, 0, 8, tzinfo=timezone.utc)
FIELDS = [
    "round",
    "verification_link",
    "scoring_link",
    "verification_status",
    "scoring_status",
]


def collect() -> int:
    count = 0
    broken = 0
    cursor = ANCHOR - links.STEP
    with OUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        while cursor >= FIRST_DAY:
            found = links.locate(cursor)
            if found is None:
                print(f"missing {links.round_id(cursor)}", flush=True)
                cursor -= links.STEP
                continue
            if found < FIRST_DAY:
                break
            if found >= ANCHOR:
                cursor = found - links.STEP
                continue
            record = links.row_for(found, scoring="200")
            writer.writerow(record)
            handle.flush()
            count += 1
            if record["verification_status"] != "200":
                broken += 1
            print(f"{record['round']} verification={record['verification_status']}", flush=True)
            cursor = found - links.STEP
    print(f"wrote {count} rows to {OUT_PATH}")
    print(f"links not 200: {broken}")
    return count


if __name__ == "__main__":
    collect()
