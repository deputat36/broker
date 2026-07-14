#!/usr/bin/env python3
"""Проверяет, что страница благодарности не передаёт данные заявки в аналитику."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts/default.html"
THANK_YOU_SOURCE = ROOT / "spasibo.md"
PRIVACY_DOC = ROOT / "docs/thank-you-privacy.md"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def require(text: str, markers: tuple[str, ...], file: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"{label}: отсутствует маркер {marker}", file)
            errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_page = site_dir / "spasibo/index.html"

    required_files = (LAYOUT, THANK_YOU_SOURCE, PRIVACY_DOC, built_page)
    missing = [file for file in required_files if not file.is_file()]
    if missing:
        for file in missing:
            error("Не найден обязательный файл", file)
        return 1

    layout = read(LAYOUT)
    thank_you = read(THANK_YOU_SOURCE)
    documentation = read(PRIVACY_DOC).casefold()
    built = read(built_page)
    errors = 0

    errors += require(
        layout,
        (
            "{% if page.url == '/spasibo/' %}",
            "window.thankYouContext",
            "new URLSearchParams(window.location.search)",
            "window.history.replaceState(null, document.title, window.location.pathname)",
        ),
        LAYOUT,
        "Ранняя очистка URL",
    )

    sanitizer_position = layout.find("window.history.replaceState")
    metrika_position = layout.find("https://mc.yandex.ru/metrika/tag.js")
    if sanitizer_position < 0 or metrika_position < 0 or sanitizer_position > metrika_position:
        error("Очистка URL страницы благодарности должна выполняться до инициализации Метрики", LAYOUT)
        errors += 1

    errors += require(
        thank_you,
        (
            "var legacyContext = window.thankYouContext || {};",
            "function cleanRequestId(value)",
            "Object.prototype.hasOwnProperty.call(statusMap, rawStatus)",
            "window.dataLayer.push({ event: 'lead_thankyou_view' });",
            "delete window.thankYouContext",
        ),
        THANK_YOU_SOURCE,
        "Безопасная сводка страницы благодарности",
    )

    for forbidden in (
        "var params = new URLSearchParams(window.location.search)",
        "request_id: requestId",
        "scenario: scenario",
        "qualification_status: status",
        "phone:",
        "delivery_state:",
    ):
        if forbidden in thank_you:
            error(f"Страница благодарности передаёт запрещённый аналитический контекст: {forbidden}", THANK_YOU_SOURCE)
            errors += 1

    errors += require(
        built,
        (
            "window.thankYouContext",
            "window.history.replaceState(null, document.title, window.location.pathname)",
            "window.dataLayer.push({ event: 'lead_thankyou_view' });",
            "id=\"lead-id\"",
            "id=\"lead-scenario\"",
            "id=\"lead-city\"",
            "id=\"lead-status\"",
        ),
        built_page,
        "Собранная страница благодарности",
    )

    built_sanitizer_position = built.find("window.history.replaceState")
    built_main_position = built.find("/assets/js/main.js")
    if built_sanitizer_position < 0 or built_main_position < 0 or built_sanitizer_position > built_main_position:
        error("В собранной странице URL должен очищаться до запуска main.js", built_page)
        errors += 1

    built_metrika_position = built.find("https://mc.yandex.ru/metrika/tag.js")
    if built_metrika_position >= 0 and built_sanitizer_position > built_metrika_position:
        error("В собранной странице URL должен очищаться до Метрики", built_page)
        errors += 1

    for forbidden in (
        "request_id: requestId",
        "scenario: scenario",
        "qualification_status: status",
    ):
        if forbidden in built:
            error(f"Собранная страница содержит запрещённое поле dataLayer: {forbidden}", built_page)
            errors += 1

    for marker in (
        "до возможной инициализации яндекс метрики",
        "не должна содержать номер заявки",
        "window.datalayer.push({ event: 'lead_thankyou_view' });",
        "не содержит телефона и полного текста заявки",
    ):
        if marker not in documentation:
            error(f"Документация приватности не содержит маркер: {marker}", PRIVACY_DOC)
            errors += 1

    if errors:
        print(f"Аудит приватности страницы благодарности завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит приватности страницы благодарности успешно завершён: URL очищается до аналитики, "
        "dataLayer не содержит request ID, сценарий, город или квалификацию"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
