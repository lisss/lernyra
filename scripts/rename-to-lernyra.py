#!/usr/bin/env python3
"""Rename Beacon → Lernyra (host: getlernyra.duckdns.org)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "static", "__pycache__", "web-next-backup"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".pdf", ".db"}

REPLACEMENTS = [
    ("getbeacon.duckdns.org", "getlernyra.duckdns.org"),
    ("https://github.com/lisss/beacon", "https://github.com/lisss/lernyra"),
    ("ghcr.io/lisss/beacon", "ghcr.io/lisss/lernyra"),
    ("lisss/beacon", "lisss/lernyra"),
    ("/opt/beacon", "/opt/lernyra"),
    ("DUCKDNS_SUBDOMAIN=getbeacon", "DUCKDNS_SUBDOMAIN=getlernyra"),
    ("DUCKDNS_SUBDOMAIN=beacon", "DUCKDNS_SUBDOMAIN=getlernyra"),
    ("BeaconMark", "LernyraMark"),
    ("beacon-todo-changed", "lernyra-todo-changed"),
    ("beacon_sid", "lernyra_sid"),
    ("beacon.sections", "lernyra.sections"),
    ("beacon.todo", "lernyra.todo"),
    ("beacon.ui", "lernyra.ui"),
    ("beacon.cv", "lernyra.cv"),
    ("beacon-cv", "lernyra-cv"),
    ("container_name: beacon-", "container_name: lernyra-"),
    ("sqlite:////data/beacon.db", "sqlite:////data/lernyra.db"),
    ("sqlite:////tmp/beacon.db", "sqlite:////tmp/lernyra.db"),
    ("sqlite:///./beacon.db", "sqlite:///./lernyra.db"),
    ("**/beacon.db", "**/lernyra.db"),
    ('title="Beacon API"', 'title="Lernyra API"'),
    ("# Beacon", "# Lernyra"),
    ("Deploy Beacon", "Deploy Lernyra"),
    ("beacon-api", "lernyra-api"),
    ("beacon/0.1", "lernyra/0.1"),
    ("beacon/1.0", "lernyra/1.0"),
    ("POSTGRES_USER: beacon", "POSTGRES_USER: lernyra"),
    ("POSTGRES_PASSWORD: beacon", "POSTGRES_PASSWORD: lernyra"),
    ("POSTGRES_DB: beacon", "POSTGRES_DB: lernyra"),
    ("-U beacon -d beacon", "-U lernyra -d lernyra"),
    ("postgresql+psycopg://beacon:beacon@", "postgresql+psycopg://lernyra:lernyra@"),
    ("beacon_pgdata", "lernyra_pgdata"),
]


def main() -> None:
    changed: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.name.startswith("rename-to-"):
            continue
        if path.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        orig = text
        for old, new in REPLACEMENTS:
            text = text.replace(old, new)
        text = re.sub(r"\bBeacon\b", "Lernyra", text)
        text = re.sub(r"\bbeacon\b", "lernyra", text)
        if text != orig:
            path.write_text(text, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))
    print(f"updated {len(changed)} files")
    for p in changed:
        print(p)


if __name__ == "__main__":
    main()
