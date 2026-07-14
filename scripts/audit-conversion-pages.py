#!/usr/bin/env python3
"""Проверяет CTA, маршруты и формулировки ключевых конверсионных страниц."""

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
    "/uslugi/ipoteka-bez-oficialnogo-dohoda/",
    "/uslugi/ipoteka-s-plohoy-kreditnoy-istoriey/",
    "/uslugi/ipoteka-bez-pervonachalnogo-vznosa/",
    "/uslugi/ipoteka-s-sozaemshchikom/",
    "/uslugi/ipoteka-pri-prodazhe-starogo-zhilya/",
    "/uslugi/ipoteka-dlya-molodoy-semi/",
    "/uslugi/ipoteka-dlya-pensionerov/",
)

ALL_SERVICE_URLS = set(STANDARD_SERVICE_URLS) | {
    "/uslugi/podbor-ipoteki/",
    "/uslugi/refinansirovanie-ipoteki/",
}

PAGE_REQUIREMENTS = {
    "/": {"/konsultaciya/", "/etagi/"},
    "/uslugi/": ALL_SERVICE_URLS
    | {"/konsultaciya/", "/kak-prohodit-rabota/", "/stoimost/", "/etagi/"},
    "/konsultaciya/": {"/etagi/"},
    "/kontakty/": {"/konsultaciya/", "/etagi/"},
    "/o-brokere/": {"/uslugi/", "/kontakty/", "/stoimost/", "/etagi/"},
    "/stoimost/": {"/konsultaciya/", "/etagi/"},
    "/etagi/": {"/stoimost/"},
    "/faq/": {"/stoimost/", "/etagi/"},
    "/kak-prohodit-rabota/": {
        "/konsultaciya/",
        "/uslugi/",
        "/stoimost/",
        "/etagi/",
    },
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
    "/": (
        "условия сопровождения через «этажи» уточняются до сделки",
        "проверить условия",
    ),
    "/uslugi/": (
        "состав ипотечного сопровождения и порядок оплаты нужно подтвердить",
        "действующим условиям компании",
    ),
    "/konsultaciya/": (
        "условия ипотечного сопровождения подтверждаются отдельно",
        "не означает, что любое дальнейшее сопровождение предоставляется без отдельной оплаты",
    ),
    "/kontakty/": (
        "условия зависят от действующих тарифов компании",
        "предусмотрена ли отдельная оплата",
    ),
    "/o-brokere/": (
        "состав ипотечного сопровождения и порядок оплаты определяются",
        "подтверждаются до начала работы",
    ),
    "/stoimost/": (
        "условия сопровождения определяются отдельно",
        "не совпадают автоматически с частными тарифами",
    ),
    "/etagi/": (
        "условия нужно подтвердить до начала сопровождения",
        "возможную отдельную оплату",
    ),
    "/faq/": (
        "до начала сопровождения нужно отдельно подтвердить",
        "предусмотрена ли дополнительная оплата",
    ),
    "/kak-prohodit-rabota/": (
        "сопровождение до решения банка",
        "конкретный объем помощи после решения банка",
        "до начала работы отдельно подтверждаются состав сопровождения",
        "возможная дополнительная стоимость",
    ),
    "/uslugi/podbor-ipoteki/": (
        "сопровождение до решения банка",
        "конкретный объем дальнейшей помощи после решения банка",
        "включено в комиссию компании",
        "отдельно клиентом не оплачивается",
    ),
    "/uslugi/refinansirovanie-ipoteki/": (
        "сопровождение до решения нового банка",
        "конкретный объем дальнейшей помощи",
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

TEXT_REQUIREMENTS["/uslugi/ipoteka-bez-pervonachalnogo-vznosa/"] += (
    "не используются схемы с фиктивным завышением стоимости",
    "решение принимает банк",
)
TEXT_REQUIREMENTS["/uslugi/ipoteka-s-plohoy-kreditnoy-istoriey/"] += (
    "разбор не гарантирует одобрение",
)
TEXT_REQUIREMENTS["/uslugi/ipoteka-pri-prodazhe-starogo-zhilya/"] += (
    "не заменяет оценку рыночной цены",
    "юридическую проверку",
)
TEXT_REQUIREMENTS["/uslugi/ipoteka-dlya-molodoy-semi/"] += (
    "актуальные требования",
)
TEXT_REQUIREMENTS["/uslugi/ipoteka-dlya-pensionerov/"] += (
    "решение, срок и условия определяет банк",
)

UNCONFIRMED_ETAGI_TEXT = (
    "сопровождение включено в комиссию компании",
    "отдельно клиентом не оплачивается",
    "без доплаты при сделке через",
    "отдельной оплаты за ипотечное сопровождение нет",
)

FORBIDDEN_TEXT = {
    "/": UNCONFIRMED_ETAGI_TEXT,
    "/uslugi/": UNCONFIRMED_ETAGI_TEXT
    + (
        "клиентам «этажи» ипотечное сопровождение бесплатно",
        "ипотечное сопровождение бесплатно",
    ),
    "/konsultaciya/": UNCONFIRMED_ETAGI_TEXT,
    "/kontakty/": UNCONFIRMED_ETAGI_TEXT,
    "/o-brokere/": UNCONFIRMED_ETAGI_TEXT,
    "/stoimost/": UNCONFIRMED_ETAGI_TEXT,
    "/etagi/": (
        '"price":"0"',
        "0 ₽ для клиентов",
        "ипотечное сопровождение бесплатно",
    )
    + UNCONFIRMED_ETAGI_TEXT,
    "/faq/": UNCONFIRMED_ETAGI_TEXT,
    "/kak-prohodit-rabota/": ("полное сопровождение сделки включено",) + UNCONFIRMED_ETAGI_TEXT,
    "/uslugi/podbor-ipoteki/": ("ипотечное сопровождение для клиента бесплатно",),
    "/uslugi/refinansirovanie-ipoteki/": (
        "ипотечное сопровождение бесплатно",
        "включено в комиссию компании",
    ),
    "/uslugi/ipoteka-bez-pervonachalnogo-vznosa/": (
        "гарантированная ипотека без первоначального взноса",
        "обойдем требования банка",
    ),
    "/uslugi/ipoteka-s-plohoy-kreditnoy-istoriey/": (
        "исправим кредитную историю",
        "гарантируем одобрение",
    ),
    "/uslugi/ipoteka-pri-prodazhe-starogo-zhilya/": (
        "полное сопровождение двух сделок входит",
    ),
}

for service_url in STANDARD_SERVICE_URLS:
    FORBIDDEN_TEXT[service_url] = FORBIDDEN_TEXT.get(service_url, ()) + (
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


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


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
        normalized_html = normalize_text(raw_html)

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
            if normalize_text(required_text) not in normalized_html:
                annotation(
                    f"На странице {page_url} отсутствует обязательная формулировка: {required_text}",
                    html_file,
                )
                errors += 1

        for forbidden_text in FORBIDDEN_TEXT.get(page_url, ()):
            if normalize_text(forbidden_text) in normalized_html:
                annotation(
                    f"На странице {page_url} найдена двусмысленная формулировка: {forbidden_text}",
                    html_file,
                )
                errors += 1

    if errors:
        print(f"Аудит конверсионных страниц завершен с ошибками: {errors}")
        return 1

    print(
        "Аудит конверсионных страниц успешно завершен: "
        f"проверено {len(PAGE_REQUIREMENTS)} страниц, "
        f"каталог содержит обязательные ссылки на {len(ALL_SERVICE_URLS)} услуг"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
