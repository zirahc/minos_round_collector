"""Write scored rounds newer than round_links_9_01_9_25.csv into a new CSV."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import append_scored_rounds as scored
import check_round_links as links

SOURCE = Path(__file__).with_name("round_links_9_01_9_25.csv")
OUT = Path(__file__).with_name("round_links_9_27_9_29.csv")


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        existing = list(csv.DictReader(handle))
    newest = max(datetime.fromisoformat(row["round"]) for row in existing)

    added = []
    cursor = newest
    while True:
        found = scored.locate_next(cursor)
        if found is None or found <= cursor:
            break
        key = links.round_id(found)
        _, scoring_link = links.links(key)
        payload = scored.scoring_body(scoring_link)
        if payload is None or not scored.is_scored(payload):
            print(f"skip {key} not scored", flush=True)
            break
        record = links.row_for(found, scoring="200")
        added.append(record)
        print(f"add {key} verification={record['verification_status']}", flush=True)
        cursor = found

    added.sort(key=lambda row: row["round"], reverse=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=scored.FIELDS)
        writer.writeheader()
        writer.writerows(added)
    print(f"wrote {len(added)} rounds to {OUT.name}")


if __name__ == "__main__":
    main()
