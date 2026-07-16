'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const scriptPath = process.argv[2] || 'assets/js/application-inputs.js';
const source = fs.readFileSync(scriptPath, 'utf8');
const secondIife = source.indexOf('\n\n(() => {', 1);
const inputSource = secondIife === -1 ? source : source.slice(0, secondIife);

function createClassList(initial = []) {
  const values = new Set(initial);
  return {
    add(...names) { names.forEach((name) => values.add(name)); },
    remove(...names) { names.forEach((name) => values.delete(name)); },
    contains(name) { return values.has(name); }
  };
}

function createEventTarget() {
  const listeners = {};
  return {
    listeners,
    addEventListener(name, callback) {
      listeners[name] = callback;
    }
  };
}

const phoneTarget = createEventTarget();
const phoneAttributes = {};
let phoneFocused = false;
let phoneReported = false;
const phone = {
  ...phoneTarget,
  value: '+7 (900) 000-00-00',
  setCustomValidity(message) { this.validationMessage = message; },
  setAttribute(name, value) { phoneAttributes[name] = String(value); },
  removeAttribute(name) { delete phoneAttributes[name]; },
  focus() { phoneFocused = true; },
  reportValidity() { phoneReported = true; }
};

const consentTarget = createEventTarget();
const consentAttributes = {};
let consentFocused = false;
let consentReported = false;
const consent = {
  ...consentTarget,
  checked: false,
  setAttribute(name, value) { consentAttributes[name] = String(value); },
  removeAttribute(name) { delete consentAttributes[name]; },
  focus() { consentFocused = true; },
  reportValidity() { consentReported = true; }
};

const phoneHint = {
  textContent: '',
  classList: createClassList()
};
const formStatus = {
  textContent: '',
  classList: createClassList()
};
const moreDetails = createEventTarget();
const formListeners = {};
const form = {
  elements: {
    namedItem(name) { return name === 'consent' ? consent : null; }
  },
  querySelector(selector) {
    if (selector === '[data-phone-input]') return phone;
    if (selector === '[data-application-more]') return moreDetails;
    if (selector === '[data-application-status]') return formStatus;
    return null;
  },
  querySelectorAll(selector) {
    return selector === '.application-consent a' ? [] : [];
  },
  addEventListener(name, callback) {
    formListeners[name] = callback;
  }
};

const goals = [];
const document = {
  querySelector(selector) {
    return selector === '[data-online-application]' ? form : null;
  },
  getElementById(id) {
    return id === 'application-phone-hint' ? phoneHint : null;
  }
};
const window = {
  sendGoal(name) { goals.push(name); }
};

vm.runInNewContext(inputSource, {
  document,
  window,
  String,
  Boolean
}, { filename: scriptPath });

assert.strictEqual(typeof formListeners.submit, 'function');
assert.strictEqual(typeof consent.listeners.change, 'function');

function createSubmitEvent() {
  return {
    prevented: false,
    stopped: false,
    preventDefault() { this.prevented = true; },
    stopImmediatePropagation() { this.stopped = true; }
  };
}

const invalidEvent = createSubmitEvent();
formListeners.submit(invalidEvent);

assert.strictEqual(invalidEvent.prevented, true);
assert.strictEqual(invalidEvent.stopped, true);
assert.strictEqual(consentAttributes['aria-invalid'], 'true');
assert.strictEqual(consentFocused, true);
assert.strictEqual(consentReported, true);
assert.strictEqual(phoneFocused, false);
assert.strictEqual(phoneReported, false);
assert.ok(formStatus.textContent.includes('Подтвердите согласие'));
assert.strictEqual(formStatus.classList.contains('is-error'), true);
assert.deepStrictEqual(goals, ['online_application_consent_error']);

consent.checked = true;
consent.listeners.change();
assert.strictEqual(Object.hasOwn(consentAttributes, 'aria-invalid'), false);

const validEvent = createSubmitEvent();
formListeners.submit(validEvent);
assert.strictEqual(validEvent.prevented, false);
assert.strictEqual(validEvent.stopped, false);
assert.strictEqual(consentAttributes['aria-invalid'], 'false');

console.log('Ошибка обязательного согласия прошла поведенческий тест');