#!/usr/bin/env python3
"""Проверяет безопасную передачу расчёта из калькулятора в онлайн-заявку."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
CALCULATOR_SOURCE = REPO_ROOT / "assets/js/mortgage-calculator.js"
PREFILL_SOURCE = REPO_ROOT / "assets/js/calculator-application-prefill.js"
APPLICATION_SOURCE = REPO_ROOT / "online-zayavka.md"
MAIN_SOURCE = REPO_ROOT / "assets/js/main.js"
PREFILL_ASSET = "/assets/js/calculator-application-prefill.js"
PARAMETERS = ("calc_amount", "calc_down", "calc_rate", "calc_years")


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        if values.get("src"):
            self.scripts.append(values["src"])


def fail(path: Path, message: str) -> None:
    print(f"::error file={path.as_posix()}::{message}")


def require_markers(path: Path, text: str, markers: tuple[str, ...]) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            fail(path, f"Отсутствует обязательный маркер: {marker}")
            errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_calculator = site_dir / "assets/js/mortgage-calculator.js"
    built_prefill = site_dir / PREFILL_ASSET.lstrip("/")
    built_main = site_dir / "assets/js/main.js"
    application_page = site_dir / "online-zayavka/index.html"
    errors = 0

    required_files = (
        CALCULATOR_SOURCE,
        PREFILL_SOURCE,
        APPLICATION_SOURCE,
        MAIN_SOURCE,
        built_calculator,
        built_prefill,
        built_main,
        application_page,
    )
    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            fail(path, "Обязательный файл отсутствует или пуст")
            errors += 1
    if errors:
        return 1

    calculator_source = CALCULATOR_SOURCE.read_text(encoding="utf-8")
    prefill_source = PREFILL_SOURCE.read_text(encoding="utf-8")
    application_source = APPLICATION_SOURCE.read_text(encoding="utf-8")
    main_source = MAIN_SOURCE.read_text(encoding="utf-8")
    built_calculator_text = built_calculator.read_text(encoding="utf-8-sig", errors="ignore")
    built_prefill_text = built_prefill.read_text(encoding="utf-8-sig", errors="ignore")
    built_main_text = built_main.read_text(encoding="utf-8-sig", errors="ignore")

    calculator_markers = (
        "const APPLICATION_PATH = '/online-zayavka/'",
        "data-calc-application-action",
        "data-calc-application-link",
        "Передать расчёт в заявку",
        "calculator_application_click",
        "new URLSearchParams",
        *PARAMETERS,
    )
    prefill_markers = (
        "readBoundedNumber",
        "calc_amount: { min: 1, max: 1000000000 }",
        "calc_down: { min: 0, max: 1000000000 }",
        "calc_rate: { min: 0, max: 100 }",
        "calc_years: { min: 1, max: 30 }",
        "downCandidate < amount",
        "setEmptyField('object_price'",
        "setEmptyField('down_payment'",
        "Расчёт из ипотечного калькулятора",
        "data-application-more",
        "moreDetails.open = true",
        "calculatorPrefill",
        "history.replaceState",
        "online_application_calculator_prefill",
        *PARAMETERS,
    )

    errors += require_markers(CALCULATOR_SOURCE, calculator_source, calculator_markers)
    errors += require_markers(built_calculator, built_calculator_text, calculator_markers)
    errors += require_markers(PREFILL_SOURCE, prefill_source, prefill_markers)
    errors += require_markers(built_prefill, built_prefill_text, prefill_markers)

    script_marker = "{{ '/assets/js/calculator-application-prefill.js' | relative_url }}"
    if application_source.count(script_marker) != 1:
        fail(APPLICATION_SOURCE, "Модуль предзаполнения должен подключаться ровно один раз")
        errors += 1

    for forbidden in ("localStorage", "sessionStorage", "fetch(", "sendBeacon"):
        if forbidden in prefill_source or forbidden in built_prefill_text:
            fail(PREFILL_SOURCE, f"Модуль предзаполнения не должен использовать {forbidden}")
            errors += 1

    for forbidden in ("client_name", "phone", "city", "preferred_contact", "bank_history"):
        if forbidden in calculator_source or forbidden in prefill_source:
            fail(PREFILL_SOURCE, f"Расчётный handoff затрагивает персональное поле: {forbidden}")
            errors += 1

    for parameter in PARAMETERS:
        if parameter in main_source or parameter in built_main_text:
            fail(MAIN_SOURCE, f"Расчётный параметр не должен попадать в глобальную атрибуцию: {parameter}")
            errors += 1

    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        fail(site_dir, "Собранные HTML-страницы не найдены")
        return 1

    pages_with_prefill: list[str] = []
    for page in html_files:
        parser = ScriptParser()
        parser.feed(page.read_text(encoding="utf-8-sig", errors="ignore"))
        count = sum(urlsplit(src).path == PREFILL_ASSET for src in parser.scripts)
        if count:
            pages_with_prefill.append(page.relative_to(site_dir).as_posix())
        expected = 1 if page == application_page else 0
        if count != expected:
            fail(page, f"Модуль предзаполнения подключён {count} раз, ожидалось {expected}")
            errors += 1

    if pages_with_prefill != ["online-zayavka/index.html"]:
        fail(site_dir, f"Неверный набор страниц с модулем предзаполнения: {pages_with_prefill}")
        errors += 1

    if errors:
        print(f"Аудит передачи расчёта в заявку завершён с ошибками: {errors}")
        return 1

    print(
        "Передача расчёта в заявку подтверждена: "
        f"{len(html_files)} HTML-страниц, модуль только на /online-zayavka/, "
        "четыре ограниченных неперсональных параметра"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
