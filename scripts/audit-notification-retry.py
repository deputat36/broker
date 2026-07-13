#!/usr/bin/env python3
"""Проверяет ручной retry уведомлений без активации публичного Supabase endpoint."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607130006_broker_lead_notification_manual_retry.sql"
FUNCTION = ROOT / "supabase/functions/broker-notification-retry/index.ts"
CONTRACT = ROOT / "docs/notification-retry-contract.md"
SMOKE = ROOT / "docs/supabase-notification-retry-smoke.md"
CONFIG = ROOT / "_config.yml"


def annotation(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def require(text: str, markers: tuple[str, ...], file: Path) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            annotation(f"Отсутствует обязательный маркер retry: {marker}", file)
            errors += 1
    return errors


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    required_files = (MIGRATION, FUNCTION, CONTRACT, SMOKE, CONFIG)
    missing = [file for file in required_files if not file.is_file()]
    for file in missing:
        annotation("Не найден обязательный файл ручного retry", file)
    if missing:
        return 1

    errors = 0
    migration = read(MIGRATION)
    function = read(FUNCTION)
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    config = read(CONFIG)

    errors += require(
        migration,
        (
            "notification_manual_retry_count integer",
            "notification_manual_retry_requested_at timestamptz",
            "notification_manual_retry_reason_code text",
            "broker_leads_notification_retry_reason_check",
            "telegram_config_fixed",
            "telegram_temporary_error",
            "notification_summary_fixed",
            "manual_recovery",
            "request_broker_lead_notification_retry",
            "and leads.notification_status = 'failed'",
            "notification_status = 'pending'",
            "notification_retry_requested",
            "broker_lead_notification_queue_health",
            "stale_count bigint",
            "total_manual_retries bigint",
            "from public, anon, authenticated",
            "to service_role",
        ),
        MIGRATION,
    )

    errors += require(
        function,
        (
            "NOTIFICATION_ADMIN_TOKEN",
            "Deno.env.get('NOTIFICATION_ADMIN_TOKEN')",
            "secureTokenEqual",
            "crypto.subtle.digest('SHA-256'",
            "Authorization",
            "Bearer",
            "MAX_BODY_BYTES = 8192",
            "request_broker_lead_notification_retry",
            "claim_broker_lead_notification",
            "broker_lead_notification_summary",
            "complete_broker_lead_notification",
            "notification_retry_sent",
            "notification_retry_failed",
            "retry_not_allowed",
            "Cache-Control",
            "no-store",
        ),
        FUNCTION,
    )

    if "Access-Control-Allow-Origin" in function:
        annotation("Административная retry-функция не должна разрешать CORS", FUNCTION)
        errors += 1
    if "reason_comment" in function or "admin_comment" in function:
        annotation("Retry-функция не должна принимать свободный административный комментарий", FUNCTION)
        errors += 1
    if "and leads.notification_status = 'failed'" not in migration:
        annotation("SQL retry должен работать только из failed", MIGRATION)
        errors += 1
    if "or leads.notification_status" in migration.split("request_broker_lead_notification_retry", 1)[-1].split("broker_lead_notification_queue_health", 1)[0]:
        annotation("SQL retry не должен разрешать дополнительные исходные статусы", MIGRATION)
        errors += 1

    errors += require(
        contract,
        (
            "failed → pending → sending → sent | failed",
            "notification_admin_token",
            "не устанавливает cors-заголовки",
            "свободный комментарий администратора не принимается",
            "broker_lead_notification_queue_health",
            "без персональных данных",
            "endpoint: \"\"",
        ),
        CONTRACT,
    )
    errors += require(
        smoke,
        (
            "проверка прав rpc",
            "контроль очереди без персональных данных",
            "unauthorized",
            "retry_not_allowed",
            "notification_retry_requested",
            "notification_retry_sent",
            "notification_retry_failed",
            "access-control-allow-origin",
            "откат",
        ),
        SMOKE,
    )

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        annotation("До smoke-теста retry рабочий режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        annotation("Публичный Supabase endpoint должен оставаться пустым", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит ручного retry уведомлений завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит ручного retry уведомлений успешно завершён: "
        "failed-only переход, whitelist причин, admin token, отсутствие CORS, "
        "обезличенная очередь, журналирование и выключенный публичный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())