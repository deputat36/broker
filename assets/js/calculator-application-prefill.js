(() => {
  const form = document.querySelector('[data-online-application]');
  if (!form) return;

  const params = new URLSearchParams(window.location.search);
  const limits = {
    calc_amount: { min: 1, max: 1000000000 },
    calc_down: { min: 0, max: 1000000000 },
    calc_rate: { min: 0, max: 100 },
    calc_years: { min: 1, max: 30 }
  };

  function readBoundedNumber(name) {
    const raw = String(params.get(name) || '').trim().replace(/\s+/g, '').replace(',', '.');
    const limit = limits[name];
    if (!raw || !limit || !/^\d+(?:\.\d+)?$/.test(raw)) return null;

    const value = Number(raw);
    if (!Number.isFinite(value) || value < limit.min || value > limit.max) return null;
    return value;
  }

  function setEmptyField(name, value) {
    const field = form.elements.namedItem(name);
    if (!field || String(field.value || '').trim()) return false;
    field.value = String(value).slice(0, field.maxLength > 0 ? field.maxLength : undefined);
    return true;
  }

  function formatMoney(value) {
    return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Math.round(value))} ₽`;
  }

  function formatNumber(value) {
    return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value);
  }

  const amount = readBoundedNumber('calc_amount');
  const downCandidate = readBoundedNumber('calc_down');
  const down = downCandidate !== null && (amount === null || downCandidate < amount)
    ? downCandidate
    : null;
  const rate = readBoundedNumber('calc_rate');
  const years = readBoundedNumber('calc_years');
  const hasCalculatorData = [amount, down, rate, years].some((value) => value !== null);

  if (!hasCalculatorData) return;

  if (amount !== null) setEmptyField('object_price', formatMoney(amount));
  if (down !== null) setEmptyField('down_payment', formatMoney(down));

  const contextParts = [];
  if (rate !== null) contextParts.push(`ставка ${formatNumber(rate)}% годовых`);
  if (years !== null) contextParts.push(`срок ${formatNumber(years)} лет`);
  if (contextParts.length) {
    setEmptyField('comment', `Расчёт из ипотечного калькулятора: ${contextParts.join(', ')}.`);
  }

  const moreDetails = form.querySelector('[data-application-more]');
  if (moreDetails && moreDetails.tagName === 'DETAILS') moreDetails.open = true;
  form.dataset.calculatorPrefill = 'true';

  const cleanUrl = new URL(window.location.href);
  Object.keys(limits).forEach((name) => cleanUrl.searchParams.delete(name));
  const cleanLocation = `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`;
  window.history.replaceState(null, document.title, cleanLocation);

  window.setTimeout(() => {
    if (typeof window.sendGoal === 'function') window.sendGoal('online_application_calculator_prefill');
  }, 0);
})();
