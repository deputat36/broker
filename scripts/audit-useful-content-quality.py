#!/usr/bin/env python3
"""Проверяет глубину, структуру и перелинковку статей раздела «Полезно»."""

from __future__ import annotations

import json
import re
import statistics
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "useful-content-quality.json"
SOURCE_DIR = ROOT / "polezno"
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-‑–—][A-Za-zА-Яа-яЁё0-9]+)*")
SITE_HOST = "sterlikova-ipoteka.ru"
CTA_PATHS = ("/konsultaciya/", "/online-zayavka/")
GENERIC_PATHS = {"/", "/polezno/", "/policy/", "/personal-data-consent/"}


def error(message: str, path: Path | None = None) -> None:
    prefix = "::error"
    if path is not None:
        try:
            display = path.relative_to(ROOT).as_posix()
        except ValueError:
            display = path.as_posix()
        prefix += f" file={display}"
    print(f"{prefix}::{message}")


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
        return value[1:-1]
    return value


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = scalar(value)
    return {}


def load_config() -> tuple[dict[str, dict[str, int]], set[str], int]:
    failures = 0
    if not CONFIG_PATH.is_file():
        error("Не найден конфиг качества материалов", CONFIG_PATH)
        return {}, set(), 1
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"Некорректный JSON: {exc}", CONFIG_PATH)
        return {}, set(), 1

    profiles: dict[str, dict[str, int]] = {}
    required = {
        "min_words",
        "min_internal_links",
        "min_unique_internal_links",
        "min_section_headings",
    }
    for name in ("article", "hub"):
        value = data.get(name)
        if not isinstance(value, dict) or set(value) != required:
            error(f"Профиль {name} должен содержать только: {', '.join(sorted(required))}", CONFIG_PATH)
            failures += 1
            continue
        normalized: dict[str, int] = {}
        for key in required:
            number = value.get(key)
            if not isinstance(number, int) or number < 1:
                error(f"{name}.{key} должен быть положительным целым числом", CONFIG_PATH)
                failures += 1
            else:
                normalized[key] = number
        profiles[name] = normalized

    raw_hubs = data.get("hubs")
    hubs: set[str] = set()
    if not isinstance(raw_hubs, list):
        error("Поле hubs должно быть массивом", CONFIG_PATH)
        failures += 1
    else:
        for value in raw_hubs:
            if not isinstance(value, str) or not value.startswith("/polezno/") or not value.endswith("/"):
                error(f"Некорректный hub permalink: {value!r}", CONFIG_PATH)
                failures += 1
                continue
            if value in hubs:
                error(f"Повторяющийся hub permalink: {value}", CONFIG_PATH)
                failures += 1
            hubs.add(value)
    return profiles, hubs, failures


class MainMetricsParser(HTMLParser):
    def __init__(self, current_path: str) -> None:
        super().__init__(convert_charrefs=True)
        self.current_path = current_path
        self.main_depth = 0
        self.skip_depth = 0
        self.breadcrumb_depth = 0
        self.text_parts: list[str] = []
        self.internal_links: list[str] = []
        self.topic_links: list[str] = []
        self.cta_found = False
        self.h1_count = 0
        self.section_headings = 0

    @property
    def in_main(self) -> bool:
        return self.main_depth > 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        classes = set(attributes.get("class", "").split())
        if tag == "main":
            self.main_depth += 1
            return
        if not self.in_main:
            return
        if tag in {"script", "style", "noscript", "template"}:
            self.skip_depth += 1
        if tag == "nav" and "breadcrumbs" in classes:
            self.breadcrumb_depth += 1
        if self.skip_depth:
            return
        if tag == "h1":
            self.h1_count += 1
        elif tag in {"h2", "h3"}:
            self.section_headings += 1
        elif tag == "a":
            self._record_link(attributes.get("href", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "main" and self.main_depth:
            self.main_depth -= 1
            return
        if not self.in_main:
            return
        if tag in {"script", "style", "noscript", "template"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "nav" and self.breadcrumb_depth:
            self.breadcrumb_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_main and not self.skip_depth and data.strip():
            self.text_parts.append(data)

    def _record_link(self, href: str) -> None:
        href = href.strip()
        if not href or self.breadcrumb_depth:
            return
        if href.startswith("tel:") or href.startswith(CTA_PATHS):
            self.cta_found = True
        parsed = urlsplit(href)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return
        if parsed.netloc and parsed.netloc != SITE_HOST:
            return
        path = parsed.path or "/"
        if not path.startswith("/"):
            return
        if path.startswith("/assets/") or path == "/404.html":
            return
        self.internal_links.append(path)
        if path not in GENERIC_PATHS and path != self.current_path:
            self.topic_links.append(path)

    def metrics(self) -> dict[str, int | bool]:
        words = WORD_RE.findall(" ".join(self.text_parts))
        return {
            "words": len(words),
            "internal_links": len(self.internal_links),
            "unique_internal_links": len(set(self.topic_links)),
            "section_headings": self.section_headings,
            "h1_count": self.h1_count,
            "cta_found": self.cta_found,
        }


def built_path(site_dir: Path, permalink: str) -> Path:
    relative = permalink.strip("/")
    return site_dir / relative / "index.html"


def source_articles(hubs: set[str]) -> tuple[list[tuple[Path, str, str]], int]:
    failures = 0
    articles: list[tuple[Path, str, str]] = []
    seen: set[str] = set()
    for path in sorted(SOURCE_DIR.glob("*.md")):
        meta = front_matter(path)
        permalink = meta.get("permalink", "")
        if meta.get("og_type") != "article" or not permalink.startswith("/polezno/"):
            continue
        if permalink == "/polezno/":
            continue
        if not permalink.endswith("/"):
            error("Permalink материала должен завершаться слешем", path)
            failures += 1
            continue
        if permalink in seen:
            error(f"Повторяющийся permalink: {permalink}", path)
            failures += 1
            continue
        seen.add(permalink)
        profile = "hub" if permalink in hubs else "article"
        articles.append((path, permalink, profile))

    unknown_hubs = hubs - seen
    for permalink in sorted(unknown_hubs):
        error(f"Hub отсутствует среди опубликованных материалов: {permalink}", CONFIG_PATH)
        failures += 1
    return articles, failures


def check_article(
    source: Path,
    permalink: str,
    profile_name: str,
    profile: dict[str, int],
    site_dir: Path,
) -> tuple[int, dict[str, int | bool]]:
    page = built_path(site_dir, permalink)
    if not page.is_file():
        error(f"Не найдена собранная страница {permalink}", source)
        return 1, {}
    parser = MainMetricsParser(permalink)
    parser.feed(page.read_text(encoding="utf-8"))
    metrics = parser.metrics()
    failures = 0

    checks = (
        ("words", "слов"),
        ("internal_links", "внутренних ссылок"),
        ("unique_internal_links", "уникальных тематических ссылок"),
        ("section_headings", "заголовков H2/H3"),
    )
    for key, label in checks:
        minimum = profile[f"min_{key}"]
        actual = int(metrics[key])
        if actual < minimum:
            error(
                f"{permalink}: найдено {actual} {label}, требуется не менее {minimum} ({profile_name})",
                source,
            )
            failures += 1
    if metrics["h1_count"] != 1:
        error(f"{permalink}: ожидается ровно один H1, найдено {metrics['h1_count']}", source)
        failures += 1
    if not metrics["cta_found"]:
        error(f"{permalink}: не найден CTA на консультацию, онлайн-заявку или телефон", source)
        failures += 1
    return failures, metrics


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        error("Каталог собранного сайта не найден", site_dir)
        return 1

    profiles, hubs, failures = load_config()
    articles, article_failures = source_articles(hubs)
    failures += article_failures
    if not articles:
        error("Не найдено ни одного материала для проверки", SOURCE_DIR)
        return 1

    word_counts: list[int] = []
    link_counts: list[int] = []
    hub_count = 0
    for source, permalink, profile_name in articles:
        profile = profiles.get(profile_name)
        if not profile:
            continue
        if profile_name == "hub":
            hub_count += 1
        article_errors, metrics = check_article(source, permalink, profile_name, profile, site_dir)
        failures += article_errors
        if metrics:
            word_counts.append(int(metrics["words"]))
            link_counts.append(int(metrics["internal_links"]))

    if failures:
        print(f"Аудит качества материалов завершён с ошибками: {failures}")
        return 1

    print(
        "Аудит качества материалов успешно завершён: "
        f"материалов {len(articles)}, хабов {hub_count}, "
        f"слов min/median {min(word_counts)}/{int(statistics.median(word_counts))}, "
        f"внутренних ссылок min/median {min(link_counts)}/{int(statistics.median(link_counts))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
