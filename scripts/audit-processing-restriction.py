#!/usr/bin/env python3
"""Проверяет operational guard для processing_restricted без активации Supabase."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607140003_broker_lead_operational_guard.sql"
PRIVACY_MIGRATION = ROOT / "supabase/migrations/202607140002_broker_lead_privacy_requests.sql"
CONTRACT = ROOT / "docs/operational-restriction-contract.md"
SMOKE = ROOT / "docs/supabase-operational-restriction-smoke.md"
CONFIG = ROOT / "_config.yml"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def require(text: str, markers: tuple[str, ...], file: Path) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"Отсутствует обязательный processing-restriction маркер: {marker}", file)
            errors += 1
    return errors


def section(text: str, start: str, end: str | None = None) -> str:
    if start not in text:
        return ""
    result = text.split(start, 1)[1]
    return result.split(end, 1)[0] if end and end in result else result


def main() -> int:
    required = (MIGRATION, PRIVACY_MIGRATION, CONTRACT, SMOKE, CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл operational guard", file)
    if missing:
        return 1

    errors = 0
    migration = read(MIGRATION)
    migration_lower = migration.casefold()
    privacy = read(PRIVACY_MIGRATION).casefold()
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    config = read(CONFIG)

    errors += require(
        migration,
        (
            "broker_lead_operational_guard",
            "broker_lead_operational_snapshot",
            "notification_claim",
            "notification_complete",
            "notification_summary",
            "notification_retry",
            "crm_read",
            "crm_update",
            "export",
            "follow_up",
            "processing_restricted",
            "retention_hold",
            "already_anonymized",
            "broker_operational_action_invalid",
            "broker_operational_snapshot_action_invalid",
            "claim_broker_lead_notification",
            "complete_broker_lead_notification",
            "broker_lead_notification_summary",
            "request_broker_lead_notification_retry",
            "broker_lead_notification_queue_health",
            "leads.processing_restricted = false",
            "leads.retention_hold = false",
            "leads.anonymized_at is null",
            "enforce_broker_lead_operational_restriction",
            "enforce_broker_lead_event_restriction",
            "broker_leads_guard_restricted_updates",
            "broker_lead_events_guard_restricted_insert",
            "privacy_request_started",
            "privacy_request_verified",
            "privacy_request_completed",
            "privacy_request_cancelled",
            "from public, anon, authenticated",
            "to service_role",
            "set search_path = ''",
        ),
        MIGRATION,
    )

    expected_actions = {
        "notification_claim",
        "notification_complete",
        "notification_summary",
        "notification_retry",
        "crm_read",
        "crm_update",
        "export",
        "follow_up",
    }
    guard_head = section(
        migration_lower,
        "create or replace function public.broker_lead_operational_guard",
        "create or replace function public.broker_lead_operational_snapshot",
    )
    action_match = re.search(r"v_action_code\s+not\s+in\s*\((.*?)\)", guard_head, re.S)
    found_actions = set(re.findall(r"'([a-z_]+)'", action_match.group(1))) if action_match else set()
    if found_actions != expected_actions:
        error("Whitelist action_code operational guard изменён или разобран неоднозначно", MIGRATION)
        errors += 1

    snapshot = section(
        migration_lower,
        "create or replace function public.broker_lead_operational_snapshot",
        "create or replace function public.broker_lead_notification_summary",
    )
    for forbidden in ("raw_payload", "spam_check", "notification_last_error", "service_role_key"):
        if forbidden in snapshot:
            error(f"Operational snapshot содержит запрещённое поле: {forbidden}", MIGRATION)
            errors += 1
    for required_marker in ("'crm_read'", "'export'", "'follow_up'", "broker_lead_operational_guard"):
        if required_marker not in snapshot:
            error(f"Operational snapshot не содержит обязательный guard-маркер: {required_marker}", MIGRATION)
            errors += 1

    summary = section(
        migration_lower,
        "create or replace function public.broker_lead_notification_summary",
        "create or replace function public.claim_broker_lead_notification",
    )
    claim = section(
        migration_lower,
        "create or replace function public.claim_broker_lead_notification",
        "create or replace function public.complete_broker_lead_notification",
    )
    complete = section(
        migration_lower,
        "create or replace function public.complete_broker_lead_notification",
        "create or replace function public.request_broker_lead_notification_retry",
    )
    retry = section(
        migration_lower,
        "create or replace function public.request_broker_lead_notification_retry",
        "create or replace function public.broker_lead_notification_queue_health",
    )
    health = section(
        migration_lower,
        "create or replace function public.broker_lead_notification_queue_health",
        "create or replace function public.enforce_broker_lead_operational_restriction",
    )

    for function_name, function_text, action_code in (
        ("notification summary", summary, "notification_summary"),
        ("notification claim", claim, "notification_claim"),
        ("notification complete", complete, "notification_complete"),
        ("notification retry", retry, "notification_retry"),
    ):
        if "broker_lead_operational_guard" not in function_text or action_code not in function_text:
            error(f"{function_name} не вызывает единый operational guard", MIGRATION)
            errors += 1

    for marker in (
        "leads.processing_restricted = false",
        "leads.retention_hold = false",
        "leads.anonymized_at is null",
    ):
        if marker not in claim or marker not in complete or marker not in retry or marker not in health:
            error(f"Notification/health контур не содержит fail-closed условие: {marker}", MIGRATION)
            errors += 1

    update_trigger = section(
        migration_lower,
        "create or replace function public.enforce_broker_lead_operational_restriction",
        "create or replace function public.enforce_broker_lead_event_restriction",
    )
    for marker in (
        "old.anonymized_at is not null",
        "broker_lead_already_anonymized",
        "requests.status = 'verified'",
        "requests.action_code = 'anonymize'",
        "new.phone = '[anonymized]'",
        "new.raw_payload = '{}'::jsonb",
        "new.retention_reason_code = 'manual_privacy_request'",
        "v_request.previous_retention_hold",
        "v_request.previous_processing_restricted",
        "broker_lead_processing_restricted",
    ):
        if marker not in update_trigger:
            error(f"Update trigger не содержит обязательную защиту: {marker}", MIGRATION)
            errors += 1

    event_trigger = section(
        migration_lower,
        "create or replace function public.enforce_broker_lead_event_restriction",
        "drop trigger if exists broker_leads_guard_restricted_updates",
    )
    allowed_privacy_events = set(re.findall(r"'((?:privacy_request_)[a-z_]+)'", event_trigger))
    expected_privacy_events = {
        "privacy_request_started",
        "privacy_request_verified",
        "privacy_request_completed",
        "privacy_request_cancelled",
    }
    if allowed_privacy_events != expected_privacy_events:
        error("Event trigger разрешает неожиданный набор событий restricted заявки", MIGRATION)
        errors += 1

    for forbidden in (
        "delete from public.broker_leads",
        "truncate public.broker_leads",
        "cron.schedule",
        "http_post",
        "net.http",
        "to anon",
        "to authenticated",
        "access-control-allow-origin",
    ):
        if forbidden in migration_lower:
            error(f"Operational guard migration содержит запрещённый фрагмент: {forbidden}", MIGRATION)
            errors += 1

    for marker in (
        "processing_restricted boolean not null default false",
        "start_broker_lead_privacy_request",
        "verify_broker_lead_privacy_request",
        "apply_broker_lead_privacy_request",
        "cancel_broker_lead_privacy_request",
        "retention_hold = true",
        "processing_restricted = true",
    ):
        if marker not in privacy:
            error(f"Privacy migration не поддерживает operational guard: {marker}", PRIVACY_MIGRATION)
            errors += 1

    errors += require(
        contract,
        (
            "broker_lead_operational_guard",
            "broker_lead_operational_snapshot",
            "processing_restricted = true",
            "retention_hold = true",
            "anonymized_at is not null",
            "crm_update",
            "export",
            "follow_up",
            "raw_payload",
            "прямое чтение таблицы",
            "privacy_request_completed",
            "web3forms email",
            "девяти миграций",
            "endpoint: \"\"",
        ),
        CONTRACT,
    )
    errors += require(
        smoke,
        (
            "девять миграций",
            "unrestricted guard",
            "restrict processing",
            "уведомления restricted заявки",
            "privacy anonymize",
            "privacy cancel",
            "broker_lead_processing_restricted",
            "broker_lead_already_anonymized",
            "notification health",
            "raw_payload",
            "web3forms email",
            "mode: web3forms",
        ),
        SMOKE,
    )

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До operational guard smoke режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до полной приёмки", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит processing restriction завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит processing restriction успешно завершён: единый guard, snapshot без raw payload, "
        "notification/health блокировки, update/event triggers, privacy apply/cancel, права, smoke "
        "и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
