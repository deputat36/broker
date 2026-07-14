#!/usr/bin/env python3
"""Агрегирует готовность всех Supabase-контуров, не заменяя специализированные аудиты."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "supabase/migrations/202607070001_create_broker_leads.sql",
    ROOT / "supabase/migrations/202607130002_broker_leads_v2.sql",
    ROOT / "supabase/migrations/202607130003_broker_lead_preparation.sql",
    ROOT / "supabase/migrations/202607130004_broker_lead_notification_summary.sql",
    ROOT / "supabase/migrations/202607130005_broker_lead_notification_delivery.sql",
    ROOT / "supabase/migrations/202607130006_broker_lead_notification_manual_retry.sql",
    ROOT / "supabase/migrations/202607140001_broker_lead_retention.sql",
    ROOT / "supabase/migrations/202607140002_broker_lead_privacy_requests.sql",
    ROOT / "supabase/migrations/202607140003_broker_lead_operational_guard.sql",
    ROOT / "supabase/migrations/202607140004_broker_lead_restricted_delivery_status.sql",
)
AUDITS = (
    ROOT / "scripts/audit-supabase-backend.py",
    ROOT / "scripts/audit-supabase-function-config.py",
    ROOT / "scripts/audit-notification-retry.py",
    ROOT / "scripts/audit-notification-health.py",
    ROOT / "scripts/audit-data-retention.py",
    ROOT / "scripts/audit-privacy-requests.py",
    ROOT / "scripts/audit-processing-restriction.py",
    ROOT / "scripts/audit-restricted-delivery-response.py",
)
DOCS = (
    ROOT / "docs/supabase-migration-order.md",
    ROOT / "docs/lead-endpoint-contract.md",
    ROOT / "docs/supabase-backend-smoke.md",
    ROOT / "docs/data-retention-contract.md",
    ROOT / "docs/supabase-retention-smoke.md",
    ROOT / "docs/privacy-request-contract.md",
    ROOT / "docs/supabase-privacy-request-smoke.md",
    ROOT / "docs/operational-restriction-contract.md",
    ROOT / "docs/supabase-operational-restriction-smoke.md",
    ROOT / "docs/restricted-delivery-response-contract.md",
    ROOT / "docs/supabase-restricted-delivery-response-smoke.md",
)
WORKFLOW = ROOT / ".github/workflows/pages.yml"
CONFIG = ROOT / "_config.yml"


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    required = (*MIGRATIONS, *AUDITS, *DOCS, WORKFLOW, CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл aggregate Supabase readiness", file)
    if missing:
        return 1

    errors = 0
    workflow = read(WORKFLOW)
    config = read(CONFIG)
    migration_order = read(DOCS[0]).casefold()
    retention = read(MIGRATIONS[-4]).casefold()
    privacy = read(MIGRATIONS[-3]).casefold()
    operational = read(MIGRATIONS[-2]).casefold()
    restricted_response = read(MIGRATIONS[-1]).casefold()
    all_docs = "\n".join(read(file).casefold() for file in DOCS)

    migration_names = [file.name for file in MIGRATIONS]
    if migration_names != sorted(migration_names):
        error("Миграции перечислены не в лексикографическом порядке применения", MIGRATIONS[0])
        errors += 1
    if len(set(migration_names)) != 10:
        error("Aggregate readiness должен проверять ровно десять уникальных миграций", MIGRATIONS[0])
        errors += 1

    for index, migration_name in enumerate(migration_names, start=1):
        marker = f"{index}. `{migration_name}`"
        if marker not in migration_order:
            error(f"Канонический порядок не содержит миграцию на позиции {index}: {migration_name}", DOCS[0])
            errors += 1

    for marker in (
        "единственным актуальным списком миграций",
        "python3 scripts/audit-supabase-readiness.py",
        "mode: \"web3forms\"",
        "endpoint: \"\"",
        "не включает `hybrid`",
    ):
        if marker not in migration_order:
            error(f"Канонический порядок не содержит обязательный marker: {marker}", DOCS[0])
            errors += 1

    workflow_commands = (
        "python3 scripts/audit-supabase-backend.py",
        "python3 scripts/audit-supabase-function-config.py",
        "python3 scripts/audit-notification-retry.py",
        "python3 scripts/audit-notification-health.py",
        "python3 scripts/audit-data-retention.py",
        "python3 scripts/audit-privacy-requests.py",
        "python3 scripts/audit-processing-restriction.py",
        "python3 scripts/audit-restricted-delivery-response.py",
        "python3 scripts/audit-supabase-readiness.py",
    )
    for command in workflow_commands:
        if command not in workflow:
            error(f"Pages workflow не запускает обязательный Supabase audit: {command}", WORKFLOW)
            errors += 1

    command_positions = [workflow.find(command) for command in workflow_commands]
    if command_positions != sorted(command_positions) or any(position < 0 for position in command_positions):
        error("Aggregate readiness должен запускаться после всех специализированных source-аудитов", WORKFLOW)
        errors += 1

    for marker in (
        "broker_lead_retention_preview",
        "apply_broker_lead_retention",
        "enabled boolean not null default false",
        "delete from public.broker_leads",
    ):
        present = marker in retention
        if marker == "delete from public.broker_leads":
            if present:
                error("Retention не должен физически удалять broker_leads", MIGRATIONS[-4])
                errors += 1
        elif not present:
            error(f"Retention migration не содержит обязательный marker: {marker}", MIGRATIONS[-4])
            errors += 1

    for marker in (
        "broker_lead_privacy_request_preview",
        "start_broker_lead_privacy_request",
        "verify_broker_lead_privacy_request",
        "apply_broker_lead_privacy_request",
        "cancel_broker_lead_privacy_request",
        "processing_restricted boolean not null default false",
        "leads.notification_status not in ('pending', 'sending')",
        "from public, anon, authenticated",
        "to service_role",
    ):
        if marker not in privacy:
            error(f"Privacy migration не содержит обязательный marker: {marker}", MIGRATIONS[-3])
            errors += 1

    for marker in (
        "broker_lead_operational_guard",
        "broker_lead_operational_snapshot",
        "notification_claim",
        "notification_retry",
        "crm_update",
        "export",
        "follow_up",
        "enforce_broker_lead_operational_restriction",
        "enforce_broker_lead_event_restriction",
        "leads.processing_restricted = false",
        "leads.retention_hold = false",
        "leads.anonymized_at is null",
        "from public, anon, authenticated",
        "to service_role",
    ):
        if marker not in operational:
            error(f"Operational guard migration не содержит обязательный marker: {marker}", MIGRATIONS[-2])
            errors += 1

    if "delete from public.broker_leads" in operational:
        error("Operational guard не должен физически удалять broker_leads", MIGRATIONS[-2])
        errors += 1
    if "cron.schedule" in operational or "http_post" in operational:
        error("Operational guard migration не должна создавать Cron или внешние HTTP-вызовы", MIGRATIONS[-2])
        errors += 1

    for marker in (
        "create or replace function public.claim_broker_lead_notification",
        "leads.processing_restricted = false",
        "leads.retention_hold = false",
        "leads.anonymized_at is null",
        "then 'disabled'::text",
        "from public, anon, authenticated",
        "to service_role",
    ):
        if marker not in restricted_response:
            error(f"Restricted delivery migration не содержит обязательный marker: {marker}", MIGRATIONS[-1])
            errors += 1

    for forbidden in ("delete from public.broker_leads", "cron.schedule", "http_post", "net.http"):
        if forbidden in restricted_response:
            error(f"Restricted delivery migration содержит запрещённый marker: {forbidden}", MIGRATIONS[-1])
            errors += 1

    for marker in (
        "десять миграций",
        "web3forms",
        "supabase",
        "retention_hold",
        "processing_restricted",
        "broker_lead_operational_guard",
        "broker_lead_operational_snapshot",
        "notification_status\": \"disabled",
        "restricted",
        "pending",
        "sending",
        "провер",
        "privacy",
        "не удаляет",
        "raw_payload",
    ):
        if marker not in all_docs:
            error(f"Комплект Supabase документов не содержит marker: {marker}", DOCS[0])
            errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До общей Supabase-приёмки режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("До общей Supabase-приёмки endpoint должен оставаться пустым", CONFIG)
        errors += 1

    if errors:
        print(f"Aggregate Supabase readiness завершён с ошибками: {errors}")
        return 1

    print(
        "Aggregate Supabase readiness успешно завершён: канонический порядок из десяти миграций, "
        "специализированные source-аудиты, retention, privacy, operational guard, browser-safe disabled "
        "response, документы, порядок CI и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
