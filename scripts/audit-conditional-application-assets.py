#!/usr/bin/env python3
"""Проверяет, что ресурсы анкеты загружаются только на её странице."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


CSS_PATH = "/assets/css/online-application.css"
JS_PATH = "/assets/js/online-application.js"
CONSENT_JS_PATH = "/assets/js/application-consent-validation.js"
FORM_MARKER = "data-online-application"


class ResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.has_form = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "link" and "stylesheet" in values.get("rel", "").split():
            self.stylesheets.append(values.get("href", ""))
        elif tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if FORM_MARKER in values:
            self.has_form = True


def path_only(value: str) -> str:
    return urlsplit(value).path


def fail(message: str, path: Path | None = None) -> None:
    prefix = "::error"
    if path is not None:
        prefix += f" file={path.as_posix()}"
    print(f"{prefix}::{message}")


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        fail("Каталог собранного сайта не найден", site_dir)
        return 1

    required_assets = (
        site_dir / CSS_PATH.lstrip("/"),
        site_dir / JS_PATH.lstrip("/"),
        site_dir / CONSENT_JS_PATH.lstrip("/"),
    )
    errors = 0
    for asset in required_assets:
        if not asset.is_file() or asset.stat().st_size == 0:
            fail("Ресурс онлайн-заявки отсутствует или пуст", asset)
            errors += 1

    pages = sorted(site_dir.rglob("*.html"))
    application_page = site_dir / "online-zayavka" / "index.html"
    if application_page not in pages:
        fail("Не найдена собранная страница онлайн-заявки", application_page)
        return 1

    pages_without_assets = 0
    for page in pages:
        parser = ResourceParser()
        parser.feed(page.read_text(encoding="utf-8"))

        css_count = sum(path_only(value) == CSS_PATH for value in parser.stylesheets)
        js_count = sum(path_only(value) == JS_PATH for value in parser.scripts)
        consent_js_count = sum(path_only(value) == CONSENT_JS_PATH for value in parser.scripts)
        is_application_page = page == application_page

        if is_application_page:
            if css_count != 1:
                fail(f"CSS анкеты подключён {css_count} раз вместо одного", page)
                errors += 1
            if js_count != 1:
                fail(f"JavaScript анкеты подключён {js_count} раз вместо одного", page)
                errors += 1
            if consent_js_count != 1:
                fail(f"Валидация согласия подключена {consent_js_count} раз вместо одного", page)
                errors += 1
            if not parser.has_form:
                fail("Страница онлайн-заявки не содержит форму", page)
                errors += 1
        else:
            if css_count:
                fail("CSS анкеты загружается вне страницы онлайн-заявки", page)
                errors += 1
            if js_count:
                fail("JavaScript анкеты загружается вне страницы онлайн-заявки", page)
                errors += 1
            if consent_js_count:
                fail("Валидация согласия загружается вне страницы онлайн-заявки", page)
                errors += 1
            if parser.has_form:
                fail("Форма онлайн-заявки обнаружена на неожиданной странице", page)
                errors += 1
            if not css_count and not js_count and not consent_js_count:
                pages_without_assets += 1

    if errors:
        print(f"Аудит условных ресурсов анкеты завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит условных ресурсов анкеты успешно завершён: "
        f"HTML-страниц {len(pages)}, без ресурсов анкеты {pages_without_assets}, "
        "страниц с ресурсами анкеты 1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())