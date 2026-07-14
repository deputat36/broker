#!/usr/bin/env python3
"""Проверяет минимизацию локальной сводки и страницы благодарности."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts/default.html"
THANK_YOU_SOURCE = ROOT / "spasibo.md"
KEEPALIVE = ROOT / "assets/js/application-delivery-keepalive.js"
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

    required_files = (LAYOUT, THANK_YOU_SOURCE, KEEPALIVE, PRIVACY_DOC, built_page)
    missing = [file for file in required_files if not file.is_file()]
    if missing:
        for file in missing:
            error("Не найден обязательный файл", file)
        return 1

    layout = read(LAYOUT)
    thank_you = read(THANK_YOU_SOURCE)
    keepalive = read(KEEPALIVE)
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
        keepalive,
        (
            "const STORAGE_KEY = 'sterlikovaMortgageLastLead'",
            "function sanitizeLastLead()",
            "request_id: requestId",
            "expires_at: new Date(expiresAt).toISOString()",
            "new MutationObserver",
            "Переходим на страницу подтверждения",
        ),
        KEEPALIVE,
        "Минимизация локальной сводки",
    )

    storage_module = keepalive.split("const STORAGE_KEY = 'sterlikovaMortgageLastLead'", 1)[-1]
    for forbidden in (
        "scenario:",
        "object_type:",
        "city:",
        "qualification:",
        "channels:",
        "phone:",
        "tracking:",
    ):
        if forbidden in storage_module:
            error(f"Локальная сводка содержит лишнее поле: {forbidden}", KEEPALIVE)
            errors += 1

    errors += require(
        thank_you,
        (
            "var legacyContext = window.thankYouContext || {};",
            "function cleanRequestId(value)",
            "document.getElementById('lead-id').textContent = requestId;",
            "JSON.stringify({",
            "request_id: requestId",
            "expires_at: new Date(Date.parse(lastLead.expires_at)).toISOString()",
            "window.dataLayer.push({ event: 'lead_thankyou_view' });",
            "delete window.thankYouContext",
        ),
        THANK_YOU_SOURCE,
        "Минимальная страница благодарности",
    )

    for forbidden in (
        'id="lead-scenario"',
        'id="lead-city"',
        'id="lead-status"',
        "lastLead.scenario",
        "lastLead.city",
        "lastLead.qualification",
        "statusMap",
        "request_id: requestId,",
        "scenario: scenario",
        "qualification_status: status",
        "delivery_state:",
        "phone:",
    ):
        if forbidden in thank_you:
            error(f"Страница благодарности содержит лишний контекст: {forbidden}", THANK_YOU_SOURCE)
            errors += 1

    errors += require(
        built,
        (
            "window.thankYouContext",
            "window.history.replaceState(null, document.title, window.location.pathname)",
            "window.dataLayer.push({ event: 'lead_thankyou_view' });",
            'id="lead-id"',
            "Хотя бы один настроенный канал принял обращение",
        ),
        built_page,
        "Собранная страница благодарности",
    )

    built_sanitizer_position = built.find("window.history.replaceState")
    built_main_position = built.find("/assets/js/main.js")
    if built_sanitizer_position < 0 or built_main_position < 0 or built_sanitizer_position > built_main_position:
        error("В собранной странице URL должен очищаться до запуска main.js", built_page)
        errors += 1

    for forbidden in (
        'id="lead-scenario"',
        'id="lead-city"',
        'id="lead-status"',
        "request_id: requestId,",
        "scenario: scenario",
        "qualification_status: status",
    ):
        if forbidden in built:
            error(f"Собранная страница содержит лишний контекст: {forbidden}", built_page)
            errors += 1

    for marker in (
        "только технический номер обращения",
        "только `request_id` и `expires_at`",
        "не должны содержать номер заявки",
        "window.datalayer.push({ event: 'lead_thankyou_view' });",
        "не показывает город, сценарий, объект или qualification",
    ):
        if marker not in documentation:
            error(f"Документация приватности не содержит маркер: {marker}", PRIVACY_DOC)
            errors += 1

    if errors:
        print(f"Аудит приватности страницы благодарности завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит приватности страницы благодарности успешно завершён: URL очищается до аналитики, "
        "локальная сводка содержит только request_id/expires_at, а экран не показывает сценарий, город или qualification"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
