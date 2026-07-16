(() => {
  const calcForms = document.querySelectorAll('[data-mortgage-calc]');
  if (!calcForms.length) return;

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
  }

  calcForms.forEach((calcForm) => {
    const result = calcForm.querySelector('[data-calc-result]');
    enhanceCalculatorInputs(calcForm);

    if (result) {
      result.setAttribute('aria-live', 'polite');
      result.setAttribute('aria-atomic', 'true');
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
