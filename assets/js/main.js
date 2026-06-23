const navToggle = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('#main-nav');
const copyPhoneButtons = document.querySelectorAll('[data-copy-phone]');
const calcForm = document.querySelector('[data-mortgage-calc]');

if (navToggle && mainNav) {
  navToggle.addEventListener('click', () => {
    const isOpen = mainNav.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });
}

copyPhoneButtons.forEach((button) => {
  button.addEventListener('click', async () => {
    const phone = '89030250807';
    try {
      await navigator.clipboard.writeText(phone);
      button.textContent = 'Телефон скопирован';
    } catch (error) {
      button.textContent = phone;
    }
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
