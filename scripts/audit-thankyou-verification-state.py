#!/usr/bin/env python3
"""Проверяет, что /spasibo/ не имитирует успешную отправку без request ID."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class ThankYouParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.current_id = ""
        self.page_state = ""
        self.visible_by_id: dict[str, list[str]] = {}
        self.visible_text: list[str] = []
        self.scripts: list[str] = []
        self._script_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag in {"script", "style"}:
            self.skip_depth += 1
            if tag == "script":
                self._script_parts = []
            return
        if self.skip_depth:
            return
        if "data-thankyou-page" in attributes:
            self.page_state = attributes.get("data-state", "")
        self.current_id = attributes.get("id", "")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            if tag == "script" and self._script_parts is not None:
                self.scripts.append("".join(self._script_parts))
                self._script_parts = None
            self.skip_depth -= 1
            return
        if not self.skip_depth:
            self.current_id = ""

    def handle_data(self, data: str) -> None:
        if self._script_parts is not None:
            self._script_parts.append(data)
            return
        if self.skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        self.visible_text.append(text)
        if self.current_id:
            self.visible_by_id.setdefault(self.current_id, []).append(text)


def fail(path: Path, message: str) -> None:
    print(f"::error file={path}::{message}")


def visible_value(parser: ThankYouParser, element_id: str) -> str:
    return " ".join(parser.visible_by_id.get(element_id, []))


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    page_path = site_dir / "spasibo" / "index.html"
    if not page_path.is_file():
        fail(page_path, "Страница /spasibo/ не найдена")
        return 1

    html = page_path.read_text(encoding="utf-8-sig")
    parser = ThankYouParser()
    parser.feed(html)
    errors = 0

    expected_defaults = {
        "thankyou-title": "Проверяем подтверждение обращения",
        "lead-id": "—",
        "delivery-status": "Не подтверждена",
        "next-step-title": "Проверьте отправку",
    }
    for element_id, expected in expected_defaults.items():
        actual = visible_value(parser, element_id)
        if actual != expected:
            fail(page_path, f"Неверное нейтральное состояние #{element_id}: {actual!r}, ожидалось {expected!r}")
            errors += 1

    if parser.page_state != "unverified":
        fail(page_path, "Страница должна собираться с data-state=unverified")
        errors += 1

    visible_page = " ".join(parser.visible_text)
    for forbidden in ("Спасибо, обращение передано", "Заявка отправлена", "Передача Подтверждена"):
        if forbidden in visible_page:
            fail(page_path, f"Успешное состояние видно без проверки request ID: {forbidden}")
            errors += 1

    inline_js = "\n".join(parser.scripts)
    required_markers = (
        "var requestId = cleanRequestId(legacyContext.id) || cleanRequestId(lastLead.request_id);",
        "if (requestId) {",
        "page.dataset.state = 'verified';",
        "trackVerifiedView(requestId);",
        "window.sessionStorage.getItem(trackingKey) === '1'",
        "window.sessionStorage.setItem(trackingKey, '1')",
        "window.dataLayer.push({ event: 'lead_thankyou_unverified_view' });",
    )
    for marker in required_markers:
        if marker not in inline_js:
            fail(page_path, f"Отсутствует маркер проверенного состояния: {marker}")
            errors += 1

    if "lead_thankyou_view" not in inline_js or "window.sendGoal('lead_thankyou_view')" not in inline_js:
        fail(page_path, "Подтверждённая конверсия не отправляется после проверки request ID")
        errors += 1

    verified_function = re.search(
        r"function trackVerifiedView\(requestId\) \{(?P<body>.*?)\n    \}",
        inline_js,
        re.DOTALL,
    )
    if not verified_function:
        fail(page_path, "Не удалось выделить функцию дедупликации подтверждённой конверсии")
        errors += 1
    else:
        body = verified_function.group("body")
        for marker in ("sessionStorage", "lead_thankyou_view", "sendGoal"):
            if marker not in body:
                fail(page_path, f"В trackVerifiedView отсутствует обязательный маркер: {marker}")
                errors += 1

    else_block = re.search(
        r"if \(requestId\) \{.*?\n    \} else \{(?P<body>.*?)\n    \}",
        inline_js,
        re.DOTALL,
    )
    if not else_block:
        fail(page_path, "Не удалось выделить неподтверждённое состояние")
        errors += 1
    elif "sendGoal" in else_block.group("body") or "lead_thankyou_view'" in else_block.group("body"):
        fail(page_path, "Неподтверждённый визит ошибочно считается успешной конверсией")
        errors += 1

    if errors:
        print(f"Аудит статуса /spasibo/ завершён с ошибками: {errors}")
        return 1

    print("Статус /spasibo/ безопасен: нейтральный по умолчанию, успех только по валидному request ID, конверсия дедуплицирована")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
