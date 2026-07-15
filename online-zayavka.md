---
layout: "default"
title: "Онлайн-заявка ипотечному брокеру | Татьяна Стерликова"
description: "Заполните и отправьте короткую онлайн-заявку на консультацию и ипотечное сопровождение из любого города. Подробные финансовые сведения можно добавить по желанию."
permalink: "/online-zayavka/"
breadcrumb: "Онлайн-заявка"
og_type: "website"
schema: '{"@context":"https://schema.org","@type":"Service","name":"Дистанционная консультация ипотечного брокера","description":"Первичный разбор ипотечной ситуации и подготовка дальнейшего маршрута в дистанционном формате.","provider":{"@type":"Person","name":"Татьяна Стерликова","telephone":"+79030250807"},"areaServed":{"@type":"Country","name":"Россия"},"serviceType":"Онлайн-консультация и сопровождение по ипотеке","url":"https://sterlikova-ipoteka.ru/online-zayavka/"}'
---

<section class="page-hero section">
  <p class="eyebrow">Дистанционно из любого города</p>
  <h1>Онлайн-заявка ипотечному брокеру</h1>
  <p class="lead">Для первого обращения достаточно имени, телефона, города и задачи. Стоимость объекта, взнос, доход и историю обращений в банки можно добавить по желанию.</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="#application-form">Заполнить короткую заявку</a>
    <a class="btn btn-light" href="tel:+79030250807">Позвонить</a>
    <a class="btn btn-light" href="{{ '/konsultaciya/' | relative_url }}">Как проходит консультация</a>
  </div>
  <ul class="trust-list"><li>Можно обратиться из любого города</li><li>Обязательных полей немного</li><li>Решение принимает банк</li></ul>
</section>

<section class="section application-layout" id="application-form">
  <div>
    <div class="section-head">
      <p class="eyebrow">Короткая анкета</p>
      <h2>Подготовьте обращение за несколько минут</h2>
      <p>Заполните основные поля. Дополнительные вводные помогут быстрее разобрать ситуацию, но не обязательны для отправки.</p>
    </div>

    {% include application-runtime-fallback.html runtime=true %}
    <noscript>{% include application-runtime-fallback.html %}</noscript>

    <form
      class="application-card"
      data-online-application
      data-lead-mode="{{ site.lead_capture.mode | default: 'disabled' | escape }}"
      data-web3forms-access-key="{{ site.lead_capture.web3forms_access_key | default: '' | escape }}"
      data-web3forms-endpoint="{{ site.lead_capture.web3forms_endpoint | default: 'https://api.web3forms.com/submit' | escape }}"
      data-lead-endpoint="{{ site.lead_capture.endpoint | default: '' | escape }}"
      data-thank-you-path="{{ site.lead_capture.thank_you_path | default: '/spasibo/' | escape }}"
      data-lead-timeout-ms="{{ site.lead_capture.timeout_ms | default: 8000 }}"
      data-lead-min-fill-ms="{{ site.lead_capture.min_fill_ms | default: 3000 }}"
      novalidate
    >
      <input name="source_page" type="hidden" value="">
      <input name="request_id" type="hidden" value="">
      <input name="form_started_at" type="hidden" value="">
      <input name="form_version" type="hidden" value="2">
      <div class="application-honeypot" aria-hidden="true">
        <label for="application-website">Оставьте это поле пустым</label>
        <input id="application-website" name="website" type="text" tabindex="-1" autocomplete="off">
      </div>

      <div class="application-step-label"><span>1</span><div><strong>Контакты и задача</strong><small>Этого достаточно для первого обращения</small></div></div>
      <div class="application-grid">
        <div class="application-field">
          <label for="application-name">Как к вам обращаться <span aria-hidden="true">*</span></label>
          <input id="application-name" name="client_name" type="text" autocomplete="name" autocapitalize="words" required maxlength="80" enterkeyhint="next" placeholder="Например, Анна">
        </div>
        <div class="application-field">
          <label for="application-phone">Телефон для связи <span aria-hidden="true">*</span></label>
          <input id="application-phone" name="phone" type="tel" autocomplete="tel" inputmode="tel" required maxlength="22" enterkeyhint="next" placeholder="+7 900 000-00-00" aria-describedby="application-phone-hint" data-phone-input>
          <small class="application-field-hint" id="application-phone-hint">Введите 10 цифр российского номера. Подойдут форматы +7 или 8.</small>
        </div>
        <div class="application-field">
          <label for="application-city">Город или населённый пункт <span aria-hidden="true">*</span></label>
          <input id="application-city" name="city" type="text" autocomplete="address-level2" autocapitalize="words" required maxlength="120" enterkeyhint="next" placeholder="Можно указать любой город">
        </div>
        <div class="application-field">
          <label for="application-contact">Удобный способ связи</label>
          <select id="application-contact" name="preferred_contact">
            <option value="Позвонить">Позвонить</option>
            <option value="MAX">MAX</option>
            <option value="ВКонтакте">ВКонтакте</option>
            <option value="SMS">SMS</option>
          </select>
        </div>
        <div class="application-field application-field-wide">
          <label for="application-scenario">Какая помощь нужна <span aria-hidden="true">*</span></label>
          <select id="application-scenario" name="scenario" required>
            <option value="">Выберите сценарий</option>
            <option>Первичная консультация и подбор ипотеки</option>
            <option>Покупка квартиры в новостройке</option>
            <option>Покупка вторичного жилья</option>
            <option>Покупка дома</option>
            <option>Строительство дома</option>
            <option>Семейная ипотека</option>
            <option>Материнский капитал</option>
            <option>Рефинансирование</option>
            <option>Банк отказал в ипотеке</option>
            <option>Плохая кредитная история</option>
            <option>Нет официального дохода</option>
            <option>Нет или мало первоначального взноса</option>
            <option>ИП или самозанятость</option>
            <option>Нужен созаёмщик</option>
            <option>Продажа старого и покупка нового жилья</option>
            <option>Другая ситуация</option>
          </select>
        </div>
      </div>

      {% include application-preparation-context.html %}

      <details class="application-more" data-application-more>
        <summary><span>Добавить подробности</span><small>Объект, стоимость, взнос, доход и обращения в банки</small></summary>
        <div class="application-step-label"><span>2</span><div><strong>Дополнительные вводные</strong><small>Необязательно, но поможет быстрее подготовиться к разговору</small></div></div>
        <div class="application-grid application-more-grid">
          <div class="application-field">
            <label for="application-object">Что планируете купить</label>
            <select id="application-object" name="object_type">
              <option value="Пока не выбрано">Пока не выбрано</option>
              <option>Квартира в новостройке</option>
              <option>Квартира на вторичном рынке</option>
              <option>Дом с участком</option>
              <option>Строительство дома</option>
              <option>Другой объект</option>
            </select>
          </div>
          <div class="application-field">
            <label for="application-price">Примерная стоимость объекта</label>
            <input id="application-price" name="object_price" type="text" inputmode="numeric" maxlength="40" placeholder="Например, 4 500 000 ₽">
          </div>
          <div class="application-field">
            <label for="application-down">Первоначальный взнос</label>
            <input id="application-down" name="down_payment" type="text" inputmode="numeric" maxlength="40" placeholder="Сумма, маткапитал или пока нет">
          </div>
          <div class="application-field">
            <label for="application-income">Как подтверждается доход</label>
            <select id="application-income" name="income_type">
              <option value="Не указано">Не указано</option>
              <option>Официальная работа</option>
              <option>ИП</option>
              <option>Самозанятость</option>
              <option>Смешанный доход</option>
              <option>Пенсия</option>
              <option>Доход без стандартной справки</option>
            </select>
          </div>
          <div class="application-field application-field-wide">
            <label for="application-history">Заявки, одобрения или отказы банков</label>
            <textarea id="application-history" name="bank_history" rows="3" maxlength="600" placeholder="Напишите кратко, в какие банки обращались и какой был результат"></textarea>
          </div>
          <div class="application-field application-field-wide">
            <label for="application-comment">Комментарий к ситуации</label>
            <textarea id="application-comment" name="comment" rows="5" maxlength="1200" placeholder="Доход, кредиты, состав семьи, сроки, выбранный объект и другие важные вводные"></textarea>
          </div>
        </div>
      </details>

      <label class="application-consent">
        <input name="consent" type="checkbox" required>
        <span>Я согласен на обработку и передачу указанных сведений для рассмотрения заявки и обратной связи, ознакомился с <a href="{{ '/policy/' | relative_url }}">политикой обработки данных</a> и <a href="{{ '/personal-data-consent/' | relative_url }}">текстом согласия</a>.</span>
      </label>

      <p class="application-privacy">После проверки и нажатия «Отправить заявку онлайн» сведения передаются через сервис Web3Forms в настроенный email-канал. Не указывайте паспортные данные, СНИЛС, реквизиты карт, коды подтверждения и не прикладывайте документы.</p>
      <button class="btn btn-primary application-submit" type="submit" data-application-submit disabled aria-busy="true">Проверить и подготовить заявку</button>
      <p class="application-status" data-application-status aria-live="polite">Загружаем форму…</p>
    </form>

    <section class="application-result" data-application-result hidden>
      <p class="eyebrow">Заявка готова</p>
      <h2>Проверьте текст и отправьте удобным способом</h2>
      <textarea data-application-output rows="16" readonly aria-label="Подготовленный текст заявки"></textarea>
      <p class="application-delivery-note" data-application-delivery-note>После проверки нажмите «Отправить заявку онлайн». При технической ошибке используйте резервный способ.</p>
      <div class="application-actions">
        <button class="btn btn-primary" type="button" data-application-direct-send hidden>Отправить заявку онлайн</button>
        <button class="btn btn-secondary" type="button" data-application-share>Поделиться заявкой</button>
        <a class="btn btn-secondary" href="#" data-application-sms>Отправить SMS</a>
        <button class="btn btn-light" type="button" data-application-copy>Скопировать текст</button>
        <a class="btn btn-light" href="https://vk.com/tatyanasterlikova" target="_blank" rel="noopener" data-application-vk>Открыть ВКонтакте</a>
        <button class="btn btn-light" type="button" data-copy-phone>Скопировать номер для MAX</button>
      </div>
      <p class="application-hint">После успешной онлайн-отправки откроется страница подтверждения с номером обращения. Резервные способы остаются доступны до перехода.</p>
    </section>
  </div>

  <aside class="application-aside">
    <div class="seo-panel">
      <h3>Короткой заявки достаточно</h3>
      <p>Для первого контакта нужны имя, телефон, город и задача. Остальные сведения можно уточнить во время разговора.</p>
    </div>
    <div class="seo-panel">
      <h3>Что произойдёт после обращения</h3>
      <ol>
        <li>Заявка поступит в настроенный email-канал с номером и источником обращения.</li>
        <li>Татьяна изучит основные вводные.</li>
        <li>Уточнит недостающие сведения.</li>
        <li>Предложит следующий шаг и формат работы.</li>
      </ol>
    </div>
    <div class="seo-panel">
      <h3>География работы</h3>
      <p>Первичную консультацию можно провести дистанционно из любого города. Локальные страницы Борисоглебска, Грибановского района и Поворино не ограничивают обращения из других регионов.</p>
      <p><a href="{{ '/geo/' | relative_url }}">Перейти к региональным материалам →</a></p>
    </div>
  </aside>
</section>

<section class="section muted">
  <div class="section-head"><p class="eyebrow">Два формата</p><h2>Частный онлайн-клиент или покупка через «ЭТАЖИ»</h2><p>При частном обращении объём и стоимость сопровождения согласуются после первичного разбора. Для сделки через компанию «ЭТАЖИ» состав услуги и порядок оплаты подтверждаются по действующим условиям компании и параметрам конкретной сделки.</p></div>
  <div class="grid cards-2">
    <article class="card"><h3>Частное дистанционное обращение</h3><p>Консультация, разбор ситуации и согласованный объём дальнейшей работы. Место проживания само по себе не мешает первичному онлайн-разбору.</p><a class="text-link" href="{{ '/stoimost/' | relative_url }}">Посмотреть частные тарифы →</a></article>
    <article class="card"><h3>Сделка через компанию «ЭТАЖИ»</h3><p>До начала сопровождения уточните, какие действия входят в услугу по линии компании и предусмотрена ли отдельная оплата в вашей ситуации.</p><a class="text-link" href="{{ '/etagi/' | relative_url }}">Уточнить условия «ЭТАЖИ» →</a></article>
  </div>
</section>

<section class="section cta-section"><div><p class="eyebrow">Нужен быстрый ответ?</p><h2>Можно не заполнять анкету</h2><p>Позвоните или напишите кратко: ваш город, цель и были ли обращения в банки.</p></div><div class="cta-actions"><a class="btn btn-primary" href="tel:+79030250807">8 903 025-08-07</a><button class="btn btn-secondary" type="button" data-copy-phone>MAX</button><a class="btn btn-secondary" href="https://vk.com/tatyanasterlikova" rel="noopener">ВКонтакте</a></div></section>

<script>
  (function () {
    var form = document.querySelector('[data-online-application]');
    if (!form) return;
    window.setTimeout(function () {
      if (form.dataset.applicationReady === 'true') return;
      var fallback = document.querySelector('[data-application-runtime-fallback]');
      var status = form.querySelector('[data-application-status]');
      if (fallback) fallback.hidden = false;
      if (status) {
        status.textContent = 'Форма не загрузилась. Используйте резервный способ обращения выше.';
        status.classList.add('is-error');
      }
    }, 5000);
  })();
</script>
<script src="{{ '/assets/js/thankyou-storage-privacy.js' | relative_url }}" defer></script>
<script src="{{ '/assets/js/application-delivery-keepalive.js' | relative_url }}" defer></script>
<script src="{{ '/assets/js/application-inputs.js' | relative_url }}" defer></script>
<script src="{{ '/assets/js/application-preparation.js' | relative_url }}" defer></script>
