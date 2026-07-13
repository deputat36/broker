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

  function parseRussianPhone(value) {
    const digits = String(value || '').replace(/\D/g, '');
    const hasCountryPrefix = digits.startsWith('7') || digits.startsWith('8');
    const body = hasCountryPrefix ? digits.slice(1) : digits;
    return {
      body,
      overflow: body.length > 10,
      normalized: body.length === 10 ? `7${body}` : ''
    };
  }

  function normalizeRussianPhone(value) {
    const parsed = parseRussianPhone(value);
    return parsed.overflow ? '' : parsed.normalized;
  }

  function formatRussianPhone(value) {
    const parsed = parseRussianPhone(value);
    const digits = parsed.body.slice(0, 10);
    if (!digits) return '';

    let formatted = '+7';
    if (digits.length > 0) formatted += ` (${digits.slice(0, 3)}`;
    if (digits.length >= 3) formatted += ')';
    if (digits.length > 3) formatted += ` ${digits.slice(3, 6)}`;
    if (digits.length > 6) formatted += `-${digits.slice(6, 8)}`;
    if (digits.length > 8) formatted += `-${digits.slice(8, 10)}`;
    return formatted;
  }

  function setPhoneHint(message, state = '') {
    if (!phoneHint) return;
    phoneHint.textContent = message;
    phoneHint.classList.remove('is-success', 'is-error');
    if (state) phoneHint.classList.add(`is-${state}`);
  }

  function setPhoneValidity(showMessage = false) {
    if (!phone) return true;
    const parsed = parseRussianPhone(phone.value);
    const normalized = parsed.overflow ? '' : parsed.normalized;
    const valid = Boolean(normalized);
    const hasValue = Boolean(phone.value.trim());
    const message = parsed.overflow
      ? 'В номере больше 10 цифр после +7. Удалите лишнюю цифру.'
      : 'Введите российский номер из 10 цифр после +7.';

    phone.setCustomValidity(valid || !hasValue ? '' : message);
    phone.setAttribute('aria-invalid', String(!valid && hasValue));

    if (valid) setPhoneHint(`Номер для связи: ${formatRussianPhone(normalized)}`, 'success');
    else setPhoneHint(
      parsed.overflow ? message : 'Введите 10 цифр российского номера. Подойдут форматы +7 или 8.',
      showMessage && hasValue ? 'error' : ''
    );

    return valid;
  }

  if (phone) {
    phone.addEventListener('input', () => {
      const parsed = parseRussianPhone(phone.value);
      if (!parsed.overflow) {
        const formatted = formatRussianPhone(phone.value);
        if (formatted) phone.value = formatted;
      }
      phone.setCustomValidity('');
      phone.removeAttribute('aria-invalid');
      setPhoneHint(
        parsed.overflow
          ? 'В номере больше 10 цифр после +7. Удалите лишнюю цифру.'
          : 'Введите 10 цифр российского номера. Подойдут форматы +7 или 8.',
        parsed.overflow ? 'error' : ''
      );
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
      formStatus.textContent = 'Проверьте номер телефона: нужно указать ровно 10 цифр после +7.';
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
