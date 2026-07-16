#!/usr/bin/env python3
"""Проверяет, что код ипотечного калькулятора загружается только там, где есть форма."""

from __future__ import annotations

import sys
from pathlib import Path


CALCULATOR_PAGES = {"index.html", "kalkulyator-ipoteki/index.html"}
SCRIPT_MARKER = '<script src="/assets/js/mortgage-calculator.js" defer></script>'
FORM_MARKER = "data-mortgage-calc"
FALLBACK_MARKER = "Если результат не появился, обновите страницу или свяжитесь с Татьяной напрямую."


def fail(path: Path, message: str) -> None:
    print(f"::error file={path}::{message}")


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    main_js_path = site_dir / "assets/js/main.js"
    calculator_js_path = site_dir / "assets/js/mortgage-calculator.js"
    errors = 0

    required_files = (
        site_dir / "index.html",
        site_dir / "kalkulyator-ipoteki/index.html",
        main_js_path,
        calculator_js_path,
    )
    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            fail(path, "Обязательный файл отсутствует или пуст")
            errors += 1
    if errors:
        return 1

    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        fail(site_dir, "HTML-страницы не найдены")
        return 1

    script_pages: list[str] = []
    form_pages: list[str] = []

    for path in html_files:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        relative = path.relative_to(site_dir).as_posix()
        script_count = text.count(SCRIPT_MARKER)
        form_count = text.count(FORM_MARKER)

        if script_count:
            script_pages.append(relative)
        if form_count:
            form_pages.append(relative)

        if relative in CALCULATOR_PAGES:
            if script_count != 1:
                fail(path, f"Скрипт калькулятора встречается {script_count} раз, ожидался один")
                errors += 1
            if form_count != 1:
                fail(path, f"Форма калькулятора встречается {form_count} раз, ожидалась одна")
                errors += 1
            if FALLBACK_MARKER not in text:
                fail(path, "Отсутствует понятный резервный текст при сбое JavaScript")
                errors += 1
            main_position = text.find('/assets/js/main.js')
            calculator_position = text.find('/assets/js/mortgage-calculator.js')
            if main_position < 0 or calculator_position < 0 or main_position > calculator_position:
                fail(path, "main.js должен загружаться раньше модуля калькулятора")
                errors += 1
        elif script_count or form_count:
            fail(path, "Код или форма калькулятора присутствуют вне двух разрешённых страниц")
            errors += 1

    if set(script_pages) != CALCULATOR_PAGES:
        fail(site_dir, f"Неверный набор страниц со скриптом: {script_pages}")
        errors += 1
    if set(form_pages) != CALCULATOR_PAGES:
        fail(site_dir, f"Неверный набор страниц с формой: {form_pages}")
        errors += 1

    main_js = main_js_path.read_text(encoding="utf-8-sig", errors="ignore")
    for forbidden in (
        "data-mortgage-calc",
        "calculateMortgage",
        "enhanceCalculatorInputs",
        "calcForms",
        "calculator_input",
    ):
        if forbidden in main_js:
            fail(main_js_path, f"Глобальный main.js содержит код калькулятора: {forbidden}")
            errors += 1

    calculator_js = calculator_js_path.read_text(encoding="utf-8-sig", errors="ignore")
    for required in (
        "data-mortgage-calc",
        "function calculateMortgage",
        "function enhanceCalculatorInputs",
        "calculator_input",
        "window.sendGoal",
        "Number.isFinite",
    ):
        if required not in calculator_js:
            fail(calculator_js_path, f"Модуль калькулятора не содержит обязательный маркер: {required}")
            errors += 1

    if errors:
        print(f"Аудит условного калькулятора завершён с ошибками: {errors}")
        return 1

    print(
        "Условная загрузка калькулятора подтверждена: "
        f"HTML {len(html_files)}, скрипт и форма только на {sorted(CALCULATOR_PAGES)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
