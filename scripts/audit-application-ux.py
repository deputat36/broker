#!/usr/bin/env python3
"""Проверяет короткий мобильный сценарий онлайн-заявки, телефон и согласие."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path

APPLICATION_URL = "/online-zayavka/"
PHONE_SCRIPT = "/assets/js/application-inputs.js"
APPLICATION_SCRIPT = "/assets/js/online-application.js"
APPLICATION_STYLE = "/assets/css/online-application.css"
CONSENT_INLINE_MARKER = "<script data-application-consent-validation>"
LEGACY_CONSENT_SCRIPT = "/assets/js/application-consent-validation.js"

REQUIRED_VISIBLE_FIELDS = {"client_name", "phone", "city", "scenario", "consent"}
OPTIONAL_DETAIL_FIELDS = {
    "object_type", "object_price", "down_payment", "income_type", "bank_history", "comment",
}


class ApplicationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: set[str] = set()
        self.styles: set[str] = set()
        self.fields_outside_details: set[str] = set()
        self.fields_inside_details: set[str] = set()
        self.required_fields: set[str] = set()
        self.form_version = ""
        self.phone_attrs: dict[str, str] = {}
        self.consent_attrs: dict[str, str] = {}
        self.details_count = 0
        self.details_open = False
        self.summary_parts: list[str] = []
        self.markers: set[str] = set()
        self._details_depth = 0
        self._in_summary = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        for key in attrs_map:
            if key.startswith("data-"):
                self.markers.add(key)

        if tag == "script" and attrs_map.get("src"):
            self.scripts.add(attrs_map["src"])
        elif tag == "link" and "stylesheet" in attrs_map.get("rel", "").lower().split():
            self.styles.add(attrs_map.get("href", ""))
        elif tag == "details":
            self.details_count += 1
            self._details_depth += 1
            self.details_open = self.details_open or "open" in attrs_map
        elif tag == "summary" and self._details_depth:
            self._in_summary = True
        elif tag in {"input", "select", "textarea"}:
            name = attrs_map.get("name", "")
            if not name:
                return
            target = self.fields_inside_details if self._details_depth else self.fields_outside_details
            target.add(name)
            if "required" in attrs_map:
                self.required_fields.add(name)
            if name == "form_version":
                self.form_version = attrs_map.get("value", "")
            if name == "phone":
                self.phone_attrs = attrs_map
            if name == "consent":
                self.consent_attrs = attrs_map

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "summary":
            self._in_summary = False
        elif tag == "details" and self._details_depth:
            self._details_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_summary:
            self.summary_parts.append(data)

    @property
    def summary_text(self) -> str:
        return " ".join(" ".join(self.summary_parts).casefold().replace("ё", "е").split())


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def page_file(site_dir: Path, url: str) -> Path:
    return site_dir / url.lstrip("/") / "index.html"


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    html_file = page_file(site_dir, APPLICATION_URL)
    if not html_file.is_file():
        error("Не найдена собранная страница онлайн-заявки", html_file)
        return 1

    html_text = html_file.read_text(encoding="utf-8", errors="ignore")
    parser = ApplicationParser()
    parser.feed(html_text)
    errors = 0

    if parser.details_count != 1:
        error(f"Ожидался один раскрываемый блок дополнительных полей, найдено: {parser.details_count}", html_file)
        errors += 1
    if parser.details_open:
        error("Блок дополнительных полей не должен быть раскрыт по умолчанию", html_file)
        errors += 1
    if "добавить подробности" not in parser.summary_text:
        error("У раскрываемого блока отсутствует понятный заголовок «Добавить подробности»", html_file)
        errors += 1

    missing_visible = REQUIRED_VISIBLE_FIELDS - parser.fields_outside_details
    if missing_visible:
        error(f"Обязательные поля скрыты внутри подробного блока или отсутствуют: {', '.join(sorted(missing_visible))}", html_file)
        errors += 1
    misplaced_optional = OPTIONAL_DETAIL_FIELDS - parser.fields_inside_details
    if misplaced_optional:
        error(f"Необязательные поля должны находиться внутри блока подробностей: {', '.join(sorted(misplaced_optional))}", html_file)
        errors += 1
    if REQUIRED_VISIBLE_FIELDS - parser.required_fields:
        missing_required = REQUIRED_VISIBLE_FIELDS - parser.required_fields
        error(f"Поля короткой заявки должны быть обязательными: {', '.join(sorted(missing_required))}", html_file)
        errors += 1
    if parser.form_version != "2":
        error("После перехода на короткую форму form_version должен быть равен 2", html_file)
        errors += 1

    phone = parser.phone_attrs
    if "data-phone-input" not in phone:
        error("Телефонное поле не подключено к нормализации номера", html_file)
        errors += 1
    if phone.get("aria-describedby") != "application-phone-hint":
        error("Телефонное поле должно быть связано с подсказкой через aria-describedby", html_file)
        errors += 1
    if phone.get("inputmode") != "tel" or phone.get("autocomplete") != "tel":
        error("Для телефона должны быть inputmode=tel и autocomplete=tel", html_file)
        errors += 1

    consent = parser.consent_attrs
    if consent.get("type") != "checkbox" or "required" not in consent:
        error("Согласие должно оставаться обязательным checkbox-полем", html_file)
        errors += 1

    for marker in ("data-application-more", "data-phone-input", "data-application-consent-validation"):
        if marker not in parser.markers:
            error(f"На странице отсутствует UX-маркер: {marker}", html_file)
            errors += 1

    for script_path, label in (
        (PHONE_SCRIPT, "скрипт телефонного поля"),
        (APPLICATION_SCRIPT, "основной скрипт заявки"),
    ):
        if script_path not in parser.scripts:
            error(f"Не подключён {label}: {script_path}", html_file)
            errors += 1
    if LEGACY_CONSENT_SCRIPT in parser.scripts:
        error("Отдельный скрипт согласия не должен загружаться после перехода на inline-проверку", html_file)
        errors += 1
    if APPLICATION_STYLE not in parser.styles:
        error(f"Не подключены стили заявки: {APPLICATION_STYLE}", html_file)
        errors += 1

    phone_script_file = site_dir / PHONE_SCRIPT.lstrip("/")
    if not phone_script_file.is_file():
        error("Не найден собранный скрипт телефонного поля", phone_script_file)
        errors += 1
    else:
        script = phone_script_file.read_text(encoding="utf-8", errors="ignore")
        for marker in (
            "normalizeRussianPhone", "formatRussianPhone", "setCustomValidity",
            "stopImmediatePropagation", "online_application_phone_error",
            "online_application_more_open", "addEventListener('submit'",
        ):
            if marker not in script:
                error(f"В UX-скрипте отсутствует маркер: {marker}", phone_script_file)
                errors += 1
        if "localStorage" in script or "sessionStorage" in script:
            error("UX-скрипт не должен сохранять имя или телефон в браузере", phone_script_file)
            errors += 1

    legacy_consent_file = site_dir / LEGACY_CONSENT_SCRIPT.lstrip("/")
    if legacy_consent_file.exists():
        error("Standalone-файл согласия должен быть удалён из Pages-артефакта", legacy_consent_file)
        errors += 1

    if CONSENT_INLINE_MARKER not in html_text:
        error("На странице отсутствует inline-валидация согласия", html_file)
        errors += 1
    else:
        consent_script = html_text.split(CONSENT_INLINE_MARKER, 1)[1].split("</script>", 1)[0]
        for marker in (
            "DOMContentLoaded", "namedItem('consent')", "aria-invalid",
            "addEventListener('submit'", "addEventListener('change'",
        ):
            if marker not in consent_script:
                error(f"В inline-валидации согласия отсутствует маркер: {marker}", html_file)
                errors += 1
        for forbidden in ("localStorage", "sessionStorage", "fetch(", "sendBeacon", "preparation_check"):
            if forbidden in consent_script:
                error(f"Inline-валидация согласия не должна использовать {forbidden}", html_file)
                errors += 1

    style_file = site_dir / APPLICATION_STYLE.lstrip("/")
    if style_file.is_file():
        styles = style_file.read_text(encoding="utf-8", errors="ignore")
        for marker in (
            ".application-more", ".application-field-hint", ".application-step-label",
            ".application-consent input[aria-invalid=\"true\"]",
            ".application-consent input[aria-invalid=\"true\"] + span",
            ".application-submit", "@media (max-width: 760px)",
        ):
            if marker not in styles:
                error(f"В стилях короткой формы отсутствует маркер: {marker}", style_file)
                errors += 1

    if errors:
        print(f"UX-аудит онлайн-заявки завершён с ошибками: {errors}")
        return 1

    print("UX-аудит онлайн-заявки успешно завершён: короткий сценарий, телефон и inline-согласие подтверждены")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
