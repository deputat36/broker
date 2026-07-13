(() => {
  const form = document.querySelector('[data-online-application]');
  if (!form) return;

  const phone = form.querySelector('[data-phone-input]');
  const phoneHint = document.getElementById('application-phone-hint');
  const moreDetails = form.querySelector('[data-application-more]');
  const formStatus = form.querySelector('[data-application-status]');

  function track(goalName) {
    if (typeof window.sendGoal === 'function') window.sendGoal(goalName);
  }

  function normalizeRussianPhone(value) {
    let digits = String(value || '').replace(/\D/g, '');
    if (digits.length === 10) digits = `7${digits}`;
    if (digits.length === 11 && digits.startsWith('8')) digits = `7${digits.slice(1)}`;
    return digits.length === 11 && digits.startsWith('7') ? digits : '';
  }

  function formatRussianPhone(value) {
    let digits = String(value || '').replace(/\D/g, '');
    if (digits.startsWith('7') || digits.startsWith('8')) digits = digits.slice(1);
    digits = digits.slice(0, 10);

    if (!digits) return '';
    let formatted = '+7';
    if (digits.length > 0) formatted += ` (${digits.slice(0, 3)}`;
    if (digits.length >= 3) formatted += ')';
    if (digits.length > 3) formatted += ` ${digits.slice(3, 6)}`;
    if (digits.length > 6) formatted += `-${digits.slice(6, 8)}`;
    if (digits.length > 8) formatted += `-${digits.slice(8, 10)}`;
    return formatted;
  }

  function setPhoneValidity(showMessage = false) {
    if (!phone) return true;
    const normalized = normalizeRussianPhone(phone.value);
    const valid = Boolean(normalized);

    phone.setCustomValidity(valid || !phone.value.trim() ? '' : 'Введите российский номер из 10 цифр после +7.');
    phone.setAttribute('aria-invalid', String(!valid && Boolean(phone.value.trim())));

    if (phoneHint) {
      phoneHint.textContent = valid
        ? `Номер для связи: +${normalized}`
        : 'Введите 10 цифр российского номера. Подойдут форматы +7 или 8.';
      phoneHint.classList.toggle('is-success', valid);
      phoneHint.classList.toggle('is-error', showMessage && !valid && Boolean(phone.value.trim()));
    }

    return valid;
  }

  if (phone) {
    phone.addEventListener('input', () => {
      const formatted = formatRussianPhone(phone.value);
      if (formatted) phone.value = formatted;
      phone.setCustomValidity('');
      phone.removeAttribute('aria-invalid');
      if (phoneHint) {
        phoneHint.textContent = 'Введите 10 цифр российского номера. Подойдут форматы +7 или 8.';
        phoneHint.classList.remove('is-success', 'is-error');
      }
    });

    phone.addEventListener('blur', () => {
      const normalized = normalizeRussianPhone(phone.value);
      if (normalized) phone.value = formatRussianPhone(normalized);
      setPhoneValidity(true);
    });
  }

  form.addEventListener('submit', (event) => {
    if (setPhoneValidity(true)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (formStatus) {
      formStatus.textContent = 'Проверьте номер телефона: нужно указать 10 цифр после +7.';
      formStatus.classList.remove('is-success');
      formStatus.classList.add('is-error');
    }
    phone.focus();
    phone.reportValidity();
    track('online_application_phone_error');
  }, true);

  if (moreDetails) {
    moreDetails.addEventListener('toggle', () => {
      if (moreDetails.open) track('online_application_more_open');
    });
  }
})();
