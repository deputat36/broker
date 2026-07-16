(() => {
  const form = document.querySelector('[data-online-application]');
  if (!form) return;

  const result = document.querySelector('[data-application-result]');
  const output = document.querySelector('[data-application-output]');
  const status = form.querySelector('[data-application-status]');
  const submitButton = form.querySelector('[data-application-submit]');
  const runtimeFallback = document.querySelector('[data-application-runtime-fallback]');
  const copyButton = document.querySelector('[data-application-copy]');
  const shareButton = document.querySelector('[data-application-share]');
  const smsLink = document.querySelector('[data-application-sms]');
  const vkLink = document.querySelector('[data-application-vk]');
  const directSendButton = document.querySelector('[data-application-direct-send]');
  const deliveryNote = document.querySelector('[data-application-delivery-note]');
  const LAST_LEAD_STORAGE_KEY = 'sterlikovaMortgageLastLead';
  const LAST_LEAD_RETENTION_MS = 24 * 60 * 60 * 1000;

  let preparedText = '';
  let preparedPayload = null;
  let startGoalSent = false;
  let deliveryCompleted = false;

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
    return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
  }

  function normalizeHttpsUrl(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    try {
      const url = new URL(raw, window.location.origin);
      return url.protocol === 'https:' ? url.href : '';
    } catch (error) {
      return '';
    }
  }

  function normalizeInternalPath(value, fallback) {
    const raw = String(value || '').trim();
    if (!raw) return fallback;
    try {
      const url = new URL(raw, window.location.origin);
      if (url.origin !== window.location.origin) return fallback;
      const path = url.pathname.replace(/\/index\.html$/, '/');
      return path.startsWith('/') ? path : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function validWeb3FormsKey(value) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value || '').trim());
  }

  const leadConfig = {
    mode: String(form.dataset.leadMode || 'disabled').trim().toLowerCase(),
    web3formsAccessKey: String(form.dataset.web3formsAccessKey || '').trim(),
    web3formsEndpoint: normalizeHttpsUrl(form.dataset.web3formsEndpoint),
    endpoint: normalizeHttpsUrl(form.dataset.leadEndpoint),
    thankYouPath: normalizeInternalPath(form.dataset.thankYouPath, '/spasibo/'),
    timeoutMs: boundedNumber(form.dataset.leadTimeoutMs, 8000, 2000, 20000),
    minFillMs: boundedNumber(form.dataset.leadMinFillMs, 3000, 1000, 30000)
  };

  const web3FormsEnabled = ['web3forms', 'hybrid'].includes(leadConfig.mode)
    && validWeb3FormsKey(leadConfig.web3formsAccessKey)
    && Boolean(leadConfig.web3formsEndpoint);
  const customEndpointEnabled = ['direct', 'hybrid'].includes(leadConfig.mode) && Boolean(leadConfig.endpoint);
  const directDeliveryEnabled = web3FormsEnabled || customEndpointEnabled;

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
    return referrerSource && referrerSource !== '/online-zayavka/' ? referrerSource : '';
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
    if (!field || value === undefined || value === null) return false;
    const text = String(value);
    const maxLength = Number(field.maxLength);
    field.value = text.slice(0, maxLength > 0 ? maxLength : text.length);
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
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const randomPart = Math.random().toString(36).slice(2, 10).toUpperCase();
    return `IP-${date}-${randomPart}`;
  }

  function resetAttemptMetadata() {
    setInputValue('request_id', createRequestId());
    setInputValue('form_started_at', String(Date.now()));
    deliveryCompleted = false;
    if (directSendButton) {
      directSendButton.disabled = false;
      directSendButton.removeAttribute('aria-busy');
      directSendButton.textContent = 'Отправить заявку онлайн';
    }
  }

  function normalizePhone(value) {
    return String(value || '').replace(/[^\d+]/g, '');
  }

  function getSafePageContext() {
    if (typeof window.getSiteSafePageContext === 'function') return window.getSiteSafePageContext();
    const normalizedPath = String(window.location.pathname || '/')
      .replace(/\/index\.html$/, '/')
      .replace(/\/+$/, '/') || '/';
    return {
      page_url: `${window.location.origin}${normalizedPath}`,
      page_path: normalizedPath,
      referrer: ''
    };
  }

  function getTrackingData() {
    if (typeof window.getSiteTrackingData === 'function') return window.getSiteTrackingData();
    return { first_touch: {}, last_touch: {}, current: {} };
  }

  function qualifyLead(payload) {
    let score = 0;
    const reasons = [];
    const mortgage = payload.mortgage || {};
    const client = payload.client || {};
    if (normalizePhone(client.phone).replace(/\D/g, '').length >= 10) { score += 15; reasons.push('оставлен корректный телефон'); }
    if (client.city) { score += 5; reasons.push('указан город'); }
    if (mortgage.scenario) { score += 10; reasons.push('понятна задача'); }
    if (mortgage.object_type && mortgage.object_type !== 'Пока не выбрано') { score += 10; reasons.push('определён тип объекта'); }
    if (mortgage.object_price && mortgage.object_price !== 'Не указано') { score += 12; reasons.push('указана стоимость объекта'); }
    if (mortgage.down_payment && mortgage.down_payment !== 'Не указано') { score += 12; reasons.push('указан первоначальный взнос'); }
    if (mortgage.bank_history && mortgage.bank_history !== 'Не указано') { score += 8; reasons.push('описана история обращений в банки'); }
    if (mortgage.comment && mortgage.comment !== 'Не указано') { score += 5; reasons.push('добавлены подробности'); }
    if (/отказ|кредитн/i.test(mortgage.scenario || '')) { score += 8; reasons.push('требуется разбор сложной ситуации'); }
    const statusValue = score >= 60 ? 'hot' : score >= 35 ? 'warm' : 'cold';
    const priority = statusValue === 'hot' ? 'срочно обработать' : statusValue === 'warm' ? 'обработать в рабочий день' : 'уточнить вводные';
    return { score, status: statusValue, priority, reasons };
  }

  function buildLeadPayload() {
    const startedAt = Number(rawFieldValue('form_started_at'));
    const pageContext = getSafePageContext();
    const payload = {
      schema_version: 1,
      request_id: fieldValue('request_id'),
      form_version: fieldValue('form_version', '1'),
      submitted_at: new Date().toISOString(),
      form_fill_ms: Number.isFinite(startedAt) ? Math.max(0, Date.now() - startedAt) : null,
      source_page: fieldValue('source_page', 'Прямой переход на форму'),
      page_url: pageContext.page_url,
      page_title: document.title,
      referrer: pageContext.referrer,
      tracking: getTrackingData(),
      client: {
        name: fieldValue('client_name'),
        phone: fieldValue('phone'),
        phone_normalized: normalizePhone(fieldValue('phone')),
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
      personal_data_consent: 'yes',
      consent: true,
      spam_check: {
        honeypot_empty: !rawFieldValue('website'),
        form_fill_ms: Number.isFinite(startedAt) ? Math.max(0, Date.now() - startedAt) : null,
        likely_bot: Boolean(rawFieldValue('website'))
      }
    };
    payload.qualification = qualifyLead(payload);
    return payload;
  }

  function buildApplicationText(payload) {
    const qualification = payload.qualification || {};
    return [
      'ОНЛАЙН-ЗАЯВКА С САЙТА sterlikova-ipoteka.ru',
      `Номер заявки: ${payload.request_id}`,
      `Источник обращения: ${payload.source_page}`,
      '',
      `Имя: ${payload.client.name}`,
      `Телефон: ${payload.client.phone}`,
      `Город / населённый пункт: ${payload.client.city}`,
      `Удобный способ связи: ${payload.client.preferred_contact}`,
      '',
      `Какая помощь нужна: ${payload.mortgage.scenario}`,
      `Объект: ${payload.mortgage.object_type}`,
      `Примерная стоимость: ${payload.mortgage.object_price}`,
      `Первоначальный взнос: ${payload.mortgage.down_payment}`,
      `Подтверждение дохода: ${payload.mortgage.income_type}`,
      '',
      `Заявки, одобрения или отказы банков: ${payload.mortgage.bank_history}`,
      `Комментарий: ${payload.mortgage.comment}`,
      `Квалификация: ${qualification.status}, ${qualification.score} баллов, ${qualification.priority}`,
      `Причины квалификации: ${(qualification.reasons || []).join(', ')}`,
      '',
      'Прошу связаться со мной для первичного разбора ситуации. Понимаю, что окончательное решение по ипотеке принимает банк.'
    ].join('\n');
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
    if (explicitCity) setInputValue('city', explicitCity);
    else if (sourcePath) {
      const matchingPrefix = Object.keys(CITY_BY_PREFIX).find((prefix) => sourcePath.startsWith(prefix));
      if (matchingPrefix) setInputValue('city', CITY_BY_PREFIX[matchingPrefix]);
    }
    const explicitContact = params.get('contact');
    if (explicitContact) setSelectValue('preferred_contact', explicitContact);
    const explicitScenario = params.get('scenario');
    const slug = sourceSlug(sourcePath);
    if (!setSelectValue('scenario', explicitScenario) && slug) setSelectValue('scenario', SCENARIO_BY_SLUG[slug]);
    const explicitObject = params.get('object');
    if (!setSelectValue('object_type', explicitObject) && slug) setSelectValue('object_type', OBJECT_BY_SLUG[slug]);
    if (sourcePath) track('online_application_prefill');
  }

  async function parseJsonResponse(response) {
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return {};
    try { return await response.json(); } catch (error) { return {}; }
  }

  async function sendWeb3FormsLead(payload, signal) {
    const tracking = payload.tracking || {};
    const current = tracking.current || {};
    const emailPayload = {
      access_key: leadConfig.web3formsAccessKey,
      subject: `Новая заявка ипотечному брокеру — ${payload.mortgage.scenario}`,
      from_name: 'Сайт ипотечного брокера Татьяны Стерликовой',
      name: payload.client.name,
      phone: payload.client.phone,
      city: payload.client.city,
      preferred_contact: payload.client.preferred_contact,
      scenario: payload.mortgage.scenario,
      object_type: payload.mortgage.object_type,
      object_price: payload.mortgage.object_price,
      down_payment: payload.mortgage.down_payment,
      income_type: payload.mortgage.income_type,
      bank_history: payload.mortgage.bank_history,
      comment: payload.mortgage.comment,
      request_id: payload.request_id,
      source_page: payload.source_page,
      page_url: payload.page_url,
      page_title: payload.page_title,
      referrer: payload.referrer,
      qualification_status: payload.qualification.status,
      qualification_score: String(payload.qualification.score),
      qualification_priority: payload.qualification.priority,
      utm_source: current.utm_source || '',
      utm_medium: current.utm_medium || '',
      utm_campaign: current.utm_campaign || '',
      utm_content: current.utm_content || '',
      utm_term: current.utm_term || '',
      yclid: current.yclid || '',
      vkclid: current.vkclid || '',
      personal_data_consent: payload.personal_data_consent,
      form_fill_ms: String(payload.form_fill_ms || 0),
      submitted_at: payload.submitted_at,
      tracking_json: JSON.stringify(tracking),
      fields_json: JSON.stringify(payload, null, 2),
      message: preparedText
    };
    const response = await fetch(leadConfig.web3formsEndpoint, {
      method: 'POST',
      mode: 'cors',
      credentials: 'omit',
      referrerPolicy: 'strict-origin-when-cross-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(emailPayload),
      signal
    });
    const responsePayload = await parseJsonResponse(response);
    if (!response.ok || responsePayload.success === false) throw new Error(responsePayload.message || `Web3Forms HTTP ${response.status}`);
    return { channel: 'web3forms', response: responsePayload };
  }

  async function sendCustomLead(payload, signal) {
    const response = await fetch(leadConfig.endpoint, {
      method: 'POST',
      mode: 'cors',
      credentials: 'omit',
      referrerPolicy: 'strict-origin-when-cross-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal
    });
    const responsePayload = await parseJsonResponse(response);
    if (!response.ok || responsePayload.ok === false || responsePayload.success === false) {
      throw new Error(responsePayload.message || responsePayload.error || `Endpoint HTTP ${response.status}`);
    }
    return { channel: 'endpoint', response: responsePayload };
  }

  async function sendLead(payload, signal) {
    const tasks = [];
    if (web3FormsEnabled) tasks.push(sendWeb3FormsLead(payload, signal));
    if (customEndpointEnabled) tasks.push(sendCustomLead(payload, signal));
    if (!tasks.length) throw new Error('Нет активного канала приёма заявок');
    const results = await Promise.allSettled(tasks);
    const successful = results.filter((item) => item.status === 'fulfilled').map((item) => item.value);
    if (!successful.length) {
      const aborted = results.find((item) => item.status === 'rejected' && item.reason && item.reason.name === 'AbortError');
      if (aborted) throw aborted.reason;
      throw new Error('Все каналы приёма заявки недоступны');
    }
    return successful;
  }

  function saveLastLead(payload) {
    const safeLead = {
      request_id: payload.request_id,
      expires_at: new Date(Date.now() + LAST_LEAD_RETENTION_MS).toISOString()
    };
    try { window.localStorage.setItem(LAST_LEAD_STORAGE_KEY, JSON.stringify(safeLead)); } catch (error) { /* Fragment содержит резервный request_id. */ }
  }

  function buildThankYouUrl(payload) {
    const url = new URL(leadConfig.thankYouPath, window.location.origin);
    url.hash = new URLSearchParams({ id: payload.request_id }).toString();
    return url.toString();
  }

  async function sendDirectly() {
    if (!preparedPayload || !preparedText || !directDeliveryEnabled || deliveryCompleted) return;
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
    setDeliveryNote('Передаём заявку. Не закрывайте страницу до подтверждения.');
    try {
      track('online_application_direct_attempt');
      const channels = await sendLead(preparedPayload, controller.signal);
      deliveryCompleted = true;
      saveLastLead(preparedPayload);
      setDeliveryNote('Заявка отправлена. Переходим на страницу подтверждения.', 'success');
      directSendButton.textContent = 'Заявка отправлена';
      track('online_application_direct_success');
      track('lead_submit');
      window.setTimeout(() => window.location.assign(buildThankYouUrl(preparedPayload)), 350);
    } catch (error) {
      const timedOut = error && error.name === 'AbortError';
      setDeliveryNote(
        timedOut
          ? 'Сервис не ответил вовремя. Данные не потеряны — отправьте готовый текст через SMS, MAX или ВКонтакте.'
          : 'Онлайн-отправка не удалась. Данные не потеряны — используйте один из резервных способов ниже.',
        'error'
      );
      directSendButton.disabled = false;
      directSendButton.removeAttribute('aria-busy');
      directSendButton.textContent = 'Повторить отправку';
      track(timedOut ? 'online_application_direct_timeout' : 'online_application_direct_error');
    } finally {
      window.clearTimeout(timeoutId);
      if (deliveryCompleted) {
        directSendButton.disabled = true;
        directSendButton.removeAttribute('aria-busy');
      }
    }
  }

  if (shareButton && !navigator.share) shareButton.hidden = true;
  if (directSendButton) directSendButton.hidden = !directDeliveryEnabled;
  setDeliveryNote(
    directDeliveryEnabled
      ? 'После проверки текста нажмите «Отправить заявку онлайн». При ошибке останутся SMS, MAX, ВКонтакте и копирование.'
      : 'Онлайн-отправка временно недоступна. Используйте один из резервных способов ниже.'
  );
  resetAttemptMetadata();
  prefillFromSource();
  if (directDeliveryEnabled) track('online_application_endpoint_ready');

  form.addEventListener('input', () => {
    if (!startGoalSent) { startGoalSent = true; track('online_application_start'); }
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
    preparedPayload = buildLeadPayload();
    preparedText = buildApplicationText(preparedPayload);
    if (output) output.value = preparedText;
    if (smsLink) smsLink.href = `sms:+79030250807?body=${encodeURIComponent(preparedText)}`;
    if (result) result.hidden = false;
    setStatus('Заявка подготовлена. Проверьте текст и отправьте её онлайн.', 'success');
    setDeliveryNote(
      directDeliveryEnabled
        ? 'Проверьте текст. Основной канал — отправка на email; резервные способы доступны ниже.'
        : 'Онлайн-отправка временно недоступна. Используйте один из резервных способов ниже.'
    );
    track('online_application_prepare');
    window.setTimeout(() => {
      if (result) result.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (directSendButton && directDeliveryEnabled) directSendButton.focus({ preventScroll: true });
      else if (output) output.focus({ preventScroll: true });
    }, 0);
  });

  if (directSendButton) directSendButton.addEventListener('click', sendDirectly);
  if (copyButton) copyButton.addEventListener('click', async () => {
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

  if (shareButton) shareButton.addEventListener('click', async () => {
    if (!preparedText || !navigator.share) return;
    try {
      await navigator.share({ title: 'Онлайн-заявка ипотечному брокеру', text: preparedText });
      setStatus('Заявка передана в выбранное приложение.', 'success');
      track('online_application_share');
    } catch (error) {
      if (error && error.name === 'AbortError') return;
      setStatus('Системное меню недоступно. Скопируйте текст или отправьте SMS.', 'error');
    }
  });

  if (smsLink) smsLink.addEventListener('click', (event) => {
    if (!preparedText) {
      event.preventDefault();
      setStatus('Сначала подготовьте заявку.', 'error');
      return;
    }
    track('online_application_sms');
  });

  if (vkLink) vkLink.addEventListener('click', async () => {
    if (!preparedText) return;
    try {
      await copyText(preparedText);
      setStatus('Текст скопирован. Вставьте его в сообщение ВКонтакте.', 'success');
    } catch (error) {
      setStatus('ВКонтакте открыт. Скопируйте текст из поля заявки вручную.', 'error');
    }
    track('online_application_vk');
  });

  form.dataset.applicationReady = 'true';
  if (submitButton) {
    submitButton.disabled = false;
    submitButton.removeAttribute('aria-busy');
  }
  if (runtimeFallback) runtimeFallback.hidden = true;
  setStatus('');
})();
