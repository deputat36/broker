#!/usr/bin/env python3
"""Проверяет онлайн-заявку, атрибуцию источника и дистанционный маршрут из любого города."""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

BASE_URL = "https://sterlikova-ipoteka.ru"
APPLICATION_URL = "/online-zayavka/"
PHONE_LINK = "tel:+79030250807"
VK_PROFILE = "https://vk.com/tatyanasterlikova"

KEY_PAGE_REQUIREMENTS = {
    "/": ("любого города",),
    "/konsultaciya/": ("любого города",),
    "/kontakty/": ("любого города",),
}

REQUIRED_FIELDS = {
    "source_page",
    "client_name",
    "phone",
    "city",
    "preferred_contact",
    "scenario",
    "object_type",
    "object_price",
    "down_payment",
    "income_type",
    "bank_history",
    "comment",
    "consent",
}

REQUIRED_FORM_MARKERS = {
    "data-online-application",
    "data-application-status",
    "data-application-result",
    "data-application-output",
    "data-application-share",
    "data-application-sms",
    "data-application-copy",
    "data-application-vk",
}

REQUIRED_LINKS = {
    "/policy/",
    "/konsultaciya/",
    "/stoimost/",
    "/etagi/",
    "/geo/",
    PHONE_LINK,
    VK_PROFILE,
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.description = ""
        self.canonical = ""
        self.links: set[str] = set()
        self.contextual_application_links = 0
        self.styles: set[str] = set()
        self.scripts: set[str] = set()
        self.fields: set[str] = set()
        self.required_fields: set[str] = set()
        self.form_count = 0
        self.form_actions: list[str] = []
        self.form_methods: list[str] = []
        self.markers: set[str] = set()
        self.text_parts: list[str] = []
        self.ld_json_blocks: list[str] = []
        self._in_title = False
        self._in_json = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value for key, value in attrs}
        for key in attrs_map:
            if key.startswith("data-"):
                self.markers.add(key)

        if tag == "title":
            self._in_title = True
        elif tag == "meta" and (attrs_map.get("name") or "").lower() == "description":
            self.description = attrs_map.get("content") or ""
        elif tag == "link":
            href = attrs_map.get("href") or ""
            rel = (attrs_map.get("rel") or "").lower().split()
            if "canonical" in rel:
                self.canonical = href
            if "stylesheet" in rel and href:
                self.styles.add(urlparse(href).path or href)
        elif tag == "script":
            src = attrs_map.get("src")
            if src:
                self.scripts.add(urlparse(src).path or src)
            if (attrs_map.get("type") or "").lower() == "application/ld+json":
                self._in_json = True
                self._json_parts = []
        elif tag == "a":
            href = attrs_map.get("href")
            if href:
                parsed = urlparse(href)
                if parsed.scheme in {"http", "https"}:
                    self.links.add(href)
                elif parsed.scheme:
                    self.links.add(href)
                else:
                    path = parsed.path or "/"
                    self.links.add(path)
                    if path == APPLICATION_URL and "source=" in parsed.query:
                        self.contextual_application_links += 1
        elif tag == "form":
            self.form_count += 1
            self.form_actions.append(attrs_map.get("action") or "")
            self.form_methods.append((attrs_map.get("method") or "").lower())
        elif tag in {"input", "select", "textarea"}:
            name = attrs_map.get("name")
            if name:
                self.fields.add(name)
                if "required" in attrs_map:
                    self.required_fields.add(name)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json:
            self._in_json = False
            self.ld_json_blocks.append("".join(self._json_parts).strip())
            self._json_parts = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json:
            self._json_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).casefold().replace("ё", "е").split())


def annotation(message: str, file: Path | None = None) -> None:
    prefix = "::error"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def url_to_file(site_dir: Path, page_url: str) -> Path:
    if page_url == "/":
        return site_dir / "index.html"
    return site_dir / page_url.lstrip("/") / "index.html"


def load_page(site_dir: Path, page_url: str) -> tuple[Path, PageParser] | None:
    html_file = url_to_file(site_dir, page_url)
    if not html_file.is_file():
        annotation(f"Не найдена HTML-страница: {page_url}", html_file)
        return None
    try:
        raw_html = html_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        annotation(f"Не удалось прочитать HTML: {error}", html_file)
        return None
    parser = PageParser()
    parser.feed(raw_html)
    return html_file, parser


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


def area_contains_russia(value: Any) -> bool:
    if isinstance(value, str):
        return "росси" in value.casefold()
    if isinstance(value, dict):
        return area_contains_russia(value.get("name"))
    if isinstance(value, list):
        return any(area_contains_russia(item) for item in value)
    return False


def validate_schema(parser: PageParser, html_file: Path) -> int:
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

    matching = [service for service in services if service.get("url") == BASE_URL + APPLICATION_URL]
    if not matching:
        annotation("Не найден Service JSON-LD с URL онлайн-заявки", html_file)
        return errors + 1

    service = matching[0]
    provider = service.get("provider")
    if not isinstance(provider, dict) or provider.get("name") != "Татьяна Стерликова":
        annotation("В Service онлайн-заявки отсутствует корректный provider", html_file)
        errors += 1
    if not area_contains_russia(service.get("areaServed")):
        annotation("В Service онлайн-заявки areaServed не содержит Россию", html_file)
        errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        annotation(f"Каталог сборки не найден: {site_dir}")
        return 1

    errors = 0
    sitemap_file = site_dir / "sitemap.xml"
    try:
        root = ElementTree.parse(sitemap_file).getroot()
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_paths = {
            urlparse(node.text.strip()).path or "/"
            for node in root.findall("sm:url/sm:loc", namespace)
            if node.text
        }
    except (ElementTree.ParseError, OSError) as error:
        annotation(f"Не удалось разобрать sitemap.xml: {error}", sitemap_file)
        return 1

    if APPLICATION_URL not in sitemap_paths:
        annotation(f"Онлайн-заявка отсутствует в sitemap: {APPLICATION_URL}", sitemap_file)
        errors += 1

    loaded_application = load_page(site_dir, APPLICATION_URL)
    if loaded_application is None:
        return errors + 1
    application_file, application = loaded_application

    if "онлайн" not in application.title.casefold() or "онлайн" not in application.description.casefold():
        annotation("Title и description онлайн-заявки должны явно описывать онлайн-формат", application_file)
        errors += 1
    if application.canonical != BASE_URL + APPLICATION_URL:
        annotation(
            f"Canonical онлайн-заявки должен быть {BASE_URL + APPLICATION_URL}, получено: {application.canonical or 'отсутствует'}",
            application_file,
        )
        errors += 1

    required_texts = (
        "из любого города",
        "форма не отправляет данные на сервер автоматически",
        "решение принимает банк",
    )
    for required_text in required_texts:
        normalized = required_text.casefold().replace("ё", "е")
        if normalized not in application.text:
            annotation(f"На онлайн-заявке отсутствует обязательный текст: {required_text}", application_file)
            errors += 1

    if application.form_count != 1:
        annotation(f"Ожидалась одна форма онлайн-заявки, найдено: {application.form_count}", application_file)
        errors += 1
    if any(action.strip() for action in application.form_actions):
        annotation("Статическая форма не должна иметь неподтвержденный серверный action", application_file)
        errors += 1
    if any(method.strip() for method in application.form_methods):
        annotation("Статическая форма не должна заявлять серверный method", application_file)
        errors += 1

    missing_fields = REQUIRED_FIELDS - application.fields
    if missing_fields:
        annotation(f"В форме отсутствуют поля: {', '.join(sorted(missing_fields))}", application_file)
        errors += 1
    for required_field in {"client_name", "phone", "city", "scenario", "consent"} - application.required_fields:
        annotation(f"Поле должно быть обязательным: {required_field}", application_file)
        errors += 1

    missing_markers = REQUIRED_FORM_MARKERS - application.markers
    if missing_markers:
        annotation(f"В форме отсутствуют JS-маркеры: {', '.join(sorted(missing_markers))}", application_file)
        errors += 1

    missing_links = REQUIRED_LINKS - application.links
    if missing_links:
        annotation(f"На онлайн-заявке отсутствуют ссылки: {', '.join(sorted(missing_links))}", application_file)
        errors += 1

    expected_style = "/assets/css/online-application.css"
    expected_script = "/assets/js/online-application.js"
    if expected_style not in application.styles:
        annotation(f"Не подключены стили онлайн-заявки: {expected_style}", application_file)
        errors += 1
    if expected_script not in application.scripts:
        annotation(f"Не подключен скрипт онлайн-заявки: {expected_script}", application_file)
        errors += 1

    for asset_path in (expected_style, expected_script):
        asset_file = site_dir / asset_path.lstrip("/")
        if not asset_file.is_file():
            annotation(f"Не найден собранный ресурс онлайн-заявки: {asset_path}", asset_file)
            errors += 1

    script_file = site_dir / expected_script.lstrip("/")
    if script_file.is_file():
        script_text = script_file.read_text(encoding="utf-8", errors="ignore")
        for marker in (
            "SCENARIO_BY_SLUG",
            "CITY_BY_PREFIX",
            "source_page",
            "Источник обращения",
            "online_application_prefill",
            "online_application_prepare",
            "online_application_copy",
            "online_application_share",
            "online_application_sms",
            "sms:+79030250807",
        ):
            if marker not in script_text:
                annotation(f"В скрипте онлайн-заявки отсутствует маркер: {marker}", script_file)
                errors += 1

    main_script = site_dir / "assets/js/main.js"
    if main_script.is_file():
        main_script_text = main_script.read_text(encoding="utf-8", errors="ignore")
        for marker in ("window.sendGoal = sendGoal", "online_application_click"):
            if marker not in main_script_text:
                annotation(f"В основном скрипте отсутствует маркер: {marker}", main_script)
                errors += 1

    errors += validate_schema(application, application_file)

    for page_url, required_texts_for_page in KEY_PAGE_REQUIREMENTS.items():
        loaded_page = load_page(site_dir, page_url)
        if loaded_page is None:
            errors += 1
            continue
        html_file, parser = loaded_page
        if APPLICATION_URL not in parser.links:
            annotation(f"Ключевая страница не ведет на онлайн-заявку: {page_url}", html_file)
            errors += 1
        for required_text in required_texts_for_page:
            normalized = required_text.casefold().replace("ё", "е")
            if normalized not in parser.text:
                annotation(f"На странице {page_url} отсутствует дистанционная формулировка: {required_text}", html_file)
                errors += 1

    contextual_urls = sorted(
        page_url
        for page_url in sitemap_paths
        if (page_url.startswith("/uslugi/") and page_url != "/uslugi/")
        or (page_url.startswith("/geo/") and page_url != "/geo/")
    )
    for page_url in contextual_urls:
        loaded_page = load_page(site_dir, page_url)
        if loaded_page is None:
            errors += 1
            continue
        html_file, parser = loaded_page
        if parser.contextual_application_links < 1:
            annotation(f"Страница не передает source в онлайн-заявку: {page_url}", html_file)
            errors += 1
        if "подайте онлайн-заявку из любого города" not in parser.text:
            annotation(f"На странице отсутствует контекстный CTA онлайн-заявки: {page_url}", html_file)
            errors += 1

    if errors:
        print(f"Аудит онлайн-заявки завершен с ошибками: {errors}")
        return 1

    print(
        "Аудит онлайн-заявки успешно завершен: "
        f"форма, атрибуция, способы отправки и контекстные входы подтверждены; страниц {len(contextual_urls)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())