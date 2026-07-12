#!/usr/bin/env python3
"""Проверяет SEO, CTA, Schema.org и навигацию региональных посадочных страниц."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

BASE_URL = "https://sterlikova-ipoteka.ru"
PHONE_LINK = "tel:+79030250807"
VK_PROFILE = "https://vk.com/tatyanasterlikova"
BROKER_NAME = "Татьяна Стерликова"
BROKER_PHONE = "+79030250807"

REGIONS = {
    "/geo/borisoglebsk/": "борисоглебск",
    "/geo/gribanovskiy/": "грибановск",
    "/geo/povorino/": "поворино",
}
MIN_CHILD_PAGES = 10


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


class RegionalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.h1_count = 0
        self.description = ""
        self.canonical = ""
        self.links: list[str] = []
        self.max_controls = 0
        self.ld_json_blocks: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._in_json = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1_count += 1
            self._in_h1 = True
        elif tag == "meta" and (attrs_map.get("name") or "").lower() == "description":
            self.description = attrs_map.get("content") or ""
        elif tag == "link":
            rel = (attrs_map.get("rel") or "").lower().split()
            if "canonical" in rel:
                self.canonical = attrs_map.get("href") or ""
        elif tag == "a":
            href = attrs_map.get("href")
            if href:
                self.links.append(href)
        elif tag == "script" and (attrs_map.get("type") or "").lower() == "application/ld+json":
            self._in_json = True
            self._json_parts = []

        if "data-copy-phone" in attrs_map:
            self.max_controls += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "script" and self._in_json:
            self._in_json = False
            self.ld_json_blocks.append("".join(self._json_parts).strip())
            self._json_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)
        if self._in_json:
            self._json_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    @property
    def h1(self) -> str:
        return " ".join("".join(self.h1_parts).split())


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


def normalize_internal_links(page_url: str, links: list[str]) -> set[str]:
    targets: set[str] = set()
    for href in links:
        parsed = urlparse(urljoin(BASE_URL + page_url, href))
        if parsed.hostname in {"sterlikova-ipoteka.ru", "www.sterlikova-ipoteka.ru"}:
            targets.add(parsed.path or "/")
    return targets


def iter_json_objects(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_json_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_json_objects(nested)


def has_type(obj: dict[str, Any], expected: str) -> bool:
    raw_type = obj.get("@type")
    if isinstance(raw_type, str):
        return raw_type == expected
    return isinstance(raw_type, list) and expected in raw_type


def validate_service_schema(page_url: str, parser: RegionalParser, html_file: Path) -> int:
    errors = 0
    services: list[dict[str, Any]] = []
    for block_number, block in enumerate(parser.ld_json_blocks, start=1):
        if not block:
            continue
        try:
            payload = json.loads(block)
        except json.JSONDecodeError as error:
            annotation(f"Некорректный JSON-LD блок #{block_number}: {error.msg}", html_file)
            errors += 1
            continue
        services.extend(obj for obj in iter_json_objects(payload) if has_type(obj, "Service"))

    if not services:
        annotation("Не найден Schema.org объект с @type Service", html_file)
        return errors + 1

    service = services[0]
    if not str(service.get("name") or "").strip():
        annotation("У Service отсутствует name", html_file)
        errors += 1
    if not str(service.get("serviceType") or "").strip():
        annotation("У Service отсутствует serviceType", html_file)
        errors += 1
    if not service.get("areaServed"):
        annotation("У Service отсутствует areaServed", html_file)
        errors += 1

    provider = service.get("provider")
    if not isinstance(provider, dict):
        annotation("У Service отсутствует provider", html_file)
        errors += 1
    else:
        if provider.get("name") != BROKER_NAME:
            annotation(f"Provider должен быть {BROKER_NAME}", html_file)
            errors += 1
        if provider.get("telephone") != BROKER_PHONE:
            annotation(f"Телефон provider должен быть {BROKER_PHONE}", html_file)
            errors += 1

    expected_url = BASE_URL + page_url
    if service.get("url") != expected_url:
        annotation(
            f"URL Service должен быть {expected_url}, получено: {service.get('url') or 'отсутствует'}",
            html_file,
        )
        errors += 1
    return errors


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

    regional_urls: list[tuple[str, str, str]] = []
    errors = 0
    for hub_url, location_token in REGIONS.items():
        child_urls = sorted(
            path for path in sitemap_paths if path.startswith(hub_url) and path != hub_url
        )
        if len(child_urls) < MIN_CHILD_PAGES:
            annotation(
                f"В региональном кластере {hub_url} найдено только {len(child_urls)} страниц; "
                f"ожидалось не меньше {MIN_CHILD_PAGES}"
            )
            errors += 1
        regional_urls.append((hub_url, "/geo/", location_token))
        regional_urls.extend((child_url, hub_url, location_token) for child_url in child_urls)

    unique_values: dict[str, defaultdict[str, list[str]]] = {
        "title": defaultdict(list),
        "description": defaultdict(list),
        "H1": defaultdict(list),
    }

    for page_url, required_parent, location_token in regional_urls:
        html_file = url_to_file(site_dir, page_url)
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

        parser = RegionalParser()
        parser.feed(raw_html)
        fields = {
            "title": parser.title,
            "description": parser.description.strip(),
            "H1": parser.h1,
        }

        if parser.h1_count != 1:
            annotation(f"Ожидался один H1, найдено: {parser.h1_count}", html_file)
            errors += 1

        for label, value in fields.items():
            if not value:
                annotation(f"Отсутствует {label}", html_file)
                errors += 1
                continue
            normalized = normalize_text(value)
            unique_values[label][normalized].append(page_url)
            if location_token not in normalized:
                annotation(f"В {label} отсутствует региональный маркер: {location_token}", html_file)
                errors += 1

        expected_canonical = BASE_URL + page_url
        if parser.canonical != expected_canonical:
            annotation(
                f"Canonical должен быть {expected_canonical}, получено: {parser.canonical or 'отсутствует'}",
                html_file,
            )
            errors += 1

        links = set(parser.links)
        internal_links = normalize_internal_links(page_url, parser.links)
        if PHONE_LINK not in links:
            annotation(f"Отсутствует телефонный CTA {PHONE_LINK}", html_file)
            errors += 1
        if VK_PROFILE not in links:
            annotation("Отсутствует ссылка ВКонтакте", html_file)
            errors += 1
        if parser.max_controls == 0:
            annotation("Отсутствует CTA для MAX", html_file)
            errors += 1
        if required_parent not in internal_links:
            annotation(f"Отсутствует обратная ссылка на родительский хаб: {required_parent}", html_file)
            errors += 1

        errors += validate_service_schema(page_url, parser, html_file)

    for label, grouped in unique_values.items():
        for urls in grouped.values():
            if len(urls) > 1:
                annotation(f"Дублирующийся {label} у региональных страниц: {', '.join(sorted(urls))}")
                errors += 1

    if errors:
        print(f"Аудит региональных страниц завершен с ошибками: {errors}")
        return 1

    child_count = len(regional_urls) - len(REGIONS)
    print(
        "Аудит региональных страниц успешно завершен: "
        f"проверено {len(REGIONS)} хаба и {child_count} посадочных страниц"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
