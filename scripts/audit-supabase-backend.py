#!/usr/bin/env python3
"""Проверяет core-готовность Supabase backend без активации endpoint."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "supabase/functions/broker-public-lead/index.ts"
HANDLER = ROOT / "supabase/functions/broker-public-lead/handler.ts"
ADMIN_RETRY = ROOT / "supabase/functions/broker-notification-retry/index.ts"
BASE = ROOT / "supabase/migrations/202607130002_broker_leads_v2.sql"
PREPARATION = ROOT / "supabase/migrations/202607130003_broker_lead_preparation.sql"
SUMMARY = ROOT / "supabase/migrations/202607130004_broker_lead_notification_summary.sql"
DELIVERY = ROOT / "supabase/migrations/202607130005_broker_lead_notification_delivery.sql"
RETRY = ROOT / "supabase/migrations/202607130006_broker_lead_notification_manual_retry.sql"
RETENTION = ROOT / "supabase/migrations/202607140001_broker_lead_retention.sql"
CONFIG = ROOT / "_config.yml"
CONTRACTS = (
    ROOT / "docs/lead-endpoint-contract.md",
    ROOT / "docs/public-lead-response-contract.md",
    ROOT / "docs/public-lead-error-contract.md",
    ROOT / "docs/preparation-context-contract.md",
    ROOT / "docs/notification-summary-contract.md",
    ROOT / "docs/notification-retry-contract.md",
    ROOT / "docs/data-retention-contract.md",
)
SMOKE_FILES = (
    ROOT / "docs/supabase-backend-smoke.md",
    ROOT / "docs/supabase-public-response-smoke.md",
    ROOT / "docs/supabase-public-error-smoke.md",
    ROOT / "docs/supabase-notification-smoke.md",
    ROOT / "docs/supabase-notification-retry-smoke.md",
    ROOT / "docs/supabase-retention-smoke.md",
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
    files = (
        ENTRYPOINT,
        HANDLER,
        ADMIN_RETRY,
        BASE,
        PREPARATION,
        SUMMARY,
        DELIVERY,
        RETRY,
        RETENTION,
        CONFIG,
        *CONTRACTS,
        *SMOKE_FILES,
    )
    missing = [file for file in files if not file.is_file()]
    for file in missing:
        error("Не найден обязательный core backend файл", file)
    if missing:
        return 1

    errors = 0
    entrypoint = read(ENTRYPOINT)
    handler = read(HANDLER)
    admin_retry = read(ADMIN_RETRY)
    base = read(BASE)
    preparation = read(PREPARATION)
    summary = read(SUMMARY)
    delivery = read(DELIVERY)
    retry = read(RETRY)
    retention = read(RETENTION)
    config = read(CONFIG)
    contracts = "\n".join(read(file).casefold() for file in CONTRACTS)
    smoke = "\n".join(read(file).casefold() for file in SMOKE_FILES)

    errors += require(entrypoint, ("import './handler.ts'",), ENTRYPOINT, "Entrypoint")
    errors += require(
        handler,
        (
            "schema_version=1",
            "createClient",
            "ALLOWED_ORIGINS.has(normalizeOrigin(origin))",
            "MAX_BODY_BYTES",
            "cleanRequestId",
            "normalizeRussianPhone",
            "findExistingLead",
            "consume_broker_lead_rate_limit",
            "buildLeadRow",
            "broker_lead_events",
            "claim_broker_lead_notification",
            "complete_broker_lead_notification",
            "broker_lead_notification_summary",
            "deliverNotification",
            "function successResponse",
            "function errorResponse",
            "error_code: errorCode",
            "request_id: correlationRequestId(requestId)",
            "const correlationId = crypto.randomUUID();",
            "errorResponse('request_rejected', 202",
            "errorResponse('validation_failed', 422",
            "errorResponse('rate_limit_exceeded', 429",
            "TELEGRAM_BOT_TOKEN",
            "SUPABASE_SERVICE_ROLE_KEY",
            "'Cache-Control': 'no-store'",
        ),
        HANDLER,
        "Public handler",
    )
    errors += require(
        admin_retry,
        (
            "NOTIFICATION_ADMIN_TOKEN",
            "secureTokenEqual",
            "crypto.subtle.digest('SHA-256'",
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
        ADMIN_RETRY,
        "Admin retry",
    )

    for forbidden in (
        "origin.startsWith(",
        "ALLOWED_ORIGINS.some((item) => origin.startsWith(item))",
        "cleanText(payload.user_agent",
        "last_payload",
        "service_role_key: ",
        "telegram_bot_token: ",
        "telegramSummary(row)",
        "return jsonResponse({ ok: false",
        "blocked: true",
        "errors: validation.errors",
        "attempt_count: rateLimit.attemptCount",
        "rate_limit: rateLimit.limit",
    ):
        if forbidden.casefold() in handler.casefold():
            error(f"Handler содержит небезопасный или устаревший фрагмент: {forbidden}", HANDLER)
            errors += 1

    if "Access-Control-Allow-Origin" in admin_retry:
        error("Административная retry-функция не должна разрешать CORS", ADMIN_RETRY)
        errors += 1
    if "reason_comment" in admin_retry or "admin_comment" in admin_retry:
        error("Retry-функция не должна принимать свободный административный комментарий", ADMIN_RETRY)
        errors += 1

    migration_checks = (
        (
            base,
            BASE,
            (
                "broker_leads_request_id_uidx",
                "broker_lead_events",
                "broker_lead_rate_limits",
                "consume_broker_lead_rate_limit",
                "purge_broker_lead_rate_limits",
                "security definer",
                "enable row level security",
                "raw_payload jsonb",
                "tracking jsonb",
                "qualification jsonb",
                "spam_check jsonb",
            ),
        ),
        (
            preparation,
            PREPARATION,
            (
                "journey_type text",
                "journey_stage text",
                "journey_scenario_slug text",
                "preparation jsonb",
                "preparation_completed jsonb",
                "remaining_questions text",
                "sync_broker_lead_preparation",
                "raw_payload -> 'preparation'",
            ),
        ),
        (
            summary,
            SUMMARY,
            (
                "broker_lead_notification_summary",
                "returns text",
                "security definer",
                "broker_lead_not_found",
                "preparation_completed",
                "to service_role",
            ),
        ),
        (
            delivery,
            DELIVERY,
            (
                "notification_attempt_count integer",
                "claim_broker_lead_notification",
                "complete_broker_lead_notification",
                "notification_status = 'sending'",
                "interval '15 minutes'",
                "to service_role",
            ),
        ),
        (
            retry,
            RETRY,
            (
                "notification_manual_retry_count integer",
                "request_broker_lead_notification_retry",
                "and leads.notification_status = 'failed'",
                "broker_lead_notification_queue_health",
                "to service_role",
            ),
        ),
        (
            retention,
            RETENTION,
            (
                "retention_hold boolean not null default false",
                "anonymized_at timestamptz",
                "enabled boolean not null default false",
                "broker_lead_retention_preview",
                "apply_broker_lead_retention",
                "APPLY_BROKER_RETENTION",
                "to service_role",
            ),
        ),
    )
    for text, file, markers in migration_checks:
        errors += require(text, markers, file, "Migration")

    if "last_payload" in base:
        error("Rate limit не должен хранить полный payload", BASE)
        errors += 1
    if "delete from public.broker_leads" in retention.casefold():
        error("Retention не должен физически удалять лиды", RETENTION)
        errors += 1
    if "cron.schedule" in retention.casefold() or "set enabled = true" in retention.casefold():
        error("Retention migration не должна автоматически включать policy или Cron", RETENTION)
        errors += 1
    if "to anon" in summary.casefold() or "to authenticated" in summary.casefold():
        error("Сводка не должна быть доступна публичным ролям", SUMMARY)
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
        "request_broker_lead_notification_retry",
        "broker_lead_notification_queue_health",
        "broker_lead_retention_preview",
        "единый успешный envelope",
        "единый error envelope",
        "endpoint должен оставаться пустым",
    ):
        if marker not in contracts:
            error(f"Контракты не содержат marker: {marker}", CONTRACTS[0])
            errors += 1

    for marker in (
        "проверка миграций",
        "cors preflight",
        "идемпотентность",
        "request_rejected",
        "rate_limit_exceeded",
        "backend_migration_required",
        "validation_failed",
        "lead_storage_failed",
        "telegram",
        "проверка прав",
        "проверка hybrid",
        "откат",
    ):
        if marker not in smoke:
            error(f"Smoke-чеклисты не содержат сценарий: {marker}", SMOKE_FILES[0])
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

    if errors:
        print(f"Core аудит Supabase backend завершён с ошибками: {errors}")
        return 1

    print(
        "Core аудит Supabase backend успешно завершён: public/admin handlers, идемпотентность, rate limit, "
        "success/error envelopes, notification pipeline, core migrations, документы и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
