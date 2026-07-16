'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const htmlPath = process.argv[2] || '_site/online-zayavka/index.html';
const html = fs.readFileSync(htmlPath, 'utf8');
const match = html.match(/<script[^>]*data-application-consent-validation[^>]*>([\s\S]*?)<\/script>/i);
assert.ok(match, 'На странице отсутствует inline-валидация согласия');
const source = match[1];

function createField(name) {
  const attributes = {};
  const listeners = {};
  return {
    name,
    checked: false,
    attributes,
    listeners,
    setAttribute(key, value) { attributes[key] = String(value); },
    removeAttribute(key) { delete attributes[key]; },
    addEventListener(type, callback) { listeners[type] = callback; }
  };
}

const consent = createField('consent');
const optional = createField('preparation_check');
const formListeners = {};
const documentListeners = {};
const form = {
  elements: {
    namedItem(name) {
      if (name === 'consent') return consent;
      if (name === 'preparation_check') return optional;
      return null;
    }
  },
  addEventListener(type, callback) { formListeners[type] = callback; }
};
const document = {
  querySelector(selector) {
    return selector === '[data-online-application]' ? form : null;
  },
  addEventListener(type, callback) { documentListeners[type] = callback; }
};

vm.runInNewContext(source, { document, String }, { filename: htmlPath });
assert.strictEqual(typeof documentListeners.DOMContentLoaded, 'function');
documentListeners.DOMContentLoaded();

assert.strictEqual(typeof formListeners.submit, 'function');
assert.strictEqual(typeof consent.listeners.change, 'function');

formListeners.submit();
assert.strictEqual(consent.attributes['aria-invalid'], 'true');
assert.strictEqual(Object.hasOwn(optional.attributes, 'aria-invalid'), false);

consent.checked = true;
consent.listeners.change();
assert.strictEqual(Object.hasOwn(consent.attributes, 'aria-invalid'), false);

formListeners.submit();
assert.strictEqual(consent.attributes['aria-invalid'], 'false');

console.log('Inline-маркировка обязательного согласия прошла поведенческий тест');
