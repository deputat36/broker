(() => {
  const form = document.querySelector('[data-online-application]');
  if (!form) return;

  const params = new URLSearchParams(window.location.search);
  const calculatorParams = ['calc_amount', 'calc_down', 'calc_rate', 'calc_years'];
  if (!calculatorParams.some((name) => params.has(name))) return;

  const currentScript = document.currentScript;
  if (!currentScript || !currentScript.src) return;

  const runtime = document.createElement('script');
  runtime.src = new URL('calculator-application-prefill-runtime.js', currentScript.src).href;
  runtime.async = false;
  runtime.dataset.calculatorPrefillRuntime = 'true';
  document.head.appendChild(runtime);
})();
