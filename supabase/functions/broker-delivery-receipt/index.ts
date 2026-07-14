import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.45.4';

type JsonRecord = Record<string, unknown>;

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || '';
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || '';
const ALLOW_ORIGINLESS = (Deno.env.get('ALLOW_ORIGINLESS') || 'false').toLowerCase() === 'true';
const MAX_BODY_BYTES = 4096;

const supabase = SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY
  ? createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } })
  : null;

function normalizeOrigin(value: string): string {
  try {
    return new URL(value).origin;
  } catch (_error) {
    return '';
  }
}

const ALLOWED_ORIGINS = new Set(
  (Deno.env.get('ALLOWED_ORIGINS') || 'https://sterlikova-ipoteka.ru,https://www.sterlikova-ipoteka.ru,https://deputat36.github.io')
    .split(',')
    .map((origin) => normalizeOrigin(origin.trim()))
    .filter(Boolean)
);

function isAllowedOrigin(origin: string | null): boolean {
  if (!origin) return ALLOW_ORIGINLESS;
  return ALLOWED_ORIGINS.has(normalizeOrigin(origin));
}

function responseHeaders(origin: string | null): HeadersInit {
  const headers: Record<string, string> = {
    'Access-Control-Allow-Headers': 'content-type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Cache-Control': 'no-store',
    'Vary': 'Origin'
  };
  if (origin && isAllowedOrigin(origin)) headers['Access-Control-Allow-Origin'] = normalizeOrigin(origin);
  return headers;
}

function jsonResponse(body: JsonRecord, status: number, origin: string | null): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...responseHeaders(origin), 'Content-Type': 'application/json; charset=utf-8' }
  });
}

function cleanText(value: unknown, maxLength = 100): string {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, maxLength) : '';
}

function cleanRequestId(value: unknown): string {
  const requestId = cleanText(value, 80);
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const fallbackPattern = /^IP-\d{8}-[A-Z0-9]{6,16}$/;
  return uuidPattern.test(requestId) || fallbackPattern.test(requestId) ? requestId : '';
}

function errorResponse(errorCode: string, status: number, origin: string | null, requestId = ''): Response {
  return jsonResponse({
    ok: false,
    success: false,
    error_code: errorCode,
    request_id: cleanRequestId(requestId) || crypto.randomUUID()
  }, status, origin);
}

Deno.serve(async (request) => {
  const origin = request.headers.get('origin');
  const correlationId = crypto.randomUUID();

  if (request.method === 'OPTIONS') {
    if (!isAllowedOrigin(origin)) return errorResponse('origin_not_allowed', 403, origin, correlationId);
    return new Response(null, { status: 204, headers: responseHeaders(origin) });
  }
  if (!isAllowedOrigin(origin)) return errorResponse('origin_not_allowed', 403, origin, correlationId);
  if (request.method !== 'POST') return errorResponse('method_not_allowed', 405, origin, correlationId);
  if (!supabase) return errorResponse('backend_unavailable', 503, origin, correlationId);

  const contentType = request.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    return errorResponse('content_type_not_supported', 415, origin, correlationId);
  }

  const declaredLength = Number(request.headers.get('content-length') || 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    return errorResponse('payload_too_large', 413, origin, correlationId);
  }

  let payload: JsonRecord;
  try {
    const rawBody = await request.text();
    if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
      return errorResponse('payload_too_large', 413, origin, correlationId);
    }
    const parsed = JSON.parse(rawBody);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error('invalid_payload');
    payload = parsed as JsonRecord;
  } catch (_error) {
    return errorResponse('invalid_json', 400, origin, correlationId);
  }

  const requestId = cleanRequestId(payload.request_id);
  const requestKind = cleanText(payload.request_kind, 40).toLowerCase();
  const deliveryState = cleanText(payload.delivery_state, 40).toLowerCase();

  if (!requestId || requestKind !== 'delivery_receipt' || deliveryState !== 'both') {
    return errorResponse('validation_failed', 422, origin, requestId || correlationId);
  }

  const { error } = await supabase.rpc('mark_broker_lead_delivery_both', {
    p_request_id: requestId
  });

  if (error) {
    console.error('broker_delivery_receipt_failed', error.code || 'unknown');
    return errorResponse('backend_migration_required', 503, origin, requestId);
  }

  // Одинаковый ответ для существующей, restricted и отсутствующей заявки.
  return new Response(null, { status: 204, headers: responseHeaders(origin) });
});
