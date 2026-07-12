#!/usr/bin/env python3
"""Выявляет полные и потенциальные дубли региональных страниц одного сценария."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

REGION_PREFIXES = (
    "/geo/borisoglebsk/",
    "/geo/gribanovskiy/",
    "/geo/povorino/",
)
REGION_TOKEN_PREFIXES = (
    "борисоглебск",
    "грибановск",
    "поворин",
)
MIN_WORDS = 100
SHINGLE_SIZE = 5
MAX_JACCARD = 0.82
MAX_SEQUENCE = 0.90
WARN_JACCARD = 0.58
WARN_SEQUENCE = 0.78
SKIPPED_TAGS = {"nav", "script", "style", "noscript"}


def annotation(level: str, message: str, file: Path | None = None) -> None:
    prefix = f"::{level}"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def load_sitemap_paths(sitemap_file: Path) -> set[str]:
    root = ElementTree.parse(sitemap_file).getroot()
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {
        urlparse(node.text.strip()).path or "/"
        for node in root.findall("sm:url/sm:loc", namespace)
        if node.text
    }


def url_to_file(site_dir: Path, page_url: str) -> Path:
    return site_dir / page_url.lstrip("/") / "index.html"


class MainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.found_main = False
        self.skip_stack: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value for key, value in attrs}
        if tag == "main" and attrs_map.get("id") == "main-content":
            self.in_main = True
            self.found_main = True
            return
        if self.in_main and tag in SKIPPED_TAGS:
            self.skip_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.in_main:
            return
        if tag == "main":
            self.in_main = False
            self.skip_stack.clear()
            return
        if self.skip_stack and tag == self.skip_stack[-1]:
            self.skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_main and not self.skip_stack:
            self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def normalized_words(raw_text: str) -> list[str]:
    words = re.findall(r"[a-zа-я0-9]+", raw_text.casefold().replace("ё", "е"))
    result: list[str] = []
    for word in words:
        if len(word) < 3:
            continue
        if word in {"татьяна", "стерликова"}:
            continue
        if any(word.startswith(prefix) for prefix in REGION_TOKEN_PREFIXES):
            continue
        result.append(word)
    return result


def shingles(words: list[str]) -> set[tuple[str, ...]]:
    if len(words) < SHINGLE_SIZE:
        return set()
    return {
        tuple(words[index : index + SHINGLE_SIZE])
        for index in range(len(words) - SHINGLE_SIZE + 1)
    }


def jaccard(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def scenario_slug(page_url: str) -> str:
    return page_url.rstrip("/").rsplit("/", 1)[-1]


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

    grouped_urls: defaultdict[str, list[str]] = defaultdict(list)
    for page_url in sitemap_paths:
        for prefix in REGION_PREFIXES:
            if page_url.startswith(prefix) and page_url != prefix:
                grouped_urls[scenario_slug(page_url)].append(page_url)
                break

    parsed: dict[str, tuple[Path, list[str], set[tuple[str, ...]]]] = {}
    errors = 0
    warnings = 0
    compared_pairs = 0

    for slug, urls in sorted(grouped_urls.items()):
        if len(urls) < 2:
            continue

        for page_url in sorted(urls):
            html_file = url_to_file(site_dir, page_url)
            if not html_file.is_file():
                annotation("error", f"Не найдена региональная страница: {page_url}", html_file)
                errors += 1
                continue
            try:
                raw_html = html_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                annotation("error", f"Не удалось прочитать HTML: {error}", html_file)
                errors += 1
                continue

            parser = MainTextParser()
            parser.feed(raw_html)
            if not parser.found_main:
                annotation("error", "Не найден контейнер main#main-content", html_file)
                errors += 1
                continue

            words = normalized_words(parser.text)
            if len(words) < MIN_WORDS:
                annotation(
                    "error",
                    f"На региональной странице слишком мало содержательного текста: {len(words)} слов",
                    html_file,
                )
                errors += 1
            parsed[page_url] = (html_file, words, shingles(words))

        available_urls = [page_url for page_url in sorted(urls) if page_url in parsed]
        for index, left_url in enumerate(available_urls):
            for right_url in available_urls[index + 1 :]:
                compared_pairs += 1
                left_file, left_words, left_shingles = parsed[left_url]
                _, right_words, right_shingles = parsed[right_url]
                jaccard_score = jaccard(left_shingles, right_shingles)
                sequence_score = SequenceMatcher(
                    None,
                    " ".join(left_words),
                    " ".join(right_words),
                    autojunk=False,
                ).ratio()
                score_text = (
                    f"{slug}: {left_url} и {right_url}; "
                    f"Jaccard={jaccard_score:.2f}, Sequence={sequence_score:.2f}"
                )
                if jaccard_score >= MAX_JACCARD and sequence_score >= MAX_SEQUENCE:
                    annotation("error", f"Почти полный дубль регионального сценария {score_text}", left_file)
                    errors += 1
                elif jaccard_score >= WARN_JACCARD or sequence_score >= WARN_SEQUENCE:
                    annotation("warning", f"Высокая близость регионального сценария {score_text}", left_file)
                    warnings += 1

    if errors:
        print(
            "Аудит смысловой уникальности региональных страниц завершен с ошибками: "
            f"{errors}; предупреждений: {warnings}"
        )
        return 1

    print(
        "Аудит смысловой уникальности региональных страниц успешно завершен: "
        f"сценариев {sum(1 for urls in grouped_urls.values() if len(urls) >= 2)}, "
        f"сравнено пар {compared_pairs}, предупреждений {warnings}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
