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
  let preparedText = '';
  let startGoalSent = false;

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

  function setStatus(message, type = '') {
    if (!status) return;
    status.textContent = message;
    status.classList.remove('is-error', 'is-success');
    if (type) status.classList.add(`is-${type}`);
  }

  function fieldValue(name, fallback = 'Не указано') {
    const field = form.elements.namedItem(name);
    if (!field) return fallback;
    const value = String(field.value || '').trim();
    return value || fallback;
  }

  function buildApplicationText() {
    const lines = [
      'ОНЛАЙН-ЗАЯВКА С САЙТА sterlikova-ipoteka.ru',
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

  function setFieldValidity() {
    form.querySelectorAll('input, select, textarea').forEach((field) => {
      if (field.type === 'checkbox' || field.type === 'hidden') return;
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

  if (shareButton && !navigator.share) shareButton.hidden = true;
  prefillFromSource();

  form.addEventListener('input', () => {
    if (!startGoalSent) {
      startGoalSent = true;
      track('online_application_start');
    }

    if (result && !result.hidden) {
      result.hidden = true;
      preparedText = '';
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
    if (output) output.value = preparedText;
    if (smsLink) smsLink.href = `sms:+79030250807?body=${encodeURIComponent(preparedText)}`;
    if (result) result.hidden = false;

    setStatus('Заявка подготовлена. Выберите способ отправки ниже.', 'success');
    track('online_application_prepare');

    window.setTimeout(() => {
      if (result) result.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (output) output.focus({ preventScroll: true });
    }, 0);
  });

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