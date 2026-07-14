#!/usr/bin/env python3
"""Проверяет безопасный контракт состояний Web3Forms/Supabase delivery."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607140005_broker_lead_delivery_state.sql"
RECEIPT = ROOT / "supabase/functions/broker-delivery-receipt/index.ts"
KEEPALIVE = ROOT / "assets/js/application-delivery-keepalive.js"
INPUTS = ROOT / "assets/js/application-inputs.js"
ONLINE = ROOT / "assets/js/online-application.js"
PAGE = ROOT / "online-zayavka.md"
CONFIG_TOML = ROOT / "supabase/config.toml"
SITE_CONFIG = ROOT / "_config.yml"
THANK_YOU = ROOT / "spasibo.md"
CONTRACT = ROOT / "docs/hybrid-delivery-state-contract.md"
SMOKE = ROOT / "docs/hybrid-delivery-state-smoke.md"
ANALYTICS = ROOT / "docs/analytics-events.md"
WORKFLOW = ROOT / ".github/workflows/pages.yml"


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
    required = (
        MIGRATION,
        RECEIPT,
        KEEPALIVE,
        INPUTS,
        ONLINE,
        PAGE,
        CONFIG_TOML,
        SITE_CONFIG,
        THANK_YOU,
        CONTRACT,
        SMOKE,
        ANALYTICS,
        WORKFLOW,
    )
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл hybrid delivery state", file)
    if missing:
        return 1

    errors = 0
    migration = read(MIGRATION)
    migration_cf = migration.casefold()
    receipt = read(RECEIPT)
    keepalive = read(KEEPALIVE)
    inputs = read(INPUTS)
    online = read(ONLINE)
    page = read(PAGE)
    config_toml = read(CONFIG_TOML)
    site_config = read(SITE_CONFIG)
    thank_you = read(THANK_YOU).casefold()
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    analytics = read(ANALYTICS)
    workflow = read(WORKFLOW)

    errors += require(
        migration_cf,
        (
            "client_delivery_state text not null default 'supabase_only'",
            "delivery_state_updated_at timestamptz not null default now()",
            "client_delivery_state in ('supabase_only', 'both')",
            "mark_broker_lead_delivery_both",
            "broker_lead_delivery_state",
            "client_delivery_state = 'both'",
            "delivery_channel = 'both'",
            "processing_restricted = false",
            "retention_hold = false",
            "anonymized_at is null",
            "delivery_state_updated",
            "from public, anon, authenticated",
            "to service_role",
        ),
        MIGRATION,
        "Delivery state migration",
    )

    if re.search(r"set\s+client_delivery_state\s*=\s*'supabase_only'", migration_cf):
        error("Миграция не должна понижать подтверждённое состояние both", MIGRATION)
        errors += 1
    for forbidden in (
        "delete from public.broker_leads",
        "cron.schedule",
        "http_post",
        "net.http",
        "to anon",
        "to authenticated",
    ):
        if forbidden in migration_cf:
            error(f"Delivery state migration содержит запрещённый marker: {forbidden}", MIGRATION)
            errors += 1

    errors += require(
        receipt,
        (
            "ALLOWED_ORIGINS.has(normalizeOrigin(origin))",
            "if (!isAllowedOrigin(origin))",
            "MAX_BODY_BYTES = 4096",
            "requestKind !== 'delivery_receipt'",
            "deliveryState !== 'both'",
            "mark_broker_lead_delivery_both",
            "return new Response(null, { status: 204",
            "SUPABASE_SERVICE_ROLE_KEY",
            "Cache-Control",
            "no-store",
        ),
        RECEIPT,
        "Receipt handler",
    )

    for forbidden in (
        "client_name",
        "phone_normalized",
        "mortgage_goal",
        "raw_payload",
        "tracking",
        "qualification",
        "TELEGRAM_BOT_TOKEN",
        "NOTIFICATION_ADMIN_TOKEN",
        "NOTIFICATION_MONITOR_TOKEN",
    ):
        if forbidden in receipt:
            error(f"Receipt handler содержит данные или чужой secret: {forbidden}", RECEIPT)
            errors += 1

    errors += require(
        keepalive,
        (
            "payload.request_kind === 'delivery_receipt'",
            "payload.delivery_state === 'both'",
            "return originalFetch(input, { ...init, keepalive: true })",
        ),
        KEEPALIVE,
        "Receipt keepalive adapter",
    )
    for forbidden in (
        "client_name",
        "phone_normalized",
        "localStorage",
        "sessionStorage",
        "sendGoal",
    ):
        if forbidden in keepalive:
            error(f"Keepalive adapter содержит запрещённый fragment: {forbidden}", KEEPALIVE)
            errors += 1

    errors += require(
        inputs,
        (
            "const WEB3FORMS_WAIT_MS = 2500",
            "web3forms_only",
            "supabase_only",
            "const state = web3formsAccepted && supabaseAccepted",
            "online_application_delivery_${state}",
            "request_kind: 'delivery_receipt'",
            "delivery_state: 'both'",
            "broker-delivery-receipt",
            "online_application_delivery_receipt_success",
            "online_application_delivery_receipt_error",
            "payload.delivery_state = state",
            "payload.delivery_state_source = 'browser_confirmed'",
            "if (state === 'both') void sendBothReceipt",
            "Квитанция не должна менять успешный клиентский результат",
        ),
        INPUTS,
        "Browser delivery coordinator",
    )

    delivery_module = inputs.split("const mode = String(form.dataset.leadMode", 1)[-1]
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "client_name",
        "phone_normalized",
        "window.sendGoal(requestId",
        "window.sendGoal(request_id",
        "window.sendGoal(body.request_id",
    ):
        if forbidden in delivery_module:
            error(f"Delivery coordinator содержит запрещённый fragment: {forbidden}", INPUTS)
            errors += 1

    errors += require(
        online,
        (
            "Promise.allSettled(tasks)",
            "if (!successful.length)",
            "saveLastLead(preparedPayload, channels)",
            "window.location.assign(buildThankYouUrl(preparedPayload))",
        ),
        ONLINE,
        "Основной transport",
    )

    script_order = (
        "assets/js/application-delivery-keepalive.js",
        "assets/js/application-inputs.js",
        "assets/js/application-preparation.js",
    )
    positions = [page.find(marker) for marker in script_order]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        error("Keepalive, inputs и preparation должны быть подключены в безопасном порядке", PAGE)
        errors += 1

    if "delivery_state" in thank_you or "web3forms_only" in thank_you or "supabase_only" in thank_you:
        error("Страница благодарности не должна показывать внутреннее состояние каналов", THANK_YOU)
        errors += 1

    section_pattern = r"(?ms)^\[functions\.broker-delivery-receipt\]\s*\n\s*verify_jwt\s*=\s*false\s*$"
    if not re.search(section_pattern, config_toml):
        error("supabase/config.toml не содержит verify_jwt=false для receipt handler", CONFIG_TOML)
        errors += 1

    for marker in (
        "`web3forms_only`",
        "`supabase_only`",
        "`both`",
        "supabase_only → both",
        "2500",
        "keepalive: true",
        "http `204`",
        "не показывается клиенту",
        "best-effort",
        "endpoint: \"\"",
    ):
        if marker not in contract:
            error(f"Delivery state contract не содержит marker: {marker}", CONTRACT)
            errors += 1

    for marker in (
        "применены все 11 миграций",
        "порядок браузерных скриптов",
        "keepalive: true",
        "web3forms-only",
        "supabase-only",
        "оба канала",
        "медленный supabase",
        "ошибка receipt-handler",
        "restricted, hold и anonymized",
        "отсутствующая заявка",
        "mode: \"web3forms\"",
        "endpoint: \"\"",
    ):
        if marker not in smoke:
            error(f"Delivery state smoke не содержит marker: {marker}", SMOKE)
            errors += 1

    goals = (
        "online_application_delivery_web3forms_only",
        "online_application_delivery_supabase_only",
        "online_application_delivery_both",
        "online_application_delivery_receipt_success",
        "online_application_delivery_receipt_error",
    )
    for goal in goals:
        if goal not in analytics:
            error(f"Карта аналитики не содержит цель: {goal}", ANALYTICS)
            errors += 1

    command = "python3 scripts/audit-hybrid-delivery-state.py"
    if command not in workflow:
        error("Pages workflow не запускает hybrid delivery state audit", WORKFLOW)
        errors += 1
    for command_marker in (
        "node --check assets/js/application-delivery-keepalive.js",
        "node --check assets/js/application-inputs.js",
    ):
        if command_marker not in workflow:
            error(f"Workflow не проверяет syntax: {command_marker}", WORKFLOW)
            errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", site_config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", site_config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До hybrid delivery smoke режим должен оставаться web3forms", SITE_CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до общей приёмки", SITE_CONFIG)
        errors += 1

    if errors:
        print(f"Аудит hybrid delivery state завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит hybrid delivery state успешно завершён: web3forms_only/supabase_only/both, "
        "монотонная receipt-квитанция, keepalive при навигации, operator RPC, безопасная аналитика, "
        "неизменная /spasibo/ и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
