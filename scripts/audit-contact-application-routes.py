#!/usr/bin/env python3
"""Проверяет контекстные маршруты со страницы контактов в онлайн-заявку."""

from __future__ import annotations

import html
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "kontakty.md"
PAGE_URL = "/kontakty/"
APPLICATION_URL = "/online-zayavka/"
SCENARIO = "Первичная консультация и подбор ипотеки"
EXPECTED_ROUTE_COUNT = 6


class ContactParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.copy_phone_buttons = 0
        self._anchor: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "a":
            self._anchor = {
                "href": html.unescape(values.get("href", "")),
                "class": values.get("class", ""),
                "parts": [],
            }
        elif tag.lower() == "button" and "data-copy-phone" in values:
            self.copy_phone_buttons += 1

    def handle_data(self, data: str) -> None:
        if self._anchor is None:
            return
        parts = self._anchor["parts"]
        assert isinstance(parts, list)
        parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._anchor is None:
            return
        parts = self._anchor["parts"]
        assert isinstance(parts, list)
        self.anchors.append(
            {
                "href": str(self._anchor["href"]),
                "class": str(self._anchor["class"]),
                "text": " ".join(" ".join(parts).split()),
            }
        )
        self._anchor = None


def fail(path: Path, message: str) -> None:
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = path.as_posix()
    print(f"::error file={display}::{message}")


def parse_page(path: Path) -> ContactParser:
    parser = ContactParser()
    parser.feed(path.read_text(encoding="utf-8-sig", errors="ignore"))
    return parser


def validate_source(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    expected_route = (
        "{{ '/online-zayavka/' | relative_url }}?source={{ page.url | url_encode }}"
        "&amp;scenario={{ 'Первичная консультация и подбор ипотеки' | url_encode }}"
    )
    errors = 0

    route_count = text.count(expected_route)
    if route_count != EXPECTED_ROUTE_COUNT:
        fail(
            path,
            f"В исходнике должно быть {EXPECTED_ROUTE_COUNT} контекстных маршрутов, найдено: {route_count}",
        )
        errors += 1

    if text.count("href=\"{{ '/online-zayavka/' | relative_url }}\""):
        fail(path, "На странице остались прямые ссылки на анкету без источника и сценария")
        errors += 1

    required_markers = (
        '"@type":"ContactPage"',
        "Заполнить онлайн-заявку",
        "Перейти к анкете",
        "Заполнить форму вместо сообщения",
        "Другой город",
        "tel:+79030250807",
        "data-copy-phone",
        "https://vk.com/tatyanasterlikova",
        "{{ '/etagi/' | relative_url }}",
        "{{ '/geo/borisoglebsk/' | relative_url }}",
        "{{ '/geo/gribanovskiy/' | relative_url }}",
        "{{ '/geo/povorino/' | relative_url }}",
    )
    for marker in required_markers:
        if marker not in text:
            fail(path, f"В исходнике отсутствует обязательный элемент: {marker}")
            errors += 1

    return errors


def validate_built(path: Path) -> int:
    parser = parse_page(path)
    routes: list[dict[str, str]] = []
    phone_links = 0
    vk_links = 0
    etagi_links = 0
    regional_paths: set[str] = set()
    errors = 0

    for anchor in parser.anchors:
        parsed = urlsplit(anchor["href"])
        query = parse_qs(parsed.query, keep_blank_values=True)
        if parsed.path == APPLICATION_URL and "source" in query and "scenario" in query:
            routes.append(anchor)
        elif parsed.scheme == "tel" and parsed.path == "+79030250807":
            phone_links += 1
        elif anchor["href"] == "https://vk.com/tatyanasterlikova":
            vk_links += 1
        elif parsed.path == "/etagi/":
            etagi_links += 1
        elif parsed.path in {"/geo/borisoglebsk/", "/geo/gribanovskiy/", "/geo/povorino/"}:
            regional_paths.add(parsed.path)

    if len(routes) != EXPECTED_ROUTE_COUNT:
        fail(path, f"Ожидалось {EXPECTED_ROUTE_COUNT} контекстных CTA, найдено: {len(routes)}")
        errors += 1

    for anchor in routes:
        parsed = urlsplit(anchor["href"])
        query = parse_qs(parsed.query, keep_blank_values=True)
        source = query.get("source", [""])[0]
        scenario = query.get("scenario", [""])[0]
        if source != PAGE_URL:
            fail(path, f"CTA «{anchor['text']}» передаёт неверный источник: {source or 'пусто'}")
            errors += 1
        if scenario != SCENARIO:
            fail(path, f"CTA «{anchor['text']}» передаёт неверный сценарий: {scenario or 'пусто'}")
            errors += 1

    route_text = "\n".join(anchor["text"] for anchor in routes)
    for marker in (
        "Заполнить онлайн-заявку",
        "Перейти к анкете",
        "Заполнить анкету",
        "Заполнить форму вместо сообщения",
        "Другой город",
        "Онлайн-заявка",
    ):
        if marker not in route_text:
            fail(path, f"Среди контекстных CTA отсутствует обязательная подпись: {marker}")
            errors += 1

    if phone_links < 2:
        fail(path, f"Должны сохраниться минимум две телефонные ссылки, найдено: {phone_links}")
        errors += 1
    if parser.copy_phone_buttons < 3:
        fail(path, f"Должны сохраниться минимум три кнопки MAX, найдено: {parser.copy_phone_buttons}")
        errors += 1
    if vk_links < 3:
        fail(path, f"Должны сохраниться минимум три ссылки ВКонтакте, найдено: {vk_links}")
        errors += 1
    if etagi_links < 1:
        fail(path, "Отсутствует ссылка на условия для клиентов «ЭТАЖИ»")
        errors += 1
    if len(regional_paths) != 3:
        fail(path, f"Должны сохраниться три региональные ссылки, найдено: {len(regional_paths)}")
        errors += 1

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_file = site_dir / "kontakty" / "index.html"
    errors = 0

    if not SOURCE_FILE.is_file():
        fail(SOURCE_FILE, "Исходная страница контактов отсутствует")
        errors += 1
    else:
        errors += validate_source(SOURCE_FILE)

    if not built_file.is_file():
        fail(built_file, "Собранная страница контактов отсутствует")
        errors += 1
    else:
        errors += validate_built(built_file)

    if errors:
        print(f"Аудит маршрутов страницы контактов завершён с ошибками: {errors}")
        return 1

    print(
        "Маршруты страницы контактов подтверждены: шесть контекстных CTA, "
        "источник /kontakty/, единый сценарий и сохранённые каналы связи"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
