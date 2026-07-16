'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const scriptPath = process.argv[2] || 'assets/js/mortgage-calculator.js';
const source = fs.readFileSync(scriptPath, 'utf8');

function createClassList(initial = []) {
  const values = new Set(initial);
  return {
    add(...names) { names.forEach((name) => values.add(name)); },
    remove(...names) { names.forEach((name) => values.delete(name)); },
    contains(name) { return values.has(name); },
    toArray() { return Array.from(values); }
  };
}

function createLink(text, href, classes) {
  const attributes = { href };
  const listeners = {};
  return {
    textContent: text,
    className: classes.join(' '),
    classList: createClassList(classes),
    dataset: {},
    href,
    hasAttribute(name) {
      if (name === 'data-calc-application-link') return Object.hasOwn(this.dataset, 'calcApplicationLink');
      return Object.hasOwn(attributes, name);
    },
    getAttribute(name) {
      return name === 'href' ? this.href : (attributes[name] || '');
    },
    setAttribute(name, value) {
      attributes[name] = String(value);
      if (name === 'href') this.href = String(value);
    },
    addEventListener(name, callback) {
      listeners[name] = callback;
    },
    click() {
      if (listeners.click) listeners.click();
    }
  };
}

function createInput(name, value) {
  const attributes = {};
  return {
    name,
    value: String(value),
    setAttribute(attribute, attributeValue) {
      attributes[attribute] = String(attributeValue);
    },
    getAttribute(attribute) {
      return attributes[attribute] || '';
    }
  };
}

const staticLink = createLink(
  'Передать расчёт в заявке',
  '/online-zayavka/',
  ['btn', 'btn-primary']
);
const section = {
  querySelectorAll(selector) {
    return selector === 'a[href="/online-zayavka/"]' ? [staticLink] : [];
  }
};

const inputs = {
  amount: createInput('amount', 3500000),
  down: createInput('down', 700000),
  rate: createInput('rate', 18),
  years: createInput('years', 20)
};

let applicationContainer = null;
let applicationLink = null;
let inputListener = null;
const result = {
  classList: createClassList(['is-error']),
  innerHTML: '',
  nextSibling: null,
  attributes: {},
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  },
  parentNode: {
    insertBefore(container) {
      applicationContainer = container;
      applicationLink = container.children[0];
    }
  }
};

const calcForm = {
  closest(selector) {
    return selector === '.calc-section' ? section : null;
  },
  querySelector(selector) {
    const nameMatch = selector.match(/^\[name="(.+)"\]$/);
    if (nameMatch) return inputs[nameMatch[1]] || null;
    if (selector === '[data-calc-result]') return result;
    if (selector === '[data-calc-application-action]') return applicationContainer;
    if (selector === '[data-calc-application-link]') return applicationLink;
    return null;
  },
  querySelectorAll(selector) {
    return selector === 'input' ? Object.values(inputs) : [];
  },
  addEventListener(name, callback) {
    if (name === 'input') inputListener = callback;
  }
};

function createElement(tagName) {
  const attributes = {};
  const element = {
    tagName: tagName.toUpperCase(),
    className: '',
    classList: createClassList(),
    dataset: {},
    hidden: false,
    textContent: '',
    href: '',
    children: [],
    appendChild(child) {
      this.children.push(child);
    },
    setAttribute(name, value) {
      attributes[name] = String(value);
    },
    getAttribute(name) {
      return attributes[name] || '';
    },
    hasAttribute(name) {
      if (name === 'data-calc-application-link') return Object.hasOwn(this.dataset, 'calcApplicationLink');
      return Object.hasOwn(attributes, name);
    },
    addEventListener(name, callback) {
      this[`on${name}`] = callback;
    }
  };

  Object.defineProperty(element, 'className', {
    get() { return this._className || ''; },
    set(value) {
      this._className = String(value);
      this.classList = createClassList(String(value).split(/\s+/).filter(Boolean));
    }
  });

  return element;
}

const goals = [];
const document = {
  querySelectorAll(selector) {
    return selector === '[data-mortgage-calc]' ? [calcForm] : [];
  },
  createElement
};
const window = {
  location: {
    origin: 'https://sterlikova-ipoteka.ru',
    pathname: '/'
  },
  sendGoal(name) {
    goals.push(name);
  }
};

vm.runInNewContext(source, {
  document,
  window,
  URL,
  URLSearchParams,
  Intl,
  Number,
  String,
  Object,
  Math,
  RegExp
}, { filename: scriptPath });

assert.strictEqual(staticLink.textContent, 'Открыть онлайн-заявку');
assert.strictEqual(staticLink.classList.contains('btn-primary'), false);
assert.strictEqual(staticLink.classList.contains('btn-light'), true);

assert.ok(applicationContainer);
assert.strictEqual(applicationContainer.hidden, false);
assert.strictEqual(applicationLink.textContent, 'Перенести этот расчёт в заявку');
assert.strictEqual(applicationLink.classList.contains('btn-primary'), true);
assert.ok(applicationLink.href.startsWith('/online-zayavka/?'));
assert.ok(applicationLink.href.includes('source=%2F'));
assert.ok(applicationLink.href.includes('calc_amount=3500000'));
assert.ok(applicationLink.href.includes('calc_down=700000'));
assert.ok(applicationLink.href.includes('calc_rate=18'));
assert.ok(applicationLink.href.includes('calc_years=20'));
assert.ok(result.innerHTML.includes('Примерный ежемесячный платёж'));

applicationLink.onclick();
assert.deepStrictEqual(goals, ['calculator_application_click']);

inputs.down.value = '4000000';
inputListener();
assert.strictEqual(applicationContainer.hidden, true);
assert.ok(result.innerHTML.includes('Взнос должен быть меньше стоимости жилья'));
assert.strictEqual(inputs.down.getAttribute('aria-invalid'), 'true');

console.log('Действия калькулятора и заявки прошли поведенческие тесты');
