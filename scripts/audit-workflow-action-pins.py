#!/usr/bin/env python3
"""Проверяет, что внешние GitHub Actions закреплены immutable commit SHA."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^@\s]+)@([^\s#]+)", re.MULTILINE)
SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def error(message: str, path: Path) -> None:
    print(f"::error file={path.relative_to(ROOT).as_posix()}::{message}")


def main() -> int:
    if not WORKFLOW_DIR.is_dir():
        error("Каталог workflows не найден", WORKFLOW_DIR)
        return 1

    workflow_files = sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")))
    failures = 0
    remote_actions = 0

    for path in workflow_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for action, ref in USES_RE.findall(text):
            if action.startswith("./") or action.startswith("docker://"):
                continue
            remote_actions += 1
            if not SHA_RE.fullmatch(ref):
                error(
                    f"Внешний action {action}@{ref} должен быть закреплён полным 40-символьным commit SHA",
                    path,
                )
                failures += 1

    if remote_actions == 0:
        print("::warning::В workflow не найдено ни одного внешнего action")

    if failures:
        print(f"Workflow action pin audit: ошибок {failures}, внешних actions {remote_actions}")
        return 1

    print(f"Workflow action pin audit: {remote_actions} внешних actions закреплены immutable SHA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
