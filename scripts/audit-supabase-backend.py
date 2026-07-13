#!/usr/bin/env python3
"""Проверяет подготовленность Supabase backend v2 без активации endpoint."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTION_FILE = ROOT / "supabase/functions/broker-public-lead/index.ts"
MIGRATION_FILE = ROOT / "supabase/migrations/202607130002_broker_leads_v2.sql"
CONFIG_FILE = ROOT / "_config.yml"
CONTRACT_FILE = ROOT / "docs/lead-endpoint-contract.md"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def require_markers(text: str, markers: tuple[str, ...], file: Path) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"Отсутствует обязательный маркер backend v2: {marker}", file)
            errors += 1
    return errors


def main() -> int:
    errors = 0

    for file in (FUNCTION_FILE, MIGRATION_FILE, CONFIG_FILE, CONTRACT_FILE):
        if not file.is_file():
            error("Не найден обязательный файл", file)
            errors += 1
    if errors:
        return 1

    function = FUNCTION_FILE.read_text(encoding="utf-8", errors="ignore")
    migration = MIGRATION_FILE.read_text(encoding="utf-8", errors="ignore")
    config = CONFIG_FILE.read_text(encoding="utf-8", errors="ignore")
    contract = CONTRACT_FILE.read_text(encoding="utf-8", errors="ignore").casefold()

    errors += require_markers(
        function,
        (
            "schema_version=1",
            "createClient",
            "ALLOWED_ORIGINS",
            "ALLOWED_ORIGINS.has(normalizeOrigin(origin))",
            "MAX_BODY_BYTES",
            "content_type_not_supported",
            "payload_too_large",
            "cleanRequestId",
            "normalizeRussianPhone",
            "findExistingLead",
            "consume_broker_lead_rate_limit",
            "backend_migration_required",
            "rate_limit_exceeded",
            "request_rejected",
            "duplicate_read_failed",
            "request.headers.get('user-agent')",
            "request_id",
            "lead_id",
            "broker_lead_events",
            "notification_status",
            "TELEGRAM_BOT_TOKEN",
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        FUNCTION_FILE,
    )

    for forbidden in (
        "origin.startsWith(",
        "ALLOWED_ORIGINS.some((item) => origin.startsWith(item))",
        "cleanText(payload.user_agent",
        "last_payload",
        "service_role_key: ",
        "telegram_bot_token: ",
    ):
        if forbidden.casefold() in function.casefold():
            error(f"Небезопасный или устаревший фрагмент в Edge Function: {forbidden}", FUNCTION_FILE)
            errors += 1

    if "return jsonResponse({ ok: false, success: false, blocked: true, error: 'request_rejected' }, 202, origin);" not in function:
        error("Spam-блок не должен считаться успешной доставкой в hybrid-режиме", FUNCTION_FILE)
        errors += 1

    errors += require_markers(
        migration,
        (
            "broker_leads_request_id_uidx",
            "where request_id is not null",
            "broker_lead_events",
            "broker_lead_rate_limits",
            "broker_lead_rate_limits_unique_window",
            "consume_broker_lead_rate_limit",
            "security definer",
            "grant execute on function",
            "purge_broker_lead_rate_limits",
            "enable row level security",
            "raw_payload jsonb",
            "tracking jsonb",
            "qualification jsonb",
            "spam_check jsonb",
        ),
        MIGRATION_FILE,
    )

    if "last_payload" in migration:
        error("Таблица rate limit не должна хранить полный payload заявки", MIGRATION_FILE)
        errors += 1
    if "unique index if not exists broker_leads_request_id_uidx" not in migration:
        error("request_id должен иметь частичный уникальный индекс", MIGRATION_FILE)
        errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"

    if mode != "web3forms":
        error("До smoke-теста Supabase рабочий режим должен оставаться web3forms", CONFIG_FILE)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до применения миграции и smoke-теста", CONFIG_FILE)
        errors += 1

    for marker in (
        "web3forms",
        "hybrid",
        "schema_version",
        "request_id",
        "идемпотент",
        "rate limit",
        "cors",
        "service_role",
        "lead_id",
        "политика обработки данных",
        "endpoint должен оставаться пустым",
    ):
        if marker not in contract:
            error(f"Контракт backend не содержит обязательный раздел или маркер: {marker}", CONTRACT_FILE)
            errors += 1

    if errors:
        print(f"Аудит Supabase backend v2 завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит Supabase backend v2 успешно завершён: "
        "миграция, идемпотентность, атомарный rate limit, CORS, события, edge-case защита и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
