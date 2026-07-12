#!/usr/bin/env python3
"""Проверяет обязательные CTA и разделение форматов работы на ключевых страницах."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE_URL = "https://sterlikova-ipoteka.ru"
PHONE_LINK = "tel:+79030250807"
VK_PROFILE = "https://vk.com/tatyanasterlikova"

STANDARD_SERVICE_LINKS = {
    "/konsultaciya/",
    "/kak-prohodit-rabota/",
    "/stoimost/",
    "/etagi/",
}

STANDARD_SERVICE_URLS = (
    "/uslugi/slozhnaya-ipoteka/",
    "/uslugi/otkazali-v-ipoteke/",
    "/uslugi/ipoteka-na-novostroyku/",
    "/uslugi/ipoteka-na-vtorichnoe-zhile/",
    "/uslugi/ipoteka-na-dom/",
    "/uslugi/semeynaya-ipoteka/",
    "/uslugi/materinskiy-kapital/",
    "/uslugi/ipoteka-na-stroitelstvo-doma/",
    "/uslugi/ipoteka-dlya-ip-samozanyatyh/",
)

PAGE_REQUIREMENTS = {
    "/": {"/konsultaciya/", "/etagi/"},
    "/konsultaciya/": {"/etagi/"},
    "/kontakty/": {"/konsultaciya/", "/etagi/"},
    "/stoimost/": {"/konsultaciya/", "/etagi/"},
    "/etagi/": {"/stoimost/"},
    "/faq/": {"/stoimost/", "/etagi/"},
    "/kak-prohodit-rabota/": {"/konsultaciya/", "/uslugi/", "/stoimost/", "/etagi/"},
    "/uslugi/podbor-ipoteki/": STANDARD_SERVICE_LINKS,
    "/uslugi/refinansirovanie-ipoteki/": {
        "/konsultaciya/",
        "/kak-prohodit-rabota/",
        "/stoimost/",
        "/kontakty/",
    },
}

for service_url in STANDARD_SERVICE_URLS:
    PAGE_REQUIREMENTS[service_url] = STANDARD_SERVICE_LINKS

TEXT_REQUIREMENTS = {
    "/": ("включено в комиссию компании", "отдельно клиентом не оплачивается"),
    "/stoimost/": ("включено в комиссию компании", "отдельно не оплачивает"),
    "/etagi/": ("включено в комиссию компании", "отдельно не оплачивается"),
    "/faq/": ("включено в комиссию компании", "отдельно клиентом не оплачивается"),
    "/kak-prohodit-rabota/": (
        "сопровождение до решения банка",
        "конкретный объём помощи после решения банка",
        "включено в комиссию компании",
    ),
    "/uslugi/podbor-ipoteki/": (
        "сопровождение до решения банка",
        "конкретный объём дальнейшей помощи после решения банка",
        "включено в комиссию компании",
        "отдельно клиентом не оплачивается",
    ),
    "/uslugi/refinansirovanie-ipoteki/": (
        "сопровождение до решения нового банка",
        "конкретный объём дальнейшей помощи",
        "условия компании «этажи» для рефинансирования не предполагаются автоматически",
    ),
}

STANDARD_SERVICE_TEXT = (
    "сопровождение до решения банка",
    "включено в комиссию компании",
    "отдельно клиентом не оплачивается",
)

for service_url in STANDARD_SERVICE_URLS:
    TEXT_REQUIREMENTS[service_url] = STANDARD_SERVICE_TEXT

FORBIDDEN_TEXT = {
    "/etagi/": ('"price":"0"', "0 ₽ для клиентов", "ипотечное сопровождение бесплатно"),
    "/kak-prohodit-rabota/": ("полное сопровождение сделки включено",),
    "/uslugi/podbor-ipoteki/": ("ипотечное сопровождение для клиента бесплатно",),
    "/uslugi/refinansirovanie-ipoteki/": (
        "ипотечное сопровождение бесплатно",
        "включено в комиссию компании",
    ),
}

for service_url in STANDARD_SERVICE_URLS:
    FORBIDDEN_TEXT[service_url] = (
        "ипотечное сопровождение бесплатно",
        "сопровождение по ипотеке бесплатно",
        "ипотечное сопровождение для клиента бесплатно",
        "консультация и ипотечное сопровождение для клиента бесплатны",
    )


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
    for page_url, required_internal_links in PAGE_REQUIREMENTS.items():
        html_file = url_to_file(site_dir, page_url)
        if not html_file.is_file():
            annotation(f"Не найдена ключевая страница: {page_url}", html_file)
            errors += 1
            continue

        parser = ConversionParser()
        try:
            raw_html = html_file.read_text(encoding="utf-8")
            parser.feed(raw_html)
        except (OSError, UnicodeDecodeError) as error:
            annotation(f"Не удалось прочитать HTML: {error}", html_file)
            errors += 1
            continue

        links = set(parser.links)
        internal_links = normalize_internal_links(page_url, parser.links)
        normalized_html = " ".join(raw_html.casefold().split())

        if PHONE_LINK not in links:
            annotation(f"На странице {page_url} отсутствует телефонный CTA {PHONE_LINK}", html_file)
            errors += 1
        if VK_PROFILE not in links:
            annotation(f"На странице {page_url} отсутствует ссылка ВКонтакте", html_file)
            errors += 1
        if parser.max_controls == 0:
            annotation(f"На странице {page_url} отсутствует CTA для MAX", html_file)
            errors += 1

        for target in sorted(required_internal_links - internal_links):
            annotation(f"На странице {page_url} отсутствует обязательный переход: {target}", html_file)
            errors += 1

        for required_text in TEXT_REQUIREMENTS.get(page_url, ()):
            if required_text.casefold() not in normalized_html:
                annotation(
                    f"На странице {page_url} отсутствует обязательная формулировка: {required_text}",
                    html_file,
                )
                errors += 1

        for forbidden_text in FORBIDDEN_TEXT.get(page_url, ()):
            if forbidden_text.casefold() in normalized_html:
                annotation(
                    f"На странице {page_url} найдена двусмысленная формулировка: {forbidden_text}",
                    html_file,
                )
                errors += 1

    if errors:
        print(f"Аудит конверсионных страниц завершен с ошибками: {errors}")
        return 1

    print(f"Аудит конверсионных страниц успешно завершен: проверено {len(PAGE_REQUIREMENTS)} страниц")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
