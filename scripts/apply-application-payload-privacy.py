#!/usr/bin/env python3
"""Одноразово канонизирует безопасный контекст явного payload заявки."""

from pathlib import Path

app = Path("assets/js/online-application.js")
text = app.read_text(encoding="utf-8")

old = """  function normalizePhone(value) {
    return String(value || '').replace(/[^\\d+]/g, '');
  }

  function getTrackingData() {"""
new = """  function normalizePhone(value) {
    return String(value || '').replace(/[^\\d+]/g, '');
  }

  function getSafePageContext() {
    if (typeof window.getSiteSafePageContext === 'function') return window.getSiteSafePageContext();
    const normalizedPath = String(window.location.pathname || '/')
      .replace(/\\/index\\.html$/, '/')
      .replace(/\\/+$/, '/') || '/';
    return {
      page_url: `${window.location.origin}${normalizedPath}`,
      page_path: normalizedPath,
      referrer: ''
    };
  }

  function getTrackingData() {"""
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Safe context helper marker not found exactly once")
    text = text.replace(old, new, 1)

old = """    const startedAt = Number(rawFieldValue('form_started_at'));
    const payload = {"""
new = """    const startedAt = Number(rawFieldValue('form_started_at'));
    const pageContext = getSafePageContext();
    const payload = {"""
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Payload preamble marker not found exactly once")
    text = text.replace(old, new, 1)

old = """      page_url: window.location.href,
      page_title: document.title,
      referrer: document.referrer || '',
      tracking: getTrackingData(),"""
new = """      page_url: pageContext.page_url,
      page_title: document.title,
      referrer: pageContext.referrer,
      tracking: getTrackingData(),"""
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Unsafe payload marker not found exactly once")
    text = text.replace(old, new, 1)

app.write_text(text, encoding="utf-8")

policy = Path("policy.md")
text = policy.read_text(encoding="utf-8")
old = "      <li>страница обращения, referrer, UTM-метки и рекламные click-id;</li>"
new = "      <li>страница обращения без query-параметров и fragment, сокращённый referrer, UTM-метки и рекламные click-id;</li>"
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Policy data-list marker not found exactly once")
    text = text.replace(old, new, 1)

old = "    <p>При онлайн-отправке сведения передаются сервису Web3Forms для формирования и доставки email-сообщения. Email содержит основные поля анкеты, технический номер, источник страницы, рекламные метки, добровольный контекст подготовки и структурированную копию заявки.</p>"
new = old + "\n    <p>В технический контекст заявки передаётся безопасный адрес текущей страницы без query-параметров и fragment. Внутренний referrer сокращается до origin и пути, внешний — до origin. UTM-метки и рекламные click-id передаются отдельно только по фиксированному списку.</p>"
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("Policy Web3Forms marker not found exactly once")
    text = text.replace(old, new, 1)

policy.write_text(text, encoding="utf-8")
print("Application payload privacy migration applied")
