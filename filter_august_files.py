"""Drop August rounds whose verification payload has no downloadable files."""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("rounds_links_august.csv")
FIELDS = [
    "round",
    "verification_link",
    "scoring_link",
    "verification_status",
    "scoring_status",
]


def file_link_count(url: str) -> int | None:
    """Return how many reveal files have a URL. None means the request failed."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.load(response)
            files = (payload.get("reveal") or {}).get("files") or []
            return sum(1 for item in files if item.get("url"))
        except urllib.error.HTTPError as error:
            if error.code in (403, 429, 503) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            return 0
        except Exception:
            if attempt < 5:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def main() -> None:
    with PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    with ThreadPoolExecutor(max_workers=4) as pool:
        counts = list(pool.map(lambda row: file_link_count(row["verification_link"]), rows))

    kept = []
    removed = 0
    failed = 0
    for row, count in zip(rows, counts):
        if count is None:
            failed += 1
            kept.append(row)
            print(f"keep {row['round']} request failed", flush=True)
            continue
        if count == 0:
            removed += 1
            print(f"remove {row['round']}", flush=True)
            continue
        kept.append(row)

    temporary = PATH.with_suffix(PATH.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(kept)
    temporary.replace(PATH)
    print(f"kept {len(kept)} removed {removed} failed {failed}")


if __name__ == "__main__":
    main()
