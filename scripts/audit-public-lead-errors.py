#!/usr/bin/env python3
"""Проверяет единый безопасный error envelope публичной Edge Function."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLER = ROOT / "supabase/functions/broker-public-lead/handler.ts"
CLIENT = ROOT / "assets/js/online-application.js"
CONTRACT = ROOT / "docs/public-lead-error-contract.md"
SMOKE = ROOT / "docs/supabase-public-error-smoke.md"
WORKFLOW = ROOT / ".github/workflows/pages.yml"
CONFIG = ROOT / "_config.yml"

PUBLIC_CODES = (
    "origin_not_allowed",
    "method_not_allowed",
    "backend_unavailable",
    "content_type_not_supported",
    "payload_too_large",
    "invalid_json",
    "backend_migration_required",
    "rate_limit_exceeded",
    "request_rejected",
    "validation_failed",
    "lead_storage_failed",
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


def require(text: str, markers: tuple[str, ...], file: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            error(f"{label}: отсутствует marker {marker}", file)
            errors += 1
    return errors


def main() -> int:
    required = (HANDLER, CLIENT, CONTRACT, SMOKE, WORKFLOW, CONFIG)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл public error audit", file)
    if missing:
        return 1

    errors = 0
    handler = read(HANDLER)
    client = read(CLIENT)
    contract = read(CONTRACT).casefold()
    smoke = read(SMOKE).casefold()
    workflow = read(WORKFLOW)
    config = read(CONFIG)

    helper = section(handler, "function errorResponse(", "function cleanIsoDate", HANDLER)
    serve = section(handler, "Deno.serve(async (request) => {", "\n});", HANDLER)

    errors += require(
        handler,
        (
            "type PublicErrorCode =",
            "function correlationRequestId(value: unknown = ''): string",
            "return cleanRequestId(value) || crypto.randomUUID();",
            "const correlationId = crypto.randomUUID();",
            "const responseRequestId = requestId || correlationId;",
            "'Cache-Control': 'no-store'",
        ),
        HANDLER,
        "Handler",
    )

    errors += require(
        helper,
        (
            "ok: false",
            "success: false",
            "error_code: errorCode",
            "request_id: correlationRequestId(requestId)",
            "body.retry_after_seconds = retryAfterSeconds",
            "return jsonResponse(body, status, origin)",
        ),
        HANDLER,
        "Error helper",
    )

    for code in PUBLIC_CODES:
        if f"'{code}'" not in handler:
            error(f"Публичный код не входит в allowlist handler: {code}", HANDLER)
            errors += 1
        if f"`{code}`" not in contract:
            error(f"Контракт не описывает публичный код: {code}", CONTRACT)
            errors += 1

    expected_calls = (
        "errorResponse('origin_not_allowed', 403, origin, correlationId)",
        "errorResponse('method_not_allowed', 405, origin, correlationId)",
        "errorResponse('backend_unavailable', 503, origin, correlationId)",
        "errorResponse('content_type_not_supported', 415, origin, correlationId)",
        "errorResponse('payload_too_large', 413, origin, correlationId)",
        "errorResponse('invalid_json', 400, origin, correlationId)",
        "errorResponse('backend_migration_required', 503, origin, responseRequestId)",
        "errorResponse('rate_limit_exceeded', 429, origin, responseRequestId, 3600)",
        "errorResponse('request_rejected', 202, origin, responseRequestId)",
        "errorResponse('validation_failed', 422, origin, responseRequestId)",
        "errorResponse('lead_storage_failed', 500, origin, validation.lead.requestId)",
    )
    errors += require(serve, expected_calls, HANDLER, "HTTP error branches")

    if "return jsonResponse({ ok: false" in serve:
        error("В Deno.serve остался обход единого errorResponse", HANDLER)
        errors += 1

    for forbidden in (
        "blocked: true",
        "errors: validation.errors",
        "attempt_count: rateLimit.attemptCount",
        "rate_limit: rateLimit.limit",
        "error: 'request_rejected'",
        "error: 'lead_storage_failed'",
        "message:",
        "lead_id:",
        "technical_priority:",
        "qualification:",
    ):
        if forbidden in serve:
            error(f"Public error branch раскрывает запрещённое поле: {forbidden}", HANDLER)
            errors += 1

    if re.search(r"errorResponse\([^\n]*(?:error\.code|error\.message|duplicateReadError)", serve):
        error("errorResponse не должен получать внутренний текст исключения или PostgreSQL code", HANDLER)
        errors += 1

    if serve.count("retryAfterSeconds"):
        error("Deno.serve не должен формировать произвольный retryAfterSeconds", HANDLER)
        errors += 1
    if serve.count("errorResponse('rate_limit_exceeded'") != 1:
        error("Ожидается ровно одна публичная rate-limit ветка", HANDLER)
        errors += 1

    for marker in (
        "responsePayload.ok === false",
        "responsePayload.success === false",
        "Все каналы приёма заявки недоступны",
        "Данные не потеряны",
    ):
        if marker not in client:
            error(f"Клиентская совместимость error envelope не подтверждена: {marker}", CLIENT)
            errors += 1

    for forbidden_usage in (
        "responsePayload.errors",
        "responsePayload.attempt_count",
        "responsePayload.rate_limit",
        "responsePayload.blocked",
    ):
        if forbidden_usage in client:
            error(f"Клиент зависит от удалённого error-поля: {forbidden_usage}", CLIENT)
            errors += 1

    for marker in (
        "единый error envelope",
        "correlation request id",
        "retry_after_seconds",
        "postgresql",
        "cache-control: no-store",
        "web3forms",
        "endpoint: \"\"",
    ):
        if marker not in contract:
            error(f"Error contract не содержит marker: {marker}", CONTRACT)
            errors += 1

    for marker in (
        "применены 11 миграций",
        "общий критерий envelope",
        "invalid json",
        "rate limit",
        "ошибка сохранения",
        "запрещённые поля",
        "mode: \"web3forms\"",
        "endpoint: \"\"",
    ):
        if marker not in smoke:
            error(f"Public error smoke не содержит marker: {marker}", SMOKE)
            errors += 1

    command = "python3 scripts/audit-public-lead-errors.py"
    if command not in workflow:
        error("Pages workflow не запускает public lead error audit", WORKFLOW)
        errors += 1

    mode_match = re.search(r"(?ms)^lead_capture:\s*.*?^\s{2}mode:\s*[\"']?([^\"'\n]+)", config)
    endpoint_match = re.search(r"(?m)^\s{2}endpoint:\s*[\"']?([^\"'\n]*)", config)
    mode = mode_match.group(1).strip() if mode_match else ""
    endpoint = endpoint_match.group(1).strip() if endpoint_match else "missing"
    if mode != "web3forms":
        error("До error-response smoke режим должен оставаться web3forms", CONFIG)
        errors += 1
    if endpoint:
        error("Supabase endpoint должен оставаться пустым до общей приёмки", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит публичных ошибок завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит публичных ошибок успешно завершён: единый error envelope, allowlist кодов, correlation ID, "
        "минимальный 429, отсутствие PostgreSQL/validation деталей, документы, smoke и выключенный endpoint подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
