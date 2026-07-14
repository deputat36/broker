(() => {
  if (typeof window.fetch !== 'function') return;

  const originalFetch = window.fetch.bind(window);

  function isDeliveryReceipt(init) {
    if (!init || typeof init.body !== 'string') return false;
    try {
      const payload = JSON.parse(init.body);
      return payload
        && payload.request_kind === 'delivery_receipt'
        && payload.delivery_state === 'both';
    } catch (_error) {
      return false;
    }
  }

  window.fetch = (input, init = {}) => {
    if (!isDeliveryReceipt(init)) return originalFetch(input, init);
    return originalFetch(input, { ...init, keepalive: true });
  };
})();
