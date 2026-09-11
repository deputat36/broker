#!/usr/bin/env python3
"""Проверяет атрибуцию переходов в онлайн-заявку."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from html.parser import HTMLParser


APPLICATION_LINK = re.compile(r"/online-zayavka/\?[^\"'<> ]*")
REQUIRED = ("source=", "scenario=", "placement=")
PLACEMENT = re.compile(r"placement=([A-Za-z0-9_-]+)")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    failures = 0

    for page in root.rglob("*.html"):
        try:
            html = page.read_text(encoding="utf-8")
        except OSError:
            continue

        parser = LinkParser()
        parser.feed(html)
        placements = set()

        for link in parser.links:
            if "/online-zayavka/" not in link:
                continue
            for item in REQUIRED:
                if item not in link:
                    print(f"::error file={page}::CTA без обязательного параметра {item}: {link}")
                    failures += 1
            match = PLACEMENT.search(link)
            if match:
                value = match.group(1)
                if value in placements:
                    print(f"::error file={page}::Дублируется placement: {value}")
                    failures += 1
                placements.add(value)
            else:
                print(f"::error file={page}::CTA без placement: {link}")
                failures += 1

    if failures:
        return 1

    print("CTA attribution contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
