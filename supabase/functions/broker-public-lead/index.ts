const allowedOrigins = new Set([
  'https://sterlikova-ipoteka.ru',
  'https://www.sterlikova-ipoteka.ru',
  'https://deputat36.github.io',
  'http://localhost:4000',
  'http://127.0.0.1:4000'
]);

function getCorsHeaders(origin: string | null) {
  const allowOrigin = origin && allowedOrigins.has(origin) ? origin : 'https://sterlikova-ipoteka.ru';

  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Vary': 'Origin'
  };
}

function jsonResponse(body: Record<string, unknown>, status: number, origin: string | null) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...getCorsHeaders(origin),
      'Content-Type': 'application/json; charset=utf-8'
    }
  });
}

function cleanText(value: unknown, maxLength = 500) {
  if (typeof value !== 'string') return null;
  const cleaned = value.replace(/\s+/g, ' ').trim();
  return cleaned ? cleaned.slice(0, maxLength) : null;
}

function cleanPhone(value: unknown) {
  if (typeof value !== 'string') return null;
  const cleaned = value.replace(/[^\d+]/g, '').trim();
  const digits = cleaned.replace(/\D/g, '');
  if (digits.length < 10 || digits.length > 15) return null;
  return cleaned.slice(0, 20);
}

function cleanNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value !== 'string') return null;

  const normalized = value.replace(/\s+/g, '').replace(',', '.');
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function cleanBoolean(value: unknown) {
  if (typeof value === 'boolean') return value;
  if (value === 'true') return true;
  if (value === 'false') return false;
  return null;
}

Deno.serve(async (request) => {
  const origin = request.headers.get('Origin');

  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: getCorsHeaders(origin)
    });
  }

  if (origin && !allowedOrigins.has(origin)) {
    return jsonResponse({ ok: false, message: 'Недопустимый источник запроса' }, 403, origin);
  }

  if (request.method !== 'POST') {
    return jsonResponse({ ok: false, message: 'Метод не поддерживается' }, 405, origin);
  }

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');

  if (!supabaseUrl || !serviceRoleKey) {
    return jsonResponse({ ok: false, message: 'Сервис временно недоступен' }, 500, origin);
  }

  let payload: Record<string, unknown>;

  try {
    payload = await request.json();
  } catch (_error) {
    return jsonResponse({ ok: false, message: 'Некорректный формат заявки' }, 400, origin);
  }

  const honeypot = cleanText(payload.company || payload.website || payload.url, 100);
  if (honeypot) {
    return jsonResponse({ ok: true, message: 'Заявка принята' }, 200, origin);
  }

  const phone = cleanPhone(payload.phone);
  const consentAccepted = payload.consent_accepted === true;

  if (!phone) {
    return jsonResponse({ ok: false, message: 'Укажите корректный телефон' }, 400, origin);
  }

  if (!consentAccepted) {
    return jsonResponse({ ok: false, message: 'Нужно согласие на обработку персональных данных' }, 400, origin);
  }

  const lead = {
    status: 'new',
    source: cleanText(payload.source, 80) || 'site',
    source_page: cleanText(payload.source_page, 300),
    client_name: cleanText(payload.client_name, 120),
    phone,
    city: cleanText(payload.city, 120),
    contact_time: cleanText(payload.contact_time, 120),
    mortgage_goal: cleanText(payload.mortgage_goal, 200),
    property_type: cleanText(payload.property_type, 120),
    property_price: cleanNumber(payload.property_price),
    down_payment: cleanNumber(payload.down_payment),
    monthly_income: cleanNumber(payload.monthly_income),
    has_matkapital: cleanBoolean(payload.has_matkapital),
    has_bad_credit_history: cleanBoolean(payload.has_bad_credit_history),
    has_previous_rejection: cleanBoolean(payload.has_previous_rejection),
    comment: cleanText(payload.comment, 1000),
    consent_accepted: true,
    utm_source: cleanText(payload.utm_source, 120),
    utm_medium: cleanText(payload.utm_medium, 120),
    utm_campaign: cleanText(payload.utm_campaign, 200),
    utm_content: cleanText(payload.utm_content, 200),
    utm_term: cleanText(payload.utm_term, 200),
    user_agent: cleanText(request.headers.get('User-Agent'), 500),
    page_title: cleanText(payload.page_title, 300)
  };

  const insertResponse = await fetch(`${supabaseUrl}/rest/v1/broker_leads`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${serviceRoleKey}`,
      'apikey': serviceRoleKey,
      'Content-Type': 'application/json',
      'Prefer': 'return=minimal'
    },
    body: JSON.stringify(lead)
  });

  if (!insertResponse.ok) {
    return jsonResponse({ ok: false, message: 'Не удалось сохранить заявку' }, 500, origin);
  }

  return jsonResponse({ ok: true, message: 'Заявка принята' }, 201, origin);
});
