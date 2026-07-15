#!/usr/bin/env python3
"""Делает ресурсы онлайн-заявки условными до Jekyll-сборки."""

from __future__ import annotations

import argparse
from pathlib import Path


CSS_OLD = "  <link rel=\"stylesheet\" href=\"{{ '/assets/css/online-application.css' | relative_url }}\">"
CSS_NEW = """  {% if page.url == '/online-zayavka/' %}
  <link rel=\"stylesheet\" href=\"{{ '/assets/css/online-application.css' | relative_url }}\">
  {% endif %}"""
JS_OLD = "  <script src=\"{{ '/assets/js/online-application.js' | relative_url }}\" defer></script>"
JS_NEW = """  {% if page.url == '/online-zayavka/' %}
  <script src=\"{{ '/assets/js/online-application.js' | relative_url }}\" defer></script>
  {% endif %}"""


def apply_replacements(path: Path, write: bool) -> bool:
    raw = path.read_text(encoding="utf-8-sig")
    updated = raw

    for old, new, label in (
        (CSS_OLD, CSS_NEW, "CSS онлайн-заявки"),
        (JS_OLD, JS_NEW, "JavaScript онлайн-заявки"),
    ):
        if old in updated:
            updated = updated.replace(old, new, 1)
            continue
        if new in updated:
            continue
        raise ValueError(f"Не найден ожидаемый маркер: {label}")

    changed = updated != raw
    if changed and write:
        path.write_text(updated, encoding="utf-8", newline="")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Корень исходников Jekyll")
    parser.add_argument("--write", action="store_true", help="Записать подготовленный layout")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    layout = root / "_layouts" / "default.html"
    changed = apply_replacements(layout, args.write)
    action = "подготовлены" if args.write else "требуют подготовки"
    print(f"Условные ресурсы анкеты: {action}: файлов — {1 if changed else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
