#!/usr/bin/env python3
"""Проверяет единый минимальный success response публичной Edge Function."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLER = ROOT / "supabase/functions/broker-public-lead/handler.ts"
CLIENT = ROOT / "assets/js/online-application.js"
CONTRACT = ROOT / "docs/public-lead-response-contract.md"
SMOKE = ROOT / "docs/supabase-public-response-smoke.md"
RESTRICTED_CONTRACT = ROOT / "docs/restricted-delivery-response-contract.md"
WORKFLOW = ROOT / ".github/workflows/pages.yml"
CONFIG = ROOT / "_config.yml"

ALLOWED_SUCCESS_KEYS = (
    "ok:",
    "success:",
    "duplicate,",
    "request_id:",
    "notification_status:",
)
FORBIDDEN_PUBLIC_FIELDS = (
    "lead_id",
    "crm_status",
    "technical_priority",
    "qualification",
    "raw_payload",
    "processing_restricted",
    "retention_hold",
    "anonymized_at",
    "client_name",
    "phone_normalized",
)


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def section(text: str, start: str, end: str, file: Path) -> str:
    if start not in text or end not in text.split(start, 1)[-1]:
        error(f"Не найден проверяемый блок между {start!r} и {end!r}", file)
        return ""
    return text.split(start, 1)[-1].split(end, 1)[0]


def main() -> int:
    required = (HANDLER, CLIENT, CONTRACT, SMOKE, RESTRICTED_CONTRACT, WORKFLOW, CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл public response audit", file)
    if missing:
        return 1

    errors = 0
    handler = read(HANDLER)
    client = read(CLIENT)
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    restricted_contract = read(RESTRICTED_CONTRACT).casefold()
    workflow = read(WORKFLOW)
    config = read(CONFIG)

    success_body = section(
        handler,
        "function successResponse(requestId: string, duplicate: boolean, notificationStatus: NotificationStatus): JsonRecord {",
        "async function duplicateResponse",
        HANDLER,
    )
    duplicate_body = section(
        handler,
        "async function duplicateResponse",
        "Deno.serve",
        HANDLER,
    )
    final_body = section(
        handler,
        "const notificationStatus = await deliverNotification(String(data.id), validation.lead.requestId);",
        "});",
        HANDLER,
    )
    lookup_body = section(
        handler,
        "async function findExistingLead",
        "function isOperationallyRestricted",
        HANDLER,
    )

    for marker in ALLOWED_SUCCESS_KEYS:
        if marker not in success_body:
            error(f"Единый success envelope не содержит поле: {marker}", HANDLER)
            errors += 1

    if handler.count("successResponse(") != 4:
        error("Ожидались declaration и три вызова единого successResponse", HANDLER)
        errors += 1

    for field in FORBIDDEN_PUBLIC_FIELDS:
        if field in success_body:
            error(f"Единый success envelope раскрывает внутреннее поле: {field}", HANDLER)
            errors += 1
        if field in duplicate_body:
            error(f"Duplicate success response раскрывает внутреннее поле: {field}", HANDLER)
            errors += 1
        if field in final_body:
            error(f"Новая заявка раскрывает внутреннее поле: {field}", HANDLER)
            errors += 1

    for marker in (
        "return jsonResponse(successResponse(responseRequestId, true, 'disabled'), 200, origin);",
        "return jsonResponse(successResponse(responseRequestId, true, notificationStatus), 200, origin);",
        "return jsonResponse(successResponse(String(data.request_id || validation.lead.requestId), false, notificationStatus), 201, origin);",
        ".select('id, request_id')",
    ):
        if marker not in handler:
            error(f"Handler не содержит обязательный минимальный response marker: {marker}", HANDLER)
            errors += 1

    required_lookup_fields = (
        "id",
        "request_id",
        "notification_status",
        "processing_restricted",
        "retention_hold",
        "anonymized_at",
    )
    for marker in required_lookup_fields:
        if marker not in lookup_body:
            error(f"Idempotency lookup не содержит необходимое поле: {marker}", HANDLER)
            errors += 1
    if re.search(r"(?<![\w])status(?![\w])", lookup_body):
        error("Idempotency lookup загружает ненужный CRM status", HANDLER)
        errors += 1
    for forbidden in ("technical_priority", "qualification"):
        if forbidden in lookup_body:
            error(f"Idempotency lookup загружает ненужное публичному ответу поле: {forbidden}", HANDLER)
            errors += 1

    for forbidden_usage in (
        "response.lead_id",
        "response.crm_status",
        "response.technical_priority",
        "response.qualification",
        "responsePayload.lead_id",
        "responsePayload.crm_status",
        "responsePayload.technical_priority",
        "responsePayload.qualification",
    ):
        if forbidden_usage in client:
            error(f"Клиентский код зависит от удалённого внутреннего поля: {forbidden_usage}", CLIENT)
            errors += 1

    for marker in (
        "sendCustomLead",
        "responsePayload.ok === false",
        "responsePayload.success === false",
        "buildThankYouUrl(preparedPayload)",
        "saveLastLead(preparedPayload, channels)",
    ):
        if marker not in client:
            error(f"Не подтверждена клиентская совместимость минимального ответа: {marker}", CLIENT)
            errors += 1

    for marker in (
        "единый успешный envelope",
        '"duplicate": false',
        '"duplicate": true',
        '"request_id"',
        '"notification_status"',
        "lead_id",
        "technical_priority",
        "qualification",
        "серверное хранение",
        "web3forms",
    ):
        if marker not in contract:
            error(f"Public response contract не содержит marker: {marker}", CONTRACT)
            errors += 1

    for marker in (
        "применены десять миграций",
        "ровно пять ключей",
        "обычный duplicate",
        "restricted duplicate",
        "клиентская совместимость",
        "lead_id",
        "technical_priority",
        "qualification",
        "mode: \"web3forms\"",
        "endpoint: \"\"",
    ):
        if marker not in smoke:
            error(f"Public response smoke не содержит marker: {marker}", SMOKE)
            errors += 1

    for marker in (
        "lead_id",
        "crm_status",
        "technical_priority",
        "qualification",
        'notification_status": "disabled',
    ):
        if marker not in restricted_contract:
            error(f"Restricted contract не синхронизирован с минимальным ответом: {marker}", RESTRICTED_CONTRACT)
            errors += 1

    command = "python3 scripts/audit-public-lead-response.py"
    if command not in workflow:
        error("Pages workflow не запускает public lead response audit", WORKFLOW)
        errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До public response smoke режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до общей приёмки", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит минимального публичного ответа завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит минимального публичного ответа успешно завершён: новая, duplicate и restricted заявки "
        "используют единый пятиключевой envelope, внутренние CRM-поля не раскрываются, клиентская "
        "совместимость, документы, smoke и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
