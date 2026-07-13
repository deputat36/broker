#!/usr/bin/env python3
"""Проверяет, что ключевые региональные страницы сохраняют отдельный пользовательский сценарий."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

INTENT_MARKERS = {
    "/geo/gribanovskiy/ipoteka-s-materinskim-kapitalom/": "продать в районе и купить новое жилье",
    "/geo/povorino/ipoteka-s-materinskim-kapitalom/": "квартира и дом требуют разных вводных",
    "/geo/gribanovskiy/ipoteka-s-sozaemshchikom/": "работа в разных местах",
    "/geo/povorino/ipoteka-s-sozaemshchikom/": "сравните заявку с созаемщиком и без него",
    "/geo/gribanovskiy/ipoteka-na-stroitelstvo-doma/": "семейный участок",
    "/geo/povorino/ipoteka-na-stroitelstvo-doma/": "готовый дом или стройка",
}

SKIPPED_TAGS = {"nav", "script", "style", "noscript"}


class MainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.found_main = False
        self.skip_stack: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value for key, value in attrs}
        if tag == "main" and attrs_map.get("id") == "main-content":
            self.in_main = True
            self.found_main = True
            return
        if self.in_main and tag in SKIPPED_TAGS:
            self.skip_stack.append(tag)

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
            self.parts.append(data)

    @property
    def normalized_text(self) -> str:
        return " ".join(" ".join(self.parts).casefold().replace("ё", "е").split())


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
    for page_url, marker in INTENT_MARKERS.items():
        html_file = url_to_file(site_dir, page_url)
        if page_url not in sitemap_paths:
            annotation(f"Региональная страница отсутствует в sitemap: {page_url}", sitemap_file)
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

        parser = MainTextParser()
        parser.feed(raw_html)
        if not parser.found_main:
            annotation("Не найден контейнер main#main-content", html_file)
            errors += 1
            continue

        normalized_marker = " ".join(marker.casefold().replace("ё", "е").split())
        if normalized_marker not in parser.normalized_text:
            annotation(
                f"Страница потеряла отдельный региональный сценарий; ожидаемый маркер: {marker}",
                html_file,
            )
            errors += 1

    if errors:
        print(f"Аудит региональных намерений завершен с ошибками: {errors}")
        return 1

    print(
        "Аудит региональных намерений успешно завершен: "
        f"проверено страниц {len(INTENT_MARKERS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
