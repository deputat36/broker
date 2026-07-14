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
)
AUDITS = (
    ROOT / "scripts/audit-supabase-backend.py",
    ROOT / "scripts/audit-supabase-function-config.py",
    ROOT / "scripts/audit-notification-retry.py",
    ROOT / "scripts/audit-notification-health.py",
    ROOT / "scripts/audit-data-retention.py",
    ROOT / "scripts/audit-privacy-requests.py",
)
DOCS = (
    ROOT / "docs/lead-endpoint-contract.md",
    ROOT / "docs/supabase-backend-smoke.md",
    ROOT / "docs/data-retention-contract.md",
    ROOT / "docs/supabase-retention-smoke.md",
    ROOT / "docs/privacy-request-contract.md",
    ROOT / "docs/supabase-privacy-request-smoke.md",
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
    privacy = read(MIGRATIONS[-1]).casefold()
    retention = read(MIGRATIONS[-2]).casefold()
    all_docs = "\n".join(read(file).casefold() for file in DOCS)

    migration_names = [file.name for file in MIGRATIONS]
    if migration_names != sorted(migration_names):
        error("Миграции перечислены не в лексикографическом порядке применения", MIGRATIONS[0])
        errors += 1
    if len(set(migration_names)) != 8:
        error("Aggregate readiness должен проверять ровно восемь уникальных миграций", MIGRATIONS[0])
        errors += 1

    workflow_commands = (
        "python3 scripts/audit-supabase-backend.py",
        "python3 scripts/audit-supabase-function-config.py",
        "python3 scripts/audit-notification-retry.py",
        "python3 scripts/audit-notification-health.py",
        "python3 scripts/audit-data-retention.py",
        "python3 scripts/audit-privacy-requests.py",
        "python3 scripts/audit-supabase-readiness.py",
    )
    for command in workflow_commands:
        if command not in workflow:
            error(f"Pages workflow не запускает обязательный Supabase audit: {command}", WORKFLOW)
            errors += 1

    if workflow.find(workflow_commands[-1]) < workflow.find(workflow_commands[0]):
        error("Aggregate readiness должен запускаться после специализированных source-аудитов", WORKFLOW)
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
                error("Retention не должен физически удалять broker_leads", MIGRATIONS[-2])
                errors += 1
        elif not present:
            error(f"Retention migration не содержит обязательный marker: {marker}", MIGRATIONS[-2])
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
            error(f"Privacy migration не содержит обязательный marker: {marker}", MIGRATIONS[-1])
            errors += 1

    for marker in (
        "восемь миграций",
        "web3forms",
        "supabase",
        "retention_hold",
        "pending",
        "sending",
        "провер",
        "privacy",
        "не удаляет",
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
        "Aggregate Supabase readiness успешно завершён: восемь миграций, специализированные source-аудиты, "
        "retention, индивидуальные privacy-запросы, документы, порядок CI и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
