#!/usr/bin/env python3
"""Проверяет второй слой премиального оформления главной страницы."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSS = ROOT / "assets" / "css" / "nav-state.css"
SOURCE_HOME = ROOT / "index.md"

CSS_MARKERS = (
    "--shadow-premium:",
    "--gold-light:",
    ".hero .hero-actions",
    ".hero-card-photo",
    ".main-nav a.is-current",
    ".rate-board",
    ".notice::after",
    "@media (max-width: 760px)",
    "grid-template-columns: 1fr;",
)

HOME_MARKERS = (
    'class="hero section"',
    'class="hero-actions"',
    'class="trust-list"',
    'class="hero-stats"',
    'class="hero-card hero-card-photo"',
    'class="portrait-frame"',
    'class="rate-board"',
)

FORBIDDEN_COLORS = ("#b5121b", "#7c0a10")
MAX_CSS_BYTES = 12_000


def fail(path: Path, message: str) -> None:
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = path.as_posix()
    print(f"::error file={display}::{message}")


def validate_css(path: Path) -> int:
    if not path.is_file():
        fail(path, "Файл дизайн-слоя отсутствует")
        return 1

    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    folded = text.lower()
    errors = 0

    for marker in CSS_MARKERS:
        if marker.lower() not in folded:
            fail(path, f"Отсутствует обязательный маркер оформления: {marker}")
            errors += 1

    for color in FORBIDDEN_COLORS:
        if color in folded:
            fail(path, f"В премиальном дизайн-слое найден старый красный цвет: {color}")
            errors += 1

    if path.stat().st_size > MAX_CSS_BYTES:
        fail(path, f"Дизайн-слой слишком тяжёлый: {path.stat().st_size} байт")
        errors += 1

    return errors


def validate_home(path: Path) -> int:
    if not path.is_file():
        fail(path, "Исходник главной страницы отсутствует")
        return 1

    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    errors = 0
    for marker in HOME_MARKERS:
        if marker not in text:
            fail(path, f"Главная потеряла элемент первого экрана: {marker}")
            errors += 1
    return errors


def validate_built(site_dir: Path) -> int:
    css = site_dir / "assets" / "css" / "nav-state.css"
    home = site_dir / "index.html"
    errors = validate_css(css)

    if not home.is_file():
        fail(home, "Собранная главная страница отсутствует")
        return errors + 1

    text = home.read_text(encoding="utf-8-sig", errors="ignore")
    for marker in (
        'class="hero section"',
        'class="hero-card hero-card-photo"',
        'class="hero-stats"',
        'class="rate-board"',
        'Татьяна Стерликова',
    ):
        if marker not in text:
            fail(home, f"В собранной главной отсутствует элемент: {marker}")
            errors += 1

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    errors = validate_css(SOURCE_CSS)
    errors += validate_home(SOURCE_HOME)

    if not site_dir.is_dir():
        fail(site_dir, "Каталог собранного сайта отсутствует")
        errors += 1
    else:
        errors += validate_built(site_dir)

    if errors:
        print(f"Аудит премиального оформления главной завершён с ошибками: {errors}")
        return 1

    print(
        "Премиальное оформление главной подтверждено: navy/sage/gold, "
        "двухуровневые CTA, доверительные блоки и мобильная адаптация"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
