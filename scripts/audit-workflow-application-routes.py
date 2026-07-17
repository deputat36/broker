#!/usr/bin/env python3
"""Проверяет прямые маршруты со страницы «Как проходит работа» в онлайн-заявку."""

from __future__ import annotations

import html
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "kak-prohodit-rabota.md"
PAGE_URL = "/kak-prohodit-rabota/"
APPLICATION_URL = "/online-zayavka/"
CONSULTATION_URL = "/konsultaciya/"
SCENARIO = "Первичная консультация и подбор ипотеки"
ROUTE_LABELS = {"Заполнить онлайн-заявку", "Онлайн-заявка"}


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self._anchor: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        self._anchor = {"href": html.unescape(values.get("href", "")), "parts": []}

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


def parse_anchors(path: Path) -> list[dict[str, str]]:
    parser = AnchorParser()
    parser.feed(path.read_text(encoding="utf-8-sig", errors="ignore"))
    return parser.anchors


def validate_source(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    expected_route = (
        "{{ '/online-zayavka/' | relative_url }}?source={{ page.url | url_encode }}"
        "&amp;scenario={{ 'Первичная консультация и подбор ипотеки' | url_encode }}"
    )
    errors = 0

    route_count = text.count(expected_route)
    if route_count != 2:
        fail(path, f"В исходнике должно быть два прямых маршрута, найдено: {route_count}")
        errors += 1

    if text.count("href=\"{{ '/online-zayavka/' | relative_url }}\""):
        fail(path, "На странице осталась прямая ссылка на анкету без источника и сценария")
        errors += 1

    for marker in (
        "Заполнить онлайн-заявку",
        "Онлайн-заявка",
        "Как проходит консультация",
        "Консультация",
        "tel:+79030250807",
    ):
        if marker not in text:
            fail(path, f"В исходнике отсутствует обязательный маршрут или контакт: {marker}")
            errors += 1

    return errors


def validate_built(path: Path) -> int:
    anchors = parse_anchors(path)
    routes: list[dict[str, str]] = []
    consultation_links = 0
    phone_links = 0
    errors = 0

    for anchor in anchors:
        parsed = urlsplit(anchor["href"])
        query = parse_qs(parsed.query, keep_blank_values=True)
        if parsed.path == APPLICATION_URL and "source" in query and "scenario" in query:
            routes.append(anchor)
        elif parsed.path == CONSULTATION_URL:
            consultation_links += 1
        elif parsed.scheme == "tel" and parsed.path == "+79030250807":
            phone_links += 1

    if len(routes) != 2:
        fail(path, f"Ожидалось два прямых CTA в анкету, найдено: {len(routes)}")
        errors += 1

    found_labels = {anchor["text"] for anchor in routes}
    missing_labels = ROUTE_LABELS - found_labels
    extra_labels = found_labels - ROUTE_LABELS
    if missing_labels:
        fail(path, "Отсутствуют CTA: " + ", ".join(sorted(missing_labels)))
        errors += 1
    if extra_labels:
        fail(path, "Найдены неожиданные прямые CTA: " + ", ".join(sorted(extra_labels)))
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

    if consultation_links < 2:
        fail(path, f"Должны сохраниться минимум две ссылки на консультацию, найдено: {consultation_links}")
        errors += 1
    if phone_links < 2:
        fail(path, f"Должны сохраниться минимум две телефонные ссылки, найдено: {phone_links}")
        errors += 1

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_file = site_dir / "kak-prohodit-rabota" / "index.html"
    errors = 0

    if not SOURCE_FILE.is_file():
        fail(SOURCE_FILE, "Исходная страница процесса отсутствует")
        errors += 1
    else:
        errors += validate_source(SOURCE_FILE)

    if not built_file.is_file():
        fail(built_file, "Собранная страница процесса отсутствует")
        errors += 1
    else:
        errors += validate_built(built_file)

    if errors:
        print(f"Аудит прямых заявок со страницы процесса завершён с ошибками: {errors}")
        return 1

    print(
        "Маршруты страницы процесса подтверждены: два прямых CTA, "
        "источник /kak-prohodit-rabota/, единый сценарий и сохранённые контакты"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
