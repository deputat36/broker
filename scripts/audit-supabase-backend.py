#!/usr/bin/env python3
"""Проверяет подготовленность Supabase backend без активации endpoint."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "supabase/functions/broker-public-lead/index.ts"
HANDLER = ROOT / "supabase/functions/broker-public-lead/handler.ts"
BASE_MIGRATION = ROOT / "supabase/migrations/202607130002_broker_leads_v2.sql"
PREPARATION_MIGRATION = ROOT / "supabase/migrations/202607130003_broker_lead_preparation.sql"
SUMMARY_MIGRATION = ROOT / "supabase/migrations/202607130004_broker_lead_notification_summary.sql"
DELIVERY_MIGRATION = ROOT / "supabase/migrations/202607130005_broker_lead_notification_delivery.sql"
CONFIG = ROOT / "_config.yml"
CONTRACTS = (
    ROOT / "docs/lead-endpoint-contract.md",
    ROOT / "docs/preparation-context-contract.md",
    ROOT / "docs/notification-summary-contract.md",
)
SMOKE_FILES = (
    ROOT / "docs/supabase-backend-smoke.md",
    ROOT / "docs/supabase-notification-smoke.md",
)


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def require(text: str, markers: tuple[str, ...], file: Path) -> int:
    missing = [marker for marker in markers if marker not in text]
    for marker in missing:
        error(f"Отсутствует обязательный маркер backend: {marker}", file)
    return len(missing)


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    files = (
        ENTRYPOINT,
        HANDLER,
        BASE_MIGRATION,
        PREPARATION_MIGRATION,
        SUMMARY_MIGRATION,
        DELIVERY_MIGRATION,
        CONFIG,
        *CONTRACTS,
        *SMOKE_FILES,
    )
    missing_files = [file for file in files if not file.is_file()]
    for file in missing_files:
        error("Не найден обязательный файл", file)
    if missing_files:
        return 1

    errors = 0
    entrypoint = read(ENTRYPOINT)
    handler = read(HANDLER)
    function = f"{entrypoint}\n{handler}"
    base = read(BASE_MIGRATION)
    preparation = read(PREPARATION_MIGRATION)
    summary = read(SUMMARY_MIGRATION)
    delivery = read(DELIVERY_MIGRATION)
    config = read(CONFIG)
    contracts = "\n".join(read(file).casefold() for file in CONTRACTS)
    smoke = "\n".join(read(file).casefold() for file in SMOKE_FILES)

    errors += require(entrypoint, ("import './handler.ts'",), ENTRYPOINT)
    errors += require(
        function,
        (
            "schema_version=1",
            "createClient",
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
            "broker_lead_events",
            "claim_broker_lead_notification",
            "complete_broker_lead_notification",
            "broker_lead_notification_summary",
            "deliverNotification",
            "notification_status",
            "TELEGRAM_BOT_TOKEN",
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        HANDLER,
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
            error(f"Небезопасный или устаревший фрагмент: {forbidden}", HANDLER)
            errors += 1

    spam_return = "return jsonResponse({ ok: false, success: false, blocked: true, error: 'request_rejected' }, 202, origin);"
    if spam_return not in function:
        error("Spam-блок ошибочно может считаться успешной доставкой", HANDLER)
        errors += 1

    errors += require(
        base,
        (
            "broker_leads_request_id_uidx",
            "broker_lead_events",
            "broker_lead_rate_limits",
            "broker_lead_rate_limits_unique_window",
            "consume_broker_lead_rate_limit",
            "purge_broker_lead_rate_limits",
            "security definer",
            "enable row level security",
            "raw_payload jsonb",
            "tracking jsonb",
            "qualification jsonb",
            "spam_check jsonb",
        ),
        BASE_MIGRATION,
    )
    errors += require(
        preparation,
        (
            "journey_type text",
            "journey_stage text",
            "journey_scenario_slug text",
            "preparation jsonb",
            "preparation_completed jsonb",
            "remaining_questions text",
            "sync_broker_lead_preparation",
            "before insert or update of raw_payload",
            "raw_payload -> 'preparation'",
            "completed_labels",
        ),
        PREPARATION_MIGRATION,
    )
    errors += require(
        summary,
        (
            "broker_lead_notification_summary",
            "returns text",
            "security definer",
            "broker_lead_not_found",
            "preparation_completed",
            "ПОДГОТОВКА ДО ОБРАЩЕНИЯ",
            "grant execute on function public.broker_lead_notification_summary(uuid)",
            "to service_role",
        ),
        SUMMARY_MIGRATION,
    )
    errors += require(
        delivery,
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
            "to service_role",
        ),
        DELIVERY_MIGRATION,
    )

    if "last_payload" in base:
        error("Rate limit не должен хранить полный payload", BASE_MIGRATION)
        errors += 1
    if "drop column" in preparation.casefold() or "drop column" in delivery.casefold():
        error("Дополнительные миграции не должны удалять поля", DELIVERY_MIGRATION)
        errors += 1
    if "to anon" in summary.casefold() or "to authenticated" in summary.casefold():
        error("Сводка не должна быть доступна публичным ролям", SUMMARY_MIGRATION)
        errors += 1
    if "telegram_bot_token" in summary.casefold() or "http_post" in summary.casefold():
        error("SQL-сводка не должна хранить secrets или выполнять HTTP", SUMMARY_MIGRATION)
        errors += 1
    if "or leads.notification_status = 'failed'" in delivery:
        error("Failed-уведомление нельзя автоматически захватывать повторно", DELIVERY_MIGRATION)
        errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До smoke-теста режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до smoke-теста", CONFIG)
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
        "preparation",
        "broker_lead_notification_summary",
        "claim_broker_lead_notification",
        "notification_status",
        "endpoint должен оставаться пустым",
    ):
        if marker not in contracts:
            error(f"Контракты не содержат маркер: {marker}", CONTRACTS[0])
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
        "claim_broker_lead_notification",
        "проверка прав",
        "неизвестный uuid",
        "проверка hybrid",
        "откат",
    ):
        if marker not in smoke:
            error(f"Smoke-чеклисты не содержат сценарий: {marker}", SMOKE_FILES[0])
            errors += 1

    if errors:
        print(f"Аудит Supabase backend завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит Supabase backend успешно завершён: пять миграций, модульный Edge Function, "
        "идемпотентность, rate limit, CORS, preparation, атомарная доставка, контракты, smoke и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
