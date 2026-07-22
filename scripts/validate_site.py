#!/usr/bin/env python3
"""Validate the static files that GitHub Pages publishes from ``docs/``."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.resources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.resources.append(value)


def local_target(source: Path, reference: str) -> Path | None:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None

    if parsed.path.startswith("/"):
        target = DOCS / parsed.path.lstrip("/")
    else:
        target = source.parent / parsed.path

    if target.is_dir():
        target /= "index.html"
    return target.resolve()


def main() -> int:
    errors: list[str] = []

    for relative in ("index.html", "404.html", "CNAME", ".nojekyll", "archive.json", "favicon.svg"):
        if not (DOCS / relative).is_file():
            errors.append(f"missing published file: docs/{relative}")

    if (DOCS / "CNAME").is_file() and (DOCS / "CNAME").read_text(encoding="utf-8").strip() != "hiworld.uk":
        errors.append("docs/CNAME must contain exactly hiworld.uk")

    archive_file = DOCS / "archive.json"
    if archive_file.is_file():
        try:
            entries = json.loads(archive_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid docs/archive.json: {exc}")
        else:
            dates = [entry.get("date") for entry in entries] if isinstance(entries, list) else []
            if not isinstance(entries, list) or not all(isinstance(date, str) and DATE_RE.fullmatch(date) for date in dates):
                errors.append("docs/archive.json contains an invalid date entry")
            elif dates != sorted(set(dates)):
                errors.append("docs/archive.json dates must be sorted and unique")

    for html_file in DOCS.rglob("*.html"):
        parser = ResourceParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for reference in parser.resources:
            target = local_target(html_file, reference)
            if target is not None and not target.is_file():
                display = reference.split("#", 1)[0].split("?", 1)[0]
                errors.append(f"{html_file.relative_to(ROOT)} references missing local resource: {display}")

    if errors:
        for error in errors:
            print(f"❌ {error}", file=sys.stderr)
        return 1

    print("✅ Published site files, CNAME, archive index, and local resources are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
