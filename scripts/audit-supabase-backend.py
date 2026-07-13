#!/usr/bin/env python3
"""Проверяет подготовленность Supabase backend v2 без активации endpoint."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT_FILE = ROOT / "supabase/functions/broker-public-lead/index.ts"
HANDLER_FILE = ROOT / "supabase/functions/broker-public-lead/handler.ts"
MIGRATION_FILE = ROOT / "supabase/migrations/202607130002_broker_leads_v2.sql"
PREPARATION_MIGRATION_FILE = ROOT / "supabase/migrations/202607130003_broker_lead_preparation.sql"
NOTIFICATION_MIGRATION_FILE = ROOT / "supabase/migrations/202607130004_broker_lead_notification_summary.sql"
DELIVERY_MIGRATION_FILE = ROOT / "supabase/migrations/202607130005_broker_lead_notification_delivery.sql"
CONFIG_FILE = ROOT / "_config.yml"
CONTRACT_FILE = ROOT / "docs/lead-endpoint-contract.md"
PREPARATION_CONTRACT_FILE = ROOT / "docs/preparation-context-contract.md"
NOTIFICATION_CONTRACT_FILE = ROOT / "docs/notification-summary-contract.md"
SMOKE_FILE = ROOT / "docs/supabase-backend-smoke.md"
NOTIFICATION_SMOKE_FILE = ROOT / "docs/supabase-notification-smoke.md"


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
    required_files = (
        ENTRYPOINT_FILE,
        HANDLER_FILE,
        MIGRATION_FILE,
        PREPARATION_MIGRATION_FILE,
        NOTIFICATION_MIGRATION_FILE,
        DELIVERY_MIGRATION_FILE,
        CONFIG_FILE,
        CONTRACT_FILE,
        PREPARATION_CONTRACT_FILE,
        NOTIFICATION_CONTRACT_FILE,
        SMOKE_FILE,
        NOTIFICATION_SMOKE_FILE,
    )
    for file in required_files:
        if not file.is_file():
            error("Не найден обязательный файл", file)
            errors += 1
    if errors:
        return 1

    entrypoint = ENTRYPOINT_FILE.read_text(encoding="utf-8", errors="ignore")
    handler = HANDLER_FILE.read_text(encoding="utf-8", errors="ignore")
    function = f"{entrypoint}\n{handler}"
    migration = MIGRATION_FILE.read_text(encoding="utf-8", errors="ignore")
    preparation_migration = PREPARATION_MIGRATION_FILE.read_text(encoding="utf-8", errors="ignore")
    notification_migration = NOTIFICATION_MIGRATION_FILE.read_text(encoding="utf-8", errors="ignore")
    delivery_migration = DELIVERY_MIGRATION_FILE.read_text(encoding="utf-8", errors="ignore")
    config = CONFIG_FILE.read_text(encoding="utf-8", errors="ignore")
    contract = CONTRACT_FILE.read_text(encoding="utf-8", errors="ignore").casefold()
    preparation_contract = PREPARATION_CONTRACT_FILE.read_text(encoding="utf-8", errors="ignore").casefold()
    notification_contract = NOTIFICATION_CONTRACT_FILE.read_text(encoding="utf-8", errors="ignore").casefold()
    combined_contract = f"{contract}\n{preparation_contract}\n{notification_contract}"
    smoke = SMOKE_FILE.read_text(encoding="utf-8", errors="ignore").casefold()
    notification_smoke = NOTIFICATION_SMOKE_FILE.read_text(encoding="utf-8", errors="ignore").casefold()
    combined_smoke = f"{smoke}\n{notification_smoke}"

    errors += require_markers(entrypoint, ("import './handler.ts'",), ENTRYPOINT_FILE)
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
            "claim_broker_lead_notification",
            "complete_broker_lead_notification",
            "broker_lead_notification_summary",
            "deliverNotification",
            "TELEGRAM_BOT_TOKEN",
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        HANDLER_FILE,
    )

    for forbidden in (
        "origin.startsWith(",
        "ALLOWED_ORIGINS.some((item) => origin.startsWith(item))",
        "cleanText(payload.user_agent",
        "last_payload",
        "service_role_key: ",
        "telegram_bot_token: ",
        "telegramSummary(row)",
    ):
        if forbidden.casefold() in function.casefold():
            error(f"Небезопасный или устаревший фрагмент в Edge Function: {forbidden}", HANDLER_FILE)
            errors += 1

    if "return jsonResponse({ ok: false, success: false, blocked: true, error: 'request_rejected' }, 202, origin);" not in function:
        error("Spam-блок не должен считаться успешной доставкой в hybrid-режиме", HANDLER_FILE)
        errors += 1

    errors += require_markers(
        migration,
        (
            "broker_leads_request_id_uidx",
            "where request_id is not null",
            "broker_lead_events",
            "broker_lead_rate_limits",
            "broker_lead_rates_limits_unique_window".replace("rates_", "rate_"),
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

    errors += require_markers(
        preparation_migration,
        (
            "journey_type text",
            "journey_stage text",
            "journey_scenario_slug text",
            "preparation jsonb",
            "preparation_completed jsonb",
            "remaining_questions text",
            "broker_leads_preparation_gin_idx",
            "sync_broker_lead_preparation",
            "before insert or update of raw_payload",
            "raw_payload -> 'preparation'",
            "completed_labels",
            "security definer",
            "grant execute on function",
        ),
        PREPARATION_MIGRATION_FILE,
    )

    errors += require_markers(
        notification_migration,
        (
            "broker_lead_notification_summary",
            "returns text",
            "security definer",
            "broker_lead_not_found",
            "preparation_completed",
            "journey_type",
            "journey_stage",
            "journey_scenario_slug",
            "remaining_questions",
            "ПОДГОТОВКА ДО ОБРАЩЕНИЯ",
            "revoke all on function",
            "grant execute on function public.broker_lead_notification_summary(uuid)",
            "to service_role",
        ),
        NOTIFICATION_MIGRATION_FILE,
    )

    errors += require_markers(
        delivery_migration,
        (
            "notification_attempt_count integer",
            "notification_attempted_at timestamptz",
            "notification_sent_at timestamptz",
            "notification_last_error text",
            "notification_status in ('pending', 'sending', 'sent', 'failed', 'disabled')",
            "claim_broker_lead_notification",
            "complete_broker_lead_notification",
            "notification_status = 'sending'",
            "interval '15 minutes'",
            "notification_attempt_count = leads.notification_attempt_count + 1",
            "and leads.notification_status = 'sending'",
            "revoke all on function",
            "to service_role",
        ),
        DELIVERY_MIGRATION_FILE,
    )

    errors += require_markers(
        preparation_contract,
        (
            "context_version",
            "completed_checks",
            "completed_labels",
            "preparation_json",
            "journey_scenario_slug",
            "sync_broker_lead_preparation",
            "не является оценкой вероятности одобрения",
        ),
        PREPARATION_CONTRACT_FILE,
    )

    errors += require_markers(
        notification_contract,
        (
            "broker_lead_notification_summary",
            "service_role",
            "публичный доступ",
            "подготовка до обращения",
            "raw_payload",
            "notification_status",
            "notification_sent",
            "notification_failed",
        ),
        NOTIFICATION_CONTRACT_FILE,
    )

    if "last_payload" in migration:
        error("Таблица rate limit не должна хранить полный payload заявки", MIGRATION_FILE)
        errors += 1
    if "unique index if not exists broker_leads_request_id_uidx" not in migration:
        error("request_id должен иметь частичный уникальный индекс", MIGRATION_FILE)
        errors += 1
    if "drop column" in preparation_migration.casefold() or "drop column" in delivery_migration.casefold():
        error("Дополнительные миграции не должны удалять существующие поля", DELIVERY_MIGRATION_FILE)
        errors += 1
    if "to anon" in notification_migration.casefold() or "to authenticated" in notification_migration.casefold():
        error("Серверная сводка уведомления не должна быть доступна публичным ролям", NOTIFICATION_MIGRATION_FILE)
        errors += 1
    if "telegram_bot_token" in notification_migration.casefold() or "http_post" in notification_migration.casefold():
        error("SQL-сводка не должна хранить Telegram secrets или выполнять HTTP-запрос", NOTIFICATION_MIGRATION_FILE)
        errors += 1
    if "notification_status = 'failed'" in delivery_migration and "or leads.notification_status = 'failed'" in delivery_migration:
        error("Failed-уведомление нельзя автоматически повторно захватывать", DELIVERY_MIGRATION_FILE)
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
        "preparation",
        "journey_type",
        "remaining_questions",
        "broker_lead_notification_summary",
        "notification_status",
        "политика обработки данных",
        "endpoint должен оставаться пустым",
    ):
        if marker not in combined_contract:
            error(f"Контракт backend не содержит обязательный раздел или маркер: {marker}", CONTRACT_FILE)
            errors += 1

    for marker in (
        "проверка миграций",
        "cors preflight",
        "идемпотентность",
        "request_rejected",
        "rate_limit_exceeded",
        "backend_migration_required",
        "telegram",
        "broker_lead_notification_summary",
        "проверка прав",
        "неизвестный uuid",
        "проверка hybrid",
        "откат",
    ):
        if marker not in combined_smoke:
            error(f"Smoke-чеклисты Supabase не содержат обязательный сценарий: {marker}", SMOKE_FILE)
            errors += 1

    if errors:
        print(f"Аудит Supabase backend v2 завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит Supabase backend v2 успешно завершён: "
        "пять миграций, модульный Edge Function, идемпотентность, rate limit, CORS, "
        "атомарная доставка уведомлений, защищённая сводка, контракты, smoke-планы и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
