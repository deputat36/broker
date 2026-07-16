#!/usr/bin/env python3
"""Проверяет маршруты со страницы консультации в онлайн-заявку."""

from __future__ import annotations

import html
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "konsultaciya.md"
PAGE_URL = "/konsultaciya/"
APPLICATION_URL = "/online-zayavka/"
SCENARIO = "Первичная консультация и подбор ипотеки"
ROUTE_LABELS = {
    "Заполнить онлайн-заявку",
    "Перейти к анкете",
    "Заполнить готовую форму",
    "Онлайн-заявка",
}


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

    if text.count(expected_route) != 4:
        fail(path, f"В исходнике должно быть четыре целевых маршрута, найдено: {text.count(expected_route)}")
        errors += 1

    if text.count("href=\"{{ '/online-zayavka/' | relative_url }}\""):
        fail(path, "На странице осталась ссылка на анкету без источника и сценария")
        errors += 1

    return errors


def validate_built(path: Path) -> int:
    anchors = parse_anchors(path)
    routes: list[dict[str, str]] = []
    errors = 0

    for anchor in anchors:
        parsed = urlsplit(anchor["href"])
        query = parse_qs(parsed.query, keep_blank_values=True)
        if parsed.path == APPLICATION_URL and "source" in query and "scenario" in query:
            routes.append(anchor)

    if len(routes) != 4:
        fail(path, f"Ожидалось четыре целевых CTA, найдено: {len(routes)}")
        errors += 1

    found_labels = {anchor["text"] for anchor in routes}
    missing_labels = ROUTE_LABELS - found_labels
    extra_labels = found_labels - ROUTE_LABELS
    if missing_labels:
        fail(path, "Отсутствуют CTA: " + ", ".join(sorted(missing_labels)))
        errors += 1
    if extra_labels:
        fail(path, "Найдены неожиданные целевые CTA: " + ", ".join(sorted(extra_labels)))
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

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_file = site_dir / "konsultaciya" / "index.html"
    errors = 0

    if not SOURCE_FILE.is_file():
        fail(SOURCE_FILE, "Исходная страница консультации отсутствует")
        errors += 1
    else:
        errors += validate_source(SOURCE_FILE)

    if not built_file.is_file():
        fail(built_file, "Собранная страница консультации отсутствует")
        errors += 1
    else:
        errors += validate_built(built_file)

    if errors:
        print(f"Аудит маршрутов страницы консультации завершён с ошибками: {errors}")
        return 1

    print(
        "Маршруты страницы консультации подтверждены: четыре CTA, "
        "источник /konsultaciya/ и единый сценарий первичной консультации"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
