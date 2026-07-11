#!/usr/bin/env python3
"""Проверяет обязательные CTA на ключевых конверсионных страницах сайта."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE_URL = "https://sterlikova-ipoteka.ru"
PHONE_LINK = "tel:+79030250807"
VK_PROFILE = "https://vk.com/tatyanasterlikova"

PAGE_REQUIREMENTS = {
    "/": {
        "internal": {"/konsultaciya/"},
        "phone": True,
        "vk": True,
        "max": True,
    },
    "/konsultaciya/": {
        "internal": {"/etagi/"},
        "phone": True,
        "vk": True,
        "max": True,
    },
    "/kontakty/": {
        "internal": {"/konsultaciya/"},
        "phone": True,
        "vk": True,
        "max": True,
    },
    "/stoimost/": {
        "internal": {"/konsultaciya/", "/etagi/"},
        "phone": True,
        "vk": True,
        "max": True,
    },
}


class ConversionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.max_controls = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value for key, value in attrs}
        if "data-copy-phone" in attrs_map:
            self.max_controls += 1
        if tag.lower() == "a":
            href = attrs_map.get("href")
            if href:
                self.links.append(href)


def annotation(message: str, file: Path | None = None) -> None:
    prefix = "::error"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def url_to_file(site_dir: Path, page_url: str) -> Path:
    if page_url == "/":
        return site_dir / "index.html"
    return site_dir / page_url.lstrip("/") / "index.html"


def normalize_internal_links(page_url: str, links: list[str]) -> set[str]:
    targets: set[str] = set()
    for href in links:
        parsed = urlparse(urljoin(BASE_URL + page_url, href))
        if parsed.hostname in {"sterlikova-ipoteka.ru", "www.sterlikova-ipoteka.ru"}:
            targets.add(parsed.path or "/")
    return targets


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        annotation(f"Каталог сборки не найден: {site_dir}")
        return 1

    errors = 0
    for page_url, requirements in PAGE_REQUIREMENTS.items():
        html_file = url_to_file(site_dir, page_url)
        if not html_file.is_file():
            annotation(f"Не найдена ключевая страница: {page_url}", html_file)
            errors += 1
            continue

        parser = ConversionParser()
        try:
            parser.feed(html_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            annotation(f"Не удалось прочитать HTML: {error}", html_file)
            errors += 1
            continue

        links = set(parser.links)
        internal_links = normalize_internal_links(page_url, parser.links)

        if requirements["phone"] and PHONE_LINK not in links:
            annotation(f"На странице {page_url} отсутствует телефонный CTA {PHONE_LINK}", html_file)
            errors += 1
        if requirements["vk"] and VK_PROFILE not in links:
            annotation(f"На странице {page_url} отсутствует ссылка ВКонтакте", html_file)
            errors += 1
        if requirements["max"] and parser.max_controls == 0:
            annotation(f"На странице {page_url} отсутствует CTA для MAX", html_file)
            errors += 1

        for target in sorted(requirements["internal"] - internal_links):
            annotation(f"На странице {page_url} отсутствует обязательный переход: {target}", html_file)
            errors += 1

    if errors:
        print(f"Аудит конверсионных страниц завершен с ошибками: {errors}")
        return 1

    print(f"Аудит конверсионных страниц успешно завершен: проверено {len(PAGE_REQUIREMENTS)} страницы")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
