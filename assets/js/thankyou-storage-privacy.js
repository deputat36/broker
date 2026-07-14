(() => {
  const STORAGE_KEY = 'sterlikovaMortgageLastLead';
  const deliveryNote = document.querySelector('[data-application-delivery-note]');

  function cleanRequestId(value) {
    const requestId = String(value || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const fallbackPattern = /^IP-\d{8}-[A-Z0-9]{6,16}$/;
    return uuidPattern.test(requestId) || fallbackPattern.test(requestId) ? requestId : '';
  }

  function sanitizeLastLead() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;

      const stored = JSON.parse(raw);
      const requestId = cleanRequestId(stored && stored.request_id);
      const expiresAt = Date.parse(stored && stored.expires_at ? stored.expires_at : '');

      if (!requestId || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
        window.localStorage.removeItem(STORAGE_KEY);
        return;
      }

      const safeSummary = {
        request_id: requestId,
        expires_at: new Date(expiresAt).toISOString()
      };
      const serialized = JSON.stringify(safeSummary);
      if (serialized !== raw) window.localStorage.setItem(STORAGE_KEY, serialized);
    } catch (_error) {
      try { window.localStorage.removeItem(STORAGE_KEY); } catch (_storageError) { /* Браузер запретил доступ. */ }
    }
  }

  sanitizeLastLead();

  if (deliveryNote) {
    const observer = new MutationObserver(() => {
      if (!deliveryNote.classList.contains('is-success')) return;
      if (!String(deliveryNote.textContent || '').includes('Переходим на страницу подтверждения')) return;
      sanitizeLastLead();
    });
    observer.observe(deliveryNote, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  }
})();
