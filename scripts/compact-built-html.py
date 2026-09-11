#!/usr/bin/env python3
"""Компактизирует собранный Pages-артефакт без изменения текстового смысла.

Вне script/style/pre/code/textarea удаляются отступы перед HTML-тегами, хвостовые
пробелы и пустые строки. Дополнительно убирается межтеговый перенос строки, если
хотя бы одна сторона границы — блочный HTML-элемент. Между inline-элементами
whitespace сохраняется, поэтому текст вроде ``</span> <span>`` не склеивается.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


TAG_INDENT_RE = re.compile(r"^[\t ]+(?=<)")
TRAILING_WS_RE = re.compile(r"[\t ]+(?=\r?\n$)")
PROTECTED_OPEN_RE = re.compile(r"<\s*(script|style|pre|code|textarea)\b", re.I)
PROTECTED_CLOSE_RE = re.compile(r"<\s*/\s*(script|style|pre|code|textarea)\s*>", re.I)
FINAL_TAG_RE = re.compile(r"</?([a-z][a-z0-9-]*)\b[^>]*>\s*$", re.I)
FIRST_TAG_RE = re.compile(r"^\s*</?([a-z][a-z0-9-]*)\b", re.I)

# Только элементы, для которых межтеговый whitespace не участвует в текстовом
# содержимом. Inline-теги намеренно не включены.
BLOCK_TAGS = {
    "html",
    "head",
    "body",
    "header",
    "main",
    "footer",
    "nav",
    "section",
    "article",
    "aside",
    "div",
    "form",
    "fieldset",
    "details",
    "summary",
    "ul",
    "ol",
    "li",
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "figure",
    "figcaption",
    "blockquote",
    "noscript",
}


def block_boundary(previous: str, current: str) -> bool:
    """Можно ли безопасно убрать перенос между двумя строками с тегами."""
    if not previous.endswith(("\n", "\r")) or not current.lstrip().startswith("<"):
        return False

    previous_tag = FINAL_TAG_RE.search(previous.rstrip("\r\n"))
    current_tag = FIRST_TAG_RE.match(current)
    if not previous_tag or not current_tag:
        return False

    return (
        previous_tag.group(1).lower() in BLOCK_TAGS
        or current_tag.group(1).lower() in BLOCK_TAGS
    )


def compact_text(original: str) -> str:
    lines = original.splitlines(keepends=True)
    protected: str | None = None
    result: list[str] = []

    for line in lines:
        line_is_protected = protected is not None
        if protected is None:
            open_match = PROTECTED_OPEN_RE.search(line)
            if open_match and not PROTECTED_CLOSE_RE.search(line):
                protected = open_match.group(1).lower()
                line_is_protected = True

            line = TAG_INDENT_RE.sub("", line)
            line = TRAILING_WS_RE.sub("", line)
            if not line.strip():
                continue
        else:
            close_match = PROTECTED_CLOSE_RE.search(line)
            if close_match and close_match.group(1).lower() == protected:
                protected = None

        if result and not line_is_protected and block_boundary(result[-1], line):
            result[-1] = result[-1].rstrip("\r\n")

        result.append(line)

    return "".join(result)


def self_test() -> None:
    sample = (
        "<div>\n"
        "  <span>Первый</span>\n"
        "  <span>Второй</span>\n"
        "</div>\n"
        "<script>\n"
        "  const marker = '</div> <div>';\n"
        "</script>\n"
    )
    compacted = compact_text(sample)

    # Блочные границы схлопываются.
    if "<div><span>Первый</span>" not in compacted or "<span>Второй</span></div>" not in compacted:
        raise AssertionError("block boundary compaction failed")
    # Между inline-элементами перенос остаётся и не склеивает текст.
    if "</span>\n<span>Второй</span>" not in compacted:
        raise AssertionError("inline whitespace was removed")
    # Whitespace-sensitive содержимое script не меняется.
    if "  const marker = '</div> <div>';\n" not in compacted:
        raise AssertionError("protected script content changed")


def compact_html(path: Path) -> tuple[int, int]:
    original = path.read_text(encoding="utf-8")
    compacted = compact_text(original)
    if compacted != original:
        path.write_text(compacted, encoding="utf-8")
    return len(original.encode("utf-8")), len(compacted.encode("utf-8"))


def main() -> int:
    try:
        self_test()
    except AssertionError as exc:
        print(f"::error file={Path(__file__).name}::Self-test HTML compact failed: {exc}")
        return 1

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
