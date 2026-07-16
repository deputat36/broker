(() => {
  const calcForms = document.querySelectorAll('[data-mortgage-calc]');
  if (!calcForms.length) return;

  const APPLICATION_PATH = '/online-zayavka/';

  function track(goalName) {
    if (typeof window.sendGoal === 'function') window.sendGoal(goalName);
  }

  function enhanceCalculatorInputs(calcForm) {
    const inputHints = {
      amount: { enterkeyhint: 'next', inputmode: 'numeric' },
      down: { enterkeyhint: 'next', inputmode: 'numeric' },
      rate: { enterkeyhint: 'next', inputmode: 'decimal' },
      years: { enterkeyhint: 'done', inputmode: 'numeric' }
    };

    Object.entries(inputHints).forEach(([fieldName, attributes]) => {
      const input = calcForm.querySelector(`[name="${fieldName}"]`);
      if (!input) return;

      input.setAttribute('autocomplete', 'off');
      input.setAttribute('enterkeyhint', attributes.enterkeyhint);
      input.setAttribute('inputmode', attributes.inputmode);
    });
  }

  function formatRub(value) {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0
    }).format(value);
  }

  function normalizePath(pathname) {
    const normalized = String(pathname || '/')
      .replace(/\/index\.html$/, '/')
      .replace(/\/+$/, '/');
    return normalized || '/';
  }

  function normalizeDirectApplicationAction(calcForm) {
    const section = calcForm.closest('.calc-section');
    if (!section) return;
    section.querySelectorAll('a[href="/online-zayavka/"]').forEach((link) => {
      if (link.textContent.trim() !== 'Передать расчёт в заявке') return;
      link.textContent = 'Открыть онлайн-заявку';
      link.classList.remove('btn-primary');
      link.classList.add('btn-light');
    });
  }

  function buildApplicationUrl(amount, down, rate, years) {
    const url = new URL(APPLICATION_PATH, window.location.origin);
    url.search = new URLSearchParams({
      source: normalizePath(window.location.pathname),
      calc_amount: String(Math.round(amount)),
      calc_down: String(Math.round(down)),
      calc_rate: String(rate),
      calc_years: String(years)
    }).toString();
    return `${url.pathname}${url.search}`;
  }

  function ensureApplicationAction(calcForm, result) {
    let container = calcForm.querySelector('[data-calc-application-action]');
    let link = calcForm.querySelector('[data-calc-application-link]');

    if (!container || !link) {
      container = document.createElement('div');
      container.className = 'hero-actions';
      container.dataset.calcApplicationAction = '';
      container.hidden = true;

      link = document.createElement('a');
      link.className = 'btn btn-primary';
      link.dataset.calcApplicationLink = '';
      link.textContent = 'Перенести этот расчёт в заявку';
      link.addEventListener('click', () => track('calculator_application_click'));

      container.appendChild(link);
      result.parentNode.insertBefore(container, result.nextSibling);
    }

    return { container, link };
  }

  function hideApplicationAction(calcForm) {
    const container = calcForm.querySelector('[data-calc-application-action]');
    if (container) container.hidden = true;
  }

  function showApplicationAction(calcForm, result, amount, down, rate, years) {
    const action = ensureApplicationAction(calcForm, result);
    action.link.href = buildApplicationUrl(amount, down, rate, years);
    action.container.hidden = false;
  }

  function getCalcNumber(calcForm, fieldName) {
    const input = calcForm.querySelector(`[name="${fieldName}"]`);
    if (!input) return NaN;

    const normalizedValue = String(input.value || '')
      .replace(/\s+/g, '')
      .replace(',', '.');

    return Number(normalizedValue);
  }

  function setInvalidField(calcForm, fieldName) {
    calcForm.querySelectorAll('input').forEach((input) => {
      input.setAttribute('aria-invalid', String(input.name === fieldName));
    });
  }

  function showCalcMessage(calcForm, result, message, fieldName) {
    setInvalidField(calcForm, fieldName);
    hideApplicationAction(calcForm);
    result.classList.add('is-error');
    result.innerHTML = `<span>Проверьте данные</span><strong>${message}</strong><small>Измените значение, и расчёт обновится автоматически.</small>`;
  }

  function calculateMortgage(calcForm) {
    const amount = getCalcNumber(calcForm, 'amount');
    const down = getCalcNumber(calcForm, 'down');
    const rate = getCalcNumber(calcForm, 'rate');
    const years = getCalcNumber(calcForm, 'years');
    const result = calcForm.querySelector('[data-calc-result]');

    if (!result) return;
    if (!Number.isFinite(amount) || amount <= 0) return showCalcMessage(calcForm, result, 'Укажите стоимость жилья', 'amount');
    if (!Number.isFinite(down) || down < 0) return showCalcMessage(calcForm, result, 'Укажите корректный первоначальный взнос', 'down');
    if (down >= amount) return showCalcMessage(calcForm, result, 'Взнос должен быть меньше стоимости жилья', 'down');
    if (!Number.isFinite(rate) || rate < 0 || rate > 100) return showCalcMessage(calcForm, result, 'Укажите ставку от 0 до 100%', 'rate');
    if (!Number.isFinite(years) || years < 1 || years > 30) return showCalcMessage(calcForm, result, 'Укажите срок от 1 до 30 лет', 'years');

    const credit = amount - down;
    const months = Math.round(years * 12);
    const monthlyRate = rate / 100 / 12;
    let payment = credit / months;

    if (monthlyRate > 0) {
      const growth = Math.pow(1 + monthlyRate, months);
      payment = credit * ((monthlyRate * growth) / (growth - 1));
    }

    const total = payment * months;
    setInvalidField(calcForm, '');
    result.classList.remove('is-error');
    result.innerHTML = `<span>Примерный ежемесячный платёж</span><strong>${formatRub(payment)}</strong><small>Сумма кредита: ${formatRub(credit)}. Общая выплата: около ${formatRub(total)}. Расчёт предварительный, финальные условия определяет банк.</small>`;
    showApplicationAction(calcForm, result, amount, down, rate, years);
  }

  calcForms.forEach((calcForm) => {
    const result = calcForm.querySelector('[data-calc-result]');
    enhanceCalculatorInputs(calcForm);
    normalizeDirectApplicationAction(calcForm);

    if (result) {
      result.setAttribute('aria-live', 'polite');
      result.setAttribute('aria-atomic', 'true');
      ensureApplicationAction(calcForm, result);
    }

    let calcGoalSent = false;
    calcForm.addEventListener('input', () => {
      calculateMortgage(calcForm);
      if (!calcGoalSent) {
        calcGoalSent = true;
        track('calculator_input');
      }
    });
    calculateMortgage(calcForm);
  });
})();