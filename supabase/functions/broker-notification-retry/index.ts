// Private Edge Function: broker-notification-retry
//
// Выполняет ручной повтор только для failed-уведомления. Функция не подключается
// к публичному сайту, не разрешает CORS и требует отдельный NOTIFICATION_ADMIN_TOKEN.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.45.4';

type JsonRecord = Record<string, unknown>;

type RetryRequest = {
  leadId: string;
  requestId: string;
  reasonCode: string;
};

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || '';
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || '';
const NOTIFICATION_ADMIN_TOKEN = Deno.env.get('NOTIFICATION_ADMIN_TOKEN') || '';
const TELEGRAM_BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN') || '';
const TELEGRAM_CHAT_ID = Deno.env.get('TELEGRAM_CHAT_ID') || '';
const MAX_BODY_BYTES = 8192;

function boundedEnvNumber(name: string, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(Deno.env.get(name) || fallback);
  return Number.isFinite(parsed) ? Math.min(maximum, Math.max(minimum, parsed)) : fallback;
}

const TELEGRAM_TIMEOUT_MS = boundedEnvNumber('TELEGRAM_TIMEOUT_MS', 5000, 1000, 15000);

const supabase = SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY
  ? createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } })
  : null;

function response(body: JsonRecord, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff'
    }
  });
}

function asRecord(value: unknown): JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as JsonRecord : {};
}

function cleanText(value: unknown, maxLength = 500): string {
  if (typeof value !== 'string') return '';
  return value.replace(/\s+/g, ' ').trim().slice(0, maxLength);
}

function cleanMultiline(value: unknown, maxLength = 3500): string {
  if (typeof value !== 'string') return '';
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim().slice(0, maxLength);
}

function validUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

function validRequestId(value: string): boolean {
  return validUuid(value) || /^IP-\d{8}-[A-Z0-9]{6,16}$/.test(value);
}

function validReasonCode(value: string): boolean {
  return [
    'telegram_config_fixed',
    'telegram_temporary_error',
    'notification_summary_fixed',
    'manual_recovery'
  ].includes(value);
}

async function sha256(value: string): Promise<Uint8Array> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return new Uint8Array(digest);
}

async function secureTokenEqual(actual: string, expected: string): Promise<boolean> {
  if (!actual || !expected) return false;
  const [actualHash, expectedHash] = await Promise.all([sha256(actual), sha256(expected)]);
  let difference = actualHash.length ^ expectedHash.length;
  const length = Math.max(actualHash.length, expectedHash.length);
  for (let index = 0; index < length; index += 1) {
    difference |= (actualHash[index] || 0) ^ (expectedHash[index] || 0);
  }
  return difference === 0;
}

function bearerToken(request: Request): string {
  const authorization = request.headers.get('authorization') || '';
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : '';
}

function parseRetryRequest(payload: JsonRecord): RetryRequest | null {
  const leadId = cleanText(payload.lead_id, 80);
  const requestId = cleanText(payload.request_id, 80);
  const reasonCode = cleanText(payload.reason_code, 80).toLowerCase();
  if (!validUuid(leadId) || !validRequestId(requestId) || !validReasonCode(reasonCode)) return null;
  return { leadId, requestId, reasonCode };
}

async function requestRetry(input: RetryRequest): Promise<JsonRecord> {
  if (!supabase) throw new Error('server_not_configured');
  const { data, error } = await supabase.rpc('request_broker_lead_notification_retry', {
    p_lead_id: input.leadId,
    p_request_id: input.requestId,
    p_reason_code: input.reasonCode
  });
  if (error) throw new Error(`retry_request_failed:${error.code || 'unknown'}`);
  return Array.isArray(data) ? asRecord(data[0]) : asRecord(data);
}

async function claimNotification(input: RetryRequest): Promise<JsonRecord> {
  if (!supabase) throw new Error('server_not_configured');
  const { data, error } = await supabase.rpc('claim_broker_lead_notification', {
    p_lead_id: input.leadId,
    p_request_id: input.requestId
  });
  if (error) throw new Error(`notification_claim_failed:${error.code || 'unknown'}`);
  return Array.isArray(data) ? asRecord(data[0]) : asRecord(data);
}

async function loadSummary(leadId: string): Promise<string> {
  if (!supabase) throw new Error('server_not_configured');
  const { data, error } = await supabase.rpc('broker_lead_notification_summary', { p_lead_id: leadId });
  if (error) throw new Error(`notification_summary_failed:${error.code || 'unknown'}`);
  const summary = cleanMultiline(data, 3500);
  if (!summary) throw new Error('notification_summary_empty');
  return summary;
}

async function sendTelegram(text: string): Promise<void> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TELEGRAM_TIMEOUT_MS);
  try {
    const telegramResponse = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: TELEGRAM_CHAT_ID,
        text,
        disable_web_page_preview: true
      }),
      signal: controller.signal
    });
    if (!telegramResponse.ok) throw new Error(`telegram_http_${telegramResponse.status}`);
  } finally {
    clearTimeout(timeoutId);
  }
}

function safeErrorCode(error: unknown): string {
  if (error instanceof DOMException && error.name === 'AbortError') return 'telegram_timeout';
  if (!(error instanceof Error)) return 'notification_retry_failed';
  if (/^telegram_http_\d{3}$/.test(error.message)) return error.message;
  if (error.message.startsWith('notification_summary_')) return 'notification_summary_failed';
  if (error.message.startsWith('notification_claim_')) return 'notification_claim_failed';
  if (error.message.startsWith('retry_request_')) return 'retry_request_failed';
  return error.message === 'notification_summary_empty' ? 'notification_summary_empty' : 'notification_retry_failed';
}

async function completeNotification(input: RetryRequest, success: boolean, errorCode = ''): Promise<string> {
  if (!supabase) return success ? 'sent' : 'failed';
  const { data, error } = await supabase.rpc('complete_broker_lead_notification', {
    p_lead_id: input.leadId,
    p_request_id: input.requestId,
    p_success: success,
    p_error: errorCode || null
  });
  if (error) throw new Error(`notification_complete_failed:${error.code || 'unknown'}`);
  return cleanText(data, 20) || (success ? 'sent' : 'failed');
}

async function addRetryEvent(input: RetryRequest, eventType: string, title: string, comment: string, payload: JsonRecord): Promise<void> {
  if (!supabase) return;
  const { error } = await supabase.from('broker_lead_events').insert({
    lead_id: input.leadId,
    request_id: input.requestId,
    event_type: eventType,
    event_title: title,
    event_comment: comment,
    payload
  });
  if (error) console.error('notification_retry_event_failed', error.code || 'unknown');
}

Deno.serve(async (request) => {
  if (request.method !== 'POST') return response({ ok: false, success: false, error: 'method_not_allowed' }, 405);
  if (!supabase || !NOTIFICATION_ADMIN_TOKEN || !TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
    return response({ ok: false, success: false, error: 'server_not_configured' }, 503);
  }

  const authorized = await secureTokenEqual(bearerToken(request), NOTIFICATION_ADMIN_TOKEN);
  if (!authorized) return response({ ok: false, success: false, error: 'unauthorized' }, 401);

  const contentType = request.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    return response({ ok: false, success: false, error: 'content_type_not_supported' }, 415);
  }

  const declaredLength = Number(request.headers.get('content-length') || 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    return response({ ok: false, success: false, error: 'payload_too_large' }, 413);
  }

  let payload: JsonRecord;
  try {
    const rawBody = await request.text();
    if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
      return response({ ok: false, success: false, error: 'payload_too_large' }, 413);
    }
    payload = asRecord(JSON.parse(rawBody));
  } catch (_error) {
    return response({ ok: false, success: false, error: 'invalid_json' }, 400);
  }

  const input = parseRetryRequest(payload);
  if (!input) return response({ ok: false, success: false, error: 'invalid_retry_request' }, 422);

  let retryResult: JsonRecord;
  try {
    retryResult = await requestRetry(input);
  } catch (error) {
    console.error('notification_retry_request_failed', safeErrorCode(error));
    return response({ ok: false, success: false, error: 'retry_unavailable' }, 503);
  }

  const retryRequested = retryResult.retry_requested === true;
  const currentStatus = cleanText(retryResult.current_status, 20) || 'unknown';
  const retryCount = Number(retryResult.retry_count || 0);
  const storedReasonCode = cleanText(retryResult.reason_code, 80).toLowerCase();
  const recoveryStatus = ['pending', 'sending'].includes(currentStatus);
  const recoveryAllowed = !retryRequested
    && retryCount > 0
    && recoveryStatus
    && validReasonCode(storedReasonCode)
    && storedReasonCode === input.reasonCode;

  if (!retryRequested && recoveryStatus && retryCount > 0 && storedReasonCode !== input.reasonCode) {
    return response({
      ok: false,
      success: false,
      error: 'retry_reason_mismatch',
      notification_status: currentStatus,
      retry_count: retryCount
    }, 409);
  }

  if (!retryRequested && !recoveryAllowed) {
    return response({
      ok: false,
      success: false,
      error: 'retry_not_allowed',
      notification_status: currentStatus,
      retry_count: retryCount
    }, 409);
  }

  const effectiveReasonCode = storedReasonCode || input.reasonCode;
  let claim: JsonRecord;
  try {
    claim = await claimNotification(input);
  } catch (error) {
    const errorCode = safeErrorCode(error);
    console.error('notification_retry_claim_failed', errorCode);
    return response({ ok: false, success: false, error: errorCode }, 503);
  }

  if (claim.claimed !== true) {
    return response({
      ok: false,
      success: false,
      error: 'notification_not_claimed',
      notification_status: cleanText(claim.current_status, 20) || 'unknown',
      retry_count: retryCount,
      resumed: recoveryAllowed
    }, 409);
  }

  const attemptCount = Number(claim.attempt_count || 0);
  try {
    const summary = await loadSummary(input.leadId);
    await sendTelegram(summary);
    const notificationStatus = await completeNotification(input, true);
    await addRetryEvent(
      input,
      'notification_retry_sent',
      'Ручной повтор Telegram-уведомления выполнен',
      'Уведомление отправлено после подтверждённого административного retry',
      { reason_code: effectiveReasonCode, retry_count: retryCount, attempt_count: attemptCount, resumed: recoveryAllowed }
    );
    return response({
      ok: true,
      success: true,
      notification_status: notificationStatus,
      retry_count: retryCount,
      attempt_count: attemptCount,
      resumed: recoveryAllowed
    }, 200);
  } catch (error) {
    const errorCode = safeErrorCode(error);
    console.error('notification_manual_retry_failed', errorCode);
    let notificationStatus = 'failed';
    try {
      notificationStatus = await completeNotification(input, false, errorCode);
    } catch (completeError) {
      console.error('notification_retry_complete_failed', safeErrorCode(completeError));
    }
    await addRetryEvent(
      input,
      'notification_retry_failed',
      'Ручной повтор Telegram-уведомления завершился ошибкой',
      'Заявка сохранена, повтор уведомления требует проверки',
      {
        reason_code: effectiveReasonCode,
        retry_count: retryCount,
        attempt_count: attemptCount,
        error_code: errorCode,
        resumed: recoveryAllowed
      }
    );
    return response({
      ok: false,
      success: false,
      error: errorCode,
      notification_status: notificationStatus,
      retry_count: retryCount,
      attempt_count: attemptCount,
      resumed: recoveryAllowed
    }, 502);
  }
});