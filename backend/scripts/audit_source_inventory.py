"""Read-only comparison of an exported source list and the active database."""
from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalized_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def normalized_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    port = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    path = (parsed.path or "/").rstrip("/") or "/"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit(("https", host + port, path, query, ""))


def load_database(path: Path) -> list[dict]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = [dict(row) for row in connection.execute(
        "SELECT id, name, base_url, api_endpoint, homepage_url, channel "
        "FROM source_configs"
    )]
    connection.close()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("db_path", type=Path)
    args = parser.parse_args()
    with args.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        incoming = list(csv.DictReader(handle))
    columns = list(incoming[0])
    (
        id_column, name_column, _channel_column, collect_url_column,
        homepage_column, *_rest,
    ) = columns
    current = load_database(args.db_path)

    current_ids = {normalized_text(row["id"]) for row in current}
    current_names: dict[str, list[dict]] = defaultdict(list)
    current_urls: dict[str, list[dict]] = defaultdict(list)
    for row in current:
        current_names[normalized_text(row["name"])].append(row)
        for field in ("base_url", "api_endpoint", "homepage_url"):
            if url := normalized_url(row[field]):
                current_urls[url].append(row)

    counts: Counter[str] = Counter()
    examples: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for row in incoming:
        source_id = normalized_text(row[id_column])
        name = normalized_text(row[name_column])
        urls = {
            normalized_url(row[collect_url_column]), normalized_url(row[homepage_column]),
        } - {""}
        if source_id in current_ids:
            match = "same_id"
        elif any(url in current_urls for url in urls):
            match = "same_url"
        elif name and name in current_names:
            match = "same_name"
        else:
            match = "new"
        counts[match] += 1
        if len(examples[match]) < 12:
            examples[match].append((row[id_column], row[name_column], row[collect_url_column]))

    duplicate_fields = {
        "ids": Counter(normalized_text(row[id_column]) for row in incoming),
        "names": Counter(normalized_text(row[name_column]) for row in incoming),
        "urls": Counter(
            normalized_url(row[collect_url_column]) for row in incoming
            if normalized_url(row[collect_url_column])
        ),
    }
    print(f"incoming={len(incoming)} current={len(current)}")
    print("matches=" + ", ".join(f"{key}:{value}" for key, value in counts.items()))
    for field, values in duplicate_fields.items():
        duplicates = [count for count in values.values() if count > 1]
        print(f"duplicate_{field}=groups:{len(duplicates)} rows:{sum(duplicates)}")
    for match, rows in examples.items():
        print(f"\n[{match}]")
        for row in rows:
            print(" | ".join(row))


if __name__ == "__main__":
    main()
