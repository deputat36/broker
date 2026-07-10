#!/usr/bin/env python3
"""Проверяет собранный Jekyll-сайт без сторонних зависимостей."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from xml.etree import ElementTree

BASE_URL = "https://sterlikova-ipoteka.ru"
ALLOWED_HOSTS = {"sterlikova-ipoteka.ru", "www.sterlikova-ipoteka.ru"}
IGNORED_SCHEMES = {"tel", "mailto", "javascript", "data"}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.description: str | None = None
        self.robots = ""
        self.canonical: str | None = None
        self.h1_count = 0
        self.links: list[str] = []
        self.images: list[tuple[str, str | None]] = []
        self.ld_json_blocks: list[str] = []
        self.in_ld_json = False
        self.ld_json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value for key, value in attrs}
        tag = tag.lower()

        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta":
            name = (attrs_map.get("name") or "").lower()
            if name == "description":
                self.description = attrs_map.get("content")
            elif name == "robots":
                self.robots = attrs_map.get("content") or ""
        elif tag == "link":
            rel = (attrs_map.get("rel") or "").lower().split()
            if "canonical" in rel:
                self.canonical = attrs_map.get("href")
        elif tag == "a":
            href = attrs_map.get("href")
            if href:
                self.links.append(href)
        elif tag == "img":
            src = attrs_map.get("src")
            if src:
                self.images.append((src, attrs_map.get("alt")))
        elif tag == "script" and (attrs_map.get("type") or "").lower() == "application/ld+json":
            self.in_ld_json = True
            self.ld_json_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_ld_json:
            self.in_ld_json = False
            self.ld_json_blocks.append("".join(self.ld_json_parts).strip())
            self.ld_json_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_ld_json:
            self.ld_json_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def annotation(level: str, message: str, file: Path | None = None) -> None:
    prefix = f"::{level}"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def output_path_to_url(site_dir: Path, html_file: Path) -> str:
    relative = html_file.relative_to(site_dir).as_posix()
    if relative == "index.html":
        return "/"
    if relative.endswith("/index.html"):
        return "/" + relative[: -len("index.html")]
    return "/" + relative


def resolve_site_path(site_dir: Path, url_path: str) -> Path | None:
    clean_path = unquote(url_path or "/").split("?", 1)[0]
    if clean_path == "/":
        candidate = site_dir / "index.html"
        return candidate if candidate.is_file() else None

    relative = clean_path.lstrip("/")
    direct = site_dir / relative
    if direct.is_file():
        return direct

    if clean_path.endswith("/"):
        index_file = direct / "index.html"
        return index_file if index_file.is_file() else None

    index_file = direct / "index.html"
    if index_file.is_file():
        return index_file

    return None


def normalize_internal_url(current_url: str, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith("#") or href.startswith("//"):
        return None

    parsed_original = urlparse(href)
    if parsed_original.scheme.lower() in IGNORED_SCHEMES:
        return None

    absolute = urljoin(BASE_URL + current_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.hostname not in ALLOWED_HOSTS:
        return None

    return parsed.path or "/"


def load_sitemap_paths(sitemap_file: Path) -> set[str]:
    root = ElementTree.parse(sitemap_file).getroot()
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    paths: set[str] = set()
    for loc in root.findall("sm:url/sm:loc", namespace):
        if not loc.text:
            continue
        parsed = urlparse(loc.text.strip())
        paths.add(parsed.path or "/")
    return paths


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        annotation("error", f"Каталог сборки не найден: {site_dir}")
        return 1

    sitemap_file = site_dir / "sitemap.xml"
    try:
        sitemap_paths = load_sitemap_paths(sitemap_file)
    except (ElementTree.ParseError, OSError) as error:
        annotation("error", f"Не удалось разобрать sitemap.xml: {error}", sitemap_file)
        return 1

    html_files = sorted(site_dir.rglob("*.html"))
    parsed_pages: dict[str, tuple[Path, PageParser]] = {}
    errors = 0
    warnings = 0

    for html_file in html_files:
        parser = PageParser()
        try:
            parser.feed(html_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            annotation("error", f"Не удалось прочитать HTML: {error}", html_file)
            errors += 1
            continue
        page_url = output_path_to_url(site_dir, html_file)
        parsed_pages[page_url] = (html_file, parser)

    inbound_links: Counter[str] = Counter()
    titles: defaultdict[str, list[str]] = defaultdict(list)
    descriptions: defaultdict[str, list[str]] = defaultdict(list)

    for page_url, (html_file, parser) in parsed_pages.items():
        relative_file = html_file.relative_to(site_dir)
        is_noindex = "noindex" in parser.robots.lower()
        is_sitemap_page = page_url in sitemap_paths

        if is_sitemap_page:
            if not parser.title:
                annotation("error", "Отсутствует title", relative_file)
                errors += 1
            else:
                titles[parser.title].append(page_url)

            if not (parser.description or "").strip():
                annotation("error", "Отсутствует meta description", relative_file)
                errors += 1
            else:
                descriptions[(parser.description or "").strip()].append(page_url)

            if parser.h1_count != 1:
                annotation("error", f"Ожидался один H1, найдено: {parser.h1_count}", relative_file)
                errors += 1

            expected_canonical = BASE_URL + page_url
            if parser.canonical != expected_canonical:
                annotation(
                    "error",
                    f"Canonical должен быть {expected_canonical}, получено: {parser.canonical or 'отсутствует'}",
                    relative_file,
                )
                errors += 1

            if is_noindex:
                annotation("error", "Страница из sitemap помечена noindex", relative_file)
                errors += 1
        elif not is_noindex and page_url != "/404.html":
            annotation("warning", "Индексируемая HTML-страница отсутствует в sitemap", relative_file)
            warnings += 1

        for block_number, block in enumerate(parser.ld_json_blocks, start=1):
            if not block:
                annotation("error", f"Пустой JSON-LD блок #{block_number}", relative_file)
                errors += 1
                continue
            try:
                json.loads(block)
            except json.JSONDecodeError as error:
                annotation(
                    "error",
                    f"Некорректный JSON-LD блок #{block_number}: {error.msg} на позиции {error.pos}",
                    relative_file,
                )
                errors += 1

        for src, alt in parser.images:
            if alt is None:
                annotation("error", f"У изображения отсутствует атрибут alt: {src}", relative_file)
                errors += 1

            target_path = normalize_internal_url(page_url, src)
            if target_path and resolve_site_path(site_dir, target_path) is None:
                annotation("error", f"Не найден файл изображения: {src}", relative_file)
                errors += 1

        for href in parser.links:
            target_path = normalize_internal_url(page_url, href)
            if target_path is None:
                continue

            if resolve_site_path(site_dir, target_path) is None:
                annotation("error", f"Битая внутренняя ссылка: {href}", relative_file)
                errors += 1
                continue

            if target_path in sitemap_paths and target_path != page_url:
                inbound_links[target_path] += 1

    for sitemap_path in sorted(sitemap_paths):
        if resolve_site_path(site_dir, sitemap_path) is None:
            annotation("error", f"URL из sitemap не имеет выходного файла: {sitemap_path}", sitemap_file.relative_to(site_dir))
            errors += 1
            continue
        if sitemap_path != "/" and inbound_links[sitemap_path] == 0:
            annotation("warning", f"Возможная страница-сирота без входящих ссылок: {sitemap_path}")
            warnings += 1

    for title, urls in sorted(titles.items()):
        if len(urls) > 1:
            annotation("warning", f"Дублирующийся title у страниц: {', '.join(urls)}")
            warnings += 1

    for description, urls in sorted(descriptions.items()):
        if len(urls) > 1:
            annotation("warning", f"Дублирующийся description у страниц: {', '.join(urls)}")
            warnings += 1

    if errors:
        print(f"Аудит сборки завершен с ошибками: {errors}; предупреждений: {warnings}")
        return 1

    print(
        "Аудит сборки успешно завершен: "
        f"HTML-страниц {len(parsed_pages)}, URL в sitemap {len(sitemap_paths)}, предупреждений {warnings}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
