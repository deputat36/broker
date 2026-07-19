#!/usr/bin/env python3
"""Проверяет подключение и основные контракты дизайн-системы 2026."""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSS = ROOT / "assets" / "css" / "nav-state.css"
THEME_PLACEHOLDER = ROOT / "assets" / "css" / "style.css"
MANIFEST_SOURCE = ROOT / "site.webmanifest"
DESIGN_DOC = ROOT / "docs" / "design-system-2026.md"
EXPECTED_STYLESHEET = "/assets/css/nav-state.css"

PALETTE_MARKERS = {
    "--red: #2f6b62;": "спокойный зелёный alias",
    "--black: #17283d;": "глубокий синий",
    "--gold: #c89445;": "тёплое золото",
    "--warm: #fbf7ef;": "тёплый фон",
    "--radius: 18px;": "базовый радиус",
}

COMPONENT_MARKERS = {
    ".site-header": "header",
    ".hero-card-photo": "фотокарточка hero",
    ".btn-primary": "основная кнопка",
    ".intent-card.featured": "featured-сценарий",
    ".calc-field input:focus": "focus формы",
    ".sticky-apply": "мобильная заявка",
    ".site-footer": "footer",
}

FORBIDDEN_BRAND_COLORS = ("#b5121b", "#7c0a10")


class StylesheetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stylesheets: list[str] = []
        self.classes: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "link":
            rel = {item.lower() for item in values.get("rel", "").split()}
            if "stylesheet" in rel and values.get("href"):
                self.stylesheets.append(values["href"])
        for class_name in values.get("class", "").split():
            if class_name:
                self.classes.add(class_name)


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def fail(path: Path, message: str) -> None:
    print(f"::error file={display(path)}::{message}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def validate_source() -> int:
    errors = 0
    for path, label in (
        (SOURCE_CSS, "CSS дизайн-системы"),
        (THEME_PLACEHOLDER, "placeholder CSS темы"),
        (MANIFEST_SOURCE, "webmanifest"),
        (DESIGN_DOC, "документация дизайн-системы"),
    ):
        if not path.is_file():
            fail(path, f"Отсутствует {label}")
            errors += 1

    if not SOURCE_CSS.is_file():
        return errors

    css = read_text(SOURCE_CSS).lower()
    for marker, label in PALETTE_MARKERS.items():
        if marker not in css:
            fail(SOURCE_CSS, f"Не зафиксирован токен: {label}")
            errors += 1
    for marker, label in COMPONENT_MARKERS.items():
        if marker.lower() not in css:
            fail(SOURCE_CSS, f"Не оформлен компонент: {label}")
            errors += 1
    for color in FORBIDDEN_BRAND_COLORS:
        if color in css:
            fail(SOURCE_CSS, f"В новой дизайн-системе остался старый фирменный цвет {color}")
            errors += 1

    if SOURCE_CSS.stat().st_size > 20_000:
        fail(SOURCE_CSS, f"Глобальный дизайн-слой слишком тяжёлый: {SOURCE_CSS.stat().st_size} байт")
        errors += 1

    if THEME_PLACEHOLDER.is_file() and THEME_PLACEHOLDER.stat().st_size > 512:
        fail(THEME_PLACEHOLDER, "Неиспользуемый CSS темы должен оставаться минимальным")
        errors += 1

    if MANIFEST_SOURCE.is_file():
        try:
            manifest = json.loads(read_text(MANIFEST_SOURCE))
        except json.JSONDecodeError as error:
            fail(MANIFEST_SOURCE, f"Некорректный JSON: {error}")
            errors += 1
        else:
            if manifest.get("theme_color", "").lower() != "#17283d":
                fail(MANIFEST_SOURCE, "theme_color не соответствует глубокому синему")
                errors += 1
            if manifest.get("background_color", "").lower() != "#fbf7ef":
                fail(MANIFEST_SOURCE, "background_color не соответствует тёплому фону")
                errors += 1

    if DESIGN_DOC.is_file():
        doc = read_text(DESIGN_DOC)
        for marker in (
            "https://www.figma.com/design/Sz62KR5VogV6KAGJfeHCZi",
            "#17283D",
            "#2F6B62",
            "#C89445",
            "assets/css/nav-state.css",
        ):
            if marker not in doc:
                fail(DESIGN_DOC, f"В документации отсутствует обязательный маркер: {marker}")
                errors += 1

    return errors


def validate_built(site_dir: Path) -> int:
    errors = 0
    css_path = site_dir / "assets" / "css" / "nav-state.css"
    placeholder_path = site_dir / "assets" / "css" / "style.css"
    manifest_path = site_dir / "site.webmanifest"

    for path in (css_path, placeholder_path, manifest_path):
        if not path.is_file():
            fail(path, "Обязательный файл дизайна отсутствует в сборке")
            errors += 1

    if css_path.is_file():
        built_css = read_text(css_path).lower()
        for marker in (*PALETTE_MARKERS.keys(), *COMPONENT_MARKERS.keys()):
            if marker.lower() not in built_css:
                fail(css_path, f"В собранном CSS отсутствует контракт: {marker}")
                errors += 1

    if placeholder_path.is_file() and placeholder_path.stat().st_size > 512:
        fail(placeholder_path, f"Jekyll опубликовал тяжёлый CSS темы: {placeholder_path.stat().st_size} байт")
        errors += 1

    html_files = sorted(site_dir.rglob("*.html"))
    if len(html_files) < 100:
        fail(site_dir, f"Для проверки дизайна найдено слишком мало HTML-страниц: {len(html_files)}")
        errors += 1

    missing_stylesheet: list[str] = []
    duplicate_stylesheet: list[str] = []
    for path in html_files:
        parser = StylesheetParser()
        parser.feed(read_text(path))
        normalized = [urlsplit(url).path for url in parser.stylesheets]
        count = normalized.count(EXPECTED_STYLESHEET)
        if count == 0:
            missing_stylesheet.append(display(path))
        elif count > 1:
            duplicate_stylesheet.append(display(path))

    if missing_stylesheet:
        fail(site_dir, "Дизайн-слой не подключён: " + ", ".join(missing_stylesheet[:8]))
        errors += 1
    if duplicate_stylesheet:
        fail(site_dir, "Дизайн-слой подключён повторно: " + ", ".join(duplicate_stylesheet[:8]))
        errors += 1

    homepage = site_dir / "index.html"
    if homepage.is_file():
        parser = StylesheetParser()
        parser.feed(read_text(homepage))
        for class_name in ("hero", "hero-card-photo", "btn-primary", "sticky-contacts", "site-footer"):
            if class_name not in parser.classes:
                fail(homepage, f"Главная потеряла ключевой компонент дизайна: {class_name}")
                errors += 1

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    errors = validate_source()
    if not site_dir.is_dir():
        fail(site_dir, "Каталог собранного сайта отсутствует")
        errors += 1
    else:
        errors += validate_built(site_dir)

    if errors:
        print(f"Аудит дизайн-системы завершён с ошибками: {errors}")
        return 1

    html_count = len(list(site_dir.rglob("*.html")))
    print(
        "Дизайн-система подтверждена: navy/sage/gold, глобальные компоненты, "
        f"PWA-цвета и подключение на {html_count} HTML-страницах"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
