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
  <div class="section-head"><p class="eyebrow">После технического подтверждения</p><h2>Что можно сделать дальше</h2><p>Успешный ответ сервиса означает технический приём обращения, но сам по себе не подтверждает доставку или прочтение email получателем, не является одобрением ипотеки и не создаёт обязательств по платному сопровождению.</p></div>
  <div class="grid cards-3">
    <article class="card"><h3>1. Сохраните номер</h3><p>Номер обращения поможет отличить подтверждённую отправку от повторного или прямого перехода на эту страницу.</p></article>
    <article class="card"><h3>2. При необходимости подтвердите получение</h3><p>Если вопрос срочный или важно отдельно подтвердить получение обращения, свяжитесь с Татьяной напрямую по телефону, через MAX или ВКонтакте.</p></article>
    <article class="card"><h3>3. После установления контакта</h3><p>Можно уточнить недостающие вводные и согласовать следующий шаг. Возможность и условия дальнейшего сопровождения обсуждаются отдельно.</p></article>
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

    var contextRequestId = cleanRequestId(legacyContext.id);
    var storedRequestId = cleanRequestId(lastLead.request_id);
    var requestId = contextRequestId || storedRequestId;
    var currentRedirectVerified = Boolean(contextRequestId);
    var page = document.querySelector('[data-thankyou-page]');

    if (requestId) {
      if (page) page.dataset.state = currentRedirectVerified ? 'verified' : 'restored';
      setText('lead-id', requestId);
      setText('next-step-title', 'Сохраните номер');
      setText('next-step-note', 'Если важно подтвердить получение обращения, свяжитесь с Татьяной напрямую.');

      if (currentRedirectVerified) {
        setText('thankyou-eyebrow', 'Заявка принята сервисом');
        setText('thankyou-title', 'Обращение технически принято');
        setText('thankyou-message', 'Сервис вернул успешный технический ответ и номер обращения. Это не подтверждает доставку или прочтение email получателем.');
        setText('lead-id-note', 'Сохраните этот номер для проверки обращения.');
        setText('delivery-status', 'Принято сервисом');
        setText('delivery-note', 'Получен технический успешный ответ канала. Фактическое получение email отдельно не подтверждено.');
        trackVerifiedView(contextRequestId);
      } else {
        setText('thankyou-eyebrow', 'Последнее подтверждённое обращение');
        setText('thankyou-title', 'Найдено ранее подтверждённое обращение');
        setText('thankyou-message', 'В этом браузере сохранён номер недавнего обращения. Это не новая отправка заявки.');
        setText('lead-id-note', 'Это номер последнего сохранённого обращения в этом браузере.');
        setText('delivery-status', 'Подтверждена ранее');
        setText('delivery-note', 'Сохранённый статус не считается новой отправкой и новой конверсией.');
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ event: 'lead_thankyou_restored_view' });
      }

      if (lastLead.expires_at) {
        try {
          window.localStorage.setItem(storageKey, JSON.stringify({
            request_id: requestId,
            expires_at: new Date(Date.parse(lastLead.expires_at)).toISOString()
          }));
        } catch (_storageError) { /* Страница продолжает работать без localStorage. */ }
      }
    } else {
      if (page) page.dataset.state = 'unverified';
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: 'lead_thankyou_unverified_view' });
    }

    try { delete window.thankYouContext; } catch (error) { window.thankYouContext = {}; }
  });
</script>
