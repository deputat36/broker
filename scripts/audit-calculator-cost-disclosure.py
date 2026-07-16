#!/usr/bin/env python3
"""Проверяет раскрытие расходов, которые не входят в расчёт калькулятора."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = "kalkulyator-ipoteki.md"
BUILT_PATH = "kalkulyator-ipoteki/index.html"
MARKER = "data-calculator-cost-disclosure"
DETAILS_PATH = "/polezno/rashody-pri-oformlenii-ipoteki/"
DETAILS_LABEL = "Разобрать расходы"
SOURCE_DIRS = ("uslugi", "geo", "polezno")
REQUIRED_MEANINGS = (
    "считает только платёж по сумме кредита",
    "страхование",
    "оценку",
    "регистрацию",
    "безопасные расчёты",
    "банковские",
    "профессиональные услуги",
    "не равен полной стоимости кредита",
    "зависит от банка, объекта и схемы сделки",
)
SPACE_RE = re.compile(r"\s+")
DIGIT_RE = re.compile(r"\d")


class DisclosureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.disclosures: list[dict[str, object]] = []
        self.current: dict[str, object] | None = None
        self.depth = 0
        self.current_link: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()

        if self.current is None:
            if tag == "section" and MARKER in values:
                self.current = {"parts": [], "links": []}
                self.depth = 1
            return

        self.depth += 1
        if tag == "a":
            self.current_link = {"href": values.get("href", ""), "parts": []}

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        parts = self.current["parts"]
        assert isinstance(parts, list)
        parts.append(data)
        if self.current_link is not None:
            link_parts = self.current_link["parts"]
            assert isinstance(link_parts, list)
            link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.current is None:
            return

        if tag == "a" and self.current_link is not None:
            links = self.current["links"]
            assert isinstance(links, list)
            parts = self.current_link["parts"]
            assert isinstance(parts, list)
            links.append({
                "href": str(self.current_link["href"]),
                "text": normalize(" ".join(parts)),
            })
            self.current_link = None

        self.depth -= 1
        if self.depth == 0:
            self.disclosures.append(self.current)
            self.current = None
            self.current_link = None


def normalize(value: str) -> str:
    return SPACE_RE.sub(" ", value).strip()


def fail(path: Path, message: str) -> None:
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = path.as_posix()
    print(f"::error file={display}::{message}")


def parse(path: Path) -> DisclosureParser:
    parser = DisclosureParser()
    parser.feed(path.read_text(encoding="utf-8-sig", errors="ignore"))
    return parser


def validate_disclosure(path: Path, *, built: bool) -> int:
    parser = parse(path)
    if len(parser.disclosures) != 1:
        fail(path, f"Ожидался один блок расходов калькулятора, найдено: {len(parser.disclosures)}")
        return 1

    errors = 0
    disclosure = parser.disclosures[0]
    parts = disclosure["parts"]
    links = disclosure["links"]
    assert isinstance(parts, list)
    assert isinstance(links, list)
    text = normalize(" ".join(parts))
    folded = text.casefold()

    for meaning in REQUIRED_MEANINGS:
        if meaning.casefold() not in folded:
            fail(path, f"Блок не содержит обязательный смысл: {meaning}")
            errors += 1

    if DIGIT_RE.search(text):
        fail(path, "В блоке расходов не должно быть неподтверждённых чисел или ставок")
        errors += 1

    if len(links) != 1:
        fail(path, f"Ожидалась одна ссылка на подробный материал, найдено: {len(links)}")
        errors += 1
    else:
        link = links[0]
        href = str(link["href"])
        label = str(link["text"])
        if label != DETAILS_LABEL:
            fail(path, f"Неверная подпись ссылки: {label or 'пусто'}")
            errors += 1
        if built:
            if urlsplit(href).path != DETAILS_PATH:
                fail(path, f"Ссылка ведёт не на материал о расходах: {href or 'пусто'}")
                errors += 1
        elif DETAILS_PATH not in href:
            fail(path, "Исходная ссылка не содержит путь к материалу о расходах")
            errors += 1

    return errors


def public_source_files() -> list[Path]:
    files = list(ROOT.glob("*.md"))
    for directory in SOURCE_DIRS:
        files.extend((ROOT / directory).rglob("*.md"))
    return sorted(set(files))


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    source = ROOT / SOURCE_PATH
    built = site_dir / BUILT_PATH
    errors = 0

    if not source.is_file():
        fail(source, "Исходная страница калькулятора отсутствует")
        errors += 1
    if not built.is_file():
        fail(built, "Собранная страница калькулятора отсутствует")
        errors += 1
    if errors:
        return 1

    source_with_marker = {
        path.relative_to(ROOT).as_posix()
        for path in public_source_files()
        if MARKER in path.read_text(encoding="utf-8", errors="ignore")
    }
    if source_with_marker != {SOURCE_PATH}:
        fail(ROOT, f"Неверный набор исходных страниц с раскрытием расходов: {sorted(source_with_marker)}")
        errors += 1

    built_with_marker = {
        path.relative_to(site_dir).as_posix()
        for path in site_dir.rglob("*.html")
        if MARKER in path.read_text(encoding="utf-8-sig", errors="ignore")
    }
    if built_with_marker != {BUILT_PATH}:
        fail(site_dir, f"Неверный набор собранных страниц с раскрытием расходов: {sorted(built_with_marker)}")
        errors += 1

    errors += validate_disclosure(source, built=False)
    errors += validate_disclosure(built, built=True)

    if errors:
        print(f"Аудит расходов вне калькулятора завершён с ошибками: {errors}")
        return 1

    print(
        "Раскрытие расходов калькулятора подтверждено: один исходный и один собранный блок, "
        "без ставок и сумм, со ссылкой на подробный материал"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
