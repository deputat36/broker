#!/usr/bin/env python3
"""Проверяет безопасную retention policy без применения миграции и активации Supabase."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607140001_broker_lead_retention.sql"
CONTRACT = ROOT / "docs/data-retention-contract.md"
SMOKE = ROOT / "docs/supabase-retention-smoke.md"
POLICY = ROOT / "policy.md"
CONSENT = ROOT / "personal-data-consent.md"
CONFIG = ROOT / "_config.yml"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def require(text: str, markers: tuple[str, ...], file: Path) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"Отсутствует обязательный retention-маркер: {marker}", file)
            errors += 1
    return errors


def main() -> int:
    required = (MIGRATION, CONTRACT, SMOKE, POLICY, CONSENT, CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл retention", file)
    if missing:
        return 1

    errors = 0
    migration = read(MIGRATION)
    migration_lower = migration.casefold()
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    policy = read(POLICY).casefold()
    consent = read(CONSENT).casefold()
    config = read(CONFIG)

    errors += require(
        migration,
        (
            "retention_hold boolean not null default false",
            "anonymized_at timestamptz",
            "retention_reason_code text",
            "broker_lead_retention_settings",
            "enabled boolean not null default false",
            "anonymize_after_days integer not null default 365",
            "delete_events_after_days integer not null default 180",
            "delete_rate_limits_after_days integer not null default 7",
            "terminal_statuses <@ array['closed', 'lost', 'archived', 'cancelled']::text[]",
            "broker_lead_retention_runs",
            "broker_lead_retention_preview",
            "apply_broker_lead_retention",
            "APPLY_BROKER_RETENTION",
            "broker_retention_confirmation_required",
            "broker_retention_disabled",
            "leads.retention_hold = false",
            "leads.status in ('closed', 'lost', 'archived', 'cancelled')",
            "leads.notification_status in ('sent', 'disabled')",
            "flags.notification_status in ('pending', 'sending', 'failed')",
            "leads.anonymized_at is not null",
            "purge_broker_lead_rate_limits",
            "raw_payload = '{}'::jsonb",
            "phone = '[anonymized]'",
            "retention_reason_code = 'scheduled_anonymization'",
            "from public, anon, authenticated",
            "to service_role",
            "enable row level security",
        ),
        MIGRATION,
    )

    forbidden_sql = (
        "delete from public.broker_leads",
        "truncate public.broker_leads",
        "drop table public.broker_leads",
        "cron.schedule",
        "http_post",
        "net.http",
        "enabled boolean not null default true",
        "set enabled = true",
        "sqlerrm",
        "error_message",
    )
    for fragment in forbidden_sql:
        if fragment in migration_lower:
            error(f"Retention migration содержит запрещённый фрагмент: {fragment}", MIGRATION)
            errors += 1

    allowed_statuses = {"closed", "lost", "archived", "cancelled"}
    status_literals = set(
        re.findall(
            r"terminal_statuses\s*<@\s*array\[([^\]]+)\]",
            migration_lower,
        )[0].replace("'", "").replace(" ", "").split(",")
    ) if "terminal_statuses <@ array[" in migration_lower else set()
    if status_literals != allowed_statuses:
        error("Жёсткий whitelist terminal-статусов изменён или разобран неоднозначно", MIGRATION)
        errors += 1

    preview_section = migration_lower.split(
        "create or replace function public.broker_lead_retention_preview", 1
    )[-1].split(
        "create or replace function public.apply_broker_lead_retention", 1
    )[0]
    for marker in (
        "from public.broker_lead_events as events",
        "leads.anonymized_at is not null",
        "leads.anonymized_at is null",
        "and leads.status = any(v_settings.terminal_statuses)",
        "and leads.status in ('closed', 'lost', 'archived', 'cancelled')",
        "and leads.notification_status in ('sent', 'disabled')",
        "make_interval(days => v_settings.anonymize_after_days)",
        "make_interval(days => v_settings.delete_events_after_days)",
    ):
        if marker not in preview_section:
            error(f"Preview не прогнозирует события будущих кандидатов: {marker}", MIGRATION)
            errors += 1

    apply_section = migration_lower.split(
        "create or replace function public.apply_broker_lead_retention", 1
    )[-1]
    if "and leads.notification_status in ('sent', 'disabled')" not in apply_section:
        error("Apply должен защищать pending/sending/failed уведомления", MIGRATION)
        errors += 1
    if "and leads.retention_hold = false" not in apply_section:
        error("Apply должен уважать retention_hold", MIGRATION)
        errors += 1
    if "insert into public.broker_lead_retention_runs" not in apply_section:
        error("Успешный retention-запуск должен фиксироваться агрегированно", MIGRATION)
        errors += 1
    if apply_section.find("insert into public.broker_lead_retention_runs") < apply_section.find("update public.broker_leads"):
        error("Run нельзя фиксировать completed до успешного обезличивания и очистки", MIGRATION)
        errors += 1

    errors += require(
        contract,
        (
            "enabled = false",
            "не считаются утверждённым юридическим сроком",
            "closed",
            "lost",
            "archived",
            "cancelled",
            "pending",
            "sending",
            "failed",
            "retention_hold",
            "apply_broker_retention",
            "delete from public.broker_leads",
            "web3forms и email",
            "не удаляет",
            "cron job намеренно не создаётся",
            "endpoint: \"\"",
        ),
        CONTRACT,
    )
    errors += require(
        smoke,
        (
            "policy_enabled = false",
            "broker_retention_disabled",
            "broker_retention_confirmation_required",
            "старый `new`",
            "старый `closed` + `failed`",
            "retention_hold = true",
            "неизвестный статус",
            "старое событие кандидата учитывается",
            "проверка атомарного отката",
            "строка лида физически не удалена",
            "enabled = false",
            "автоматический cron job отсутствует",
            "web3forms email",
        ),
        SMOKE,
    )

    for marker in (
        "срок хранения",
        "supabase",
        "web3forms",
        "email",
        "не удал",
        "актив",
    ):
        if marker not in policy:
            error(f"Публичная политика не отражает retention-границу: {marker}", POLICY)
            errors += 1

    for marker in ("срок", "supabase", "обновлен", "сервер"):
        if marker not in consent:
            error(f"Текст согласия не отражает будущий серверный срок: {marker}", CONSENT)
            errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До retention smoke рабочий режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до полной приёмки", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит retention завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит retention успешно завершён: policy выключена, active/unresolved/hold защищены, "
        "preview согласован с apply, hard delete и Cron отсутствуют, журнал/документы и пустой endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
