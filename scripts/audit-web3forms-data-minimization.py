#!/usr/bin/env python3
"""Проверяет минимальный, но рабочий набор данных Web3Forms email."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_APP = ROOT / "assets/js/online-application.js"
SOURCE_PREPARATION = ROOT / "assets/js/application-preparation.js"
SOURCE_POLICY = ROOT / "policy.md"
PREPARATION_CONTRACT = ROOT / "docs/preparation-context-contract.md"
TECHNICAL_DOC = ROOT / "docs/web3forms-data-minimization.md"
POST_BUILD = ROOT / "scripts/post-build-check.sh"


def fail(path: Path, message: str) -> None:
    print(f"::error file={path.as_posix()}::{message}")


def require(text: str, markers: tuple[str, ...], path: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            fail(path, f"{label}: отсутствует маркер {marker}")
            errors += 1
    return errors


def forbid(text: str, markers: tuple[str, ...], path: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker in text:
            fail(path, f"{label}: найден запрещённый маркер {marker}")
            errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_app = site_dir / "assets/js/online-application.js"
    built_preparation = site_dir / "assets/js/application-preparation.js"
    built_policy = site_dir / "policy/index.html"
    required_files = (
        SOURCE_APP,
        SOURCE_PREPARATION,
        SOURCE_POLICY,
        PREPARATION_CONTRACT,
        TECHNICAL_DOC,
        POST_BUILD,
        built_app,
        built_preparation,
        built_policy,
    )
    errors = 0

    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            fail(path, "Обязательный файл отсутствует или пуст")
            errors += 1
    if errors:
        return 1

    source_app = SOURCE_APP.read_text(encoding="utf-8")
    source_preparation = SOURCE_PREPARATION.read_text(encoding="utf-8")
    source_policy = SOURCE_POLICY.read_text(encoding="utf-8")
    contract = PREPARATION_CONTRACT.read_text(encoding="utf-8")
    documentation = TECHNICAL_DOC.read_text(encoding="utf-8")
    post_build = POST_BUILD.read_text(encoding="utf-8")
    built_app_text = built_app.read_text(encoding="utf-8-sig", errors="ignore")
    built_preparation_text = built_preparation.read_text(encoding="utf-8-sig", errors="ignore")
    built_policy_text = built_policy.read_text(encoding="utf-8-sig", errors="ignore")

    app_markers = (
        "name: payload.client.name",
        "phone: payload.client.phone",
        "city: payload.client.city",
        "scenario: payload.mortgage.scenario",
        "request_id: payload.request_id",
        "tracking_json: JSON.stringify(tracking)",
        "message: preparedText",
        "utm_source: current.utm_source || ''",
        "personal_data_consent: payload.personal_data_consent",
        "body: JSON.stringify(emailPayload)",
        "body: JSON.stringify(payload)",
    )
    errors += require(source_app, app_markers, SOURCE_APP, "Исходный Web3Forms payload")
    errors += require(built_app_text, app_markers, built_app, "Собранный Web3Forms payload")
    errors += forbid(source_app, ("fields_json",), SOURCE_APP, "Исходный Web3Forms payload")
    errors += forbid(built_app_text, ("fields_json",), built_app, "Собранный Web3Forms payload")

    preparation_markers = (
        "payload.preparation = data;",
        "payload.preparation_json = JSON.stringify(data, null, 2);",
        "payload.preparation_completed_keys",
        "payload.remaining_questions",
        "payload.message = appendPreparationToApplicationText(payload.message);",
    )
    errors += require(source_preparation, preparation_markers, SOURCE_PREPARATION, "Исходный preparation payload")
    errors += require(built_preparation_text, preparation_markers, built_preparation, "Собранный preparation payload")
    errors += forbid(source_preparation, ("fields_json",), SOURCE_PREPARATION, "Исходный preparation payload")
    errors += forbid(built_preparation_text, ("fields_json",), built_preparation, "Собранный preparation payload")

    policy_markers = (
        "Полная JSON-копия всей заявки в email-канал дополнительно не дублируется",
        "отдельные необходимые поля анкеты",
        "готовый текст обращения",
    )
    errors += require(source_policy, policy_markers, SOURCE_POLICY, "Исходная политика")
    errors += require(built_policy_text, policy_markers, built_policy, "Собранная политика")

    contract_markers = (
        "Полная JSON-копия заявки в Web3Forms не дублируется",
        "preparation_json",
        "ПОДГОТОВКА ДО ОБРАЩЕНИЯ",
    )
    errors += require(contract, contract_markers, PREPARATION_CONTRACT, "Контракт подготовки")

    documentation_markers = (
        "Минимизация данных Web3Forms",
        "Полный `fields_json` не отправляется",
        "Будущий закрытый endpoint получает канонический JSON payload напрямую",
        "audit-web3forms-data-minimization.py",
    )
    errors += require(documentation, documentation_markers, TECHNICAL_DOC, "Документация")

    audit_command = 'python3 scripts/audit-web3forms-data-minimization.py "$SITE_DIR"'
    if audit_command not in post_build:
        fail(POST_BUILD, "Аудит минимизации Web3Forms не подключён к post-build")
        errors += 1

    if errors:
        print(f"Аудит минимизации Web3Forms завершён с ошибками: {errors}")
        return 1

    print("Минимизация Web3Forms подтверждена: full payload JSON отсутствует, рабочие поля сохранены")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
