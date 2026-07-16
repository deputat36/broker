#!/usr/bin/env python3
"""Одноразово переводит старые аудиты с требования fields_json на запрет."""

from pathlib import Path

online_audit = Path("scripts/audit-online-application.py")
text = online_audit.read_text(encoding="utf-8")
old = '''            "tracking_json",
            "fields_json",
            "expires_at",'''
new = '''            "tracking_json",
            "expires_at",'''
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Online audit fields_json marker not found exactly once")
    text = text.replace(old, new, 1)
old = '''        if INLINE_UUID_PATTERN.findall(script_text):
            annotation("Web3Forms access key не должен быть жёстко зашит в JavaScript", script_file)
            errors += 1'''
new = '''        if "fields_json" in script_text:
            annotation("Web3Forms email не должен содержать дублирующий full payload fields_json", script_file)
            errors += 1
        if INLINE_UUID_PATTERN.findall(script_text):
            annotation("Web3Forms access key не должен быть жёстко зашит в JavaScript", script_file)
            errors += 1'''
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Online audit UUID marker not found exactly once")
    text = text.replace(old, new, 1)
online_audit.write_text(text, encoding="utf-8")

privacy_audit = Path("scripts/audit-application-payload-privacy.py")
text = privacy_audit.read_text(encoding="utf-8")
old = '''        "tracking_json: JSON.stringify(tracking)",
        "fields_json: JSON.stringify(payload, null, 2)",
    )
    forbidden_markers = (
        "page_url: window.location.href",
        "referrer: document.referrer || ''",
    )'''
new = '''        "tracking_json: JSON.stringify(tracking)",
    )
    forbidden_markers = (
        "page_url: window.location.href",
        "referrer: document.referrer || ''",
        "fields_json",
    )'''
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Payload privacy audit fields_json marker not found exactly once")
    text = text.replace(old, new, 1)
privacy_audit.write_text(text, encoding="utf-8")

doc = Path("docs/application-payload-privacy.md")
text = doc.read_text(encoding="utf-8")
old = "Из-за этого случайные значения могли попасть в Web3Forms email, `fields_json` или будущий серверный канал вместе с заявкой."
new = "Из-за этого случайные значения могли попасть в Web3Forms email, существовавшую тогда дублирующую полную JSON-копию заявки или будущий серверный канал вместе с заявкой."
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Payload privacy documentation marker not found exactly once")
    text = text.replace(old, new, 1)
old = '''```text
page_url: window.location.href
referrer: document.referrer || ''
```'''
new = '''```text
page_url: window.location.href
referrer: document.referrer || ''
fields_json
```'''
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Payload privacy forbidden marker list not found exactly once")
    text = text.replace(old, new, 1)
doc.write_text(text, encoding="utf-8")

print("Web3Forms minimization audits migrated")
