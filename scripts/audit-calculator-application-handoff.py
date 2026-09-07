#!/usr/bin/env python3
"""Проверяет безопасную передачу расчёта из калькулятора в онлайн-заявку."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_SOURCE = REPO_ROOT / "index.md"
CALCULATOR_SOURCE = REPO_ROOT / "assets/js/mortgage-calculator.js"
BOOTSTRAP_SOURCE = REPO_ROOT / "assets/js/calculator-application-prefill.js"
RUNTIME_SOURCE = REPO_ROOT / "assets/js/calculator-application-prefill-runtime.js"
APPLICATION_SOURCE = REPO_ROOT / "online-zayavka.md"
MAIN_SOURCE = REPO_ROOT / "assets/js/main.js"
BOOTSTRAP_ASSET = "/assets/js/calculator-application-prefill.js"
RUNTIME_ASSET = "/assets/js/calculator-application-prefill-runtime.js"
PARAMETERS = ("calc_amount", "calc_down", "calc_rate", "calc_years")
LEGACY_DIRECT_LABEL = "Передать расчёт в заявке"
DIRECT_LABEL = "Открыть онлайн-заявку"
TRANSFER_LABEL = "Перенести этот расчёт в заявку"
SOURCE_DIRECT_RE = re.compile(
    r'<a\s+class="btn btn-light"\s+href="\{\{\s*\'/online-zayavka/\'\s*\|\s*relative_url\s*\}\}'
    r'(?P<query>\?[^\"]*)?">Открыть онлайн-заявку</a>'
)


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


class DirectApplicationLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current: dict[str, str] | None = None
        self.current_text: list[str] = []
        self.links: list[tuple[str, set[str], str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self.current = {name.lower(): value or "" for name, value in attrs}
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self.current is None:
            return
        label = " ".join("".join(self.current_text).split())
        href = self.current.get("href", "")
        classes = set(self.current.get("class", "").split())
        self.links.append((href, classes, label))
        self.current = None
        self.current_text = []


def fail(path: Path, message: str) -> None:
    print(f"::error file={path.as_posix()}::{message}")


def require_markers(path: Path, text: str, markers: tuple[str, ...]) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            fail(path, f"Отсутствует обязательный маркер: {marker}")
            errors += 1
    return errors


def validate_direct_source_link(source: str) -> int:
    matches = list(SOURCE_DIRECT_RE.finditer(source))
    if len(matches) != 1:
        fail(
            INDEX_SOURCE,
            "На главной должна быть одна честно подписанная прямая ссылка «Открыть онлайн-заявку»",
        )
        return 1

    href_fragment = matches[0].group(0)
    for parameter in PARAMETERS:
        if parameter in href_fragment:
            fail(INDEX_SOURCE, f"Прямая ссылка не должна переносить параметр калькулятора {parameter}")
            return 1
    return 0


def validate_direct_built_link(html_text: str, path: Path) -> int:
    parser = DirectApplicationLinkParser()
    parser.feed(html_text)
    candidates = [
        (href, classes)
        for href, classes, label in parser.links
        if label == DIRECT_LABEL and "btn-light" in classes
    ]
    if len(candidates) != 1:
        fail(path, "В собранной главной должна быть одна прямая ссылка «Открыть онлайн-заявку»")
        return 1

    href, _classes = candidates[0]
    parsed = urlsplit(href)
    if parsed.path != "/online-zayavka/":
        fail(path, f"Прямая ссылка ведёт не на /online-zayavka/: {href}")
        return 1

    query = parse_qs(parsed.query, keep_blank_values=True)
    leaked = [parameter for parameter in PARAMETERS if parameter in query]
    if leaked:
        fail(path, f"Прямая ссылка ошибочно переносит параметры калькулятора: {leaked}")
        return 1
    return 0


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_index = site_dir / "index.html"
    built_calculator = site_dir / "assets/js/mortgage-calculator.js"
    built_bootstrap = site_dir / BOOTSTRAP_ASSET.lstrip("/")
    built_runtime = site_dir / RUNTIME_ASSET.lstrip("/")
    built_main = site_dir / "assets/js/main.js"
    application_page = site_dir / "online-zayavka/index.html"
    errors = 0

    required_files = (
        INDEX_SOURCE,
        CALCULATOR_SOURCE,
        BOOTSTRAP_SOURCE,
        RUNTIME_SOURCE,
        APPLICATION_SOURCE,
        MAIN_SOURCE,
        built_index,
        built_calculator,
        built_bootstrap,
        built_runtime,
        built_main,
        application_page,
    )
    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            fail(path, "Обязательный файл отсутствует или пуст")
            errors += 1
    if errors:
        return 1

    index_source = INDEX_SOURCE.read_text(encoding="utf-8")
    calculator_source = CALCULATOR_SOURCE.read_text(encoding="utf-8")
    bootstrap_source = BOOTSTRAP_SOURCE.read_text(encoding="utf-8")
    runtime_source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    application_source = APPLICATION_SOURCE.read_text(encoding="utf-8")
    main_source = MAIN_SOURCE.read_text(encoding="utf-8")
    built_index_text = built_index.read_text(encoding="utf-8-sig", errors="ignore")
    built_calculator_text = built_calculator.read_text(encoding="utf-8-sig", errors="ignore")
    built_bootstrap_text = built_bootstrap.read_text(encoding="utf-8-sig", errors="ignore")
    built_runtime_text = built_runtime.read_text(encoding="utf-8-sig", errors="ignore")
    built_main_text = built_main.read_text(encoding="utf-8-sig", errors="ignore")

    calculator_markers = (
        "const APPLICATION_PATH = '/online-zayavka/'",
        "data-calc-application-action",
        "data-calc-application-link",
        TRANSFER_LABEL,
        "calculator_application_click",
        "new URLSearchParams",
        *PARAMETERS,
    )
    bootstrap_markers = (
        "new URLSearchParams(window.location.search)",
        "calculatorParams",
        "params.has(name)",
        "document.currentScript",
        "calculator-application-prefill-runtime.js",
        "document.createElement('script')",
        "runtime.async = false",
        "calculatorPrefillRuntime",
        *PARAMETERS,
    )
    runtime_markers = (
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
    errors += require_markers(BOOTSTRAP_SOURCE, bootstrap_source, bootstrap_markers)
    errors += require_markers(built_bootstrap, built_bootstrap_text, bootstrap_markers)
    errors += require_markers(RUNTIME_SOURCE, runtime_source, runtime_markers)
    errors += require_markers(built_runtime, built_runtime_text, runtime_markers)

    errors += validate_direct_source_link(index_source)
    errors += validate_direct_built_link(built_index_text, built_index)

    for path, text in (
        (INDEX_SOURCE, index_source),
        (built_index, built_index_text),
        (CALCULATOR_SOURCE, calculator_source),
        (built_calculator, built_calculator_text),
    ):
        if LEGACY_DIRECT_LABEL in text:
            fail(path, f"Найдена устаревшая вводящая в заблуждение подпись: {LEGACY_DIRECT_LABEL}")
            errors += 1

    for path, text in ((CALCULATOR_SOURCE, calculator_source), (built_calculator, built_calculator_text)):
        if "normalizeDirectApplicationAction" in text or ".closest('.calc-section')" in text:
            fail(path, "Статическую подпись нельзя исправлять runtime-кодом")
            errors += 1

    script_marker = "{{ '/assets/js/calculator-application-prefill.js' | relative_url }}"
    if application_source.count(script_marker) != 1:
        fail(APPLICATION_SOURCE, "Bootstrap предзаполнения должен подключаться ровно один раз")
        errors += 1

    for forbidden in ("localStorage", "sessionStorage", "fetch(", "sendBeacon"):
        if forbidden in bootstrap_source or forbidden in runtime_source or forbidden in built_runtime_text:
            fail(RUNTIME_SOURCE, f"Передача расчёта не должна использовать {forbidden}")
            errors += 1

    for forbidden in ("client_name", "phone", "city", "preferred_contact", "bank_history"):
        if forbidden in calculator_source or forbidden in bootstrap_source or forbidden in runtime_source:
            fail(RUNTIME_SOURCE, f"Расчётный handoff затрагивает персональное поле: {forbidden}")
            errors += 1

    for parameter in PARAMETERS:
        if parameter in main_source or parameter in built_main_text:
            fail(MAIN_SOURCE, f"Расчётный параметр не должен попадать в глобальную атрибуцию: {parameter}")
            errors += 1

    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        fail(site_dir, "Собранные HTML-страницы не найдены")
        return 1

    pages_with_bootstrap: list[str] = []
    pages_with_static_runtime: list[str] = []
    for page in html_files:
        parser = ScriptParser()
        parser.feed(page.read_text(encoding="utf-8-sig", errors="ignore"))
        bootstrap_count = sum(urlsplit(src).path == BOOTSTRAP_ASSET for src in parser.scripts)
        runtime_count = sum(urlsplit(src).path == RUNTIME_ASSET for src in parser.scripts)
        if bootstrap_count:
            pages_with_bootstrap.append(page.relative_to(site_dir).as_posix())
        if runtime_count:
            pages_with_static_runtime.append(page.relative_to(site_dir).as_posix())
        expected_bootstrap = 1 if page == application_page else 0
        if bootstrap_count != expected_bootstrap:
            fail(page, f"Bootstrap предзаполнения подключён {bootstrap_count} раз, ожидалось {expected_bootstrap}")
            errors += 1
        if runtime_count:
            fail(page, "Runtime предзаполнения не должен загружаться статически")
            errors += 1

    if pages_with_bootstrap != ["online-zayavka/index.html"]:
        fail(site_dir, f"Неверный набор страниц с bootstrap предзаполнения: {pages_with_bootstrap}")
        errors += 1
    if pages_with_static_runtime:
        fail(site_dir, f"Runtime ошибочно подключён статически: {pages_with_static_runtime}")
        errors += 1

    if errors:
        print(f"Аудит передачи расчёта в заявку завершён с ошибками: {errors}")
        return 1

    print(
        "Передача расчёта в заявку подтверждена: "
        f"{len(html_files)} HTML-страниц, bootstrap только на /online-zayavka/, "
        "runtime загружается условно по четырём ограниченным неперсональным параметрам"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
