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
  <div class="grid cards-3" aria-label="Подтверждение отправленного обращения">
    <article class="card"><p class="eyebrow">Номер обращения</p><h2 id="lead-id">—</h2><p>Сохраните этот номер до ответа Татьяны.</p></article>
    <article class="card"><p class="eyebrow">Передача</p><h2>Подтверждена</h2><p>Хотя бы один настроенный канал принял обращение.</p></article>
    <article class="card"><p class="eyebrow">Следующий шаг</p><h2>Обратная связь</h2><p>Татьяна изучит вводные и свяжется с вами удобным способом.</p></article>
  </div>
  <div hidden aria-hidden="true">
    <span id="lead-scenario"></span>
    <span id="lead-city"></span>
    <span id="lead-status"></span>
  </div>
</section>

<section class="section muted">
  <div class="section-head"><p class="eyebrow">Что будет дальше</p><h2>От заявки до следующего шага</h2><p>Техническое подтверждение отправки не является одобрением ипотеки и не создаёт обязательств по платному сопровождению.</p></div>
  <div class="grid cards-3">
    <article class="card"><h3>1. Проверка вводных</h3><p>Татьяна посмотрит цель, объект, первоначальный взнос, доход и историю обращений в банки.</p></article>
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

    function cleanRequestId(value) {
      var requestId = String(value || '').replace(/\s+/g, ' ').trim().slice(0, 80);
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
      try { window.localStorage.removeItem(storageKey); } catch (_storageError) { /* Доступ к хранилищу запрещён. */ }
      lastLead = {};
    }

    var requestId = cleanRequestId(legacyContext.id || lastLead.request_id);
    document.getElementById('lead-id').textContent = requestId;

    if (requestId !== '—' && lastLead.expires_at) {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify({
          request_id: requestId,
          expires_at: new Date(Date.parse(lastLead.expires_at)).toISOString()
        }));
      } catch (_storageError) { /* Страница продолжает работать без localStorage. */ }
    }

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({ event: 'lead_thankyou_view' });
    if (typeof window.sendGoal === 'function') window.sendGoal('lead_thankyou_view');
    try { delete window.thankYouContext; } catch (error) { window.thankYouContext = {}; }
  });
</script>
