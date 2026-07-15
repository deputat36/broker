---
layout: "default"
title: "Статус онлайн-заявки | Ипотечный брокер Татьяна Стерликова"
description: "Проверка статуса онлайн-заявки ипотечному брокеру. Подтверждение отправки показывается только при наличии корректного номера обращения."
permalink: "/spasibo/"
breadcrumb: "Статус заявки"
og_type: "website"
robots: "noindex, follow"
sitemap: false
---

<section class="page-hero section" data-thankyou-page data-state="unverified">
  <p class="eyebrow" id="thankyou-eyebrow">Статус обращения</p>
  <h1 id="thankyou-title">Проверяем подтверждение обращения</h1>
  <p class="lead" id="thankyou-message">Подтверждение появится, если сервис действительно принял заявку и передал номер обращения. При прямом переходе на эту страницу статус отправки не считается подтверждённым.</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="tel:+79030250807">Позвонить брокеру</a>
    <a class="btn btn-light" href="{{ '/online-zayavka/' | relative_url }}">Вернуться к онлайн-заявке</a>
    <a class="btn btn-light" href="{{ '/uslugi/' | relative_url }}">Посмотреть услуги</a>
  </div>
</section>

<section class="section">
  <div class="grid cards-3" aria-label="Статус обращения">
    <article class="card"><p class="eyebrow">Номер обращения</p><h2 id="lead-id">—</h2><p id="lead-id-note">Номер появится после подтверждённой отправки.</p></article>
    <article class="card"><p class="eyebrow">Передача</p><h2 id="delivery-status">Не подтверждена</h2><p id="delivery-note">Прямой переход на страницу не подтверждает передачу данных.</p></article>
    <article class="card"><p class="eyebrow">Следующий шаг</p><h2 id="next-step-title">Проверьте отправку</h2><p id="next-step-note">Вернитесь к форме или свяжитесь с Татьяной напрямую.</p></article>
  </div>
</section>

<section class="section muted">
  <div class="section-head"><p class="eyebrow">После подтверждённой отправки</p><h2>Что произойдёт дальше</h2><p>Техническое подтверждение отправки не является одобрением ипотеки и не создаёт обязательств по платному сопровождению.</p></div>
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
      return uuidPattern.test(requestId) || fallbackPattern.test(requestId) ? requestId : '';
    }

    function setText(id, value) {
      var element = document.getElementById(id);
      if (element) element.textContent = value;
    }

    function trackVerifiedView(requestId) {
      var trackingKey = 'sterlikovaThankYouTracked:' + requestId;
      try {
        if (window.sessionStorage.getItem(trackingKey) === '1') return;
        window.sessionStorage.setItem(trackingKey, '1');
      } catch (_storageError) { /* Аналитика продолжает работать без sessionStorage. */ }
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: 'lead_thankyou_view' });
      if (typeof window.sendGoal === 'function') window.sendGoal('lead_thankyou_view');
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

    var requestId = cleanRequestId(legacyContext.id) || cleanRequestId(lastLead.request_id);
    var page = document.querySelector('[data-thankyou-page]');

    if (requestId) {
      if (page) page.dataset.state = 'verified';
      setText('thankyou-eyebrow', 'Заявка отправлена');
      setText('thankyou-title', 'Спасибо, обращение передано');
      setText('thankyou-message', 'Сервис подтвердил передачу обращения через настроенный канал. Сохраните номер заявки до ответа Татьяны.');
      setText('lead-id', requestId);
      setText('lead-id-note', 'Сохраните этот номер до ответа Татьяны.');
      setText('delivery-status', 'Подтверждена');
      setText('delivery-note', 'Хотя бы один настроенный канал принял обращение.');
      setText('next-step-title', 'Обратная связь');
      setText('next-step-note', 'Татьяна изучит вводные и свяжется с вами удобным способом.');

      if (lastLead.expires_at) {
        try {
          window.localStorage.setItem(storageKey, JSON.stringify({
            request_id: requestId,
            expires_at: new Date(Date.parse(lastLead.expires_at)).toISOString()
          }));
        } catch (_storageError) { /* Страница продолжает работать без localStorage. */ }
      }
      trackVerifiedView(requestId);
    } else {
      if (page) page.dataset.state = 'unverified';
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: 'lead_thankyou_unverified_view' });
    }

    try { delete window.thankYouContext; } catch (error) { window.thankYouContext = {}; }
  });
</script>
