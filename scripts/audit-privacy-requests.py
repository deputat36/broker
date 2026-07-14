#!/usr/bin/env python3
"""Проверяет закрытый индивидуальный privacy workflow без активации Supabase."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607140002_broker_lead_privacy_requests.sql"
CONTRACT = ROOT / "docs/privacy-request-contract.md"
SMOKE = ROOT / "docs/supabase-privacy-request-smoke.md"
POLICY = ROOT / "policy.md"
CONSENT = ROOT / "personal-data-consent.md"
CONFIG = ROOT / "_config.yml"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def require(text: str, markers: tuple[str, ...], file: Path) -> int:
    missing = [marker for marker in markers if marker not in text]
    for marker in missing:
        error(f"Отсутствует обязательный privacy-маркер: {marker}", file)
    return len(missing)


def main() -> int:
    required = (MIGRATION, CONTRACT, SMOKE, POLICY, CONSENT, CONFIG)
    missing_files = [file for file in required if not file.is_file()]
    for file in missing_files:
        error("Не найден обязательный файл privacy workflow", file)
    if missing_files:
        return 1

    migration = read(MIGRATION)
    lower = migration.casefold()
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    policy = read(POLICY).casefold()
    consent = read(CONSENT).casefold()
    config = read(CONFIG)
    errors = 0

    errors += require(
        migration,
        (
            "processing_restricted boolean not null default false",
            "broker_lead_privacy_requests",
            "action_code in ('anonymize', 'restrict_processing')",
            "status in ('pending_verification', 'verified', 'completed', 'cancelled')",
            "same_contact_channel",
            "callback_verified",
            "documented_internal_check",
            "identity_not_verified",
            "duplicate_request",
            "request_withdrawn",
            "broker_lead_privacy_request_preview",
            "start_broker_lead_privacy_request",
            "verify_broker_lead_privacy_request",
            "apply_broker_lead_privacy_request",
            "cancel_broker_lead_privacy_request",
            "START_BROKER_PRIVACY_REQUEST",
            "VERIFY_BROKER_PRIVACY_REQUEST",
            "APPLY_BROKER_PRIVACY_REQUEST",
            "CANCEL_BROKER_PRIVACY_REQUEST",
            "broker_privacy_notification_unresolved",
            "broker_privacy_request_not_verified",
            "broker_privacy_lead_state_changed",
            "retention_reason_code = 'manual_privacy_request'",
            "raw_payload = '{}'::jsonb",
            "phone = '[anonymized]'",
            "privacy_request_started",
            "privacy_request_verified",
            "privacy_request_completed",
            "privacy_request_cancelled",
            "from public, anon, authenticated",
            "to service_role",
            "enable row level security",
        ),
        MIGRATION,
    )

    for forbidden in (
        "delete from public.broker_leads",
        "truncate public.broker_leads",
        "drop table public.broker_leads",
        "cron.schedule",
        "http_post",
        "net.http",
        "p_phone",
        "p_client_name",
        "p_city",
        "p_email",
        "admin_comment",
        "operator_comment",
        "free_text",
    ):
        if forbidden in lower:
            error(f"Privacy migration содержит запрещённый фрагмент: {forbidden}", MIGRATION)
            errors += 1

    table_section = lower.split(
        "create table if not exists public.broker_lead_privacy_requests", 1
    )[-1].split("create unique index", 1)[0]
    for forbidden_column in (
        "phone text",
        "client_name text",
        "city text",
        "email text",
        "comment text",
        "document bytea",
        "document_url",
        "document_path",
    ):
        if forbidden_column in table_section:
            error(f"Таблица privacy requests содержит запрещённое поле: {forbidden_column}", MIGRATION)
            errors += 1

    start = lower.split(
        "create or replace function public.start_broker_lead_privacy_request", 1
    )[-1].split("create or replace function public.verify_broker_lead_privacy_request", 1)[0]
    errors += require(
        start,
        (
            "where leads.id = p_lead_id",
            "and leads.request_id = p_request_id",
            "if v_lead.retention_hold",
            "if v_lead.notification_status in ('pending', 'sending')",
            "retention_hold = true",
            "processing_restricted = true",
        ),
        MIGRATION,
    )

    apply = lower.split(
        "create or replace function public.apply_broker_lead_privacy_request", 1
    )[-1].split("create or replace function public.cancel_broker_lead_privacy_request", 1)[0]
    errors += require(
        apply,
        (
            "v_request.status <> 'verified'",
            "v_request.verified_at is null",
            "leads.retention_hold = true",
            "leads.processing_restricted = true",
            "leads.notification_status not in ('pending', 'sending')",
            "retention_hold = false",
            "processing_restricted = true",
        ),
        MIGRATION,
    )

    cancel = lower.split(
        "create or replace function public.cancel_broker_lead_privacy_request", 1
    )[-1]
    errors += require(
        cancel,
        (
            "v_request.previous_retention_hold",
            "v_request.previous_processing_restricted",
            "v_request.status not in ('pending_verification', 'verified')",
        ),
        MIGRATION,
    )

    errors += require(
        contract,
        (
            "не выполняет поиск по телефону",
            "lead_id",
            "request_id",
            "restrict_processing",
            "anonymize",
            "pending_verification → verified → completed",
            "start_broker_lead_privacy_request",
            "verify_broker_lead_privacy_request",
            "apply_broker_lead_privacy_request",
            "cancel_broker_lead_privacy_request",
            "web3forms email",
            "не удаляет",
            "endpoint: \"\"",
        ),
        CONTRACT,
    )
    errors += require(
        smoke,
        (
            "восемь миграций",
            "проверить права",
            "lead_not_found",
            "notification_unresolved",
            "existing_retention_hold",
            "broker_privacy_open_request_exists",
            "broker_privacy_request_not_verified",
            "broker_privacy_lead_state_changed",
            "строка `broker_leads` физически не удалена",
            "отсутствия поиска по персональным данным",
            "web3forms email",
            "откат",
        ),
        SMOKE,
    )

    for marker in ("провер", "личност", "удален", "web3forms", "email", "supabase"):
        if marker not in policy:
            error(f"Публичная политика не отражает privacy-процесс: {marker}", POLICY)
            errors += 1
    for marker in ("отоз", "провер", "удален", "web3forms", "supabase"):
        if marker not in consent:
            error(f"Согласие не отражает privacy-процесс: {marker}", CONSENT)
            errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До privacy smoke рабочий режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до полной приёмки", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит privacy workflow завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит privacy workflow успешно завершён: точная идентификация, verification, hold, "
        "pending/sending guard, точечное обезличивание, cancel restore, отсутствие PII-поиска, "
        "публичных прав и hard delete, документы и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
