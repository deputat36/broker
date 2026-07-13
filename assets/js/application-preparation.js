(() => {
  const form = document.querySelector('[data-online-application]');
  const preparation = form ? form.querySelector('[data-application-preparation]') : null;
  if (!form || !preparation) return;

  const params = new URLSearchParams(window.location.search);
  const journeyTypeField = form.elements.namedItem('journey_type');
  const journeyStageField = form.elements.namedItem('journey_stage');
  const journeyScenarioField = form.elements.namedItem('journey_scenario_slug');
  const remainingQuestions = form.elements.namedItem('remaining_questions');
  const detailsStepNumber = form.querySelector('[data-application-more] .application-step-label > span');
  const intro = preparation.querySelector('[data-preparation-intro]');
  const checkboxes = Array.from(form.querySelectorAll('input[name="preparation_check"]'));
  const output = document.querySelector('[data-application-output]');
  const smsLink = document.querySelector('[data-application-sms]');
  const copyButton = document.querySelector('[data-application-copy]');
  const shareButton = document.querySelector('[data-application-share]');
  const vkLink = document.querySelector('[data-application-vk]');
  const maxButton = document.querySelector('[data-application-max], [data-application-result] [data-copy-phone]');
  const formStatus = form.querySelector('[data-application-status]');
  const APPLICATION_TEXT_MARKER = 'ОНЛАЙН-ЗАЯВКА С САЙТА';
  const PREPARATION_TEXT_MARKER = 'ПОДГОТОВКА ДО ОБРАЩЕНИЯ';

  if (maxButton) {
    maxButton.removeAttribute('data-copy-phone');
    maxButton.setAttribute('data-application-max', '');
    maxButton.textContent = 'Скопировать заявку для MAX';
  }

  const CONFIG_BY_SLUG = {
    'otkazali-v-ipoteke': {
      intro: 'После отказа важно отделить финансовый профиль заемщика от вопросов по объекту и не повторять ту же подачу без анализа.',
      labels: {
        diagnosis: 'Зафиксировал(а) банк, дату и этап отказа',
        finances: 'Проверил(а) кредиты, карты и ежемесячные платежи',
        documents: 'Собрал(а) сведения по объекту и запросам банка',
        next_step: 'Не подавал(а) новые заявки после отказа'
      }
    },
    'ipoteka-s-plohoy-kreditnoy-istoriey': {
      intro: 'Отметьте, какие факты по кредитной истории и текущей нагрузке уже проверены до нового обращения в банк.',
      labels: {
        diagnosis: 'Получил(а) или проверил(а) кредитную историю',
        finances: 'Посчитал(а) действующие кредиты, карты и лимиты',
        documents: 'Отметил(а) просрочки, закрытые долги или возможные ошибки',
        next_step: 'Не отправлял(а) новые заявки сразу во все банки'
      }
    },
    'ipoteka-bez-oficialnogo-dohoda': {
      intro: 'Для разбора нужен реальный состав дохода и доступные подтверждения, а не попытка скрыть поступления или обязательства.',
      labels: {
        diagnosis: 'Перечислил(а) все реальные источники дохода',
        finances: 'Посчитал(а) доход, кредиты и комфортный платеж',
        documents: 'Собрал(а) доступные подтверждения регулярных поступлений',
        next_step: 'Не использую недостоверные сведения или документы'
      }
    },
    'ipoteka-bez-pervonachalnogo-vznosa': {
      intro: 'Отметьте законные источники средств и расчеты, которые уже проверены до выбора банка и объекта.',
      labels: {
        diagnosis: 'Посчитал(а), какой суммы не хватает до взноса',
        finances: 'Проверил(а) маткапитал, накопления или продажу имущества',
        documents: 'Оценил(а) расходы после покупки и финансовый резерв',
        next_step: 'Не рассматриваю фиктивное завышение стоимости'
      }
    }
  };

  function track(goalName) {
    if (typeof window.sendGoal === 'function') window.sendGoal(goalName);
  }

  function setStatus(message, type = '') {
    if (!formStatus) return;
    formStatus.textContent = message;
    formStatus.classList.remove('is-error', 'is-success');
    if (type) formStatus.classList.add(`is-${type}`);
  }

  function normalizeSourcePath(value) {
    if (!value) return '';
    try {
      const url = new URL(value, window.location.origin);
      if (url.origin !== window.location.origin) return '';
      return url.pathname.replace(/\/index\.html$/, '/').replace(/\/+$/, '/') || '/';
    } catch (error) {
      return '';
    }
  }

  function sourceSlug(sourcePath) {
    const parts = sourcePath.split('/').filter(Boolean);
    return parts.length ? parts[parts.length - 1] : '';
  }

  function checkedPreparation() {
    const completedChecks = [];
    const completedLabels = [];
    checkboxes.forEach((checkbox) => {
      if (!checkbox.checked) return;
      completedChecks.push(checkbox.value);
      const label = preparation.querySelector(`[data-preparation-label="${checkbox.value}"]`);
      completedLabels.push(label ? label.textContent.trim() : checkbox.value);
    });
    return { completedChecks, completedLabels };
  }

  window.getApplicationPreparationData = () => {
    const active = preparation.dataset.active === 'true';
    const completed = active ? checkedPreparation() : { completedChecks: [], completedLabels: [] };
    return {
      context_version: Number(preparation.dataset.preparationContextVersion || 1),
      active,
      journey_type: active && journeyTypeField ? String(journeyTypeField.value || '').trim() : '',
      journey_stage: active && journeyStageField ? String(journeyStageField.value || '').trim() : '',
      scenario_slug: active && journeyScenarioField ? String(journeyScenarioField.value || '').trim() : '',
      completed_checks: completed.completedChecks,
      completed_labels: completed.completedLabels,
      remaining_questions: active && remainingQuestions ? String(remainingQuestions.value || '').trim() : ''
    };
  };

  function preparationMessage(data) {
    if (!data.active) return '';
    return [
      PREPARATION_TEXT_MARKER,
      `Тип маршрута: ${data.journey_type || 'не указан'}`,
      `Этап: ${data.journey_stage || 'не указан'}`,
      `Сценарий: ${data.scenario_slug || 'не указан'}`,
      `Что уже проверено: ${data.completed_labels.length ? data.completed_labels.join('; ') : 'не отмечено'}`,
      `Что осталось уточнить: ${data.remaining_questions || 'не указано'}`
    ].join('\n');
  }

  window.getApplicationPreparationText = () => preparationMessage(window.getApplicationPreparationData());

  function appendPreparationToApplicationText(value) {
    const text = String(value || '');
    const context = window.getApplicationPreparationText();
    if (!context || !text.includes(APPLICATION_TEXT_MARKER) || text.includes(PREPARATION_TEXT_MARKER)) return text;
    return `${text}\n\n${context}`;
  }

  window.appendApplicationPreparationText = appendPreparationToApplicationText;

  function currentFallbackText() {
    return output ? appendPreparationToApplicationText(output.value) : '';
  }

  async function writeFallbackText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    if (!output) throw new Error('output_missing');
    output.focus();
    output.select();
    const copied = document.execCommand('copy');
    output.setSelectionRange(0, 0);
    if (!copied) throw new Error('copy_failed');
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    if (!init.body || String(init.method || 'GET').toUpperCase() !== 'POST') return originalFetch(input, init);

    let payload;
    try {
      payload = JSON.parse(String(init.body));
    } catch (error) {
      return originalFetch(input, init);
    }

    const data = window.getApplicationPreparationData();
    if (!data.active) return originalFetch(input, init);

    if (payload && payload.schema_version === 1) {
      payload.preparation = data;
    } else if (payload && payload.access_key) {
      payload.journey_type = data.journey_type;
      payload.journey_stage = data.journey_stage;
      payload.journey_scenario_slug = data.scenario_slug;
      payload.preparation_completed_keys = data.completed_checks.join(', ');
      payload.preparation_completed = data.completed_labels.join('; ');
      payload.remaining_questions = data.remaining_questions;
      payload.preparation_json = JSON.stringify(data, null, 2);
      if (payload.fields_json) {
        try {
          const fields = JSON.parse(payload.fields_json);
          fields.preparation = data;
          payload.fields_json = JSON.stringify(fields, null, 2);
        } catch (error) {
          // fields_json остаётся исходным, отдельные поля всё равно передаются.
        }
      }
      payload.message = appendPreparationToApplicationText(payload.message);
    }

    return originalFetch(input, { ...init, body: JSON.stringify(payload) });
  };

  function syncFallbackText() {
    const context = window.getApplicationPreparationText();
    if (!context || !output || !output.value) return;
    output.value = appendPreparationToApplicationText(output.value);
    if (smsLink) smsLink.href = `sms:+79030250807?body=${encodeURIComponent(output.value)}`;
  }

  form.addEventListener('submit', () => {
    if (preparation.dataset.active !== 'true') return;
    window.setTimeout(syncFallbackText, 0);
  });

  if (copyButton) {
    copyButton.addEventListener('click', async (event) => {
      if (preparation.dataset.active !== 'true') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const text = currentFallbackText();
      if (!text) return;
      try {
        await writeFallbackText(text);
        setStatus('Текст заявки скопирован.', 'success');
        copyButton.textContent = 'Заявка скопирована';
        track('online_application_copy');
        window.setTimeout(() => { copyButton.textContent = 'Скопировать текст'; }, 2500);
      } catch (error) {
        setStatus('Не удалось скопировать автоматически. Выделите текст заявки вручную.', 'error');
      }
    }, true);
  }

  if (shareButton) {
    shareButton.addEventListener('click', async (event) => {
      if (preparation.dataset.active !== 'true' || !navigator.share) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const text = currentFallbackText();
      if (!text) return;
      try {
        await navigator.share({ title: 'Онлайн-заявка ипотечному брокеру', text });
        setStatus('Заявка передана в выбранное приложение.', 'success');
        track('online_application_share');
      } catch (error) {
        if (error && error.name === 'AbortError') return;
        setStatus('Системное меню недоступно. Скопируйте текст или отправьте SMS.', 'error');
      }
    }, true);
  }

  if (vkLink) {
    vkLink.addEventListener('click', async (event) => {
      if (preparation.dataset.active !== 'true') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const text = currentFallbackText();
      if (!text) return;
      const popup = window.open(vkLink.href, '_blank', 'noopener');
      try {
        await writeFallbackText(text);
        setStatus('Текст скопирован. Вставьте его в сообщение ВКонтакте.', 'success');
      } catch (error) {
        setStatus('ВКонтакте открыт. Скопируйте текст из поля заявки вручную.', 'error');
      }
      if (!popup) window.location.assign(vkLink.href);
      track('online_application_vk');
    }, true);
  }

  if (maxButton) {
    maxButton.addEventListener('click', async () => {
      const text = currentFallbackText();
      if (!text) {
        setStatus('Сначала подготовьте заявку.', 'error');
        return;
      }
      try {
        await writeFallbackText(text);
        setStatus('Заявка скопирована. Вставьте её в сообщение MAX.', 'success');
        maxButton.textContent = 'Заявка для MAX скопирована';
        track('online_application_max');
        window.setTimeout(() => { maxButton.textContent = 'Скопировать заявку для MAX'; }, 2500);
      } catch (error) {
        setStatus('Не удалось скопировать автоматически. Выделите текст заявки вручную.', 'error');
      }
    });
  }

  const sourcePath = normalizeSourcePath(params.get('source'));
  const slug = sourceSlug(sourcePath);
  const config = CONFIG_BY_SLUG[slug];
  const isComplexJourney = params.get('journey') === 'complex' && Boolean(config);

  if (!isComplexJourney) return;

  preparation.hidden = false;
  preparation.dataset.active = 'true';
  if (detailsStepNumber) detailsStepNumber.textContent = '3';
  if (journeyTypeField) journeyTypeField.value = 'Сложный региональный маршрут';
  if (journeyStageField) journeyStageField.value = params.get('stage') === 'route'
    ? 'После изучения маршрута подготовки'
    : 'Сложный сценарий';
  if (journeyScenarioField) journeyScenarioField.value = slug;
  if (intro) intro.textContent = config.intro;

  Object.entries(config.labels).forEach(([key, value]) => {
    const label = preparation.querySelector(`[data-preparation-label="${key}"]`);
    if (label) label.textContent = value;
  });

  track('online_application_complex_prefill');

  let checkGoalSent = false;
  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      if (!checkGoalSent) {
        checkGoalSent = true;
        track('online_application_preparation_check');
      }
    });
  });
})();