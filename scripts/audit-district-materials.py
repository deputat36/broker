#!/usr/bin/env python3
"""Проверяет двустороннюю перелинковку материалов для жителей районов."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE_URL = "https://sterlikova-ipoteka.ru"
HUB_URL = "/polezno/materialy-dlya-zhiteley-rayonov/"
ARTICLE_URLS = (
    "/polezno/ipoteka-v-rayone-distantsionno/",
    "/polezno/kupit-zhile-v-borisoglebske-iz-rayona/",
    "/polezno/prosmotr-zhilya-v-borisoglebske-iz-rayona/",
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def annotation(message: str, file: Path | None = None) -> None:
    prefix = "::error"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def url_to_file(site_dir: Path, url: str) -> Path:
    return site_dir / url.lstrip("/") / "index.html"


def read_links(site_dir: Path, url: str) -> tuple[Path, set[str]] | None:
    html_file = url_to_file(site_dir, url)
    if not html_file.is_file():
        annotation(f"Не найден собранный файл для URL: {url}", html_file)
        return None

    parser = LinkParser()
    try:
        parser.feed(html_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        annotation(f"Не удалось прочитать HTML: {error}", html_file)
        return None

    normalized: set[str] = set()
    for href in parser.links:
        parsed = urlparse(urljoin(BASE_URL + url, href))
        if parsed.hostname in {"sterlikova-ipoteka.ru", "www.sterlikova-ipoteka.ru"}:
            normalized.add(parsed.path or "/")

    return html_file, normalized


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        annotation(f"Каталог сборки не найден: {site_dir}")
        return 1

    errors = 0
    hub_data = read_links(site_dir, HUB_URL)
    if hub_data is None:
        return 1

    hub_file, hub_links = hub_data
    for article_url in ARTICLE_URLS:
        if article_url not in hub_links:
            annotation(f"Материал отсутствует в тематической подборке: {article_url}", hub_file)
            errors += 1

        article_data = read_links(site_dir, article_url)
        if article_data is None:
            errors += 1
            continue

        article_file, article_links = article_data
        if HUB_URL not in article_links:
            annotation(f"Статья не содержит обратную ссылку на тематическую подборку: {HUB_URL}", article_file)
            errors += 1

    if errors:
        print(f"Аудит материалов для жителей районов завершен с ошибками: {errors}")
        return 1

    print("Аудит материалов для жителей районов успешно завершен: проверено 3 статьи")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
