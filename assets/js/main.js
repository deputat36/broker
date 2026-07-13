const navToggle = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('#main-nav');
const copyPhoneButtons = document.querySelectorAll('[data-copy-phone]');
const calcForms = document.querySelectorAll('[data-mortgage-calc]');
const maxPhone = '89030250807';

const TRACKING_KEYS = [
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'utm_term',
  'utm_id',
  'gclid',
  'yclid',
  'ymclid',
  'vkclid',
  'fbclid',
  'roistat',
  'openstat',
  'realtor',
  'realtor_id',
  'manager',
  'lead_source',
  'placement'
];
const TRACKING_STORAGE_KEY = 'sterlikovaMortgageTracking';
const TRACKING_RETENTION_DAYS = 90;
const TRACKING_RETENTION_MS = TRACKING_RETENTION_DAYS * 24 * 60 * 60 * 1000;

function sendGoal(goalName) {
  if (typeof window.ym !== 'function') return;
  const counterId = window.siteAnalytics && window.siteAnalytics.yandexMetrikaId;
  if (!counterId) return;

  try {
    window.ym(counterId, 'reachGoal', goalName);
  } catch (error) {
    // Ошибка аналитики не должна мешать работе кнопок, меню и калькулятора.
  }
}

window.sendGoal = sendGoal;

function safeJsonParse(value, fallback = {}) {
  try {
    return JSON.parse(value) || fallback;
  } catch (error) {
    return fallback;
  }
}

function removeStoredTracking() {
  try {
    window.localStorage.removeItem(TRACKING_STORAGE_KEY);
  } catch (error) {
    // Ограничения localStorage не должны мешать работе сайта.
  }
}

function readStoredTracking() {
  try {
    const stored = safeJsonParse(window.localStorage.getItem(TRACKING_STORAGE_KEY), {});
    const expiresAt = Date.parse(stored.expires_at || '');
    if (Number.isFinite(expiresAt) && expiresAt <= Date.now()) {
      removeStoredTracking();
      return {};
    }
    return stored;
  } catch (error) {
    return {};
  }
}

function saveStoredTracking(tracking) {
  try {
    window.localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(tracking));
  } catch (error) {
    // Ограничения localStorage не должны мешать работе сайта и формы.
  }
}

function getTrackingData() {
  const params = new URLSearchParams(window.location.search);
  const saved = readStoredTracking();
  const incoming = {};

  TRACKING_KEYS.forEach((key) => {
    const value = params.get(key);
    if (value) incoming[key] = value.trim().slice(0, 300);
  });

  const nowDate = new Date();
  const now = nowDate.toISOString();
  const pageSnapshot = {
    page_url: window.location.href,
    page_path: window.location.pathname,
    page_title: document.title,
    referrer: document.referrer || '',
    captured_at: now
  };
  const current = { ...(saved.current || {}), ...incoming };
  const tracking = {
    first_touch: saved.first_touch || { ...pageSnapshot, values: current },
    last_touch: { ...pageSnapshot, values: current },
    current,
    stored_at: now,
    expires_at: new Date(nowDate.getTime() + TRACKING_RETENTION_MS).toISOString()
  };

  saveStoredTracking(tracking);
  return tracking;
}

window.getSiteTrackingData = getTrackingData;
window.clearSiteTrackingData = removeStoredTracking;
getTrackingData();

function normalizePath(pathname) {
  const normalizedPath = String(pathname || '/')
    .replace(/\/index\.html$/, '/')
    .replace(/\/+$/, '/');

  return normalizedPath || '/';
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

function enhanceCurrentLinks() {
  const currentPath = normalizePath(window.location.pathname);
  const navLinks = document.querySelectorAll('.main-nav a[href], .site-footer a[href]');

  navLinks.forEach((link) => {
    let url;

    try {
      url = new URL(link.href);
    } catch (error) {
      return;
    }

    if (url.origin !== window.location.origin) return;

    const linkPath = normalizePath(url.pathname);
    const isExactPage = linkPath === currentPath;
    const isParentSection = linkPath !== '/' && currentPath.indexOf(linkPath) === 0;

    if (!isExactPage && !isParentSection) return;

    link.classList.add('is-current');
    link.setAttribute('aria-current', isExactPage ? 'page' : 'location');
  });
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

function closeMainNav() {
  if (!navToggle || !mainNav) return;
  mainNav.classList.remove('is-open');
  navToggle.setAttribute('aria-expanded', 'false');
  navToggle.setAttribute('aria-label', 'Открыть меню сайта');
}

enhanceExternalLinks();
enhanceCurrentLinks();

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
  if (href.indexOf('/online-zayavka/') !== -1) sendGoal('online_application_click');
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
      sendGoal('calculator_input');
    }
  });
  calculateMortgage(calcForm);
});
