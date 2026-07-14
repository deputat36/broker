#!/usr/bin/env python3
"""Проверяет безопасное отображение ошибок онлайн-заявки."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "assets/js/application-inputs.js"
ONLINE = ROOT / "assets/js/online-application.js"
PAGE = ROOT / "online-zayavka.md"
LAYOUT = ROOT / "_layouts/default.html"
CONTRACT = ROOT / "docs/application-error-ui-contract.md"
SMOKE = ROOT / "docs/application-error-ui-smoke.md"
SERVER_CONTRACT = ROOT / "docs/public-lead-error-contract.md"
WORKFLOW = ROOT / ".github/workflows/pages.yml"
CONFIG = ROOT / "_config.yml"
UNUSED_STANDALONE = ROOT / "assets/js/application-error-ui.js"

ERROR_CODES = (
    "validation_failed",
    "rate_limit_exceeded",
    "request_rejected",
    "backend_unavailable",
    "backend_migration_required",
    "lead_storage_failed",
    "origin_not_allowed",
    "method_not_allowed",
    "content_type_not_supported",
    "payload_too_large",
    "invalid_json",
)

ANALYTICS_GOALS = (
    "online_application_endpoint_error",
    "online_application_endpoint_error_validation",
    "online_application_endpoint_error_rate_limit",
    "online_application_endpoint_error_rejected",
    "online_application_endpoint_error_backend",
    "online_application_endpoint_error_request",
)


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def require(text: str, markers: tuple[str, ...], file: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"{label}: отсутствует marker {marker}", file)
            errors += 1
    return errors


def main() -> int:
    required = (INPUTS, ONLINE, PAGE, LAYOUT, CONTRACT, SMOKE, SERVER_CONTRACT, WORKFLOW, CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл application error UI", file)
    if missing:
        return 1

    errors = 0
    inputs = read(INPUTS)
    online = read(ONLINE)
    page = read(PAGE)
    layout = read(LAYOUT)
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    server_contract = read(SERVER_CONTRACT).casefold()
    workflow = read(WORKFLOW)
    config = read(CONFIG)

    if UNUSED_STANDALONE.exists():
        error("Неиспользуемый standalone error UI не должен дублировать встроенный модуль", UNUSED_STANDALONE)
        errors += 1

    if "const ERROR_GROUPS = {" not in inputs:
        error("Не найден встроенный модуль безопасных ошибок", INPUTS)
        return 1
    error_ui = inputs.split("const ERROR_GROUPS = {", 1)[-1]

    errors += require(
        error_ui,
        (
            "validation_failed: 'validation'",
            "rate_limit_exceeded: 'rate_limit'",
            "request_rejected: 'rejected'",
            "backend_unavailable: 'backend'",
            "backend_migration_required: 'backend'",
            "lead_storage_failed: 'backend'",
            "origin_not_allowed: 'request'",
            "method_not_allowed: 'request'",
            "content_type_not_supported: 'request'",
            "payload_too_large: 'request'",
            "invalid_json: 'request'",
            "network: 'Сервис не ответил. Готовый текст заявки не потерян.'",
            "payload.ok !== false || payload.success !== false",
            "const errorCode = cleanText(payload.error_code, 60)",
            "validRequestId(payload.request_id) || currentRequestId()",
            "Number.isInteger(seconds) && seconds > 0 && seconds <= 86400",
            "response.clone().json()",
            "new MutationObserver(renderSafeError)",
            "deliveryNote.dataset.errorCategory = category",
            "delete deliveryNote.dataset.errorCategory",
            "Технический номер:",
            "SMS, MAX, ВКонтакте",
        ),
        INPUTS,
        "Error UI",
    )

    for code in ERROR_CODES:
        if f"`{code}`" not in contract:
            error(f"UI-контракт не описывает серверный код: {code}", CONTRACT)
            errors += 1
        if f"`{code}`" not in server_contract:
            error(f"Серверный error-контракт не содержит код: {code}", SERVER_CONTRACT)
            errors += 1

    errors += require(
        error_ui,
        (
            "window.sendGoal('online_application_endpoint_error')",
            "const allowed = ['validation', 'rate_limit', 'rejected', 'backend', 'request'];",
            "window.sendGoal(`online_application_endpoint_error_${category}`)",
        ),
        INPUTS,
        "Аналитика error UI",
    )
    for marker in ANALYTICS_GOALS:
        if f"`{marker}`" not in contract:
            error(f"UI-контракт не описывает цель: {marker}", CONTRACT)
            errors += 1

    for forbidden in (
        "localStorage",
        "sessionStorage",
        "window.ym",
        "`${errorCode}`",
        "textContent = errorCode",
        "sendGoal(errorCode)",
        "sendGoal(requestId)",
        "payload.message",
        "payload.error ",
    ):
        if forbidden in error_ui:
            error(f"Error UI содержит запрещённый фрагмент: {forbidden}", INPUTS)
            errors += 1

    if re.search(r"sendGoal\([^)]*request", error_ui, re.IGNORECASE):
        error("Технический request ID не должен передаваться в аналитику", INPUTS)
        errors += 1

    errors += require(
        online,
        (
            "Promise.allSettled(tasks)",
            "if (!successful.length)",
            "Онлайн-отправка не удалась",
            "Сервис не ответил вовремя",
            "SMS, MAX или ВКонтакте",
        ),
        ONLINE,
        "Основной транспорт",
    )

    errors += require(
        page,
        (
            "assets/js/application-inputs.js",
            "assets/js/application-preparation.js",
            "data-application-delivery-note",
            "data-application-direct-send",
        ),
        PAGE,
        "Страница формы",
    )
    errors += require(
        layout,
        ("assets/js/main.js", "assets/js/online-application.js"),
        LAYOUT,
        "Layout",
    )

    for marker in (
        "correlation `request_id`",
        "пять стабильных категорий",
        "data-error-category",
        "только в памяти страницы",
        "retry_after_seconds",
        "hybrid",
        "web3forms",
        "сырой `error_code`",
    ):
        if marker not in contract:
            error(f"UI-контракт не содержит marker: {marker}", CONTRACT)
            errors += 1

    for marker in (
        "порядок скриптов",
        "технический номер",
        "validation",
        "rate limit",
        "request rejected",
        "неизвестный код",
        "таймаут и сеть",
        "новая попытка",
        "hybrid",
        "localstorage",
        "mode: \"web3forms\"",
        "endpoint: \"\"",
    ):
        if marker not in smoke:
            error(f"UI smoke не содержит marker: {marker}", SMOKE)
            errors += 1

    command = "python3 scripts/audit-application-error-ui.py"
    if command not in workflow:
        error("Pages workflow не запускает application error UI audit", WORKFLOW)
        errors += 1
    if "node --check assets/js/application-inputs.js" not in workflow:
        error("Pages workflow не проверяет синтаксис application-inputs.js", WORKFLOW)
        errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До UI smoke режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до общей приёмки", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит интерфейса ошибок заявки завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит интерфейса ошибок успешно завершён: allowlist-коды переведены в безопасные категории, "
        "correlation ID валидируется и не сохраняется отдельно, fallback и hybrid-семантика сохранены, "
        "документы, smoke и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
