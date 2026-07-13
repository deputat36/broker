(() => {
  const form = document.querySelector('[data-online-application]');
  if (!form) return;

  const result = document.querySelector('[data-application-result]');
  const output = document.querySelector('[data-application-output]');
  const status = form.querySelector('[data-application-status]');
  const copyButton = document.querySelector('[data-application-copy]');
  const shareButton = document.querySelector('[data-application-share]');
  const smsLink = document.querySelector('[data-application-sms]');
  const vkLink = document.querySelector('[data-application-vk]');
  const directSendButton = document.querySelector('[data-application-direct-send]');
  const deliveryNote = document.querySelector('[data-application-delivery-note]');
  let preparedText = '';
  let preparedPayload = null;
  let startGoalSent = false;
  let directSent = false;

  const SCENARIO_BY_SLUG = {
    'podbor-ipoteki': 'Первичная консультация и подбор ипотеки',
    'ipoteka-na-novostroyku': 'Покупка квартиры в новостройке',
    'ipoteka-na-vtorichnoe-zhile': 'Покупка вторичного жилья',
    'ipoteka-na-kvartiru': 'Покупка вторичного жилья',
    'ipoteka-na-dom': 'Покупка дома',
    'ipoteka-na-stroitelstvo-doma': 'Строительство дома',
    'semeynaya-ipoteka': 'Семейная ипотека',
    'ipoteka-dlya-molodoy-semi': 'Семейная ипотека',
    'materinskiy-kapital': 'Материнский капитал',
    'ipoteka-s-materinskim-kapitalom': 'Материнский капитал',
    'refinansirovanie-ipoteki': 'Рефинансирование',
    'otkazali-v-ipoteke': 'Банк отказал в ипотеке',
    'ipoteka-s-plohoy-kreditnoy-istoriey': 'Плохая кредитная история',
    'ipoteka-bez-oficialnogo-dohoda': 'Нет официального дохода',
    'ipoteka-bez-pervonachalnogo-vznosa': 'Нет или мало первоначального взноса',
    'ipoteka-dlya-ip-samozanyatyh': 'ИП или самозанятость',
    'ipoteka-s-sozaemshchikom': 'Нужен созаёмщик',
    'ipoteka-pri-prodazhe-starogo-zhilya': 'Продажа старого и покупка нового жилья',
    'slozhnaya-ipoteka': 'Другая ситуация',
    'ipoteka-dlya-pensionerov': 'Другая ситуация'
  };

  const OBJECT_BY_SLUG = {
    'ipoteka-na-novostroyku': 'Квартира в новостройке',
    'ipoteka-na-vtorichnoe-zhile': 'Квартира на вторичном рынке',
    'ipoteka-na-kvartiru': 'Квартира на вторичном рынке',
    'ipoteka-na-dom': 'Дом с участком',
    'ipoteka-na-stroitelstvo-doma': 'Строительство дома'
  };

  const CITY_BY_PREFIX = {
    '/geo/borisoglebsk/': 'Борисоглебск',
    '/geo/gribanovskiy/': 'Грибановский район',
    '/geo/povorino/': 'Поворино'
  };

  function track(goalName) {
    if (typeof window.sendGoal === 'function') window.sendGoal(goalName);
  }

  function boundedNumber(value, fallback, min, max) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.min(max, Math.max(min, parsed));
  }

  function normalizeEndpoint(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    try {
      const url = new URL(raw, window.location.origin);
      return url.protocol === 'https:' ? url.href : '';
    } catch (error) {
      return '';
    }
  }

  const leadConfig = {
    mode: String(form.dataset.leadMode || 'disabled').trim().toLowerCase(),
    endpoint: normalizeEndpoint(form.dataset.leadEndpoint),
    timeoutMs: boundedNumber(form.dataset.leadTimeoutMs, 8000, 2000, 20000),
    minFillMs: boundedNumber(form.dataset.leadMinFillMs, 3000, 1000, 30000)
  };
  const directDeliveryEnabled = leadConfig.mode === 'direct' && Boolean(leadConfig.endpoint);

  function normalizeSourcePath(value) {
    if (!value) return '';
    try {
      const url = new URL(value, window.location.origin);
      if (url.origin !== window.location.origin) return '';
      const path = url.pathname.replace(/\/index\.html$/, '/').replace(/\/+$/, '/');
      return path || '/';
    } catch (error) {
      return '';
    }
  }

  function resolveSourcePath(params) {
    const parameterSource = normalizeSourcePath(params.get('source'));
    if (parameterSource && parameterSource !== '/online-zayavka/') return parameterSource;

    const referrerSource = normalizeSourcePath(document.referrer);
    if (referrerSource && referrerSource !== '/online-zayavka/') return referrerSource;
    return '';
  }

  function sourceSlug(sourcePath) {
    const parts = sourcePath.split('/').filter(Boolean);
    return parts.length ? parts[parts.length - 1] : '';
  }

  function setSelectValue(fieldName, value) {
    const field = form.elements.namedItem(fieldName);
    if (!field || !value || field.tagName !== 'SELECT') return false;
    const option = Array.from(field.options).find((item) => item.value === value || item.text === value);
    if (!option) return false;
    field.value = option.value;
    return true;
  }

  function setInputValue(fieldName, value) {
    const field = form.elements.namedItem(fieldName);
    if (!field || !value) return false;
    const maxLength = Number(field.maxLength);
    field.value = value.slice(0, maxLength > 0 ? maxLength : value.length);
    return true;
  }

  function rawFieldValue(name) {
    const field = form.elements.namedItem(name);
    return field ? String(field.value || '').trim() : '';
  }

  function fieldValue(name, fallback = 'Не указано') {
    return rawFieldValue(name) || fallback;
  }

  function setStatus(message, type = '') {
    if (!status) return;
    status.textContent = message;
    status.classList.remove('is-error', 'is-success');
    if (type) status.classList.add(`is-${type}`);
  }

  function setDeliveryNote(message, type = '') {
    if (!deliveryNote) return;
    deliveryNote.textContent = message;
    deliveryNote.classList.remove('is-error', 'is-success');
    if (type) deliveryNote.classList.add(`is-${type}`);
  }

  function createRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    const randomPart = Math.random().toString(36).slice(2, 12);
    return `lead-${Date.now().toString(36)}-${randomPart}`;
  }

  function resetAttemptMetadata() {
    setInputValue('request_id', createRequestId());
    setInputValue('form_started_at', String(Date.now()));
    directSent = false;
    if (directSendButton) {
      directSendButton.disabled = false;
      directSendButton.removeAttribute('aria-busy');
      directSendButton.textContent = 'Отправить заявку онлайн';
    }
  }

  function buildApplicationText() {
    const lines = [
      'ОНЛАЙН-ЗАЯВКА С САЙТА sterlikova-ipoteka.ru',
      `Номер заявки: ${fieldValue('request_id')}`,
      `Источник обращения: ${fieldValue('source_page', 'Прямой переход на форму')}`,
      '',
      `Имя: ${fieldValue('client_name')}`,
      `Телефон: ${fieldValue('phone')}`,
      `Город / населённый пункт: ${fieldValue('city')}`,
      `Удобный способ связи: ${fieldValue('preferred_contact')}`,
      '',
      `Какая помощь нужна: ${fieldValue('scenario')}`,
      `Объект: ${fieldValue('object_type')}`,
      `Примерная стоимость: ${fieldValue('object_price')}`,
      `Первоначальный взнос: ${fieldValue('down_payment')}`,
      `Подтверждение дохода: ${fieldValue('income_type')}`,
      '',
      `Заявки, одобрения или отказы банков: ${fieldValue('bank_history')}`,
      `Комментарий: ${fieldValue('comment')}`,
      '',
      'Прошу связаться со мной для первичного разбора ситуации. Понимаю, что окончательное решение по ипотеке принимает банк.'
    ];

    return lines.join('\n');
  }

  function buildLeadPayload() {
    const startedAt = Number(rawFieldValue('form_started_at'));
    return {
      schema_version: 1,
      request_id: fieldValue('request_id'),
      form_version: fieldValue('form_version', '1'),
      submitted_at: new Date().toISOString(),
      form_fill_ms: Number.isFinite(startedAt) ? Math.max(0, Date.now() - startedAt) : null,
      source_page: fieldValue('source_page', 'Прямой переход на форму'),
      page_url: window.location.href,
      client: {
        name: fieldValue('client_name'),
        phone: fieldValue('phone'),
        city: fieldValue('city'),
        preferred_contact: fieldValue('preferred_contact')
      },
      mortgage: {
        scenario: fieldValue('scenario'),
        object_type: fieldValue('object_type'),
        object_price: fieldValue('object_price'),
        down_payment: fieldValue('down_payment'),
        income_type: fieldValue('income_type'),
        bank_history: fieldValue('bank_history'),
        comment: fieldValue('comment')
      },
      consent: true
    };
  }

  function getSpamReason() {
    if (rawFieldValue('website')) return 'honeypot';
    const startedAt = Number(rawFieldValue('form_started_at'));
    if (!Number.isFinite(startedAt)) return 'missing_start_time';
    if (Date.now() - startedAt < leadConfig.minFillMs) return 'too_fast';
    return '';
  }

  function setFieldValidity() {
    form.querySelectorAll('input, select, textarea').forEach((field) => {
      if (field.type === 'checkbox' || field.type === 'hidden' || field.name === 'website') return;
      field.setAttribute('aria-invalid', String(!field.checkValidity()));
    });
  }

  async function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }

    if (!output) throw new Error('Поле с текстом заявки не найдено');
    output.focus();
    output.select();
    const copied = document.execCommand('copy');
    output.setSelectionRange(0, 0);
    if (!copied) throw new Error('Не удалось скопировать текст');
  }

  function prefillFromSource() {
    const params = new URLSearchParams(window.location.search);
    const sourcePath = resolveSourcePath(params);
    const sourceField = form.elements.namedItem('source_page');
    if (sourceField) sourceField.value = sourcePath || 'Прямой переход на форму';

    const explicitCity = params.get('city');
    if (explicitCity) {
      setInputValue('city', explicitCity);
    } else if (sourcePath) {
      const matchingPrefix = Object.keys(CITY_BY_PREFIX).find((prefix) => sourcePath.startsWith(prefix));
      if (matchingPrefix) setInputValue('city', CITY_BY_PREFIX[matchingPrefix]);
    }

    const explicitContact = params.get('contact');
    if (explicitContact) setSelectValue('preferred_contact', explicitContact);

    const explicitScenario = params.get('scenario');
    const slug = sourceSlug(sourcePath);
    if (!setSelectValue('scenario', explicitScenario) && slug) {
      setSelectValue('scenario', SCENARIO_BY_SLUG[slug]);
    }

    const explicitObject = params.get('object');
    if (!setSelectValue('object_type', explicitObject) && slug) {
      setSelectValue('object_type', OBJECT_BY_SLUG[slug]);
    }

    if (sourcePath) track('online_application_prefill');
  }

  async function parseEndpointResponse(response) {
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return {};
    try {
      return await response.json();
    } catch (error) {
      return {};
    }
  }

  async function sendDirectly() {
    if (!preparedPayload || !preparedText || !directDeliveryEnabled || directSent) return;

    const spamReason = getSpamReason();
    if (spamReason) {
      setDeliveryNote('Не удалось подтвердить корректность формы. Используйте SMS, MAX, ВКонтакте или копирование текста.', 'error');
      track('online_application_spam_block');
      return;
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), leadConfig.timeoutMs);
    directSendButton.disabled = true;
    directSendButton.setAttribute('aria-busy', 'true');
    directSendButton.textContent = 'Отправляем…';
    setDeliveryNote('Передаём заявку в подключённый канал. Не закрывайте страницу.');

    try {
      track('online_application_direct_attempt');
      const response = await fetch(leadConfig.endpoint, {
        method: 'POST',
        mode: 'cors',
        credentials: 'omit',
        referrerPolicy: 'strict-origin-when-cross-origin',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(preparedPayload),
        signal: controller.signal
      });
      const responsePayload = await parseEndpointResponse(response);
      if (!response.ok || responsePayload.ok === false) {
        throw new Error(responsePayload.message || `HTTP ${response.status}`);
      }

      directSent = true;
      const leadId = String(responsePayload.lead_id || responsePayload.id || '').trim();
      const suffix = leadId ? ` Номер обращения: ${leadId}.` : '';
      setDeliveryNote(`Заявка передана в подключённый канал.${suffix} Сохраните текст ниже до ответа Татьяны.`, 'success');
      directSendButton.textContent = 'Заявка отправлена';
      track('online_application_direct_success');
    } catch (error) {
      const timedOut = error && error.name === 'AbortError';
      setDeliveryNote(
        timedOut
          ? 'Сервер не ответил вовремя. Данные не потеряны — отправьте готовый текст через SMS, MAX или ВКонтакте.'
          : 'Прямая отправка не удалась. Данные не потеряны — используйте один из резервных способов ниже.',
        'error'
      );
      directSendButton.disabled = false;
      directSendButton.removeAttribute('aria-busy');
      directSendButton.textContent = 'Повторить отправку';
      track(timedOut ? 'online_application_direct_timeout' : 'online_application_direct_error');
    } finally {
      window.clearTimeout(timeoutId);
      if (directSent) {
        directSendButton.disabled = true;
        directSendButton.removeAttribute('aria-busy');
      }
    }
  }

  if (shareButton && !navigator.share) shareButton.hidden = true;
  if (directSendButton) directSendButton.hidden = !directDeliveryEnabled;
  setDeliveryNote(
    directDeliveryEnabled
      ? 'После проверки текста заявку можно отправить напрямую. При ошибке останутся SMS, MAX, ВКонтакте и копирование.'
      : 'Прямая серверная отправка пока не подключена. Используйте один из доступных способов ниже.'
  );
  resetAttemptMetadata();
  prefillFromSource();
  if (directDeliveryEnabled) track('online_application_endpoint_ready');

  form.addEventListener('input', () => {
    if (!startGoalSent) {
      startGoalSent = true;
      track('online_application_start');
    }

    if (result && !result.hidden) {
      result.hidden = true;
      preparedText = '';
      preparedPayload = null;
      resetAttemptMetadata();
      setStatus('Данные изменены. Подготовьте заявку заново.');
    }
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    setFieldValidity();

    if (!form.checkValidity()) {
      form.reportValidity();
      setStatus('Заполните обязательные поля и подтвердите согласие.', 'error');
      track('online_application_validation_error');
      return;
    }

    preparedText = buildApplicationText();
    preparedPayload = buildLeadPayload();
    if (output) output.value = preparedText;
    if (smsLink) smsLink.href = `sms:+79030250807?body=${encodeURIComponent(preparedText)}`;
    if (result) result.hidden = false;

    setStatus('Заявка подготовлена. Выберите способ отправки ниже.', 'success');
    setDeliveryNote(
      directDeliveryEnabled
        ? 'Проверьте текст. Можно отправить заявку напрямую или выбрать резервный канал.'
        : 'Прямая серверная отправка пока не подключена. Используйте один из доступных способов ниже.'
    );
    track('online_application_prepare');

    window.setTimeout(() => {
      if (result) result.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (output) output.focus({ preventScroll: true });
    }, 0);
  });

  if (directSendButton) directSendButton.addEventListener('click', sendDirectly);

  if (copyButton) {
    copyButton.addEventListener('click', async () => {
      if (!preparedText) return;
      try {
        await copyText(preparedText);
        setStatus('Текст заявки скопирован.', 'success');
        copyButton.textContent = 'Заявка скопирована';
        track('online_application_copy');
        window.setTimeout(() => { copyButton.textContent = 'Скопировать текст'; }, 2500);
      } catch (error) {
        setStatus('Не удалось скопировать автоматически. Выделите текст заявки вручную.', 'error');
      }
    });
  }

  if (shareButton) {
    shareButton.addEventListener('click', async () => {
      if (!preparedText || !navigator.share) return;
      try {
        await navigator.share({
          title: 'Онлайн-заявка ипотечному брокеру',
          text: preparedText
        });
        setStatus('Заявка передана в выбранное приложение.', 'success');
        track('online_application_share');
      } catch (error) {
        if (error && error.name === 'AbortError') return;
        setStatus('Системное меню недоступно. Скопируйте текст или отправьте SMS.', 'error');
      }
    });
  }

  if (smsLink) {
    smsLink.addEventListener('click', (event) => {
      if (!preparedText) {
        event.preventDefault();
        setStatus('Сначала подготовьте заявку.', 'error');
        return;
      }
      track('online_application_sms');
    });
  }

  if (vkLink) {
    vkLink.addEventListener('click', async () => {
      if (!preparedText) return;
      try {
        await copyText(preparedText);
        setStatus('Текст скопирован. Вставьте его в сообщение ВКонтакте.', 'success');
      } catch (error) {
        setStatus('ВКонтакте открыт. Скопируйте текст из поля заявки вручную.', 'error');
      }
      track('online_application_vk');
    });
  }
})();
