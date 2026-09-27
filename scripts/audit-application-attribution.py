#!/usr/bin/env python3
"""Проверяет атрибуцию контекстных переходов в онлайн-заявку."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


APPLICATION_PATH = "/online-zayavka/"
REQUIRED_PARAMS = ("source", "scenario", "placement")
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


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        print(f"::error::Каталог сборки не найден: {site_dir}")
        return 1

    failures = 0
    contextual_links = 0
    neutral_links = 0
    pages_with_contextual_links = 0

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
        page_has_context = False

        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.path.rstrip("/") + "/" != APPLICATION_PATH:
                continue

            # Обычные навигационные ссылки на анкету могут оставаться без атрибуции.
            if not parsed.query:
                neutral_links += 1
                continue

            contextual_links += 1
            page_has_context = True
            params = parse_qs(parsed.query, keep_blank_values=True)

            for name in REQUIRED_PARAMS:
                values = params.get(name, [])
                if len(values) != 1 or not values[0].strip():
                    annotation(
                        page,
                        f"Контекстный CTA должен передавать один непустой параметр {name}: {link}",
                    )
                    failures += 1

            source_values = params.get("source", [])
            if len(source_values) == 1 and source_values[0].strip():
                source = source_values[0].strip()
                if source != current_url:
                    annotation(
                        page,
                        f"source не соответствует текущей странице: ожидалось {current_url}, получено {source}",
                    )
                    failures += 1

            placement_values = params.get("placement", [])
            if len(placement_values) == 1 and placement_values[0].strip():
                placement = placement_values[0].strip()
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

        if page_has_context:
            pages_with_contextual_links += 1

    if failures:
        print(
            "Аудит атрибуции CTA завершён с ошибками: "
            f"{failures}; контекстных ссылок {contextual_links}, "
            f"нейтральных ссылок {neutral_links}"
        )
        return 1

    print(
        "Атрибуция CTA согласована: "
        f"страниц с контекстными ссылками {pages_with_contextual_links}, "
        f"контекстных ссылок {contextual_links}, нейтральных ссылок {neutral_links}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
