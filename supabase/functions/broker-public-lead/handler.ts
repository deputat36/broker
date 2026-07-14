// Supabase Edge Function handler: broker-public-lead
//
// Принимает schema_version=1 от формы sterlikova-ipoteka.ru,
// применяет идемпотентность и атомарный rate limit, сохраняет заявку,
// атомарно захватывает уведомление и при наличии секретов отправляет его в Telegram.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.45.4';

type JsonRecord = Record<string, unknown>;
type NotificationStatus = 'pending' | 'sending' | 'sent' | 'failed' | 'disabled';

type RateLimitResult = {
  allowed: boolean;
  attemptCount: number;
  limit: number;
  fingerprint: string;
};

type NotificationClaim = {
  claimed: boolean;
  status: string;
  attemptCount: number;
};

type ValidatedLead = {
  requestId: string;
  schemaVersion: number;
  formVersion: string;
  submittedAt: string;
  formFillMs: number;
  sourcePage: string;
  pageUrl: string;
  pageTitle: string;
  referrer: string;
  client: {
    name: string;
    phone: string;
    phoneNormalized: string;
    city: string;
    preferredContact: string;
  };
  mortgage: {
    scenario: string;
    objectType: string;
    objectPrice: string;
    downPayment: string;
    incomeType: string;
    bankHistory: string;
    comment: string;
  };
  tracking: JsonRecord;
  qualification: JsonRecord;
  spamCheck: JsonRecord;
};

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || '';
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || '';
const TELEGRAM_BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN') || '';
const TELEGRAM_CHAT_ID = Deno.env.get('TELEGRAM_CHAT_ID') || '';

function boundedEnvNumber(name: string, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(Deno.env.get(name) || fallback);
  return Number.isFinite(parsed) ? Math.min(maximum, Math.max(minimum, parsed)) : fallback;
}

const RATE_LIMIT_PER_HOUR = boundedEnvNumber('RATE_LIMIT_PER_HOUR', 8, 1, 100);
const MIN_FILL_MS = boundedEnvNumber('MIN_FILL_MS', 1500, 500, 30000);
const MAX_BODY_BYTES = boundedEnvNumber('MAX_BODY_BYTES', 65536, 4096, 262144);
const TELEGRAM_TIMEOUT_MS = boundedEnvNumber('TELEGRAM_TIMEOUT_MS', 5000, 1000, 15000);
const ALLOW_ORIGINLESS = (Deno.env.get('ALLOW_ORIGINLESS') || 'false').toLowerCase() === 'true';

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

function corsHeaders(origin: string | null): HeadersInit {
  const headers: Record<string, string> = {
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json; charset=utf-8',
    'Vary': 'Origin'
  };
  if (origin && isAllowedOrigin(origin)) headers['Access-Control-Allow-Origin'] = normalizeOrigin(origin);
  return headers;
}

function jsonResponse(body: JsonRecord, status: number, origin: string | null): Response {
  return new Response(JSON.stringify(body), { status, headers: corsHeaders(origin) });
}

function asRecord(value: unknown): JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as JsonRecord : {};
}

function cleanText(value: unknown, maxLength = 500): string {
  if (typeof value !== 'string') return '';
  return value.replace(/\s+/g, ' ').trim().slice(0, maxLength);
}

function cleanMultiline(value: unknown, maxLength = 1500): string {
  if (typeof value !== 'string') return '';
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim().slice(0, maxLength);
}

function normalizeRussianPhone(value: unknown): string {
  const raw = typeof value === 'string' ? value : '';
  let digits = raw.replace(/\D/g, '');
  if (digits.length === 10) digits = `7${digits}`;
  if (digits.length === 11 && digits.startsWith('8')) digits = `7${digits.slice(1)}`;
  return digits.length === 11 && digits.startsWith('7') ? digits : '';
}

function cleanRequestId(value: unknown): string {
  const requestId = cleanText(value, 80);
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const fallbackPattern = /^IP-\d{8}-[A-Z0-9]{6,16}$/;
  return uuidPattern.test(requestId) || fallbackPattern.test(requestId) ? requestId : '';
}

function cleanIsoDate(value: unknown): string {
  const raw = cleanText(value, 80);
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : new Date().toISOString();
}

function cleanUrl(value: unknown, maxLength = 1200): string {
  const raw = cleanText(value, maxLength);
  if (!raw) return '';
  try {
    const url = new URL(raw);
    return ['http:', 'https:'].includes(url.protocol) ? url.href.slice(0, maxLength) : '';
  } catch (_error) {
    return '';
  }
}

function parseMoney(value: string): number | null {
  const digits = value.replace(/[^\d]/g, '');
  if (!digits) return null;
  const parsed = Number(digits);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}

function getClientIp(request: Request): string {
  const cfIp = request.headers.get('cf-connecting-ip') || '';
  const realIp = request.headers.get('x-real-ip') || '';
  const forwarded = request.headers.get('x-forwarded-for') || '';
  return (cfIp || realIp || forwarded.split(',')[0] || 'unknown').trim().slice(0, 100);
}

async function sha256(value: string): Promise<string> {
  const data = new TextEncoder().encode(value);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function getCurrentTracking(tracking: JsonRecord): JsonRecord {
  return asRecord(tracking.current);
}

function qualificationStatus(qualification: JsonRecord): string {
  const status = cleanText(qualification.status, 20).toLowerCase();
  return ['hot', 'warm', 'cold'].includes(status) ? status : 'cold';
}

function qualificationScore(qualification: JsonRecord): number {
  const parsed = Number(qualification.score);
  return Number.isFinite(parsed) ? Math.min(100, Math.max(0, Math.round(parsed))) : 0;
}

function normalizeNotificationStatus(value: unknown): NotificationStatus {
  const status = cleanText(value, 20).toLowerCase();
  return ['pending', 'sending', 'sent', 'failed', 'disabled'].includes(status)
    ? status as NotificationStatus
    : 'pending';
}

function validatePayload(payload: JsonRecord): { lead?: ValidatedLead; errors: string[]; spam: boolean } {
  const errors: string[] = [];
  const client = asRecord(payload.client);
  const mortgage = asRecord(payload.mortgage);
  const tracking = asRecord(payload.tracking);
  const qualification = asRecord(payload.qualification);
  const spamCheck = asRecord(payload.spam_check);

  const requestId = cleanRequestId(payload.request_id);
  const schemaVersion = Number(payload.schema_version);
  const formVersion = cleanText(payload.form_version, 20);
  const name = cleanText(client.name, 80);
  const phone = cleanText(client.phone, 30);
  const phoneNormalized = normalizeRussianPhone(client.phone_normalized || client.phone);
  const city = cleanText(client.city, 120);
  const preferredContact = cleanText(client.preferred_contact, 40) || 'Позвонить';
  const scenario = cleanText(mortgage.scenario, 200);
  const formFillMs = Number(payload.form_fill_ms ?? spamCheck.form_fill_ms);
  const consentAccepted = payload.consent === true && cleanText(payload.personal_data_consent, 10) === 'yes';
  const likelyBot = spamCheck.likely_bot === true || spamCheck.honeypot_empty === false;

  if (!requestId) errors.push('invalid_request_id');
  if (schemaVersion !== 1) errors.push('unsupported_schema_version');
  if (!formVersion) errors.push('form_version_required');
  if (!name) errors.push('name_required');
  if (!phoneNormalized) errors.push('invalid_phone');
  if (!city) errors.push('city_required');
  if (!scenario) errors.push('scenario_required');
  if (!consentAccepted) errors.push('personal_data_consent_required');
  if (!Number.isFinite(formFillMs) || formFillMs < 0) errors.push('invalid_form_fill_ms');
  if (Number.isFinite(formFillMs) && formFillMs < MIN_FILL_MS) errors.push('form_submitted_too_fast');

  if (likelyBot) return { errors, spam: true };
  if (errors.length) return { errors, spam: false };

  return {
    errors: [],
    spam: false,
    lead: {
      requestId,
      schemaVersion,
      formVersion,
      submittedAt: cleanIsoDate(payload.submitted_at),
      formFillMs: Math.round(formFillMs),
      sourcePage: cleanText(payload.source_page, 500) || 'Прямой переход на форму',
      pageUrl: cleanUrl(payload.page_url),
      pageTitle: cleanText(payload.page_title, 300),
      referrer: cleanUrl(payload.referrer),
      client: { name, phone, phoneNormalized, city, preferredContact },
      mortgage: {
        scenario,
        objectType: cleanText(mortgage.object_type, 120) || 'Пока не выбрано',
        objectPrice: cleanText(mortgage.object_price, 80),
        downPayment: cleanText(mortgage.down_payment, 120),
        incomeType: cleanText(mortgage.income_type, 120),
        bankHistory: cleanMultiline(mortgage.bank_history, 1000),
        comment: cleanMultiline(mortgage.comment, 1600)
      },
      tracking,
      qualification: {
        ...qualification,
        status: qualificationStatus(qualification),
        score: qualificationScore(qualification),
        priority: cleanText(qualification.priority, 120),
        reasons: Array.isArray(qualification.reasons)
          ? qualification.reasons.map((reason) => cleanText(reason, 120)).filter(Boolean).slice(0, 20)
          : []
      },
      spamCheck
    }
  };
}

async function findExistingLead(requestId: string): Promise<JsonRecord | null> {
  if (!supabase || !requestId) return null;
  const { data, error } = await supabase
    .from('broker_leads')
    .select('id, request_id, status, technical_priority, qualification, notification_status, processing_restricted, retention_hold, anonymized_at')
    .eq('request_id', requestId)
    .maybeSingle();
  if (error) throw new Error(`idempotency_check_failed:${error.code || 'unknown'}`);
  return data as JsonRecord | null;
}

function isOperationallyRestricted(existing: JsonRecord): boolean {
  return existing.processing_restricted === true
    || existing.retention_hold === true
    || Boolean(existing.anonymized_at);
}

async function consumeRateLimit(request: Request, payload: JsonRecord, requestId: string): Promise<RateLimitResult> {
  if (!supabase) throw new Error('server_not_configured');
  const client = asRecord(payload.client);
  const phoneNormalized = normalizeRussianPhone(client.phone_normalized || client.phone);
  const userAgent = cleanText(request.headers.get('user-agent'), 300) || 'unknown';
  const fingerprint = await sha256(`${getClientIp(request)}|${userAgent}|${phoneNormalized.slice(-4)}`);
  const windowStart = new Date();
  windowStart.setUTCMinutes(0, 0, 0);

  const { data, error } = await supabase.rpc('consume_broker_lead_rate_limit', {
    p_fingerprint: fingerprint,
    p_window_start: windowStart.toISOString(),
    p_request_id: requestId,
    p_limit: RATE_LIMIT_PER_HOUR
  });
  if (error) throw new Error(`rate_limit_unavailable:${error.code || 'unknown'}`);

  const row = Array.isArray(data) ? asRecord(data[0]) : asRecord(data);
  const attemptCount = Number(row.attempt_count || 0);
  const limit = Number(row.rate_limit || RATE_LIMIT_PER_HOUR);
  if (!Number.isFinite(attemptCount) || attemptCount < 1) throw new Error('rate_limit_invalid_response');
  return { allowed: row.allowed === true, attemptCount, limit, fingerprint };
}

function buildLeadRow(payload: JsonRecord, lead: ValidatedLead, rateLimit: RateLimitResult, userAgent: string): JsonRecord {
  const currentTracking = getCurrentTracking(lead.tracking);
  const status = qualificationStatus(lead.qualification);
  const priority = cleanText(lead.qualification.priority, 120) || status;
  const combinedText = `${lead.mortgage.scenario} ${lead.mortgage.downPayment} ${lead.mortgage.bankHistory}`;
  const telegramEnabled = Boolean(TELEGRAM_BOT_TOKEN && TELEGRAM_CHAT_ID);

  return {
    status: 'new',
    source: 'site',
    source_page: lead.sourcePage,
    client_name: lead.client.name,
    phone: lead.client.phone,
    city: lead.client.city,
    contact_time: lead.client.preferredContact,
    mortgage_goal: lead.mortgage.scenario,
    property_type: lead.mortgage.objectType,
    property_price: parseMoney(lead.mortgage.objectPrice),
    down_payment: parseMoney(lead.mortgage.downPayment),
    monthly_income: null,
    has_matkapital: /маткап|материнск/i.test(combinedText),
    has_bad_credit_history: /кредитн.*истор/i.test(combinedText),
    has_previous_rejection: /отказ/i.test(combinedText),
    comment: lead.mortgage.comment,
    consent_accepted: true,
    utm_source: cleanText(currentTracking.utm_source, 120),
    utm_medium: cleanText(currentTracking.utm_medium, 120),
    utm_campaign: cleanText(currentTracking.utm_campaign, 200),
    utm_content: cleanText(currentTracking.utm_content, 200),
    utm_term: cleanText(currentTracking.utm_term, 200),
    user_agent: userAgent,
    page_title: lead.pageTitle,
    request_id: lead.requestId,
    schema_version: lead.schemaVersion,
    form_version: lead.formVersion,
    submitted_at: lead.submittedAt,
    form_fill_ms: lead.formFillMs,
    phone_normalized: lead.client.phoneNormalized,
    preferred_contact: lead.client.preferredContact,
    scenario: lead.mortgage.scenario,
    object_type: lead.mortgage.objectType,
    object_price_text: lead.mortgage.objectPrice,
    down_payment_text: lead.mortgage.downPayment,
    income_type: lead.mortgage.incomeType,
    bank_history: lead.mortgage.bankHistory,
    page_url: lead.pageUrl,
    referrer: lead.referrer,
    tracking: lead.tracking,
    qualification: lead.qualification,
    spam_check: {
      ...lead.spamCheck,
      rate_limit_attempt_count: rateLimit.attemptCount,
      rate_limit_per_hour: rateLimit.limit,
      rate_limit_allowed: rateLimit.allowed,
      rate_limit_fingerprint: rateLimit.fingerprint
    },
    raw_payload: payload,
    personal_data_consent: true,
    technical_priority: priority,
    delivery_channel: 'supabase',
    notification_status: telegramEnabled ? 'pending' : 'disabled'
  };
}

async function addEvent(leadId: string, requestId: string, eventType: string, title: string, comment: string, payload: JsonRecord = {}): Promise<void> {
  if (!supabase) return;
  const { error } = await supabase.from('broker_lead_events').insert({
    lead_id: leadId,
    request_id: requestId,
    event_type: eventType,
    event_title: title,
    event_comment: comment,
    payload
  });
  if (error) console.error('broker_lead_event_insert_failed', error.code || 'unknown');
}

async function claimNotification(leadId: string, requestId: string): Promise<NotificationClaim> {
  if (!supabase) throw new Error('server_not_configured');
  const { data, error } = await supabase.rpc('claim_broker_lead_notification', {
    p_lead_id: leadId,
    p_request_id: requestId
  });
  if (error) throw new Error(`notification_claim_failed:${error.code || 'unknown'}`);
  const row = Array.isArray(data) ? asRecord(data[0]) : asRecord(data);
  return {
    claimed: row.claimed === true,
    status: cleanText(row.current_status, 20) || 'pending',
    attemptCount: Number(row.attempt_count || 0)
  };
}

async function loadNotificationSummary(leadId: string): Promise<string> {
  if (!supabase) throw new Error('server_not_configured');
  const { data, error } = await supabase.rpc('broker_lead_notification_summary', { p_lead_id: leadId });
  if (error) throw new Error(`notification_summary_failed:${error.code || 'unknown'}`);
  const summary = cleanMultiline(data, 3500);
  if (!summary) throw new Error('notification_summary_empty');
  return summary;
}

async function completeNotification(leadId: string, requestId: string, success: boolean, errorCode = ''): Promise<NotificationStatus> {
  if (!supabase) return success ? 'sent' : 'failed';
  const { data, error } = await supabase.rpc('complete_broker_lead_notification', {
    p_lead_id: leadId,
    p_request_id: requestId,
    p_success: success,
    p_error: errorCode || null
  });
  if (error) {
    console.error('notification_complete_failed', error.code || 'unknown');
    return success ? 'sent' : 'failed';
  }
  return normalizeNotificationStatus(data);
}

async function notifyTelegram(text: string): Promise<void> {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) throw new Error('telegram_disabled');
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TELEGRAM_TIMEOUT_MS);
  try {
    const response = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text, disable_web_page_preview: true }),
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`telegram_http_${response.status}`);
  } finally {
    clearTimeout(timeoutId);
  }
}

function notificationErrorCode(error: unknown): string {
  if (error instanceof DOMException && error.name === 'AbortError') return 'telegram_timeout';
  if (!(error instanceof Error)) return 'notification_failed';
  if (/^telegram_http_\d{3}$/.test(error.message)) return error.message;
  if (error.message.startsWith('notification_summary_')) return 'notification_summary_failed';
  if (error.message.startsWith('notification_claim_')) return 'notification_claim_failed';
  return error.message === 'notification_summary_empty' ? 'notification_summary_empty' : 'notification_failed';
}

async function deliverNotification(leadId: string, requestId: string): Promise<NotificationStatus> {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return 'disabled';

  let claim: NotificationClaim;
  try {
    claim = await claimNotification(leadId, requestId);
  } catch (error) {
    console.error('broker_lead_notification_claim_failed', notificationErrorCode(error));
    return 'failed';
  }
  if (!claim.claimed) return normalizeNotificationStatus(claim.status);

  try {
    const summary = await loadNotificationSummary(leadId);
    await notifyTelegram(summary);
    const status = await completeNotification(leadId, requestId, true);
    await addEvent(leadId, requestId, 'notification_sent', 'Telegram-уведомление отправлено', 'Ответственный канал уведомлён', {
      attempt_count: claim.attemptCount,
      delivery_channel: 'telegram'
    });
    return status;
  } catch (error) {
    const errorCode = notificationErrorCode(error);
    console.error('broker_lead_telegram_failed', errorCode);
    const status = await completeNotification(leadId, requestId, false, errorCode);
    await addEvent(leadId, requestId, 'notification_failed', 'Ошибка Telegram-уведомления', 'Заявка сохранена, но уведомление требует проверки', {
      attempt_count: claim.attemptCount,
      error_code: errorCode
    });
    return status;
  }
}

async function duplicateResponse(existing: JsonRecord, requestId: string, origin: string | null): Promise<Response> {
  if (isOperationallyRestricted(existing)) {
    return jsonResponse({
      ok: true,
      success: true,
      duplicate: true,
      request_id: existing.request_id || requestId,
      notification_status: 'disabled'
    }, 200, origin);
  }

  const leadId = cleanText(existing.id, 80);
  const notificationStatus = leadId
    ? await deliverNotification(leadId, requestId)
    : normalizeNotificationStatus(existing.notification_status);
  return jsonResponse({
    ok: true,
    success: true,
    duplicate: true,
    lead_id: existing.id || null,
    request_id: existing.request_id || requestId,
    crm_status: existing.status || 'new',
    technical_priority: existing.technical_priority || '',
    qualification: existing.qualification || {},
    notification_status: notificationStatus
  }, 200, origin);
}

Deno.serve(async (request) => {
  const origin = request.headers.get('origin');

  if (request.method === 'OPTIONS') {
    if (!isAllowedOrigin(origin)) return jsonResponse({ ok: false, success: false, error: 'origin_not_allowed' }, 403, origin);
    return new Response(null, { status: 204, headers: corsHeaders(origin) });
  }
  if (!isAllowedOrigin(origin)) return jsonResponse({ ok: false, success: false, error: 'origin_not_allowed' }, 403, origin);
  if (request.method !== 'POST') return jsonResponse({ ok: false, success: false, error: 'method_not_allowed' }, 405, origin);
  if (!supabase) return jsonResponse({ ok: false, success: false, error: 'server_not_configured' }, 503, origin);

  const contentType = request.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    return jsonResponse({ ok: false, success: false, error: 'content_type_not_supported' }, 415, origin);
  }
  const declaredLength = Number(request.headers.get('content-length') || 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    return jsonResponse({ ok: false, success: false, error: 'payload_too_large' }, 413, origin);
  }

  let payload: JsonRecord;
  try {
    const rawBody = await request.text();
    if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
      return jsonResponse({ ok: false, success: false, error: 'payload_too_large' }, 413, origin);
    }
    const parsed = JSON.parse(rawBody);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error('invalid_payload_shape');
    payload = parsed as JsonRecord;
  } catch (_error) {
    return jsonResponse({ ok: false, success: false, error: 'invalid_json' }, 400, origin);
  }

  const requestId = cleanRequestId(payload.request_id);
  if (requestId) {
    try {
      const existing = await findExistingLead(requestId);
      if (existing) return await duplicateResponse(existing, requestId, origin);
    } catch (error) {
      console.error(error instanceof Error ? error.message : 'idempotency_check_failed');
      return jsonResponse({ ok: false, success: false, error: 'backend_migration_required' }, 503, origin);
    }
  }

  let rateLimit: RateLimitResult;
  try {
    rateLimit = await consumeRateLimit(request, payload, requestId);
  } catch (error) {
    console.error(error instanceof Error ? error.message : 'rate_limit_unavailable');
    return jsonResponse({ ok: false, success: false, error: 'backend_migration_required' }, 503, origin);
  }
  if (!rateLimit.allowed) {
    return jsonResponse({ ok: false, success: false, blocked: true, error: 'rate_limit_exceeded', retry_after_seconds: 3600, attempt_count: rateLimit.attemptCount, rate_limit: rateLimit.limit }, 429, origin);
  }

  const validation = validatePayload(payload);
  if (validation.spam) {
    return jsonResponse({ ok: false, success: false, blocked: true, error: 'request_rejected' }, 202, origin);
  }
  if (!validation.lead || validation.errors.length) {
    return jsonResponse({ ok: false, success: false, errors: validation.errors }, 422, origin);
  }

  const userAgent = cleanText(request.headers.get('user-agent'), 500);
  const row = buildLeadRow(payload, validation.lead, rateLimit, userAgent);
  const { data, error } = await supabase
    .from('broker_leads')
    .insert(row)
    .select('id, request_id, status, technical_priority, qualification, notification_status')
    .single();

  if (error) {
    if (error.code === '23505') {
      try {
        const existing = await findExistingLead(validation.lead.requestId);
        if (existing) return await duplicateResponse(existing, validation.lead.requestId, origin);
        throw new Error('duplicate_without_existing_row');
      } catch (duplicateReadError) {
        console.error(duplicateReadError instanceof Error ? duplicateReadError.message : 'duplicate_read_failed');
        return jsonResponse({ ok: false, success: false, error: 'lead_storage_failed' }, 500, origin);
      }
    }
    console.error('broker_lead_insert_failed', error.code || 'unknown');
    return jsonResponse({ ok: false, success: false, error: 'lead_storage_failed' }, 500, origin);
  }

  await addEvent(String(data.id), validation.lead.requestId, 'created', 'Заявка создана с сайта', 'Заявка принята через Supabase Edge Function v2', {
    source_page: validation.lead.sourcePage,
    scenario: validation.lead.mortgage.scenario,
    qualification_status: qualificationStatus(validation.lead.qualification),
    delivery_channel: 'supabase'
  });

  const notificationStatus = await deliverNotification(String(data.id), validation.lead.requestId);
  return jsonResponse({
    ok: true,
    success: true,
    duplicate: false,
    lead_id: data.id,
    request_id: data.request_id,
    crm_status: data.status,
    technical_priority: data.technical_priority,
    qualification: data.qualification,
    notification_status: notificationStatus
  }, 201, origin);
});