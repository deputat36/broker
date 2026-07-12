#!/usr/bin/env python3
"""Строго проверяет SEO-метаданные и Schema.org у 18 страниц услуг."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

BASE_URL = "https://sterlikova-ipoteka.ru"
BROKER_NAME = "Татьяна Стерликова"
BROKER_PHONE = "+79030250807"

SERVICE_URLS = (
    "/uslugi/podbor-ipoteki/",
    "/uslugi/ipoteka-na-novostroyku/",
    "/uslugi/ipoteka-na-vtorichnoe-zhile/",
    "/uslugi/ipoteka-na-stroitelstvo-doma/",
    "/uslugi/refinansirovanie-ipoteki/",
    "/uslugi/semeynaya-ipoteka/",
    "/uslugi/ipoteka-dlya-molodoy-semi/",
    "/uslugi/ipoteka-dlya-pensionerov/",
    "/uslugi/materinskiy-kapital/",
    "/uslugi/otkazali-v-ipoteke/",
    "/uslugi/slozhnaya-ipoteka/",
    "/uslugi/ipoteka-bez-oficialnogo-dohoda/",
    "/uslugi/ipoteka-bez-pervonachalnogo-vznosa/",
    "/uslugi/ipoteka-dlya-ip-samozanyatyh/",
    "/uslugi/ipoteka-s-plohoy-kreditnoy-istoriey/",
    "/uslugi/ipoteka-na-dom/",
    "/uslugi/ipoteka-s-sozaemshchikom/",
    "/uslugi/ipoteka-pri-prodazhe-starogo-zhilya/",
)

FORBIDDEN_PHRASES = (
    "ипотечное сопровождение бесплатно",
    "сопровождение по ипотеке бесплатно",
    "ипотечное сопровождение для клиента бесплатно",
    "бесплатное сопровождение клиентов компании",
    "0 ₽ для клиентов",
)


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


class SeoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.h1_count = 0
        self.description = ""
        self.canonical = ""
        self.ld_json_blocks: list[str] = []
        self._capture_title = False
        self._capture_h1 = False
        self._capture_json = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self._capture_title = True
        elif tag == "h1":
            self.h1_count += 1
            self._capture_h1 = True
        elif tag == "meta" and (attrs_map.get("name") or "").lower() == "description":
            self.description = attrs_map.get("content") or ""
        elif tag == "link":
            rel = (attrs_map.get("rel") or "").lower().split()
            if "canonical" in rel:
                self.canonical = attrs_map.get("href") or ""
        elif tag == "script" and (attrs_map.get("type") or "").lower() == "application/ld+json":
            self._capture_json = True
            self._json_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._capture_title = False
        elif tag == "h1":
            self._capture_h1 = False
        elif tag == "script" and self._capture_json:
            self._capture_json = False
            self.ld_json_blocks.append("".join(self._json_parts).strip())
            self._json_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title_parts.append(data)
        if self._capture_h1:
            self.h1_parts.append(data)
        if self._capture_json:
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


def validate_service_schema(
    *,
    page_url: str,
    parser: SeoParser,
    html_file: Path,
) -> tuple[int, str]:
    errors = 0
    service_objects: list[dict[str, Any]] = []

    for block_number, block in enumerate(parser.ld_json_blocks, start=1):
        if not block:
            continue
        try:
            payload = json.loads(block)
        except json.JSONDecodeError as error:
            annotation(
                f"Некорректный JSON-LD блок #{block_number}: {error.msg}",
                html_file,
            )
            errors += 1
            continue
        service_objects.extend(
            obj for obj in iter_json_objects(payload) if has_type(obj, "Service")
        )

    if not service_objects:
        annotation("Не найден Schema.org объект с @type Service", html_file)
        return errors + 1, ""

    service = service_objects[0]
    service_name = str(service.get("name") or "").strip()
    if not service_name:
        annotation("У Service отсутствует name", html_file)
        errors += 1

    service_type = service.get("serviceType")
    if not isinstance(service_type, str) or not service_type.strip():
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

    schema_url = service.get("url")
    expected_url = BASE_URL + page_url
    if schema_url and schema_url != expected_url:
        annotation(
            f"URL Service должен быть {expected_url}, получено: {schema_url}",
            html_file,
        )
        errors += 1

    return errors, service_name


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        annotation(f"Каталог сборки не найден: {site_dir}")
        return 1

    errors = 0
    values: dict[str, defaultdict[str, list[str]]] = {
        "title": defaultdict(list),
        "description": defaultdict(list),
        "h1": defaultdict(list),
        "schema name": defaultdict(list),
    }

    for page_url in SERVICE_URLS:
        html_file = url_to_file(site_dir, page_url)
        if not html_file.is_file():
            annotation(f"Не найдена страница услуги: {page_url}", html_file)
            errors += 1
            continue

        try:
            raw_html = html_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            annotation(f"Не удалось прочитать HTML: {error}", html_file)
            errors += 1
            continue

        parser = SeoParser()
        parser.feed(raw_html)

        if parser.h1_count != 1:
            annotation(f"Ожидался один H1, найдено: {parser.h1_count}", html_file)
            errors += 1

        fields = {
            "title": parser.title,
            "description": parser.description.strip(),
            "h1": parser.h1,
        }
        for label, value in fields.items():
            if not value:
                annotation(f"Отсутствует {label}", html_file)
                errors += 1
            else:
                values[label][normalize_text(value)].append(page_url)

        expected_canonical = BASE_URL + page_url
        if parser.canonical != expected_canonical:
            annotation(
                f"Canonical должен быть {expected_canonical}, получено: {parser.canonical or 'отсутствует'}",
                html_file,
            )
            errors += 1

        schema_errors, schema_name = validate_service_schema(
            page_url=page_url,
            parser=parser,
            html_file=html_file,
        )
        errors += schema_errors
        if schema_name:
            values["schema name"][normalize_text(schema_name)].append(page_url)

    for label, grouped_values in values.items():
        for urls in grouped_values.values():
            if len(urls) > 1:
                annotation(
                    f"Дублирующийся {label} у страниц услуг: {', '.join(sorted(urls))}"
                )
                errors += 1

    normalized_site = normalize_text(
        "\n".join(
            html_file.read_text(encoding="utf-8", errors="ignore")
            for html_file in sorted(site_dir.rglob("*.html"))
        )
    )
    for phrase in FORBIDDEN_PHRASES:
        if normalize_text(phrase) in normalized_site:
            annotation(f"На собранном сайте найдена устаревшая формулировка: {phrase}")
            errors += 1

    if errors:
        print(f"SEO-аудит услуг завершен с ошибками: {errors}")
        return 1

    print(
        "SEO-аудит услуг успешно завершен: "
        f"проверено {len(SERVICE_URLS)} страниц, "
        "title/description/H1/Schema.org уникальны"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
