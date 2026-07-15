#!/usr/bin/env python3
"""Проверяет контактный блок Татьяны в общем подвале сайта."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts" / "default.html"
CSS_SOURCE = ROOT / "assets" / "css" / "footer-trust.css"
LAYOUT_MARKERS = (
    "footer-trust.css",
    'class="footer-person"',
    'class="footer-avatar"',
    "tatyana-avatar.webp",
    'width="76" height="76"',
    'loading="lazy"',
    "Подробнее о подходе к работе",
)
CSS_MARKERS = (
    ".footer-person",
    ".footer-avatar",
    ".footer-person-name",
    ".footer-person-role",
    ".footer-about-link",
    "object-fit: cover",
    "border-radius: 50%",
    "@media (max-width: 760px)",
)
HTML_MARKERS = (
    'class="footer-person"',
    'class="footer-avatar"',
    'src="/assets/img/tatyana-avatar.webp"',
    'href="/o-brokere/"',
    'width="76" height="76"',
    'loading="lazy"',
    'decoding="async"',
    'href="/assets/css/footer-trust.css"',
)


def error(message: str, path: Path | None = None) -> None:
    prefix = "::error"
    if path is not None:
        try:
            display = path.relative_to(ROOT).as_posix()
        except ValueError:
            display = path.as_posix()
        prefix += f" file={display}"
    print(f"{prefix}::{message}")


def require_markers(path: Path, markers: tuple[str, ...], label: str) -> int:
    if not path.is_file():
        error(f"Не найден {label}", path)
        return 1
    text = path.read_text(encoding="utf-8")
    failures = 0
    for marker in markers:
        if marker not in text:
            error(f"В {label} отсутствует маркер: {marker}", path)
            failures += 1
    return failures


def check_built_pages(site_dir: Path) -> tuple[int, int]:
    failures = 0
    pages = sorted(site_dir.rglob("*.html"))
    if not pages:
        error("В сборке не найдено HTML-страниц", site_dir)
        return 1, 0

    for page in pages:
        text = page.read_text(encoding="utf-8")
        for marker in HTML_MARKERS:
            if marker not in text:
                error(f"В подвале отсутствует маркер: {marker}", page)
                failures += 1
        avatar_count = text.count("tatyana-avatar.webp")
        if avatar_count != 1:
            error(
                f"Ожидалось одно footer-avatar изображение, найдено: {avatar_count}",
                page,
            )
            failures += 1
    return failures, len(pages)


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        error("Каталог собранного сайта не найден", site_dir)
        return 1

    failures = 0
    failures += require_markers(LAYOUT, LAYOUT_MARKERS, "layout подвала")
    failures += require_markers(CSS_SOURCE, CSS_MARKERS, "CSS контактного блока")
    failures += require_markers(
        site_dir / "assets" / "css" / "footer-trust.css",
        CSS_MARKERS,
        "собранный CSS контактного блока",
    )
    page_failures, page_count = check_built_pages(site_dir)
    failures += page_failures

    if failures:
        print(f"Аудит контактного блока завершён с ошибками: {failures}")
        return 1

    print(
        "Аудит контактного блока успешно завершён: "
        f"HTML-страниц {page_count}, avatar на каждой странице"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
