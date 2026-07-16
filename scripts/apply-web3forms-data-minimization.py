#!/usr/bin/env python3
"""Одноразово удаляет дублирующий full payload JSON из Web3Forms email."""

from pathlib import Path

app = Path("assets/js/online-application.js")
text = app.read_text(encoding="utf-8")
old = """      tracking_json: JSON.stringify(tracking),
      fields_json: JSON.stringify(payload, null, 2),
      message: preparedText"""
new = """      tracking_json: JSON.stringify(tracking),
      message: preparedText"""
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Web3Forms fields_json marker not found exactly once")
    text = text.replace(old, new, 1)
app.write_text(text, encoding="utf-8")

preparation = Path("assets/js/application-preparation.js")
text = preparation.read_text(encoding="utf-8")
old = """      payload.preparation_json = JSON.stringify(data, null, 2);
      if (payload.fields_json) {
        try {
          const fields = JSON.parse(payload.fields_json);
          fields.preparation = data;
          payload.fields_json = JSON.stringify(fields, null, 2);
        } catch (error) {
          // fields_json остаётся исходным, отдельные поля всё равно передаются.
        }
      }
      payload.message = appendPreparationToApplicationText(payload.message);"""
new = """      payload.preparation_json = JSON.stringify(data, null, 2);
      payload.message = appendPreparationToApplicationText(payload.message);"""
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Preparation fields_json block not found exactly once")
    text = text.replace(old, new, 1)
preparation.write_text(text, encoding="utf-8")

policy = Path("policy.md")
text = policy.read_text(encoding="utf-8")
old = "    <p>При онлайн-отправке сведения передаются сервису Web3Forms для формирования и доставки email-сообщения. Email содержит основные поля анкеты, технический номер, источник страницы, рекламные метки, добровольный контекст подготовки и структурированную копию заявки.</p>"
new = "    <p>При онлайн-отправке сведения передаются сервису Web3Forms для формирования и доставки email-сообщения. Email содержит отдельные необходимые поля анкеты, технический номер, источник страницы, рекламные метки, добровольный контекст подготовки и готовый текст обращения. Полная JSON-копия всей заявки в email-канал дополнительно не дублируется.</p>"
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Policy Web3Forms duplication marker not found exactly once")
    text = text.replace(old, new, 1)
policy.write_text(text, encoding="utf-8")

contract = Path("docs/preparation-context-contract.md")
text = contract.read_text(encoding="utf-8")
old = "`fields_json` также содержит объект `preparation`."
new = "Полная JSON-копия заявки в Web3Forms не дублируется. Контекст остаётся в отдельных полях, `preparation_json` и разделе `ПОДГОТОВКА ДО ОБРАЩЕНИЯ` поля `message`."
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Preparation contract fields_json marker not found exactly once")
    text = text.replace(old, new, 1)
contract.write_text(text, encoding="utf-8")

print("Web3Forms data minimization migration applied")
