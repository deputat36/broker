#!/usr/bin/env node

const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const scriptPath = path.resolve(process.argv[2] || 'assets/js/main.js');
const source = fs.readFileSync(scriptPath, 'utf8');
const STORAGE_KEY = 'sterlikovaMortgageTracking';
const DAY_MS = 24 * 60 * 60 * 1000;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
    removeItem(key) {
      values.delete(key);
    },
    snapshot() {
      return Object.fromEntries(values.entries());
    }
  };
}

function runBrowser({ href, referrer = '', storedTracking = null }) {
  const currentUrl = new URL(href);
  const initial = storedTracking === null
    ? {}
    : { [STORAGE_KEY]: JSON.stringify(storedTracking) };
  const localStorage = createStorage(initial);
  const listeners = new Map();

  const document = {
    title: 'Тестовая страница ипотечного брокера',
    referrer,
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    addEventListener(type, handler) {
      listeners.set(`document:${type}`, handler);
    }
  };

  const window = {
    location: {
      origin: currentUrl.origin,
      href: currentUrl.href,
      pathname: currentUrl.pathname,
      search: currentUrl.search
    },
    localStorage,
    addEventListener(type, handler) {
      listeners.set(`window:${type}`, handler);
    },
    clearTimeout() {},
    setTimeout() {
      return 1;
    },
    innerWidth: 1280
  };

  const context = {
    window,
    document,
    navigator: {},
    URL,
    URLSearchParams,
    Date,
    JSON,
    Intl,
    Set,
    Number,
    String,
    Array,
    Object,
    Boolean,
    Math,
    console
  };

  vm.runInNewContext(source, context, { filename: scriptPath });
  const stored = localStorage.snapshot()[STORAGE_KEY];
  assert(stored, 'main.js не сохранил новую атрибуцию');

  return {
    tracking: JSON.parse(stored),
    safeContext: window.getSiteSafePageContext(),
    serialized: stored
  };
}

function assertNoSecrets(result, forbiddenValues, label) {
  forbiddenValues.forEach((value) => {
    assert(!result.serialized.includes(value), `${label}: в localStorage найдено запрещённое значение ${value}`);
  });
}

const unsafeVisit = runBrowser({
  href: 'https://sterlikova-ipoteka.ru/online-zayavka/?utm_source=vk&phone=%2B79991234567&unknown=passport#request-secret',
  referrer: 'https://search.example/results?q=%2B79991234567#private'
});

assert(unsafeVisit.tracking.storage_version === 2, 'Новая запись должна иметь storage_version=2');
assert(
  unsafeVisit.tracking.first_touch.page_url === 'https://sterlikova-ipoteka.ru/online-zayavka/',
  'page_url должен сохраняться без query и fragment'
);
assert(
  unsafeVisit.tracking.first_touch.referrer === 'https://search.example',
  'Внешний referrer должен сокращаться до origin'
);
assert(unsafeVisit.tracking.current.utm_source === 'vk', 'Разрешённая UTM-метка потеряна');
assert(!Object.hasOwn(unsafeVisit.tracking.current, 'phone'), 'Произвольный phone попал в allowlist атрибуции');
assertNoSecrets(unsafeVisit, ['79991234567', 'passport', 'request-secret', '/results'], 'Небезопасный визит');

assert(
  unsafeVisit.safeContext.page_url === 'https://sterlikova-ipoteka.ru/online-zayavka/',
  'Публичный safe page context содержит query или fragment'
);
assert(unsafeVisit.safeContext.referrer === 'https://search.example', 'Safe context раскрывает путь внешнего referrer');

const legacyVisit = runBrowser({
  href: 'https://sterlikova-ipoteka.ru/konsultaciya/?utm_medium=cpc',
  storedTracking: {
    first_touch: {
      page_url: 'https://sterlikova-ipoteka.ru/?phone=79990000000#legacy',
      referrer: 'https://legacy.example/private?token=secret'
    },
    current: { utm_source: 'legacy', phone: '79990000000' },
    expires_at: '2099-01-01T00:00:00.000Z'
  }
});

assert(legacyVisit.tracking.storage_version === 2, 'Legacy-запись не заменена текущей версией');
assert(legacyVisit.tracking.current.utm_medium === 'cpc', 'Новая UTM после очистки legacy-записи потеряна');
assert(!Object.hasOwn(legacyVisit.tracking.current, 'utm_source'), 'Legacy UTM ошибочно унаследована');
assertNoSecrets(legacyVisit, ['79990000000', 'legacy.example', 'token', 'secret'], 'Legacy-запись');

const now = Date.now();
const validStored = {
  storage_version: 2,
  first_touch: {
    page_url: 'https://sterlikova-ipoteka.ru/',
    page_path: '/',
    page_title: 'Первый визит',
    referrer: 'https://vk.com',
    captured_at: new Date(now - DAY_MS).toISOString(),
    values: { utm_source: 'vk' }
  },
  last_touch: {
    page_url: 'https://sterlikova-ipoteka.ru/uslugi/',
    page_path: '/uslugi/',
    page_title: 'Услуги',
    referrer: '',
    captured_at: new Date(now - DAY_MS).toISOString(),
    values: { utm_source: 'vk' }
  },
  current: { utm_source: 'vk', unknown_key: 'drop-me' },
  stored_at: new Date(now - DAY_MS).toISOString(),
  expires_at: new Date(now - DAY_MS + 90 * DAY_MS).toISOString()
};

const validVisit = runBrowser({
  href: 'https://sterlikova-ipoteka.ru/stoimost/?utm_medium=retarget&phone=79995555555',
  referrer: 'https://sterlikova-ipoteka.ru/uslugi/?client=private#fragment',
  storedTracking: validStored
});

assert(validVisit.tracking.first_touch.page_title === 'Первый визит', 'Корректный first_touch не сохранён');
assert(validVisit.tracking.current.utm_source === 'vk', 'Сохранённая allowlist UTM потеряна');
assert(validVisit.tracking.current.utm_medium === 'retarget', 'Новая allowlist UTM не объединена');
assert(!Object.hasOwn(validVisit.tracking.current, 'unknown_key'), 'Неизвестный ключ пережил санитизацию');
assert(
  validVisit.tracking.last_touch.referrer === 'https://sterlikova-ipoteka.ru/uslugi/',
  'Внутренний referrer должен сохранять только origin+path'
);
assertNoSecrets(validVisit, ['79995555555', 'client=private', '#fragment', 'drop-me'], 'Корректная запись');

const farFutureVisit = runBrowser({
  href: 'https://sterlikova-ipoteka.ru/?utm_campaign=fresh',
  storedTracking: {
    ...validStored,
    stored_at: new Date(now).toISOString(),
    expires_at: new Date(now + 365 * DAY_MS).toISOString()
  }
});

assert(farFutureVisit.tracking.current.utm_campaign === 'fresh', 'Новая UTM после invalid lifetime потеряна');
assert(!Object.hasOwn(farFutureVisit.tracking.current, 'utm_source'), 'Запись с завышенным сроком была унаследована');

console.log(`Privacy-тест атрибуции пройден: ${path.relative(process.cwd(), scriptPath)}`);
