#!/usr/bin/env python3
"""Проверяет, что калькулятор не выдаёт ставку по умолчанию за банковское предложение."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("uslugi", "geo", "polezno")
EXPECTED_SOURCE = {"index.md", "kalkulyator-ipoteki.md"}
EXPECTED_BUILT = {"index.html", "kalkulyator-ipoteki/index.html"}
EXPECTED_LABEL = "Предполагаемая ставка, % годовых"
EXPECTED_PLACEHOLDER = "Введите ставку"
HINT_PARTS = (
    "из предложения банка или свой сценарий",
    "не подставляет актуальную ставку банка",
)
SPACE_RE = re.compile(r"\s+")
DIGIT_RE = re.compile(r"\d")


@dataclass
class CalculatorForm:
    rate_inputs: list[dict[str, str]] = field(default_factory=list)
    rate_label: list[str] = field(default_factory=list)
    text_by_id: dict[str, list[str]] = field(default_factory=dict)


class CalculatorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[CalculatorForm] = []
        self.current: CalculatorForm | None = None
        self.form_depth = 0
        self.capture_label = False
        self.capture_id: str | None = None
        self.capture_id_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()

        if tag == "form":
            if self.current is not None:
                self.form_depth += 1
            elif "data-mortgage-calc" in values:
                self.current = CalculatorForm()
                self.form_depth = 1

        if self.current is None:
            return

        if tag == "input" and values.get("name") == "rate":
            self.current.rate_inputs.append(values)

        if tag == "label" and values.get("for") == "rate":
            self.capture_label = True

        element_id = values.get("id", "").strip()
        if element_id:
            self.capture_id = element_id
            self.capture_id_tag = tag
            self.current.text_by_id.setdefault(element_id, [])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        if self.capture_label:
            self.current.rate_label.append(data)
        if self.capture_id:
            self.current.text_by_id.setdefault(self.capture_id, []).append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.current is None:
            return

        if tag == "label":
            self.capture_label = False

        if self.capture_id_tag == tag:
            self.capture_id = None
            self.capture_id_tag = None

        if tag == "form":
            self.form_depth -= 1
            if self.form_depth == 0:
                self.forms.append(self.current)
                self.current = None
                self.capture_label = False
                self.capture_id = None
                self.capture_id_tag = None


def normalize(value: str) -> str:
    return SPACE_RE.sub(" ", value).strip()


def fail(path: Path, message: str) -> None:
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = path.as_posix()
    print(f"::error file={display}::{message}")


def parse(path: Path) -> CalculatorParser:
    parser = CalculatorParser()
    parser.feed(path.read_text(encoding="utf-8-sig", errors="ignore"))
    return parser


def validate_page(path: Path) -> int:
    parser = parse(path)
    errors = 0

    if len(parser.forms) != 1:
        fail(path, f"Ожидалась одна форма калькулятора, найдено {len(parser.forms)}")
        return 1

    form = parser.forms[0]
    if len(form.rate_inputs) != 1:
        fail(path, f"Ожидалось одно поле rate, найдено {len(form.rate_inputs)}")
        return 1

    rate = form.rate_inputs[0]
    value = rate.get("value", "").strip()
    if value:
        fail(path, f"Поле ставки не должно иметь значение по умолчанию: {value}")
        errors += 1

    placeholder = normalize(rate.get("placeholder", ""))
    if placeholder != EXPECTED_PLACEHOLDER or DIGIT_RE.search(placeholder):
        fail(path, f"Неверный placeholder ставки: {placeholder or 'пусто'}")
        errors += 1

    label = normalize(" ".join(form.rate_label))
    if label != EXPECTED_LABEL:
        fail(path, f"Поле ставки должно называться «{EXPECTED_LABEL}», найдено: {label}")
        errors += 1

    described_ids = rate.get("aria-describedby", "").split()
    hint = normalize(
        " ".join(
            " ".join(form.text_by_id.get(element_id, []))
            for element_id in described_ids
        )
    ).casefold()
    for part in HINT_PARTS:
        if part.casefold() not in hint:
            fail(path, f"Подсказка ставки не содержит обязательный смысл: {part}")
            errors += 1

    return errors


def public_source_files() -> list[Path]:
    files = list(ROOT.glob("*.md"))
    for directory in SOURCE_DIRS:
        files.extend((ROOT / directory).rglob("*.md"))
    return sorted(set(files))


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        fail(site_dir, "Каталог собранного сайта не найден")
        return 1

    errors = 0
    source_files = public_source_files()
    source_with_calc = {
        path.relative_to(ROOT).as_posix()
        for path in source_files
        if "data-mortgage-calc" in path.read_text(encoding="utf-8", errors="ignore")
    }
    if source_with_calc != EXPECTED_SOURCE:
        fail(ROOT, f"Неверный набор исходных страниц с калькулятором: {sorted(source_with_calc)}")
        errors += 1

    for relative in sorted(EXPECTED_SOURCE):
        path = ROOT / relative
        if not path.is_file():
            fail(path, "Исходная страница калькулятора отсутствует")
            errors += 1
            continue
        errors += validate_page(path)

    html_files = sorted(site_dir.rglob("*.html"))
    built_with_calc = {
        path.relative_to(site_dir).as_posix()
        for path in html_files
        if "data-mortgage-calc" in path.read_text(encoding="utf-8-sig", errors="ignore")
    }
    if built_with_calc != EXPECTED_BUILT:
        fail(site_dir, f"Неверный набор собранных страниц с калькулятором: {sorted(built_with_calc)}")
        errors += 1

    for relative in sorted(EXPECTED_BUILT):
        path = site_dir / relative
        if not path.is_file():
            fail(path, "Собранная страница калькулятора отсутствует")
            errors += 1
            continue
        errors += validate_page(path)

    if errors:
        print(f"Аудит прозрачности ставки калькулятора завершён с ошибками: {errors}")
        return 1

    print(
        "Прозрачность ставки калькулятора подтверждена: "
        "2 исходные и 2 собранные страницы, числовых ставок по умолчанию 0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
