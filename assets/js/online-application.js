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

  function track(goalName) {
    if (typeof window.sendGoal === 'function') {
      window.sendGoal(goalName);
      return;
    }
    if (typeof sendGoal === 'function') sendGoal(goalName);
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
      if (field.type === 'checkbox') return;
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

  function prefillFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const simpleFields = {
      city: 'city',
      object: 'object_type',
      contact: 'preferred_contact'
    };

    Object.entries(simpleFields).forEach(([parameter, fieldName]) => {
      const value = params.get(parameter);
      const field = form.elements.namedItem(fieldName);
      if (!value || !field) return;
      if (field.tagName === 'SELECT') {
        const matchingOption = Array.from(field.options).find((option) => option.value === value || option.text === value);
        if (matchingOption) field.value = matchingOption.value;
      } else {
        field.value = value.slice(0, Number(field.maxLength) > 0 ? Number(field.maxLength) : value.length);
      }
    });

    const scenario = params.get('scenario');
    const scenarioField = form.elements.namedItem('scenario');
    if (scenario && scenarioField) {
      const matchingOption = Array.from(scenarioField.options).find((option) => option.value === scenario || option.text === scenario);
      if (matchingOption) scenarioField.value = matchingOption.value;
    }
  }

  if (shareButton && !navigator.share) shareButton.hidden = true;
  prefillFromQuery();

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
