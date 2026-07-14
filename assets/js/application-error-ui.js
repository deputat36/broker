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

  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
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
