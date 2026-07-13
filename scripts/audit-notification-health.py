#!/usr/bin/env python3
"""Проверяет закрытый health endpoint очереди без активации публичного Supabase канала."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "supabase/functions/broker-notification-health/index.ts"
SUPABASE_CONFIG = ROOT / "supabase/config.toml"
MIGRATION = ROOT / "supabase/migrations/202607130006_broker_lead_notification_manual_retry.sql"
CONTRACT = ROOT / "docs/notification-health-contract.md"
SMOKE = ROOT / "docs/supabase-notification-health-smoke.md"
RUNBOOK = ROOT / "docs/notification-operations-runbook.md"
SITE_CONFIG = ROOT / "_config.yml"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def require(text: str, markers: tuple[str, ...], file: Path) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"Отсутствует обязательный маркер health: {marker}", file)
            errors += 1
    return errors


def function_section(config: str, name: str) -> str:
    pattern = rf"(?ms)^\[functions\.{re.escape(name)}\]\s*(.*?)(?=^\[|\Z)"
    match = re.search(pattern, config)
    return match.group(1) if match else ""


def main() -> int:
    required = (FUNCTION, SUPABASE_CONFIG, MIGRATION, CONTRACT, SMOKE, RUNBOOK, SITE_CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл health контроля", file)
    if missing:
        return 1

    errors = 0
    function = read(FUNCTION)
    supabase_config = read(SUPABASE_CONFIG)
    migration = read(MIGRATION)
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    runbook = read(RUNBOOK).casefold()
    site_config = read(SITE_CONFIG)

    errors += require(
        function,
        (
            "NOTIFICATION_MONITOR_TOKEN",
            "Deno.env.get('NOTIFICATION_MONITOR_TOKEN')",
            "secureTokenEqual",
            "crypto.subtle.digest('SHA-256'",
            "request.headers.get('authorization')",
            "request.method !== 'GET'",
            "broker_lead_notification_queue_health",
            "stale_sending",
            "failed_present",
            "failed_critical",
            "pending_backlog",
            "attempts_elevated",
            "Math.max(\n  FAILED_WARNING_THRESHOLD",
            "health.status === 'critical' ? 503 : 200",
            "queue_health_unavailable",
            "Cache-Control",
            "no-store",
        ),
        FUNCTION,
    )

    health_config = function_section(supabase_config, "broker-notification-health")
    if not health_config:
        error("В supabase/config.toml отсутствует секция broker-notification-health", SUPABASE_CONFIG)
        errors += 1
    elif not re.search(r"(?m)^\s*verify_jwt\s*=\s*false\s*$", health_config):
        error("Monitor token не дойдёт до handler без verify_jwt = false", SUPABASE_CONFIG)
        errors += 1

    if "Access-Control-Allow-Origin" in function:
        error("Health endpoint не должен разрешать CORS", FUNCTION)
        errors += 1

    for forbidden in (
        "client_name",
        "phone_normalized",
        "source_page",
        "page_url",
        "raw_payload",
        "request_id",
        "lead_id",
        "telegram_chat_id",
        "telegram_bot_token",
        "notification_admin_token",
    ):
        if forbidden in function.casefold():
            error(f"Health endpoint содержит запрещённый персональный или секретный маркер: {forbidden}", FUNCTION)
            errors += 1

    errors += require(
        migration,
        (
            "broker_lead_notification_queue_health",
            "notification_status text",
            "lead_count bigint",
            "oldest_lead_at timestamptz",
            "oldest_attempted_at timestamptz",
            "stale_count bigint",
            "max_attempt_count integer",
            "total_manual_retries bigint",
            "from public, anon, authenticated",
            "to service_role",
        ),
        MIGRATION,
    )

    errors += require(
        contract,
        (
            "notification_monitor_token",
            "verify_jwt = false",
            "access-control-allow-origin",
            "без раскрытия персональных данных",
            "stale_sending",
            "failed_critical",
            "pending_backlog",
            "attempts_elevated",
            "endpoint: \"\"",
        ),
        CONTRACT,
    )
    errors += require(
        smoke,
        (
            "broker-notification-health",
            "notification_monitor_token",
            "verify_jwt = false",
            "access-control-allow-origin",
            "failed_present",
            "stale_sending",
            "failed_critical",
            "pending_backlog",
            "attempts_elevated",
            "queue_health_unavailable",
            "отсутствия персональных данных",
            "откат",
        ),
        SMOKE,
    )
    errors += require(
        runbook,
        (
            "массовый retry запрещён",
            "failed_present",
            "failed_critical",
            "stale_sending",
            "pending_backlog",
            "attempts_elevated",
            "проверка перед ручным retry",
            "закрытие инцидента",
            "эскалация",
            "endpoint: \"\"",
        ),
        RUNBOOK,
    )

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", site_config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", site_config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До smoke-теста health рабочий режим должен оставаться web3forms", SITE_CONFIG)
        errors += 1
    if endpoint:
        error("Публичный Supabase endpoint должен оставаться пустым", SITE_CONFIG)
        errors += 1

    if errors:
        print(f"Аудит health endpoint завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит health endpoint успешно завершён: отдельный monitor token, GET-only, отсутствие CORS, "
        "агрегаты без персональных данных, пороги тревог, runbook, smoke и выключенный публичный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
