(() => {
  const form = document.querySelector('[data-online-application]');
  const preparation = form ? form.querySelector('[data-application-preparation]') : null;
  if (!form || !preparation) return;

  const params = new URLSearchParams(window.location.search);
  const journeyTypeField = form.elements.namedItem('journey_type');
  const journeyStageField = form.elements.namedItem('journey_stage');
  const remainingQuestions = form.elements.namedItem('remaining_questions');
  const commentField = form.elements.namedItem('comment');
  const detailsStepNumber = form.querySelector('[data-application-more] .application-step-label > span');
  const intro = preparation.querySelector('[data-preparation-intro]');
  const checkboxes = Array.from(form.querySelectorAll('input[name="preparation_check"]'));
  const MAX_COMBINED_COMMENT_LENGTH = 1600;

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

  function checkedLabels() {
    return checkboxes
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => {
        const label = form.querySelector(`[data-preparation-label="${checkbox.value}"]`);
        return label ? label.textContent.trim() : checkbox.value;
      });
  }

  const sourcePath = normalizeSourcePath(params.get('source'));
  const slug = sourceSlug(sourcePath);
  const config = CONFIG_BY_SLUG[slug];
  const isComplexJourney = params.get('journey') === 'complex' && Boolean(config);

  if (!isComplexJourney) return;

  preparation.hidden = false;
  if (detailsStepNumber) detailsStepNumber.textContent = '3';
  if (journeyTypeField) journeyTypeField.value = 'Сложный региональный маршрут';
  if (journeyStageField) journeyStageField.value = params.get('stage') === 'route'
    ? 'После изучения маршрута подготовки'
    : 'Сложный сценарий';
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

  form.addEventListener('submit', () => {
    if (!commentField) return;

    const originalComment = String(commentField.value || '').trim();
    const completed = checkedLabels();
    const remaining = remainingQuestions ? String(remainingQuestions.value || '').trim() : '';
    const stage = journeyStageField ? String(journeyStageField.value || '').trim() : '';
    const context = [
      `Этап подготовки: ${stage || 'Сложный сценарий'}`,
      `Что уже проверено: ${completed.length ? completed.join('; ') : 'не отмечено'}`,
      `Что осталось уточнить: ${remaining || 'не указано'}`
    ].join('\n');
    const combinedComment = originalComment
      ? `${context}\n\nКомментарий клиента: ${originalComment}`
      : context;

    commentField.value = combinedComment.slice(0, MAX_COMBINED_COMMENT_LENGTH);

    const restore = () => { commentField.value = originalComment; };
    if (typeof queueMicrotask === 'function') queueMicrotask(restore);
    else Promise.resolve().then(restore);
  });
})();