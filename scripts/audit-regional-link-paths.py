#!/usr/bin/env python3
"""Проверяет разные маршруты перелинковки ключевых региональных страниц."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

ROUTE_REQUIREMENTS: dict[str, dict[str, object]] = {
    "/geo/borisoglebsk/semeynaya-ipoteka/": {
        "marker": "маршрут: квартира в городе",
        "links": {
            "/uslugi/ipoteka-na-novostroyku/",
            "/geo/borisoglebsk/ipoteka-na-vtorichnoe-zhile/",
            "/polezno/chto-proverit-pered-pokupkoy-novostroyki-v-ipoteku/",
            "/geo/borisoglebsk/ipoteka-s-materinskim-kapitalom/",
        },
    },
    "/geo/gribanovskiy/semeynaya-ipoteka/": {
        "marker": "маршрут: семейный бюджет района",
        "links": {
            "/geo/gribanovskiy/ipoteka-s-materinskim-kapitalom/",
            "/geo/gribanovskiy/ipoteka-s-sozaemshchikom/",
            "/geo/gribanovskiy/ipoteka-bez-oficialnogo-dohoda/",
            "/polezno/kupit-zhile-v-borisoglebske-iz-rayona/",
        },
    },
    "/geo/povorino/semeynaya-ipoteka/": {
        "marker": "маршрут: дом, платеж и сроки",
        "links": {
            "/geo/povorino/ipoteka-na-dom/",
            "/geo/povorino/ipoteka-s-materinskim-kapitalom/",
            "/polezno/kak-ponyat-komfortnyy-platezh-po-ipoteke/",
            "/polezno/avans-zadatok-i-ipoteka/",
        },
    },
    "/geo/borisoglebsk/ipoteka-na-kvartiru/": {
        "links": {
            "/polezno/chto-proverit-pered-pokupkoy-vtorichnogo-zhilya/",
            "/uslugi/ipoteka-na-novostroyku/",
            "/geo/borisoglebsk/ipoteka-na-vtorichnoe-zhile/",
        },
    },
    "/geo/gribanovskiy/ipoteka-na-kvartiru/": {
        "links": {
            "/polezno/kak-ponyat-komfortnyy-platezh-po-ipoteke/",
            "/polezno/avans-zadatok-i-ipoteka/",
        },
    },
    "/geo/povorino/ipoteka-na-kvartiru/": {
        "links": {
            "/polezno/kreditnaya-nagruzka-pered-ipotekoy/",
            "/polezno/avans-zadatok-i-ipoteka/",
        },
    },
    "/geo/borisoglebsk/ipoteka-na-dom/": {
        "links": {
            "/polezno/chto-proverit-pered-pokupkoy-doma-v-ipoteku/",
            "/polezno/avans-zadatok-i-ipoteka/",
            "/kalkulyator-ipoteki/",
        },
    },
    "/geo/gribanovskiy/ipoteka-na-dom/": {
        "links": {
            "/polezno/pochemu-bank-ne-odobryaet-obekt-ipoteki/",
            "/polezno/avans-zadatok-i-ipoteka/",
        },
    },
    "/geo/povorino/ipoteka-na-dom/": {
        "links": {
            "/polezno/pochemu-bank-ne-odobryaet-obekt-ipoteki/",
            "/polezno/kak-ponyat-komfortnyy-platezh-po-ipoteke/",
        },
    },
}

DIVERSITY_GROUPS = {
    "семейная ипотека": (
        "/geo/borisoglebsk/semeynaya-ipoteka/",
        "/geo/gribanovskiy/semeynaya-ipoteka/",
        "/geo/povorino/semeynaya-ipoteka/",
    ),
    "квартира": (
        "/geo/borisoglebsk/ipoteka-na-kvartiru/",
        "/geo/gribanovskiy/ipoteka-na-kvartiru/",
        "/geo/povorino/ipoteka-na-kvartiru/",
    ),
    "дом": (
        "/geo/borisoglebsk/ipoteka-na-dom/",
        "/geo/gribanovskiy/ipoteka-na-dom/",
        "/geo/povorino/ipoteka-na-dom/",
    ),
}

CONTEXT_PREFIXES = ("/polezno/", "/uslugi/", "/geo/", "/kalkulyator-ipoteki/")
SKIPPED_TAGS = {"script", "style", "noscript"}


class MainParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.found_main = False
        self.skip_stack: list[str] = []
        self.links: set[str] = set()
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value for key, value in attrs}
        if tag == "main" and attrs_map.get("id") == "main-content":
            self.in_main = True
            self.found_main = True
            return
        if not self.in_main:
            return
        if tag in SKIPPED_TAGS:
            self.skip_stack.append(tag)
            return
        if tag == "a" and not self.skip_stack:
            href = attrs_map.get("href") or ""
            if href:
                parsed = urlparse(href)
                if not parsed.scheme or parsed.scheme in {"http", "https"}:
                    self.links.add(parsed.path or "/")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.in_main:
            return
        if tag == "main":
            self.in_main = False
            self.skip_stack.clear()
            return
        if self.skip_stack and tag == self.skip_stack[-1]:
            self.skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_main and not self.skip_stack:
            self.text_parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).casefold().replace("ё", "е").split())


def annotation(message: str, file: Path | None = None) -> None:
    prefix = "::error"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def url_to_file(site_dir: Path, page_url: str) -> Path:
    return site_dir / page_url.lstrip("/") / "index.html"


def load_sitemap_paths(sitemap_file: Path) -> set[str]:
    root = ElementTree.parse(sitemap_file).getroot()
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {
        urlparse(node.text.strip()).path or "/"
        for node in root.findall("sm:url/sm:loc", namespace)
        if node.text
    }


def contextual_links(page_url: str, links: set[str]) -> set[str]:
    region_parts = page_url.strip("/").split("/")
    region_hub = f"/geo/{region_parts[1]}/" if len(region_parts) >= 2 else ""
    return {
        link
        for link in links
        if link.startswith(CONTEXT_PREFIXES)
        and link not in {page_url, region_hub, "/geo/", "/uslugi/"}
    }


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
    link_sets: dict[str, set[str]] = {}

    for page_url, requirement in ROUTE_REQUIREMENTS.items():
        html_file = url_to_file(site_dir, page_url)
        if page_url not in sitemap_paths:
            annotation(f"Страница отсутствует в sitemap: {page_url}", sitemap_file)
            errors += 1
        if not html_file.is_file():
            annotation(f"Не найдена региональная страница: {page_url}", html_file)
            errors += 1
            continue

        try:
            raw_html = html_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            annotation(f"Не удалось прочитать HTML: {error}", html_file)
            errors += 1
            continue

        parser = MainParser()
        parser.feed(raw_html)
        if not parser.found_main:
            annotation("Не найден контейнер main#main-content", html_file)
            errors += 1
            continue

        required_links = set(requirement.get("links", set()))
        missing_links = required_links - parser.links
        if missing_links:
            annotation(
                f"Региональный маршрут потерял ссылки: {', '.join(sorted(missing_links))}",
                html_file,
            )
            errors += 1

        marker = str(requirement.get("marker", "")).strip()
        if marker:
            normalized_marker = " ".join(marker.casefold().replace("ё", "е").split())
            if normalized_marker not in parser.text:
                annotation(f"Не найден маркер маршрута: {marker}", html_file)
                errors += 1

        link_sets[page_url] = contextual_links(page_url, parser.links)
        if len(link_sets[page_url]) < 2:
            annotation("Слишком мало контекстных ссылок для продолжения маршрута", html_file)
            errors += 1

    for group_name, urls in DIVERSITY_GROUPS.items():
        available = [url for url in urls if url in link_sets]
        for index, left_url in enumerate(available):
            for right_url in available[index + 1 :]:
                left_links = link_sets[left_url]
                right_links = link_sets[right_url]
                if left_links == right_links:
                    annotation(
                        f"Одинаковые наборы ссылок в группе «{group_name}»: {left_url} и {right_url}",
                        url_to_file(site_dir, left_url),
                    )
                    errors += 1

    if errors:
        print(f"Аудит региональной перелинковки завершен с ошибками: {errors}")
        return 1

    print(
        "Аудит региональной перелинковки успешно завершен: "
        f"проверено страниц {len(ROUTE_REQUIREMENTS)}, групп {len(DIVERSITY_GROUPS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
