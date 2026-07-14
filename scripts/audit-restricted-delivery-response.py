#!/usr/bin/env python3
"""Проверяет browser-safe и минимальный ответ restricted/hold/anonymized duplicate-заявок."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607140004_broker_lead_restricted_delivery_status.sql"
OPERATIONAL_MIGRATION = ROOT / "supabase/migrations/202607140003_broker_lead_operational_guard.sql"
HANDLER = ROOT / "supabase/functions/broker-public-lead/handler.ts"
CONTRACT = ROOT / "docs/restricted-delivery-response-contract.md"
SMOKE = ROOT / "docs/supabase-restricted-delivery-response-smoke.md"
WORKFLOW = ROOT / ".github/workflows/pages.yml"
CONFIG = ROOT / "_config.yml"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def require(text: str, markers: tuple[str, ...], file: Path) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"Отсутствует обязательный restricted-response маркер: {marker}", file)
            errors += 1
    return errors


def main() -> int:
    required = (MIGRATION, OPERATIONAL_MIGRATION, HANDLER, CONTRACT, SMOKE, WORKFLOW, CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл restricted delivery response", file)
    if missing:
        return 1

    errors = 0
    migration = read(MIGRATION)
    migration_lower = migration.casefold()
    operational = read(OPERATIONAL_MIGRATION).casefold()
    handler = read(HANDLER)
    handler_lower = handler.casefold()
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    workflow = read(WORKFLOW)
    config = read(CONFIG)

    errors += require(
        migration,
        (
            "create or replace function public.claim_broker_lead_notification",
            "set search_path = ''",
            "leads.processing_restricted = false",
            "leads.retention_hold = false",
            "leads.anonymized_at is null",
            "then 'disabled'::text",
            "return query select",
            "false,",
            "coalesce(v_status, 'missing')",
            "from public, anon, authenticated",
            "to service_role",
        ),
        MIGRATION,
    )

    update_section = migration_lower.split("update public.broker_leads as leads", 1)[-1].split("if found then", 1)[0]
    for marker in (
        "notification_attempt_count = leads.notification_attempt_count + 1",
        "leads.processing_restricted = false",
        "leads.retention_hold = false",
        "leads.anonymized_at is null",
    ):
        if marker not in update_section:
            error(f"Notification update не защищён маркером: {marker}", MIGRATION)
            errors += 1

    disabled_section = migration_lower.split("select\n    case", 1)[-1].split("into v_status", 1)[0]
    for marker in (
        "leads.processing_restricted",
        "leads.retention_hold",
        "leads.anonymized_at is not null",
        "then 'disabled'::text",
    ):
        if marker not in disabled_section:
            error(f"Browser-safe disabled не покрывает состояние: {marker}", MIGRATION)
            errors += 1

    for forbidden in (
        "update public.broker_leads set processing_restricted",
        "delete from public.broker_leads",
        "truncate public.broker_leads",
        "cron.schedule",
        "http_post",
        "net.http",
        "telegram_bot_token",
    ):
        if forbidden in migration_lower:
            error(f"Restricted-response migration содержит запрещённый фрагмент: {forbidden}", MIGRATION)
            errors += 1

    errors += require(
        handler,
        (
            "type NotificationStatus = 'pending' | 'sending' | 'sent' | 'failed' | 'disabled';",
            "['pending', 'sending', 'sent', 'failed', 'disabled'].includes(status)",
            "processing_restricted, retention_hold, anonymized_at",
            "function isOperationallyRestricted(existing: JsonRecord): boolean",
            "existing.processing_restricted === true",
            "existing.retention_hold === true",
            "Boolean(existing.anonymized_at)",
            "if (isOperationallyRestricted(existing)) {",
            "notification_status: 'disabled'",
            "if (!claim.claimed) return normalizeNotificationStatus(claim.status);",
        ),
        HANDLER,
    )
    if "'restricted'" in handler.split("type NotificationStatus", 1)[-1].split(";", 1)[0]:
        error("Публичный NotificationStatus не должен раскрывать внутренний restricted", HANDLER)
        errors += 1

    restricted_start = "if (isOperationallyRestricted(existing)) {"
    restricted_end = "\n  }\n\n  const leadId"
    if restricted_start in handler and restricted_end in handler.split(restricted_start, 1)[-1]:
        restricted_branch = handler.split(restricted_start, 1)[-1].split(restricted_end, 1)[0]
        errors += require(
            restricted_branch,
            (
                "ok: true",
                "success: true",
                "duplicate: true",
                "request_id: existing.request_id || requestId",
                "notification_status: 'disabled'",
                "}, 200, origin)",
            ),
            HANDLER,
        )
        for forbidden in (
            "lead_id",
            "crm_status",
            "technical_priority",
            "qualification",
            "deliverNotification",
            "existing.id",
            "processing_restricted",
            "retention_hold",
            "anonymized_at",
        ):
            if forbidden in restricted_branch:
                error(f"Restricted duplicate раскрывает или использует запрещённое поле: {forbidden}", HANDLER)
                errors += 1
    else:
        error("Не удалось выделить минимальную restricted-ветку duplicateResponse", HANDLER)
        errors += 1

    duplicate_function = handler_lower.split("async function duplicateresponse", 1)[-1].split("deno.serve", 1)[0]
    if duplicate_function.find("isoperationallyrestricted(existing)") > duplicate_function.find("delivernotification"):
        error("Restricted duplicate должен завершаться до вызова deliverNotification", HANDLER)
        errors += 1

    errors += require(
        operational,
        (
            "then 'restricted'",
            "notification_retry",
            "processing_restricted",
            "retention_hold",
            "anonymized_at is not null",
        ),
        OPERATIONAL_MIGRATION,
    )

    errors += require(
        contract,
        (
            "notification_status\": \"disabled",
            "request_id",
            "http-ответ остаётся `200`",
            "минимизация данных",
            "внутренний `lead_id`",
            "`crm_status`",
            "`technical_priority`",
            "объект `qualification`",
            "внутренний административный статус",
            "`restricted`",
            "не увеличивать `notification_attempt_count`",
            "web3forms email",
        ),
        CONTRACT,
    )
    errors += require(
        smoke,
        (
            "применены десять миграций",
            "current_status = disabled",
            "request_id\": \"<request_id>",
            "notification_status\": \"disabled",
            "restricted duplicate не должен содержать",
            "`lead_id`",
            "`crm_status`",
            "`technical_priority`",
            "`qualification`",
            "статус не заменён на `pending`",
            "внутренний `notification_status = restricted`",
            "telegram-сообщение не отправлено",
            "проверка прав",
            "mode: \"web3forms\"",
            "endpoint: \"\"",
        ),
        SMOKE,
    )

    command = "python3 scripts/audit-restricted-delivery-response.py"
    if command not in workflow:
        error("Pages workflow не запускает restricted delivery response audit", WORKFLOW)
        errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До restricted-response smoke рабочий режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до общей приёмки", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит restricted delivery response завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит restricted delivery response успешно завершён: SQL возвращает browser-safe disabled, "
        "restricted duplicate минимизирован до request_id и статуса доставки, Telegram/счётчики не запускаются, "
        "административный retry сохраняет диагностику, документы, smoke и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())