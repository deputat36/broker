(() => {
  const form = document.querySelector('[data-online-application]');
  if (!form) return;

  const phone = form.querySelector('[data-phone-input]');
  const phoneHint = document.getElementById('application-phone-hint');
  const moreDetails = form.querySelector('[data-application-more]');
  const formStatus = form.querySelector('[data-application-status]');
  const documentLinks = form.querySelectorAll('.application-consent a');

  function track(goalName) {
    if (typeof window.sendGoal === 'function') window.sendGoal(goalName);
  }

  function parseRussianPhone(value) {
    const digits = String(value || '').replace(/\D/g, '');
    const hasCountryPrefix = digits.startsWith('7') || digits.startsWith('8');
    const body = hasCountryPrefix ? digits.slice(1) : digits;
    return {
      body,
      overflow: body.length > 10,
      normalized: body.length === 10 ? `7${body}` : ''
    };
  }

  function normalizeRussianPhone(value) {
    const parsed = parseRussianPhone(value);
    return parsed.overflow ? '' : parsed.normalized;
  }

  function formatRussianPhone(value) {
    const parsed = parseRussianPhone(value);
    const digits = parsed.body.slice(0, 10);
    if (!digits) return '';

    let formatted = '+7';
    if (digits.length > 0) formatted += ` (${digits.slice(0, 3)}`;
    if (digits.length >= 3) formatted += ')';
    if (digits.length > 3) formatted += ` ${digits.slice(3, 6)}`;
    if (digits.length > 6) formatted += `-${digits.slice(6, 8)}`;
    if (digits.length > 8) formatted += `-${digits.slice(8, 10)}`;
    return formatted;
  }

  function setPhoneHint(message, state = '') {
    if (!phoneHint) return;
    phoneHint.textContent = message;
    phoneHint.classList.remove('is-success', 'is-error');
    if (state) phoneHint.classList.add(`is-${state}`);
  }

  function setPhoneValidity(showMessage = false) {
    if (!phone) return true;
    const parsed = parseRussianPhone(phone.value);
    const normalized = parsed.overflow ? '' : parsed.normalized;
    const valid = Boolean(normalized);
    const hasValue = Boolean(phone.value.trim());
    const message = parsed.overflow
      ? 'В номере больше 10 цифр после +7. Удалите лишнюю цифру.'
      : 'Введите российский номер из 10 цифр после +7.';

    phone.setCustomValidity(valid || !hasValue ? '' : message);
    phone.setAttribute('aria-invalid', String(!valid && hasValue));

    if (valid) setPhoneHint(`Номер для связи: ${formatRussianPhone(normalized)}`, 'success');
    else setPhoneHint(
      parsed.overflow ? message : 'Введите 10 цифр российского номера. Подойдут форматы +7 или 8.',
      showMessage && hasValue ? 'error' : ''
    );

    return valid;
  }

  documentLinks.forEach((link) => {
    link.setAttribute('target', '_blank');
    link.setAttribute('rel', 'noopener');
    link.setAttribute('aria-label', `${link.textContent.trim()} — откроется в новой вкладке`);
  });

  if (phone) {
    phone.addEventListener('input', () => {
      const parsed = parseRussianPhone(phone.value);
      if (!parsed.overflow) {
        const formatted = formatRussianPhone(phone.value);
        if (formatted) phone.value = formatted;
      }
      phone.setCustomValidity('');
      phone.removeAttribute('aria-invalid');
      setPhoneHint(
        parsed.overflow
          ? 'В номере больше 10 цифр после +7. Удалите лишнюю цифру.'
          : 'Введите 10 цифр российского номера. Подойдут форматы +7 или 8.',
        parsed.overflow ? 'error' : ''
      );
    });

    phone.addEventListener('blur', () => {
      const normalized = normalizeRussianPhone(phone.value);
      if (normalized) phone.value = formatRussianPhone(normalized);
      setPhoneValidity(true);
    });
  }

  form.addEventListener('submit', (event) => {
    if (setPhoneValidity(true)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (formStatus) {
      formStatus.textContent = 'Проверьте номер телефона: нужно указать ровно 10 цифр после +7.';
      formStatus.classList.remove('is-success');
      formStatus.classList.add('is-error');
    }
    phone.focus();
    phone.reportValidity();
    track('online_application_phone_error');
  }, true);

  if (moreDetails) {
    moreDetails.addEventListener('toggle', () => {
      if (moreDetails.open) track('online_application_more_open');
    });
  }
})();

(() => {
  const form = document.querySelector('[data-online-application]');
  const deliveryNote = document.querySelector('[data-application-delivery-note]');
  const directSendButton = document.querySelector('[data-application-direct-send]');
  if (!form || !deliveryNote || !directSendButton || typeof window.fetch !== 'function') return;

  const ERROR_GROUPS = {
    validation_failed: 'validation',
    rate_limit_exceeded: 'rate_limit',
    request_rejected: 'rejected',
    backend_unavailable: 'backend',
    backend_migration_required: 'backend',
    lead_storage_failed: 'backend',
    origin_not_allowed: 'request',
    method_not_allowed: 'request',
    content_type_not_supported: 'request',
    payload_too_large: 'request',
    invalid_json: 'request'
  };

  const ERROR_MESSAGES = {
    validation: 'Сервис не смог проверить часть данных. Проверьте обязательные поля и подготовьте заявку заново.',
    rate_limit: 'Слишком много попыток отправки за короткое время. Используйте готовый текст заявки или повторите отправку позже.',
    rejected: 'Автоматическая проверка не подтвердила корректность формы. Используйте готовый текст заявки для связи с Татьяной.',
    backend: 'Сервис онлайн-приёма временно недоступен. Готовый текст заявки не потерян.',
    request: 'Не удалось корректно передать заявку. Обновите страницу и попробуйте ещё раз.',
    network: 'Сервис не ответил. Готовый текст заявки не потерян.'
  };

  const originalFetch = window.fetch.bind(window);
  let lastEndpointError = null;
  let updatingNote = false;

  function cleanText(value, maxLength = 100) {
    return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, maxLength) : '';
  }

  function validRequestId(value) {
    const requestId = cleanText(value, 80);
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const fallbackPattern = /^IP-\d{8}-[A-Z0-9]{6,16}$/;
    return uuidPattern.test(requestId) || fallbackPattern.test(requestId) ? requestId : '';
  }

  function currentRequestId() {
    const field = form.elements.namedItem('request_id');
    return validRequestId(field ? field.value : '');
  }

  function safeRetryAfter(value) {
    const seconds = Number(value);
    return Number.isInteger(seconds) && seconds > 0 && seconds <= 86400 ? seconds : 0;
  }

  function trackCategory(category) {
    if (typeof window.sendGoal !== 'function') return;
    window.sendGoal('online_application_endpoint_error');
    const allowed = ['validation', 'rate_limit', 'rejected', 'backend', 'request'];
    if (allowed.includes(category)) window.sendGoal(`online_application_endpoint_error_${category}`);
  }

  function captureEndpointError(payload) {
    if (!payload || payload.ok !== false || payload.success !== false) return;
    const errorCode = cleanText(payload.error_code, 60);
    const category = ERROR_GROUPS[errorCode];
    if (!category) return;
    lastEndpointError = {
      category,
      requestId: validRequestId(payload.request_id) || currentRequestId(),
      retryAfterSeconds: safeRetryAfter(payload.retry_after_seconds)
    };
    trackCategory(category);
  }

  function retryHint(seconds) {
    if (!seconds) return '';
    const minutes = Math.max(1, Math.ceil(seconds / 60));
    return ` Повторить онлайн-отправку можно примерно через ${minutes} мин.`;
  }

  function fallbackHint() {
    return ' Отправьте готовый текст через SMS, MAX, ВКонтакте или скопируйте его вручную.';
  }

  function technicalHint(requestId) {
    return requestId ? ` Технический номер: ${requestId}.` : '';
  }

  function renderSafeError() {
    if (updatingNote || !deliveryNote.classList.contains('is-error')) return;
    const currentText = String(deliveryNote.textContent || '');
    const isGenericFailure = currentText.includes('Онлайн-отправка не удалась')
      || currentText.includes('Сервис не ответил вовремя');
    if (!isGenericFailure) return;

    const endpointError = lastEndpointError;
    const category = endpointError ? endpointError.category : 'network';
    const requestId = endpointError ? endpointError.requestId : currentRequestId();
    const retryAfterSeconds = endpointError ? endpointError.retryAfterSeconds : 0;
    const message = ERROR_MESSAGES[category] || ERROR_MESSAGES.network;

    updatingNote = true;
    deliveryNote.textContent = `${message}${retryHint(retryAfterSeconds)}${technicalHint(requestId)}${fallbackHint()}`;
    deliveryNote.dataset.errorCategory = category;
    updatingNote = false;
  }

  function requestKindFromFetchArgs(args) {
    const options = args[1] && typeof args[1] === 'object' ? args[1] : {};
    if (typeof options.body !== 'string') return '';
    try {
      const payload = JSON.parse(options.body);
      return cleanText(payload && payload.request_kind, 40).toLowerCase();
    } catch (_error) {
      return '';
    }
  }

  window.fetch = async (...args) => {
    const skipErrorCapture = requestKindFromFetchArgs(args) === 'delivery_receipt';
    const response = await originalFetch(...args);
    const contentType = response.headers.get('content-type') || '';
    if (!skipErrorCapture && contentType.includes('application/json')) {
      try {
        const payload = await response.clone().json();
        captureEndpointError(payload);
      } catch (_error) {
        // Невалидный JSON обрабатывается основным транспортом формы.
      }
    }
    return response;
  };

  const observer = new MutationObserver(renderSafeError);
  observer.observe(deliveryNote, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });

  directSendButton.addEventListener('click', () => {
    lastEndpointError = null;
    delete deliveryNote.dataset.errorCategory;
  }, true);
})();

(() => {
  const form = document.querySelector('[data-online-application]');
  if (!form || typeof window.fetch !== 'function') return;

  const mode = String(form.dataset.leadMode || 'disabled').trim().toLowerCase();
  const web3FormsEndpoint = normalizeHttpsUrl(form.dataset.web3formsEndpoint);
  const leadEndpoint = normalizeHttpsUrl(form.dataset.leadEndpoint);
  const expectsWeb3Forms = ['web3forms', 'hybrid'].includes(mode) && Boolean(web3FormsEndpoint);
  const expectsSupabase = ['direct', 'hybrid'].includes(mode) && Boolean(leadEndpoint);
  if (!expectsWeb3Forms && !expectsSupabase) return;

  const previousFetch = window.fetch.bind(window);
  const attempts = new Map();
  const WEB3FORMS_WAIT_MS = 2500;
  const receiptEndpoint = deriveReceiptEndpoint(leadEndpoint);

  function normalizeHttpsUrl(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    try {
      const url = new URL(raw, window.location.origin);
      return url.protocol === 'https:' ? url.href : '';
    } catch (_error) {
      return '';
    }
  }

  function deriveReceiptEndpoint(value) {
    if (!value) return '';
    try {
      const url = new URL(value);
      const normalizedPath = url.pathname.replace(/\/+$/, '');
      if (!normalizedPath.endsWith('/broker-public-lead')) return '';
      url.pathname = `${normalizedPath.replace(/\/broker-public-lead$/, '')}/broker-delivery-receipt`;
      url.search = '';
      url.hash = '';
      return url.href;
    } catch (_error) {
      return '';
    }
  }

  function cleanText(value, maxLength = 100) {
    return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, maxLength) : '';
  }

  function validRequestId(value) {
    const requestId = cleanText(value, 80);
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const fallbackPattern = /^IP-\d{8}-[A-Z0-9]{6,16}$/;
    return uuidPattern.test(requestId) || fallbackPattern.test(requestId) ? requestId : '';
  }

  function parseBody(options) {
    if (!options || typeof options.body !== 'string') return {};
    try {
      const parsed = JSON.parse(options.body);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  function sameEndpoint(left, right) {
    if (!left || !right) return false;
    try {
      return new URL(left, window.location.origin).href === new URL(right, window.location.origin).href;
    } catch (_error) {
      return false;
    }
  }

  function ensureAttempt(requestId) {
    if (!attempts.has(requestId)) {
      attempts.set(requestId, {
        requestId,
        expected: { web3forms: expectsWeb3Forms, supabase: expectsSupabase },
        channels: {
          web3forms: { settled: !expectsWeb3Forms, accepted: false },
          supabase: { settled: !expectsSupabase, accepted: false }
        },
        waiters: [],
        finalized: false
      });
    }
    return attempts.get(requestId);
  }

  function notifySupabaseWaiters(attempt) {
    if (!attempt.channels.supabase.settled) return;
    attempt.waiters.splice(0).forEach((resolve) => resolve(true));
  }

  function waitForSupabase(attempt) {
    if (!attempt.expected.supabase || attempt.channels.supabase.settled) return Promise.resolve(true);
    return new Promise((resolve) => {
      const timer = window.setTimeout(() => resolve(false), WEB3FORMS_WAIT_MS);
      attempt.waiters.push(() => {
        window.clearTimeout(timer);
        resolve(true);
      });
    });
  }

  function addDeliveryStateToWeb3FormsArgs(args, state) {
    if (!state || !args[1] || typeof args[1].body !== 'string') return args;
    try {
      const payload = JSON.parse(args[1].body);
      payload.delivery_state = state;
      payload.delivery_state_source = 'browser_confirmed';
      const options = { ...args[1], body: JSON.stringify(payload) };
      return [args[0], options];
    } catch (_error) {
      return args;
    }
  }

  async function responseAccepted(channel, response) {
    if (!response || !response.ok) return false;
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return channel === 'supabase' && response.status === 204;
    try {
      const payload = await response.clone().json();
      if (channel === 'web3forms') return payload.success !== false;
      return payload.ok !== false && payload.success !== false;
    } catch (_error) {
      return false;
    }
  }

  function track(goalName) {
    if (typeof window.sendGoal === 'function') window.sendGoal(goalName);
  }

  async function sendBothReceipt(requestId) {
    if (!receiptEndpoint || !validRequestId(requestId)) return false;
    try {
      const response = await previousFetch(receiptEndpoint, {
        method: 'POST',
        mode: 'cors',
        credentials: 'omit',
        referrerPolicy: 'strict-origin-when-cross-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_kind: 'delivery_receipt',
          request_id: requestId,
          delivery_state: 'both'
        })
      });
      if (response.status === 204) {
        track('online_application_delivery_receipt_success');
        return true;
      }
    } catch (_error) {
      // Квитанция не должна менять успешный клиентский результат.
    }
    track('online_application_delivery_receipt_error');
    return false;
  }

  function finalizeAttempt(attempt) {
    if (attempt.finalized) return;
    if (!attempt.channels.web3forms.settled || !attempt.channels.supabase.settled) return;

    const web3formsAccepted = attempt.channels.web3forms.accepted;
    const supabaseAccepted = attempt.channels.supabase.accepted;
    if (!web3formsAccepted && !supabaseAccepted) return;

    const state = web3formsAccepted && supabaseAccepted
      ? 'both'
      : web3formsAccepted
        ? 'web3forms_only'
        : 'supabase_only';

    attempt.finalized = true;
    window.applicationDeliveryState = state;
    track(`online_application_delivery_${state}`);
    if (state === 'both') void sendBothReceipt(attempt.requestId);
  }

  window.fetch = async (...initialArgs) => {
    let args = initialArgs;
    const options = args[1] && typeof args[1] === 'object' ? args[1] : {};
    const body = parseBody(options);
    const requestKind = cleanText(body.request_kind, 40).toLowerCase();
    if (requestKind === 'delivery_receipt') return previousFetch(...args);

    const requestId = validRequestId(body.request_id);
    const requestUrl = String(args[0] || '');
    const channel = sameEndpoint(requestUrl, web3FormsEndpoint)
      ? 'web3forms'
      : sameEndpoint(requestUrl, leadEndpoint)
        ? 'supabase'
        : '';

    if (!channel || !requestId) return previousFetch(...args);
    const attempt = ensureAttempt(requestId);

    if (channel === 'web3forms') {
      const supabaseSettled = await waitForSupabase(attempt);
      if (!attempt.expected.supabase) {
        args = addDeliveryStateToWeb3FormsArgs(args, 'web3forms_only');
      } else if (supabaseSettled) {
        args = addDeliveryStateToWeb3FormsArgs(
          args,
          attempt.channels.supabase.accepted ? 'both' : 'web3forms_only'
        );
      }
    }

    try {
      const response = await previousFetch(...args);
      attempt.channels[channel].accepted = await responseAccepted(channel, response);
      attempt.channels[channel].settled = true;
      if (channel === 'supabase') notifySupabaseWaiters(attempt);
      finalizeAttempt(attempt);
      return response;
    } catch (error) {
      attempt.channels[channel].accepted = false;
      attempt.channels[channel].settled = true;
      if (channel === 'supabase') notifySupabaseWaiters(attempt);
      finalizeAttempt(attempt);
      throw error;
    }
  };
})();
