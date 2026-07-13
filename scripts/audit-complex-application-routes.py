#!/usr/bin/env python3
"""Проверяет маршруты «диагностика → подготовка → повторная заявка → обращение»."""

from __future__ import annotations

import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

REGIONS = ("borisoglebsk", "gribanovskiy", "povorino")
SCENARIO_REQUIREMENTS = {
    "otkazali-v-ipoteke": {
        "/polezno/chto-delat-posle-otkaza/",
        "/polezno/chto-vliyaet-na-odobrenie-ipoteki/",
        "/polezno/pochemu-ne-stoit-podavat-zayavki-vo-vse-banki/",
    },
    "ipoteka-s-plohoy-kreditnoy-istoriey": {
        "/polezno/kak-proverit-kreditnuyu-istoriyu-pered-ipotekoy/",
        "/polezno/kreditnaya-nagruzka-pered-ipotekoy/",
        "/polezno/chto-vliyaet-na-odobrenie-ipoteki/",
    },
    "ipoteka-bez-oficialnogo-dohoda": {
        "/polezno/ipoteka-s-malenkoy-oficialnoy-zarplatoy/",
        "/polezno/skolko-nuzhno-zarabatyvat-dlya-ipoteki/",
        "/polezno/dokumenty-dlya-ipoteki-samozanyatomu/",
    },
    "ipoteka-bez-pervonachalnogo-vznosa": {
        "/polezno/mozhno-li-vzyat-ipoteku-bez-pervonachalnogo-vznosa/",
        "/polezno/matkapital-kak-pervonachalnyy-vznos-po-ipoteke/",
        "/polezno/kak-ponyat-komfortnyy-platezh-po-ipoteke/",
    },
}

EXPECTED_STEPS = {"1", "2", "3", "4"}
APPLICATION_URL = "/online-zayavka/"


class RouteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.route_depth = 0
        self.route_count = 0
        self.route_slugs: list[str] = []
        self.steps: Counter[str] = Counter()
        self.links: set[str] = set()
        self.application_sources: list[str] = []
        self.text_parts: list[str] = []
        self.generic_online_routes = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value for key, value in attrs}
        classes = set((attrs_map.get("class") or "").split())

        if tag == "main" and attrs_map.get("id") == "main-content":
            self.in_main = True
            return
        if not self.in_main:
            return

        if "service-online-route" in classes:
            self.generic_online_routes += 1

        if self.route_depth:
            self.route_depth += 1
        elif tag == "section" and "complex-application-route" in classes:
            self.route_depth = 1
            self.route_count += 1
            self.route_slugs.append(attrs_map.get("data-complex-route") or "")

        if not self.route_depth:
            return

        step = attrs_map.get("data-complex-route-step")
        if step:
            self.steps[step] += 1

        if tag == "a":
            href = attrs_map.get("href") or ""
            if not href:
                return
            parsed = urlparse(href)
            path = parsed.path or "/"
            self.links.add(path)
            if path == APPLICATION_URL:
                source_values = parse_qs(parsed.query).get("source", [])
                self.application_sources.extend(source_values)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.route_depth:
            self.route_depth -= 1
        if tag == "main":
            self.in_main = False
            self.route_depth = 0

    def handle_data(self, data: str) -> None:
        if self.route_depth:
            self.text_parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).casefold().replace("ё", "е").split())


def annotation(message: str, file: Path | None = None) -> None:
    prefix = "::error"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def load_sitemap_paths(sitemap_file: Path) -> set[str]:
    root = ElementTree.parse(sitemap_file).getroot()
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {
        urlparse(node.text.strip()).path or "/"
        for node in root.findall("sm:url/sm:loc", namespace)
        if node.text
    }


def url_to_file(site_dir: Path, page_url: str) -> Path:
    return site_dir / page_url.lstrip("/") / "index.html"


def expected_pages() -> list[tuple[str, str, set[str]]]:
    pages: list[tuple[str, str, set[str]]] = []
    for region in REGIONS:
        for scenario, links in SCENARIO_REQUIREMENTS.items():
            pages.append((f"/geo/{region}/{scenario}/", scenario, links))
    return pages


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        annotation(f"Каталог сборки не найден: {site_dir}")
        return 1

    sitemap_file = site_dir / "sitemap.xml"
    try:
        sitemap_paths = load_sitemap_paths(sitemap_file)
    except (ElementTree.ParseError, OSError) as error:
        annotation(f"Не удалось разобрать sitemap.xml: {error}", sitemap_file)
        return 1

    errors = 0
    checked = 0

    for page_url, scenario, required_links in expected_pages():
        checked += 1
        html_file = url_to_file(site_dir, page_url)

        if page_url not in sitemap_paths:
            annotation(f"Сложная региональная страница отсутствует в sitemap: {page_url}", sitemap_file)
            errors += 1
        if not html_file.is_file():
            annotation(f"Не найдена сложная региональная страница: {page_url}", html_file)
            errors += 1
            continue

        try:
            raw_html = html_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            annotation(f"Не удалось прочитать HTML: {error}", html_file)
            errors += 1
            continue

        parser = RouteParser()
        parser.feed(raw_html)

        if parser.route_count != 1:
            annotation(f"Ожидался один сложный маршрут, найдено: {parser.route_count}", html_file)
            errors += 1
        if parser.route_slugs != [scenario]:
            annotation(
                f"Неверный сценарий сложного маршрута: ожидался {scenario}, получено {parser.route_slugs}",
                html_file,
            )
            errors += 1

        if set(parser.steps) != EXPECTED_STEPS or any(parser.steps[step] != 1 for step in EXPECTED_STEPS):
            annotation(f"Маршрут должен содержать ровно четыре шага 1–4: {dict(parser.steps)}", html_file)
            errors += 1

        missing_links = required_links - parser.links
        if missing_links:
            annotation(f"Маршрут потерял обязательные материалы: {', '.join(sorted(missing_links))}", html_file)
            errors += 1

        if parser.application_sources != [page_url]:
            annotation(
                f"Онлайн-заявка должна передавать точный source {page_url}, получено: {parser.application_sources}",
                html_file,
            )
            errors += 1

        if parser.generic_online_routes:
            annotation("На сложной странице одновременно показан дублирующий общий CTA", html_file)
            errors += 1

        required_texts = (
            "подайте онлайн-заявку из любого города",
            "этот маршрут не гарантирует одобрение",
            "окончательное решение",
        )
        for required_text in required_texts:
            if required_text not in parser.text:
                annotation(f"В сложном маршруте отсутствует текст: {required_text}", html_file)
                errors += 1

    all_required_targets = set().union(*SCENARIO_REQUIREMENTS.values()) | {APPLICATION_URL}
    missing_targets = all_required_targets - sitemap_paths
    if missing_targets:
        annotation(f"Целевые страницы маршрутов отсутствуют в sitemap: {', '.join(sorted(missing_targets))}", sitemap_file)
        errors += 1

    if errors:
        print(f"Аудит сложных маршрутов завершен с ошибками: {errors}")
        return 1

    print(
        "Аудит сложных маршрутов успешно завершен: "
        f"проверено страниц {checked}, сценариев {len(SCENARIO_REQUIREMENTS)}, шагов на странице 4"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
