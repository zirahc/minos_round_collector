"""Write scored rounds newer than a source CSV into an output CSV."""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path

import append_scored_rounds as scored
import check_round_links as links

SOURCE = Path(__file__).with_name("round_links_9_29_10_05.csv")
OUT = Path(__file__).with_name("round_links_9_29_10_05.csv")


def scoring_body_retry(url: str, attempts: int = 5) -> dict | None:
    for attempt in range(attempts):
        payload = scored.scoring_body(url)
        if payload is not None:
            return payload
        time.sleep(2 ** attempt)
    return None


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        existing = list(csv.DictReader(handle))
    known = {row["round"] for row in existing}
    newest = max(datetime.fromisoformat(row["round"]) for row in existing)

    added = []
    cursor = newest
    while True:
        found = scored.locate_next(cursor)
        if found is None or found <= cursor:
            break
        key = links.round_id(found)
        _, scoring_link = links.links(key)
        payload = scoring_body_retry(scoring_link)
        if payload is None or not scored.is_scored(payload):
            print(f"skip {key} not scored", flush=True)
            break
        if key not in known:
            record = links.row_for(found, scoring="200")
            added.append(record)
            print(f"add {key} verification={record['verification_status']}", flush=True)
        else:
            print(f"have {key}", flush=True)
        cursor = found

    if not added:
        print(f"no new scored rounds; {OUT.name} still has {len(existing)}")
        return

    added.sort(key=lambda row: row["round"], reverse=True)
    rows = added + existing
    temporary = OUT.with_suffix(OUT.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=scored.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(OUT)
    print(f"added {len(added)} rounds, now {len(rows)} in {OUT.name}")


if __name__ == "__main__":
    main()
