const navToggle = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('#main-nav');
const copyPhoneButtons = document.querySelectorAll('[data-copy-phone]');
const calcForms = document.querySelectorAll('[data-mortgage-calc]');
const maxPhone = '89030250807';

function sendGoal(goalName) {
  if (typeof window.ym !== 'function') return;
  const counterId = window.siteAnalytics && window.siteAnalytics.yandexMetrikaId;
  if (!counterId) return;
  window.ym(counterId, 'reachGoal', goalName);
}

function enhanceExternalLinks() {
  document.querySelectorAll('a[href^="http://"], a[href^="https://"]').forEach((link) => {
    let url;

    try {
      url = new URL(link.href);
    } catch (error) {
      return;
    }

    if (url.origin === window.location.origin) return;

    const relTokens = new Set((link.getAttribute('rel') || '').split(/\s+/).filter(Boolean));
    relTokens.add('noopener');
    relTokens.add('noreferrer');
    link.setAttribute('rel', Array.from(relTokens).join(' '));
  });
}

function closeMainNav() {
  if (!navToggle || !mainNav) return;
  mainNav.classList.remove('is-open');
  navToggle.setAttribute('aria-expanded', 'false');
  navToggle.setAttribute('aria-label', 'Открыть меню сайта');
}

enhanceExternalLinks();

if (navToggle && mainNav) {
  navToggle.addEventListener('click', () => {
    const isOpen = mainNav.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
    navToggle.setAttribute('aria-label', isOpen ? 'Закрыть меню сайта' : 'Открыть меню сайта');
  });

  mainNav.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', closeMainNav);
  });

  document.addEventListener('click', (event) => {
    if (!mainNav.classList.contains('is-open')) return;
    if (mainNav.contains(event.target) || navToggle.contains(event.target)) return;
    closeMainNav();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && mainNav.classList.contains('is-open')) {
      closeMainNav();
      navToggle.focus();
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 1120) closeMainNav();
  });
}

document.addEventListener('click', (event) => {
  const link = event.target.closest('a');
  if (!link) return;
  const href = link.getAttribute('href') || '';
  if (href.indexOf('tel:') === 0) sendGoal('phone_click');
  if (href.indexOf('vk.com/tatyanasterlikova') !== -1) sendGoal('vk_click');
  if (href.indexOf('/konsultaciya/') !== -1) sendGoal('consultation_click');
  if (href.indexOf('/kontakty/') !== -1) sendGoal('contacts_click');
});

copyPhoneButtons.forEach((button) => {
  const initialText = button.textContent;
  let resetTimer;

  button.setAttribute('aria-live', 'polite');
  button.setAttribute('aria-atomic', 'true');
  button.setAttribute('aria-label', 'Скопировать номер телефона для MAX');
  button.setAttribute('title', 'Скопировать номер телефона для MAX');

  button.addEventListener('click', async () => {
    window.clearTimeout(resetTimer);
    sendGoal('max_copy');

    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard API is unavailable');
      await navigator.clipboard.writeText(maxPhone);
      button.textContent = 'Номер скопирован';
    } catch (error) {
      button.textContent = maxPhone;
    }

    resetTimer = window.setTimeout(() => {
      button.textContent = initialText;
    }, 2500);
  });
});

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
  result.innerHTML = `<span>Проверьте данные</span><strong>${message}</strong><small>Измените значение, и расчет обновится автоматически.</small>`;
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
  result.innerHTML = `<span>Примерный ежемесячный платеж</span><strong>${formatRub(payment)}</strong><small>Сумма кредита: ${formatRub(credit)}. Общая выплата: около ${formatRub(total)}. Расчет предварительный, финальные условия определяет банк.</small>`;
}

calcForms.forEach((calcForm) => {
  const result = calcForm.querySelector('[data-calc-result]');
  if (result) {
    result.setAttribute('aria-live', 'polite');
    result.setAttribute('aria-atomic', 'true');
  }

  let calcGoalSent = false;
  calcForm.addEventListener('input', () => {
    calculateMortgage(calcForm);
    if (!calcGoalSent) {
      calcGoalSent = true;
      sendGoal('calculator_input');
    }
  });
  calculateMortgage(calcForm);
});
