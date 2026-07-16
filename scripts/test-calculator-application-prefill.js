'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const scriptPath = process.argv[2] || 'assets/js/calculator-application-prefill.js';
const source = fs.readFileSync(scriptPath, 'utf8');

function createField(value = '', maxLength = 1200) {
  return { value, maxLength };
}

function normalizedSpaces(value) {
  return String(value).replace(/\s+/g, ' ').trim();
}

function runCase(search, overrides = {}) {
  const fields = {
    object_price: createField(overrides.objectPrice || '', 40),
    down_payment: createField(overrides.downPayment || '', 40),
    comment: createField(overrides.comment || '', 1200),
    client_name: createField('Анна', 80),
    phone: createField('+7 900 000-00-00', 22),
    city: createField('Борисоглебск', 120)
  };
  const details = { tagName: 'DETAILS', open: false };
  const form = {
    dataset: {},
    elements: {
      namedItem(name) {
        return fields[name] || null;
      }
    },
    querySelector(selector) {
      return selector === '[data-application-more]' ? details : null;
    }
  };
  let replacedLocation = '';
  const goals = [];
  const window = {
    location: {
      search,
      href: `https://sterlikova-ipoteka.ru/online-zayavka/${search}`
    },
    history: {
      replaceState(_state, _title, location) {
        replacedLocation = location;
      }
    },
    setTimeout(callback) {
      callback();
      return 1;
    },
    sendGoal(name) {
      goals.push(name);
    }
  };
  const document = {
    title: 'Онлайн-заявка',
    querySelector(selector) {
      return selector === '[data-online-application]' ? form : null;
    }
  };

  vm.runInNewContext(source, {
    window,
    document,
    URL,
    URLSearchParams,
    Intl,
    Number,
    String,
    Object,
    Math,
    RegExp
  }, { filename: scriptPath });

  return { fields, details, form, replacedLocation, goals };
}

const valid = runCase('?source=%2Fkalkulyator-ipoteki%2F&utm_source=vk&calc_amount=4500000&calc_down=900000&calc_rate=18.5&calc_years=20');
assert.strictEqual(normalizedSpaces(valid.fields.object_price.value), '4 500 000 ₽');
assert.strictEqual(normalizedSpaces(valid.fields.down_payment.value), '900 000 ₽');
assert.strictEqual(normalizedSpaces(valid.fields.comment.value), 'Расчёт из ипотечного калькулятора: ставка 18,5% годовых, срок 20 лет.');
assert.strictEqual(valid.details.open, true);
assert.strictEqual(valid.form.dataset.calculatorPrefill, 'true');
assert.ok(valid.replacedLocation.includes('source=%2Fkalkulyator-ipoteki%2F'));
assert.ok(valid.replacedLocation.includes('utm_source=vk'));
assert.ok(!valid.replacedLocation.includes('calc_amount'));
assert.deepStrictEqual(valid.goals, ['online_application_calculator_prefill']);
assert.strictEqual(valid.fields.client_name.value, 'Анна');
assert.strictEqual(valid.fields.phone.value, '+7 900 000-00-00');
assert.strictEqual(valid.fields.city.value, 'Борисоглебск');

const invalid = runCase('?calc_amount=4000000&calc_down=5000000&calc_rate=101&calc_years=0');
assert.strictEqual(normalizedSpaces(invalid.fields.object_price.value), '4 000 000 ₽');
assert.strictEqual(invalid.fields.down_payment.value, '');
assert.strictEqual(invalid.fields.comment.value, '');
assert.strictEqual(invalid.details.open, true);

const existing = runCase('?calc_amount=5000000&calc_down=1000000&calc_rate=17&calc_years=15', {
  objectPrice: 'Уже указано пользователем',
  comment: 'Собственный комментарий'
});
assert.strictEqual(existing.fields.object_price.value, 'Уже указано пользователем');
assert.strictEqual(normalizedSpaces(existing.fields.down_payment.value), '1 000 000 ₽');
assert.strictEqual(existing.fields.comment.value, 'Собственный комментарий');

const empty = runCase('?source=%2Fkalkulyator-ipoteki%2F&utm_source=vk');
assert.strictEqual(empty.fields.object_price.value, '');
assert.strictEqual(empty.fields.down_payment.value, '');
assert.strictEqual(empty.fields.comment.value, '');
assert.strictEqual(empty.details.open, false);
assert.strictEqual(empty.replacedLocation, '');
assert.deepStrictEqual(empty.goals, []);

console.log('Предзаполнение заявки из калькулятора прошло поведенческие тесты');
