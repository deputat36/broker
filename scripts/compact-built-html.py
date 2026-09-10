#!/usr/bin/env python3
"""Убирает незначимые пробелы из собранного Pages-артефакта.

Вне script/style/pre/code/textarea удаляются отступы перед HTML-тегами, хвостовые
пробелы и пустые строки. Текстовое содержимое, непустые переносы строк, атрибуты
и whitespace-sensitive блоки не изменяются. Это возвращает performance headroom,
не меняя смысл и структуру страниц.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


TAG_INDENT_RE = re.compile(r"^[\t ]+(?=<)")
TRAILING_WS_RE = re.compile(r"[\t ]+(?=\r?\n$)")
PROTECTED_OPEN_RE = re.compile(r"<\s*(script|style|pre|code|textarea)\b", re.I)
PROTECTED_CLOSE_RE = re.compile(r"<\s*/\s*(script|style|pre|code|textarea)\s*>", re.I)


def compact_html(path: Path) -> tuple[int, int]:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    protected: str | None = None
    result: list[str] = []

    for line in lines:
        if protected is None:
            open_match = PROTECTED_OPEN_RE.search(line)
            if open_match and not PROTECTED_CLOSE_RE.search(line):
                protected = open_match.group(1).lower()

            line = TAG_INDENT_RE.sub("", line)
            line = TRAILING_WS_RE.sub("", line)
            if not line.strip():
                continue
        else:
            close_match = PROTECTED_CLOSE_RE.search(line)
            if close_match and close_match.group(1).lower() == protected:
                protected = None

        result.append(line)

    compacted = "".join(result)
    if compacted != original:
        path.write_text(compacted, encoding="utf-8")
    return len(original.encode("utf-8")), len(compacted.encode("utf-8"))


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        print(f"::error::Каталог собранного сайта не найден: {site_dir}")
        return 1

    before = 0
    after = 0
    pages = 0
    for path in sorted(site_dir.rglob("*.html")):
        old_size, new_size = compact_html(path)
        before += old_size
        after += new_size
        pages += 1

    saved = before - after
    if saved <= 0:
        print("::warning::Компактизация HTML не освободила ни одного байта")
    print(f"HTML compact: страниц {pages}, было {before}, стало {after}, сохранено {saved} байт")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
