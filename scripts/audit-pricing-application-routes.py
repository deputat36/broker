#!/usr/bin/env python3
"""Проверяет конверсионные маршруты со страницы стоимости в онлайн-заявку."""

from __future__ import annotations

import html
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PRICING_URL = "/stoimost/"
APPLICATION_URL = "/online-zayavka/"
ETAGI_URL = "/etagi/"
ETAGI_ROUTE_LABEL = "Условия для клиентов «ЭТАЖИ»"
STANDARD_SCENARIO = "Первичная консультация и подбор ипотеки"
COMPLEX_SCENARIO = "Другая ситуация"
REQUIRED_ROUTE_LABELS = {
    "Получить расчёт стоимости",
    "Описать задачу →",
    "Подать заявку на подбор →",
    "Описать сложную ситуацию →",
    "Заполнить короткую заявку",
}
REQUIRED_PRICES = {"0 ₽", "от 15 000 ₽", "от 25 000 ₽"}


class PricingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.price_items: list[dict[str, object]] = []
        self.page_text: list[str] = []
        self._anchor: dict[str, object] | None = None
        self._price_item: dict[str, object] | None = None
        self._price_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        classes = set(attrs_map.get("class", "").split())

        if tag == "article" and "price-item" in classes and self._price_item is None:
            self._price_item = {"direct_children": [], "text": []}
            self._price_depth = 1
        elif self._price_item is not None:
            if self._price_depth == 1:
                direct_children = self._price_item["direct_children"]
                assert isinstance(direct_children, list)
                direct_children.append(tag)
            self._price_depth += 1

        if tag == "a":
            self._anchor = {
                "href": html.unescape(attrs_map.get("href", "")),
                "parts": [],
            }

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor is not None:
            parts = self._anchor["parts"]
            assert isinstance(parts, list)
            self.anchors.append({
                "href": str(self._anchor["href"]),
                "text": " ".join(" ".join(parts).split()),
            })
            self._anchor = None

        if self._price_item is not None:
            self._price_depth -= 1
            if self._price_depth == 0:
                self.price_items.append(self._price_item)
                self._price_item = None

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.page_text.append(data)
        if self._anchor is not None:
            parts = self._anchor["parts"]
            assert isinstance(parts, list)
            parts.append(data)
        if self._price_item is not None:
            parts = self._price_item["text"]
            assert isinstance(parts, list)
            parts.append(data)

    @property
    def normalized_page_text(self) -> str:
        return " ".join(" ".join(self.page_text).split())


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def page_file(site_dir: Path, url: str) -> Path:
    return site_dir / url.lstrip("/") / "index.html"


def normalized_item_text(item: dict[str, object]) -> str:
    parts = item["text"]
    assert isinstance(parts, list)
    return " ".join(" ".join(parts).split())


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    html_file = page_file(site_dir, PRICING_URL)
    if not html_file.is_file():
        error("Не найдена собранная страница стоимости", html_file)
        return 1

    parser = PricingParser()
    parser.feed(html_file.read_text(encoding="utf-8", errors="ignore"))
    errors = 0

    if len(parser.price_items) != 3:
        error(f"Ожидалось три тарифные карточки, найдено: {len(parser.price_items)}", html_file)
        errors += 1

    found_prices: set[str] = set()
    for index, item in enumerate(parser.price_items, start=1):
        direct_children = item["direct_children"]
        assert isinstance(direct_children, list)
        if direct_children != ["div", "strong"]:
            error(
                f"Тарифная карточка {index} должна состоять из блока описания и цены, найдено: {direct_children}",
                html_file,
            )
            errors += 1
        item_text = normalized_item_text(item)
        for price in REQUIRED_PRICES:
            if price in item_text:
                found_prices.add(price)
    missing_prices = REQUIRED_PRICES - found_prices
    if missing_prices:
        error("На странице изменились или пропали цены: " + ", ".join(sorted(missing_prices)), html_file)
        errors += 1

    application_links: list[dict[str, str]] = []
    etagi_links: list[dict[str, str]] = []
    for anchor in parser.anchors:
        parsed = urlsplit(anchor["href"])
        if parsed.path == APPLICATION_URL and anchor["text"] in REQUIRED_ROUTE_LABELS:
            application_links.append(anchor)
        elif parsed.path == ETAGI_URL and anchor["text"] == ETAGI_ROUTE_LABEL:
            etagi_links.append(anchor)

    if len(application_links) != 5:
        error(f"Ожидалось пять тарифных CTA в онлайн-заявку, найдено: {len(application_links)}", html_file)
        errors += 1

    found_labels = {anchor["text"] for anchor in application_links}
    missing_labels = REQUIRED_ROUTE_LABELS - found_labels
    if missing_labels:
        error("Отсутствуют CTA страницы стоимости: " + ", ".join(sorted(missing_labels)), html_file)
        errors += 1

    standard_count = 0
    complex_count = 0
    for anchor in application_links:
        parsed = urlsplit(anchor["href"])
        query = parse_qs(parsed.query, keep_blank_values=True)
        source = query.get("source", [""])[0]
        scenario = query.get("scenario", [""])[0]
        if source != PRICING_URL:
            error(f"CTA «{anchor['text']}» передаёт неверный источник: {source or 'пусто'}", html_file)
            errors += 1
        if scenario == STANDARD_SCENARIO:
            standard_count += 1
        elif scenario == COMPLEX_SCENARIO:
            complex_count += 1
        else:
            error(f"CTA «{anchor['text']}» передаёт неподдерживаемый сценарий: {scenario or 'пусто'}", html_file)
            errors += 1

    if standard_count != 4:
        error(f"Стандартный сценарий должен использоваться четырежды, найдено: {standard_count}", html_file)
        errors += 1
    if complex_count != 1:
        error(f"Сложный сценарий должен использоваться один раз, найдено: {complex_count}", html_file)
        errors += 1

    if len(etagi_links) != 1:
        error(f"Целевая кнопка отдельных условий «ЭТАЖИ» должна быть одна, найдено: {len(etagi_links)}", html_file)
        errors += 1
    for marker in (
        "До начала платной работы согласуются задача, состав действий и стоимость.",
        "не совпадают автоматически с частными тарифами",
    ):
        if marker not in parser.normalized_page_text:
            error(f"На странице отсутствует защитная формулировка: {marker}", html_file)
            errors += 1

    if errors:
        print(f"Аудит маршрутов со страницы стоимости завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит страницы стоимости успешно завершён: три тарифа, пять CTA, "
        "четыре стандартных маршрута, один сложный маршрут и отдельные условия «ЭТАЖИ» подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
