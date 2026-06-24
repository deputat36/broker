const navToggle = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('#main-nav');
const copyPhoneButtons = document.querySelectorAll('[data-copy-phone]');
const calcForm = document.querySelector('[data-mortgage-calc]');

function closeMainNav() {
  if (!navToggle || !mainNav) return;
  mainNav.classList.remove('is-open');
  navToggle.setAttribute('aria-expanded', 'false');
}

if (navToggle && mainNav) {
  navToggle.addEventListener('click', () => {
    const isOpen = mainNav.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
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
    if (event.key === 'Escape') {
      closeMainNav();
      navToggle.focus();
    }
  });
}

copyPhoneButtons.forEach((button) => {
  const initialText = button.textContent;
  let resetTimer;

  button.addEventListener('click', async () => {
    const phone = '89030250807';
    window.clearTimeout(resetTimer);

    try {
      await navigator.clipboard.writeText(phone);
      button.textContent = 'Номер скопирован';
    } catch (error) {
      button.textContent = phone;
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

function calculateMortgage() {
  if (!calcForm) return;

  const amount = Number(calcForm.querySelector('[name="amount"]').value || 0);
  const down = Number(calcForm.querySelector('[name="down"]').value || 0);
  const rate = Number(calcForm.querySelector('[name="rate"]').value || 0);
  const years = Number(calcForm.querySelector('[name="years"]').value || 0);
  const result = calcForm.querySelector('[data-calc-result]');
  const credit = Math.max(amount - down, 0);
  const months = Math.max(years * 12, 1);
  const monthlyRate = rate / 100 / 12;
  let payment = credit / months;

  if (monthlyRate > 0) {
    const coefficient = (monthlyRate * Math.pow(1 + monthlyRate, months)) / (Math.pow(1 + monthlyRate, months) - 1);
    payment = credit * coefficient;
  }

  result.innerHTML = `<span>Примерный платеж</span><strong>${formatRub(payment)}</strong><small>Сумма кредита: ${formatRub(credit)}. Расчет предварительный, финальные условия определяет банк.</small>`;
}

if (calcForm) {
  calcForm.addEventListener('input', calculateMortgage);
  calculateMortgage();
}
