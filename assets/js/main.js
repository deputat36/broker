const navToggle = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('#main-nav');
const copyPhoneButtons = document.querySelectorAll('[data-copy-phone]');
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
const TRACKING_STORAGE_VERSION = 2;
const TRACKING_RETENTION_DAYS = 90;
const TRACKING_RETENTION_MS = TRACKING_RETENTION_DAYS * 24 * 60 * 60 * 1000;
const TRACKING_CLOCK_SKEW_MS = 5 * 60 * 1000;
const TRACKING_VALUE_MAX_LENGTH = 300;
const TRACKING_TITLE_MAX_LENGTH = 200;
function sendGoal(goalName) {
  if (typeof window.ym !== 'function') return;
  const counterId = window.siteAnalytics && window.siteAnalytics.yandexMetrikaId;
  if (!counterId) return;
  try {
    window.ym(counterId, 'reachGoal', goalName);
  } catch (error) {
  }
}
window.sendGoal = sendGoal;
function normalizePath(pathname) {
  const normalizedPath = String(pathname || '/')
    .replace(/\/index\.html$/, '/')
    .replace(/\/+$/, '/');
  return normalizedPath || '/';
}
function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
function safeJsonParse(value, fallback = {}) {
  try {
    return JSON.parse(value) || fallback;
  } catch (error) {
    return fallback;
  }
}
function sanitizeTrackingValue(value, maxLength = TRACKING_VALUE_MAX_LENGTH) {
  return String(value || '').trim().slice(0, maxLength);
}
function sanitizeTrackingMap(value) {
  const source = isPlainObject(value) ? value : {};
  const safe = {};
  TRACKING_KEYS.forEach((key) => {
    const normalized = sanitizeTrackingValue(source[key]);
    if (normalized) safe[key] = normalized;
  });
  return safe;
}
function sanitizePageUrl(value, options = {}) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw, window.location.origin);
    if (!['http:', 'https:'].includes(url.protocol)) return '';
    url.username = '';
    url.password = '';
    url.search = '';
    url.hash = '';
    if (options.externalOriginOnly && url.origin !== window.location.origin) {
      return url.origin;
    }
    return `${url.origin}${normalizePath(url.pathname)}`;
  } catch (error) {
    return '';
  }
}
function getSafePageContext() {
  const pagePath = normalizePath(window.location.pathname);
  return {
    page_url: sanitizePageUrl(window.location.href) || `${window.location.origin}${pagePath}`,
    page_path: pagePath,
    referrer: sanitizePageUrl(document.referrer, { externalOriginOnly: true })
  };
}
window.getSiteSafePageContext = getSafePageContext;
function removeStoredTracking() {
  try {
    window.localStorage.removeItem(TRACKING_STORAGE_KEY);
  } catch (error) {
  }
}
function sanitizeStoredSnapshot(value) {
  if (!isPlainObject(value)) return null;
  const pageUrl = sanitizePageUrl(value.page_url);
  const parsedCapturedAt = Date.parse(value.captured_at || '');
  return {
    page_url: pageUrl,
    page_path: normalizePath(value.page_path || (pageUrl ? new URL(pageUrl).pathname : '/')),
    page_title: sanitizeTrackingValue(value.page_title, TRACKING_TITLE_MAX_LENGTH),
    referrer: sanitizePageUrl(value.referrer, { externalOriginOnly: true }),
    captured_at: Number.isFinite(parsedCapturedAt) ? new Date(parsedCapturedAt).toISOString() : '',
    values: sanitizeTrackingMap(value.values)
  };
}
function readStoredTracking() {
  try {
    const raw = window.localStorage.getItem(TRACKING_STORAGE_KEY);
    if (!raw) return {};
    const stored = safeJsonParse(raw, null);
    const now = Date.now();
    const storedAt = Date.parse(isPlainObject(stored) ? stored.stored_at || '' : '');
    const expiresAt = Date.parse(isPlainObject(stored) ? stored.expires_at || '' : '');
    const invalidLifetime = !Number.isFinite(storedAt)
      || !Number.isFinite(expiresAt)
      || storedAt > now + TRACKING_CLOCK_SKEW_MS
      || now - storedAt > TRACKING_RETENTION_MS + TRACKING_CLOCK_SKEW_MS
      || expiresAt <= now
      || expiresAt > storedAt + TRACKING_RETENTION_MS + TRACKING_CLOCK_SKEW_MS;
    if (!isPlainObject(stored)
      || stored.storage_version !== TRACKING_STORAGE_VERSION
      || invalidLifetime) {
      removeStoredTracking();
      return {};
    }
    const firstTouch = sanitizeStoredSnapshot(stored.first_touch);
    const lastTouch = sanitizeStoredSnapshot(stored.last_touch);
    if (!firstTouch || !lastTouch) {
      removeStoredTracking();
      return {};
    }
    return {
      storage_version: TRACKING_STORAGE_VERSION,
      first_touch: firstTouch,
      last_touch: lastTouch,
      current: sanitizeTrackingMap(stored.current),
      stored_at: new Date(storedAt).toISOString(),
      expires_at: new Date(expiresAt).toISOString()
    };
  } catch (error) {
    removeStoredTracking();
    return {};
  }
}
function saveStoredTracking(tracking) {
  try {
    window.localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(tracking));
  } catch (error) {
  }
}
function getTrackingData() {
  const params = new URLSearchParams(window.location.search);
  const saved = readStoredTracking();
  const incoming = {};
  TRACKING_KEYS.forEach((key) => {
    const value = sanitizeTrackingValue(params.get(key));
    if (value) incoming[key] = value;
  });
  const nowDate = new Date();
  const now = nowDate.toISOString();
  const safeContext = getSafePageContext();
  const current = { ...sanitizeTrackingMap(saved.current), ...incoming };
  const pageSnapshot = {
    page_url: safeContext.page_url,
    page_path: safeContext.page_path,
    page_title: sanitizeTrackingValue(document.title, TRACKING_TITLE_MAX_LENGTH),
    referrer: safeContext.referrer,
    captured_at: now,
    values: current
  };
  const tracking = {
    storage_version: TRACKING_STORAGE_VERSION,
    first_touch: saved.first_touch || pageSnapshot,
    last_touch: pageSnapshot,
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
