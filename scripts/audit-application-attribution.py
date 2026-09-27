#!/usr/bin/env python3
"""Проверяет атрибуцию переходов в онлайн-заявку после сборки сайта."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


APPLICATION_PATH = "/online-zayavka/"
PLACEMENT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


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


def annotation(page: Path, message: str) -> None:
    print(f"::error file={page.as_posix()}::{message}")


def page_url(site_dir: Path, page: Path) -> str:
    relative = page.relative_to(site_dir)
    if relative.as_posix() == "index.html":
        return "/"
    if relative.name == "index.html":
        parent = relative.parent.as_posix().strip("/")
        return f"/{parent}/" if parent else "/"
    return "/" + relative.as_posix()


def one_nonempty(params: dict[str, list[str]], name: str) -> str:
    values = params.get(name, [])
    if len(values) != 1:
        return ""
    return values[0].strip()


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        print(f"::error::Каталог сборки не найден: {site_dir}")
        return 1

    failures = 0
    neutral_links = 0
    source_prefill_links = 0
    explicit_links = 0
    pages_with_explicit_links = 0

    for page in sorted(site_dir.rglob("*.html")):
        try:
            raw_html = page.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            annotation(page, f"Не удалось прочитать HTML: {exc}")
            failures += 1
            continue

        parser = LinkParser()
        parser.feed(raw_html)
        current_url = page_url(site_dir, page)
        placements: set[str] = set()
        page_has_explicit = False

        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.path.rstrip("/") + "/" != APPLICATION_PATH:
                continue

            if not parsed.query:
                neutral_links += 1
                continue

            params = parse_qs(parsed.query, keep_blank_values=True)
            source = one_nonempty(params, "source")
            if not source:
                annotation(page, f"Query-маршрут онлайн-заявки должен передавать один непустой source: {link}")
                failures += 1
            elif source != current_url:
                annotation(
                    page,
                    f"source не соответствует текущей странице: ожидалось {current_url}, получено {source}",
                )
                failures += 1

            scenario = one_nonempty(params, "scenario")
            placement = one_nonempty(params, "placement")
            has_scenario = "scenario" in params
            has_placement = "placement" in params

            # Поддерживаемый prefill-маршрут может передавать только source
            # и служебные параметры (journey/stage/city/contact). Сценарий
            # в этом случае определяется формой по source slug.
            if not has_scenario and not has_placement:
                source_prefill_links += 1
                continue

            # Явная аналитическая атрибуция всегда должна быть полной парой:
            # scenario + placement. Половинчатая разметка создаёт ложные данные.
            if not scenario:
                annotation(page, f"CTA с явной атрибуцией должен передавать один непустой scenario: {link}")
                failures += 1
            if not placement:
                annotation(page, f"CTA с явной атрибуцией должен передавать один непустой placement: {link}")
                failures += 1
            if not scenario or not placement:
                continue

            explicit_links += 1
            page_has_explicit = True

            if not PLACEMENT_RE.fullmatch(placement):
                annotation(
                    page,
                    f"Некорректный placement {placement!r}; допустимы lowercase a-z, цифры, _ и -",
                )
                failures += 1
            if placement in placements:
                annotation(page, f"Дублируется placement внутри страницы: {placement}")
                failures += 1
            placements.add(placement)

        if page_has_explicit:
            pages_with_explicit_links += 1

    if failures:
        print(
            "Аудит атрибуции CTA завершён с ошибками: "
            f"{failures}; явных CTA {explicit_links}, source-prefill {source_prefill_links}, "
            f"нейтральных ссылок {neutral_links}"
        )
        return 1

    print(
        "Атрибуция CTA согласована: "
        f"страниц с явными CTA {pages_with_explicit_links}, явных CTA {explicit_links}, "
        f"source-prefill {source_prefill_links}, нейтральных ссылок {neutral_links}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
