#!/usr/bin/env python3
"""Проверяет безопасные состояния /spasibo/ и точность conversion goal."""

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
    for forbidden in (
        "Спасибо, обращение передано",
        "Заявка отправлена",
        "Найдено ранее подтверждённое обращение",
        "Передача Подтверждена",
    ):
        if forbidden in visible_page:
            fail(page_path, f"Динамическое состояние видно до проверки request ID: {forbidden}")
            errors += 1

    inline_js = "\n".join(parser.scripts)
    required_markers = (
        "var contextRequestId = cleanRequestId(legacyContext.id);",
        "var storedRequestId = cleanRequestId(lastLead.request_id);",
        "var requestId = contextRequestId || storedRequestId;",
        "var currentRedirectVerified = Boolean(contextRequestId);",
        "page.dataset.state = currentRedirectVerified ? 'verified' : 'restored';",
        "trackVerifiedView(contextRequestId);",
        "window.sessionStorage.getItem(trackingKey) === '1'",
        "window.sessionStorage.setItem(trackingKey, '1')",
        "window.dataLayer.push({ event: 'lead_thankyou_restored_view' });",
        "window.dataLayer.push({ event: 'lead_thankyou_unverified_view' });",
    )
    for marker in required_markers:
        if marker not in inline_js:
            fail(page_path, f"Отсутствует маркер проверенного состояния: {marker}")
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

    state_split = re.search(
        r"if \(currentRedirectVerified\) \{(?P<current>.*?)\n      \} else \{(?P<restored>.*?)\n      \}",
        inline_js,
        re.DOTALL,
    )
    if not state_split:
        fail(page_path, "Не удалось разделить текущее и восстановленное подтверждение")
        errors += 1
    else:
        current = state_split.group("current")
        restored = state_split.group("restored")
        for marker in ("Спасибо, обращение передано", "trackVerifiedView(contextRequestId)"):
            if marker not in current:
                fail(page_path, f"В текущем redirect-состоянии отсутствует маркер: {marker}")
                errors += 1
        for marker in ("Найдено ранее подтверждённое обращение", "lead_thankyou_restored_view"):
            if marker not in restored:
                fail(page_path, f"В restored-состоянии отсутствует маркер: {marker}")
                errors += 1
        if "trackVerifiedView" in restored or "sendGoal" in restored or "lead_thankyou_view'" in restored:
            fail(page_path, "Восстановленный из localStorage статус ошибочно считается новой конверсией")
            errors += 1

    outer_else = re.search(
        r"if \(requestId\) \{.*?\n    \} else \{(?P<body>.*?)\n    \}",
        inline_js,
        re.DOTALL,
    )
    if not outer_else:
        fail(page_path, "Не удалось выделить неподтверждённое состояние")
        errors += 1
    elif "sendGoal" in outer_else.group("body") or "lead_thankyou_view'" in outer_else.group("body"):
        fail(page_path, "Неподтверждённый визит ошибочно считается успешной конверсией")
        errors += 1

    if inline_js.count("trackVerifiedView(contextRequestId);") != 1:
        fail(page_path, "Conversion goal должна вызываться ровно один раз и только для текущего redirect")
        errors += 1

    if errors:
        print(f"Аудит статуса /spasibo/ завершён с ошибками: {errors}")
        return 1

    print("Статус /spasibo/ безопасен: neutral/verified/restored разделены, conversion goal только для текущего redirect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
