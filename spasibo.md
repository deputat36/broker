---
layout: default
title: Заявка отправлена | Ипотечный брокер Татьяна Стерликова
description: Сервис подтвердил передачу онлайн-заявки ипотечному брокеру. Сохраните номер обращения и при необходимости свяжитесь с Татьяной Стерликовой напрямую.
permalink: /spasibo/
breadcrumb: Заявка отправлена
og_type: website
robots: noindex, follow
sitemap: false
---

<section class="page-hero section">
  <p class="eyebrow">Заявка отправлена</p>
  <h1>Спасибо, обращение передано</h1>
  <p class="lead" id="thankyou-message">Сервис подтвердил передачу обращения через настроенный канал. Сохраните номер заявки до ответа Татьяны.</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="tel:+79030250807">Позвонить брокеру</a>
    <a class="btn btn-light" href="{{ '/uslugi/' | relative_url }}">Посмотреть услуги</a>
    <a class="btn btn-light" href="{{ '/online-zayavka/' | relative_url }}">Отправить ещё одну заявку</a>
  </div>
</section>

<section class="section">
  <div class="grid cards-4" aria-label="Данные отправленного обращения">
    <article class="card"><p class="eyebrow">Номер обращения</p><h2 id="lead-id">—</h2><p>Сохраните этот номер до ответа Татьяны.</p></article>
    <article class="card"><p class="eyebrow">Сценарий</p><h2 id="lead-scenario">Ипотечная консультация</h2><p>Основная задача, указанная в анкете.</p></article>
    <article class="card"><p class="eyebrow">Город</p><h2 id="lead-city">Не указан</h2><p>Первичный разбор доступен дистанционно.</p></article>
    <article class="card"><p class="eyebrow">Приоритет</p><h2 id="lead-status">Новая</h2><p>Внутренняя квалификация помогает быстрее разобрать вводные.</p></article>
  </div>
</section>

<section class="section muted">
  <div class="section-head"><p class="eyebrow">Что будет дальше</p><h2>От заявки до следующего шага</h2><p>Техническое подтверждение отправки не является одобрением ипотеки и не создаёт обязательств по платному сопровождению.</p></div>
  <div class="grid cards-3">
    <article class="card"><h3>1. Проверка вводных</h3><p>Татьяна посмотрит город, цель, объект, первоначальный взнос, доход и историю обращений в банки.</p></article>
    <article class="card"><h3>2. Уточняющий контакт</h3><p>При необходимости задаст дополнительные вопросы и предложит удобный формат разговора.</p></article>
    <article class="card"><h3>3. Согласование маршрута</h3><p>Вы получите следующий шаг. Возможность и условия дальнейшего сопровождения обсуждаются отдельно.</p></article>
  </div>
</section>

<section class="section compact-section">
  <div class="notice">
    <div><p class="eyebrow">Важно</p><h2>Не отправляйте документы повторно через открытые каналы</h2><p>Паспорт, СНИЛС, кредитный отчёт и банковские документы передаются только после отдельного согласования безопасного способа.</p></div>
    <a class="btn btn-dark" href="{{ '/policy/' | relative_url }}">Политика обработки данных</a>
  </div>
</section>

<script>
  document.addEventListener('DOMContentLoaded', function () {
    var legacyContext = window.thankYouContext || {};
    var storageKey = 'sterlikovaMortgageLastLead';
    var lastLead = {};

    function cleanText(value, fallback, maxLength) {
      var normalized = String(value || '').replace(/\s+/g, ' ').trim();
      return normalized ? normalized.slice(0, maxLength) : fallback;
    }

    function cleanRequestId(value) {
      var requestId = cleanText(value, '', 80);
      var uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      var fallbackPattern = /^IP-\d{8}-[A-Z0-9]{6,16}$/;
      return uuidPattern.test(requestId) || fallbackPattern.test(requestId) ? requestId : '—';
    }

    try {
      lastLead = JSON.parse(window.localStorage.getItem(storageKey) || '{}');
      var expiresAt = Date.parse(lastLead.expires_at || '');
      if (Object.keys(lastLead).length && (!Number.isFinite(expiresAt) || expiresAt <= Date.now())) {
        window.localStorage.removeItem(storageKey);
        lastLead = {};
      }
    } catch (error) {
      lastLead = {};
    }

    var requestId = cleanRequestId(legacyContext.id || lastLead.request_id);
    var scenario = cleanText(legacyContext.scenario || lastLead.scenario, 'Ипотечная консультация', 120);
    var city = cleanText(lastLead.city, 'Не указан', 80);
    var rawStatus = cleanText(legacyContext.status || (lastLead.qualification && lastLead.qualification.status), 'new', 20);
    var statusMap = { hot: 'Срочная', warm: 'Тёплая', cold: 'Требует уточнения', new: 'Новая' };
    var status = Object.prototype.hasOwnProperty.call(statusMap, rawStatus) ? rawStatus : 'new';

    document.getElementById('lead-id').textContent = requestId;
    document.getElementById('lead-scenario').textContent = scenario;
    document.getElementById('lead-city').textContent = city;
    document.getElementById('lead-status').textContent = statusMap[status];

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ event: 'lead_thankyou_view' });
    if (typeof window.sendGoal === 'function') window.sendGoal('lead_thankyou_view');
    try { delete window.thankYouContext; } catch (error) { window.thankYouContext = {}; }
  });
</script>
