#!/usr/bin/env python3
"""Проверяет per-function JWT config и собственную защиту Edge Functions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "supabase/config.toml"
PUBLIC_FUNCTION = ROOT / "supabase/functions/broker-public-lead/handler.ts"
ADMIN_FUNCTION = ROOT / "supabase/functions/broker-notification-retry/index.ts"
ALLOWED_FUNCTIONS = {"broker-public-lead", "broker-notification-retry"}


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def read(file: Path) -> str:
    return file.read_text(encoding="utf-8", errors="ignore")


def sections(config: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^\[functions\.([A-Za-z0-9_-]+)\]\s*$", config))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(config)
        result[match.group(1)] = config[start:end]
    return result


def main() -> int:
    required = (CONFIG, PUBLIC_FUNCTION, ADMIN_FUNCTION)
    missing = [file for file in required if not file.is_file()]
    for file in missing:
        error("Не найден обязательный файл конфигурации Edge Functions", file)
    if missing:
        return 1

    errors = 0
    config = read(CONFIG)
    public_function = read(PUBLIC_FUNCTION)
    admin_function = read(ADMIN_FUNCTION)
    function_sections = sections(config)

    unknown = set(function_sections) - ALLOWED_FUNCTIONS
    if unknown:
        error("Неожиданные функции в per-function config: " + ", ".join(sorted(unknown)), CONFIG)
        errors += 1

    for function_name in sorted(ALLOWED_FUNCTIONS):
        section = function_sections.get(function_name, "")
        if not section:
            error(f"Отсутствует секция [functions.{function_name}]", CONFIG)
            errors += 1
            continue
        if not re.search(r"(?m)^\s*verify_jwt\s*=\s*false\s*$", section):
            error(f"Для {function_name} ожидается явное verify_jwt = false", CONFIG)
            errors += 1

    if len(re.findall(r"(?m)^\s*verify_jwt\s*=\s*false\s*$", config)) != 2:
        error("verify_jwt = false должно быть задано ровно для двух контрактных функций", CONFIG)
        errors += 1

    public_markers = (
        "ALLOWED_ORIGINS.has(normalizeOrigin(origin))",
        "if (!isAllowedOrigin(origin))",
        "consume_broker_lead_rate_limit",
        "personal_data_consent_required",
        "request_rejected",
        "MAX_BODY_BYTES",
    )
    for marker in public_markers:
        if marker not in public_function:
            error(f"Публичная функция без обязательной собственной защиты: {marker}", PUBLIC_FUNCTION)
            errors += 1

    admin_markers = (
        "NOTIFICATION_ADMIN_TOKEN",
        "secureTokenEqual",
        "request.headers.get('authorization')",
        "request_broker_lead_notification_retry",
        "MAX_BODY_BYTES = 8192",
        "Cache-Control",
        "no-store",
    )
    for marker in admin_markers:
        if marker not in admin_function:
            error(f"Административная функция без обязательной собственной защиты: {marker}", ADMIN_FUNCTION)
            errors += 1

    if "Access-Control-Allow-Origin" in admin_function:
        error("Административная функция не должна устанавливать CORS", ADMIN_FUNCTION)
        errors += 1
    if "verify_jwt = true" in config:
        error("Не смешивайте противоречивые JWT-настройки в контрактных секциях", CONFIG)
        errors += 1

    if errors:
        print(f"Аудит Supabase function config завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит Supabase function config успешно завершён: две известные функции, "
        "явный verify_jwt=false и собственная защита публичного и административного handler подтверждены"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())