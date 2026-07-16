'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const scriptPath = process.argv[2] || 'assets/js/application-consent-validation.js';
const source = fs.readFileSync(scriptPath, 'utf8');

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
const listeners = {};
const form = {
  elements: {
    namedItem(name) {
      if (name === 'consent') return consent;
      if (name === 'preparation_check') return optional;
      return null;
    }
  },
  addEventListener(type, callback) { listeners[type] = callback; }
};
const document = {
  querySelector(selector) {
    return selector === '[data-online-application]' ? form : null;
  }
};

vm.runInNewContext(source, { document, String }, { filename: scriptPath });

assert.strictEqual(typeof listeners.submit, 'function');
assert.strictEqual(typeof consent.listeners.change, 'function');

listeners.submit();
assert.strictEqual(consent.attributes['aria-invalid'], 'true');
assert.strictEqual(Object.hasOwn(optional.attributes, 'aria-invalid'), false);

consent.checked = true;
consent.listeners.change();
assert.strictEqual(Object.hasOwn(consent.attributes, 'aria-invalid'), false);

listeners.submit();
assert.strictEqual(consent.attributes['aria-invalid'], 'false');

console.log('Маркировка обязательного согласия прошла поведенческий тест');