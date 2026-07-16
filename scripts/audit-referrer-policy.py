#!/usr/bin/env python3
"""Проверяет явную браузерную политику передачи referrer на всех страницах."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path

EXPECTED_POLICY = "strict-origin-when-cross-origin"
REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_PATH = REPO_ROOT / "_layouts/default.html"
META_MARKER = f'<meta name="referrer" content="{EXPECTED_POLICY}">'


class ReferrerMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.values: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "head":
            self.in_head = True
            return
        if tag != "meta":
            return
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if attrs_map.get("name", "").lower() == "referrer":
            self.values.append((attrs_map.get("content", ""), self.in_head))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "head":
            self.in_head = False


def fail(path: Path, message: str) -> None:
    print(f"::error file={path.as_posix()}::{message}")


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    errors = 0

    if not LAYOUT_PATH.is_file():
        fail(LAYOUT_PATH, "Канонический layout не найден")
        return 1

    layout = LAYOUT_PATH.read_text(encoding="utf-8")
    marker_count = layout.count(META_MARKER)
    if marker_count != 1:
        fail(LAYOUT_PATH, f"Referrer meta встречается {marker_count} раз, ожидался один")
        errors += 1

    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        fail(site_dir, "Собранные HTML-страницы не найдены")
        return 1

    for html_file in html_files:
        parser = ReferrerMetaParser()
        parser.feed(html_file.read_text(encoding="utf-8-sig", errors="ignore"))

        if len(parser.values) != 1:
            fail(html_file, f"Найдено meta referrer: {len(parser.values)}, ожидалось одно")
            errors += 1
            continue

        value, inside_head = parser.values[0]
        if value != EXPECTED_POLICY:
            fail(html_file, f"Недопустимая referrer policy: {value or '<пусто>'}")
            errors += 1
        if not inside_head:
            fail(html_file, "Meta referrer находится вне <head>")
            errors += 1

    if errors:
        print(f"Аудит referrer policy завершён с ошибками: {errors}")
        return 1

    print(
        "Явная referrer policy подтверждена: "
        f"{len(html_files)} HTML-страниц, значение {EXPECTED_POLICY}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
