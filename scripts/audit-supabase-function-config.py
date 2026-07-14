#!/usr/bin/env python3
"""Проверяет per-function JWT config и собственную защиту Edge Functions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "supabase/config.toml"
PUBLIC_FUNCTION = ROOT / "supabase/functions/broker-public-lead/handler.ts"
RECEIPT_FUNCTION = ROOT / "supabase/functions/broker-delivery-receipt/index.ts"
ADMIN_FUNCTION = ROOT / "supabase/functions/broker-notification-retry/index.ts"
HEALTH_FUNCTION = ROOT / "supabase/functions/broker-notification-health/index.ts"
ALLOWED_FUNCTIONS = {
    "broker-public-lead",
    "broker-delivery-receipt",
    "broker-notification-retry",
    "broker-notification-health",
}


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def sections(config: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^\[functions\.([A-Za-z0-9_-]+)\]\s*$", config))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(config)
        result[match.group(1)] = config[start:end]
    return result


def require_markers(text: str, markers: tuple[str, ...], file: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"{label} без обязательной собственной защиты: {marker}", file)
            errors += 1
    return errors


def main() -> int:
    required = (CONFIG, PUBLIC_FUNCTION, RECEIPT_FUNCTION, ADMIN_FUNCTION, HEALTH_FUNCTION)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл конфигурации Edge Functions", file)
    if missing:
        return 1

    errors = 0
    config = read(CONFIG)
    public_function = read(PUBLIC_FUNCTION)
    receipt_function = read(RECEIPT_FUNCTION)
    admin_function = read(ADMIN_FUNCTION)
    health_function = read(HEALTH_FUNCTION)
    function_sections = sections(config)

    unknown = set(function_sections) - ALLOWED_FUNCTIONS
    if unknown:
        error("Неожиданные функции в per-function config: " + ", ".join(sorted(unknown)), CONFIG)
        errors += 1

    for function_name in sorted(ALLOWED_FUNCTIONS):
        section = function_sections.get(function_name, "")
        if not section:
            error(f"Отсутствует секция [functions.{function_name}]", CONFIG)
            errors += 1
            continue
        if not re.search(r"(?m)^\s*verify_jwt\s*=\s*false\s*$", section):
            error(f"Для {function_name} ожидается явное verify_jwt = false", CONFIG)
            errors += 1

    if len(re.findall(r"(?m)^\s*verify_jwt\s*=\s*false\s*$", config)) != 4:
        error("verify_jwt = false должно быть задано ровно для четырёх контрактных функций", CONFIG)
        errors += 1

    errors += require_markers(
        public_function,
        (
            "ALLOWED_ORIGINS.has(normalizeOrigin(origin))",
            "if (!isAllowedOrigin(origin))",
            "consume_broker_lead_rate_limit",
            "personal_data_consent_required",
            "request_rejected",
            "MAX_BODY_BYTES",
        ),
        PUBLIC_FUNCTION,
        "Публичная функция",
    )
    errors += require_markers(
        receipt_function,
        (
            "ALLOWED_ORIGINS.has(normalizeOrigin(origin))",
            "if (!isAllowedOrigin(origin))",
            "requestKind !== 'delivery_receipt'",
            "deliveryState !== 'both'",
            "mark_broker_lead_delivery_both",
            "MAX_BODY_BYTES = 4096",
            "return new Response(null, { status: 204",
            "Cache-Control",
            "no-store",
        ),
        RECEIPT_FUNCTION,
        "Delivery receipt функция",
    )
    errors += require_markers(
        admin_function,
        (
            "NOTIFICATION_ADMIN_TOKEN",
            "secureTokenEqual",
            "request.headers.get('authorization')",
            "request_broker_lead_notification_retry",
            "MAX_BODY_BYTES = 8192",
            "Cache-Control",
            "no-store",
        ),
        ADMIN_FUNCTION,
        "Административная функция",
    )
    errors += require_markers(
        health_function,
        (
            "NOTIFICATION_MONITOR_TOKEN",
            "secureTokenEqual",
            "request.headers.get('authorization')",
            "broker_lead_notification_queue_health",
            "stale_sending",
            "failed_critical",
            "pending_backlog",
            "Cache-Control",
            "no-store",
        ),
        HEALTH_FUNCTION,
        "Health-функция",
    )

    for file, text in ((ADMIN_FUNCTION, admin_function), (HEALTH_FUNCTION, health_function)):
        if "Access-Control-Allow-Origin" in text:
            error("Закрытая функция не должна устанавливать CORS", file)
            errors += 1

    for forbidden in (
        "client_name",
        "phone_normalized",
        "mortgage_goal",
        "raw_payload",
        "TELEGRAM_BOT_TOKEN",
        "NOTIFICATION_ADMIN_TOKEN",
        "NOTIFICATION_MONITOR_TOKEN",
    ):
        if forbidden in receipt_function:
            error(f"Delivery receipt не должна содержать данные или secrets: {forbidden}", RECEIPT_FUNCTION)
            errors += 1

    if "verify_jwt = true" in config:
        error("Не смешивайте противоречивые JWT-настройки в контрактных секциях", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит Supabase function config завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит Supabase function config успешно завершён: четыре известные функции, "
        "явный verify_jwt=false и собственная защита lead, receipt, retry и health handler подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
