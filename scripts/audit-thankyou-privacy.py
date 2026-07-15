#!/usr/bin/env python3
"""Проверяет минимизацию локальной сводки и страницы благодарности."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts/default.html"
APPLICATION_JS = ROOT / "assets/js/online-application.js"
APPLICATION_SOURCE = ROOT / "online-zayavka.md"
THANK_YOU_SOURCE = ROOT / "spasibo.md"
STORAGE_MIGRATION = ROOT / "assets/js/thankyou-storage-privacy.js"
PRIVACY_DOC = ROOT / "docs/thank-you-privacy.md"
POLICY = ROOT / "policy.md"
WORKFLOW = ROOT / ".github/workflows/pages.yml"


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


def forbid(text: str, markers: tuple[str, ...], file: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker in text:
            error(f"{label}: найден запрещённый маркер {marker}", file)
            errors += 1
    return errors


def block(text: str, start: str, end: str, file: Path, label: str) -> tuple[str, int]:
    start_position = text.find(start)
    end_position = text.find(end, start_position + len(start)) if start_position >= 0 else -1
    if start_position < 0 or end_position < 0:
        error(f"{label}: не удалось выделить проверяемый блок", file)
        return "", 1
    return text[start_position:end_position], 0


def check_order(text: str, markers: tuple[str, ...], file: Path, label: str) -> int:
    positions = [text.find(marker) for marker in markers]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        error(f"{label}: нарушен безопасный порядок скриптов", file)
        return 1
    return 0


def check_application_js(text: str, file: Path, label: str) -> int:
    errors = 0
    storage_block, block_errors = block(
        text,
        "function saveLastLead",
        "function buildThankYouUrl",
        file,
        f"{label}: локальная сводка",
    )
    errors += block_errors
    if storage_block:
        errors += require(
            storage_block,
            (
                "function saveLastLead(payload)",
                "request_id: payload.request_id",
                "expires_at: new Date(Date.now() + LAST_LEAD_RETENTION_MS).toISOString()",
                "window.localStorage.setItem(LAST_LEAD_STORAGE_KEY, JSON.stringify(safeLead))",
            ),
            file,
            f"{label}: локальная сводка",
        )
        errors += forbid(
            storage_block,
            (
                "scenario:",
                "object_type:",
                "city:",
                "qualification:",
                "submitted_at:",
                "channels:",
                "phone:",
                "tracking:",
            ),
            file,
            f"{label}: локальная сводка",
        )

    redirect_block, block_errors = block(
        text,
        "function buildThankYouUrl",
        "async function sendDirectly",
        file,
        f"{label}: redirect",
    )
    errors += block_errors
    if redirect_block:
        errors += require(
            redirect_block,
            (
                "url.hash = new URLSearchParams({ id: payload.request_id }).toString();",
                "return url.toString();",
            ),
            file,
            f"{label}: redirect",
        )
        errors += forbid(
            redirect_block,
            (
                "searchParams.set",
                "payload.qualification",
                "payload.mortgage.scenario",
                "status",
                "scenario",
            ),
            file,
            f"{label}: redirect",
        )

    errors += require(
        text,
        ("saveLastLead(preparedPayload);",),
        file,
        f"{label}: вызов сохранения",
    )
    errors += forbid(
        text,
        ("saveLastLead(preparedPayload, channels);",),
        file,
        f"{label}: вызов сохранения",
    )
    return errors


def check_layout(text: str, file: Path, label: str) -> int:
    errors = 0
    context_block, block_errors = block(
        text,
        "{% if page.url == '/spasibo/' %}",
        "{% if site.yandex_metrika_id",
        file,
        f"{label}: ранняя очистка URL",
    )
    errors += block_errors
    if context_block:
        errors += require(
            context_block,
            (
                "window.location.hash.replace(/^#/, '')",
                "new URLSearchParams(window.location.search)",
                "id: fragmentParams.get('id') || legacyParams.get('id') || ''",
                "window.history.replaceState(null, document.title, window.location.pathname)",
            ),
            file,
            f"{label}: ранняя очистка URL",
        )
        errors += forbid(
            context_block,
            (
                "scenario:",
                "status:",
                "get('scenario')",
                "get('status')",
            ),
            file,
            f"{label}: ранняя очистка URL",
        )

    sanitizer_position = text.find("window.history.replaceState")
    metrika_position = text.find("https://mc.yandex.ru/metrika/tag.js")
    if sanitizer_position < 0 or metrika_position < 0 or sanitizer_position > metrika_position:
        error(f"{label}: очистка URL должна выполняться до инициализации Метрики", file)
        errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_page = site_dir / "spasibo/index.html"
    built_application = site_dir / "online-zayavka/index.html"
    built_application_js = site_dir / "assets/js/online-application.js"
    built_migration_js = site_dir / "assets/js/thankyou-storage-privacy.js"

    required_files = (
        LAYOUT,
        APPLICATION_JS,
        APPLICATION_SOURCE,
        THANK_YOU_SOURCE,
        STORAGE_MIGRATION,
        PRIVACY_DOC,
        POLICY,
        WORKFLOW,
        built_page,
        built_application,
        built_application_js,
        built_migration_js,
    )
    missing = [file for file in required_files if not file.is_file()]
    if missing:
        for file in missing:
            error("Не найден обязательный файл", file)
        return 1

    layout = read(LAYOUT)
    application_js = read(APPLICATION_JS)
    application = read(APPLICATION_SOURCE)
    thank_you = read(THANK_YOU_SOURCE)
    migration = read(STORAGE_MIGRATION)
    documentation = read(PRIVACY_DOC).casefold()
    policy = read(POLICY).casefold()
    workflow = read(WORKFLOW)
    built = read(built_page)
    built_application_text = read(built_application)
    built_js = read(built_application_js)
    built_migration = read(built_migration_js)
    errors = 0

    errors += check_layout(layout, LAYOUT, "Исходный layout")
    errors += check_layout(built, built_page, "Собранная страница")
    errors += check_application_js(application_js, APPLICATION_JS, "Исходный JS")
    errors += check_application_js(built_js, built_application_js, "Собранный JS")

    migration_markers = (
        "const STORAGE_KEY = 'sterlikovaMortgageLastLead'",
        "function migrateLegacyLastLead()",
        "request_id: requestId",
        "expires_at: new Date(expiresAt).toISOString()",
        "migrateLegacyLastLead();",
    )
    errors += require(migration, migration_markers, STORAGE_MIGRATION, "Legacy-миграция")
    errors += require(built_migration, migration_markers, built_migration_js, "Собранная legacy-миграция")
    migration_forbidden = (
        "MutationObserver",
        "deliveryNote",
        "Переходим на страницу подтверждения",
        "scenario:",
        "object_type:",
        "city:",
        "qualification:",
        "channels:",
        "phone:",
        "tracking:",
        "sessionStorage",
        "sendGoal",
    )
    errors += forbid(migration, migration_forbidden, STORAGE_MIGRATION, "Legacy-миграция")
    errors += forbid(built_migration, migration_forbidden, built_migration_js, "Собранная legacy-миграция")

    script_order = (
        "assets/js/thankyou-storage-privacy.js",
        "assets/js/application-delivery-keepalive.js",
        "assets/js/application-inputs.js",
        "assets/js/application-preparation.js",
        "assets/js/online-application.js",
    )
    errors += check_order(application + "\n" + layout, script_order, APPLICATION_SOURCE, "Исходная онлайн-заявка")
    errors += check_order(built_application_text, script_order, built_application, "Собранная онлайн-заявка")

    if "node --check assets/js/thankyou-storage-privacy.js" not in workflow:
        error("Workflow не проверяет синтаксис legacy-миграции", WORKFLOW)
        errors += 1

    errors += require(
        thank_you,
        (
            "var legacyContext = window.thankYouContext || {};",
            "function cleanRequestId(value)",
            "document.getElementById('lead-id').textContent = requestId;",
            "request_id: requestId",
            "expires_at: new Date(Date.parse(lastLead.expires_at)).toISOString()",
            "window.dataLayer.push({ event: 'lead_thankyou_view' });",
            "delete window.thankYouContext",
        ),
        THANK_YOU_SOURCE,
        "Минимальная страница благодарности",
    )
    errors += forbid(
        thank_you,
        (
            'id="lead-scenario"',
            'id="lead-city"',
            'id="lead-status"',
            "lastLead.scenario",
            "lastLead.city",
            "lastLead.qualification",
            "statusMap",
            "scenario: scenario",
            "qualification_status: status",
            "delivery_state:",
            "phone:",
        ),
        THANK_YOU_SOURCE,
        "Минимальная страница благодарности",
    )

    errors += require(
        built,
        (
            "window.thankYouContext",
            "window.location.hash.replace(/^#/, '')",
            "window.history.replaceState(null, document.title, window.location.pathname)",
            "window.dataLayer.push({ event: 'lead_thankyou_view' });",
            'id="lead-id"',
            "Хотя бы один настроенный канал принял обращение",
        ),
        built_page,
        "Собранная страница благодарности",
    )
    errors += forbid(
        built,
        (
            'id="lead-scenario"',
            'id="lead-city"',
            'id="lead-status"',
            "scenario: scenario",
            "qualification_status: status",
            "get('scenario')",
            "get('status')",
        ),
        built_page,
        "Собранная страница благодарности",
    )

    for marker in (
        "только технический номер обращения",
        "сразу только `request_id` и `expires_at`",
        "fragment `#id=`",
        "legacy query",
        "не должны содержать номер заявки",
        "window.datalayer.push({ event: 'lead_thankyou_view' });",
        "не показывает город, сценарий, объект или qualification",
    ):
        if marker not in documentation:
            error(f"Документация приватности не содержит маркер: {marker}", PRIVACY_DOC)
            errors += 1

    for marker in (
        "технический номер обращения <code>request_id</code>",
        "срок действия <code>expires_at</code>",
        "город, сценарий, объект, квалификация, список каналов",
        "сводка автоматически перестаёт использоваться через 24 часа",
    ):
        if marker not in policy:
            error(f"Публичная политика не содержит маркер минимальной сводки: {marker}", POLICY)
            errors += 1

    if "технический номер, сценарий, город, статус квалификации" in policy:
        error("Публичная политика всё ещё описывает расширенную локальную сводку", POLICY)
        errors += 1

    if errors:
        print(f"Аудит приватности страницы благодарности завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит приватности страницы благодарности успешно завершён: новые данные минимизируются до записи, "
        "request_id передаётся через fragment, URL очищается до аналитики, legacy-записи сокращаются до двух полей"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
