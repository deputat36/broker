// Private Edge Function: broker-notification-health
//
// Возвращает только агрегированное состояние очереди уведомлений. Функция не
// подключается к публичному сайту, не разрешает CORS и требует отдельный
// NOTIFICATION_MONITOR_TOKEN.

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.45.4';

type JsonRecord = Record<string, unknown>;

type QueueRow = {
  notification_status: string;
  lead_count: number;
  oldest_lead_at: string | null;
  oldest_attempted_at: string | null;
  stale_count: number;
  max_attempt_count: number;
  total_manual_retries: number;
};

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || '';
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || '';
const NOTIFICATION_MONITOR_TOKEN = Deno.env.get('NOTIFICATION_MONITOR_TOKEN') || '';

function boundedEnvNumber(name: string, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(Deno.env.get(name) || fallback);
  return Number.isFinite(parsed) ? Math.min(maximum, Math.max(minimum, Math.round(parsed))) : fallback;
}

const FAILED_WARNING_THRESHOLD = boundedEnvNumber('NOTIFICATION_FAILED_WARNING_THRESHOLD', 1, 1, 1000);
const FAILED_CRITICAL_THRESHOLD = Math.max(
  FAILED_WARNING_THRESHOLD,
  boundedEnvNumber('NOTIFICATION_FAILED_CRITICAL_THRESHOLD', 5, 1, 1000)
);
const PENDING_WARNING_THRESHOLD = boundedEnvNumber('NOTIFICATION_PENDING_WARNING_THRESHOLD', 10, 1, 10000);
const MAX_ATTEMPT_WARNING_THRESHOLD = boundedEnvNumber('NOTIFICATION_ATTEMPT_WARNING_THRESHOLD', 3, 1, 100);

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

function cleanText(value: unknown, maxLength = 100): string {
  if (typeof value !== 'string') return '';
  return value.replace(/\s+/g, ' ').trim().slice(0, maxLength);
}

function safeInteger(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.round(parsed) : 0;
}

function safeTimestamp(value: unknown): string | null {
  const raw = cleanText(value, 80);
  if (!raw) return null;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : null;
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

function normalizeQueueRows(value: unknown): QueueRow[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const row = typeof item === 'object' && item !== null && !Array.isArray(item)
      ? item as JsonRecord
      : {};
    return {
      notification_status: cleanText(row.notification_status, 20) || 'unknown',
      lead_count: safeInteger(row.lead_count),
      oldest_lead_at: safeTimestamp(row.oldest_lead_at),
      oldest_attempted_at: safeTimestamp(row.oldest_attempted_at),
      stale_count: safeInteger(row.stale_count),
      max_attempt_count: safeInteger(row.max_attempt_count),
      total_manual_retries: safeInteger(row.total_manual_retries)
    };
  });
}

function rowByStatus(rows: QueueRow[], status: string): QueueRow | undefined {
  return rows.find((row) => row.notification_status === status);
}

function evaluateHealth(rows: QueueRow[]): { status: string; alerts: string[] } {
  const alerts: string[] = [];
  const failed = rowByStatus(rows, 'failed');
  const pending = rowByStatus(rows, 'pending');
  const sending = rowByStatus(rows, 'sending');
  const failedCount = failed?.lead_count || 0;
  const pendingCount = pending?.lead_count || 0;
  const staleCount = sending?.stale_count || 0;
  const maxAttemptCount = Math.max(0, ...rows.map((row) => row.max_attempt_count));

  if (staleCount > 0) alerts.push('stale_sending');
  if (failedCount >= FAILED_CRITICAL_THRESHOLD) alerts.push('failed_critical');
  else if (failedCount >= FAILED_WARNING_THRESHOLD) alerts.push('failed_present');
  if (pendingCount >= PENDING_WARNING_THRESHOLD) alerts.push('pending_backlog');
  if (maxAttemptCount >= MAX_ATTEMPT_WARNING_THRESHOLD) alerts.push('attempts_elevated');

  const critical = alerts.includes('stale_sending') || alerts.includes('failed_critical');
  return { status: critical ? 'critical' : alerts.length ? 'warning' : 'ok', alerts };
}

Deno.serve(async (request) => {
  if (request.method !== 'GET') return response({ ok: false, error: 'method_not_allowed' }, 405);
  if (!supabase || !NOTIFICATION_MONITOR_TOKEN) {
    return response({ ok: false, error: 'server_not_configured' }, 503);
  }

  const authorized = await secureTokenEqual(bearerToken(request), NOTIFICATION_MONITOR_TOKEN);
  if (!authorized) return response({ ok: false, error: 'unauthorized' }, 401);

  const { data, error } = await supabase.rpc('broker_lead_notification_queue_health');
  if (error) {
    console.error('notification_health_rpc_failed', error.code || 'unknown');
    return response({ ok: false, error: 'queue_health_unavailable' }, 503);
  }

  const queue = normalizeQueueRows(data);
  const health = evaluateHealth(queue);
  return response({
    ok: true,
    status: health.status,
    checked_at: new Date().toISOString(),
    alerts: health.alerts,
    queue,
    thresholds: {
      failed_warning: FAILED_WARNING_THRESHOLD,
      failed_critical: FAILED_CRITICAL_THRESHOLD,
      pending_warning: PENDING_WARNING_THRESHOLD,
      attempts_warning: MAX_ATTEMPT_WARNING_THRESHOLD,
      stale_sending_minutes: 15
    }
  }, health.status === 'critical' ? 503 : 200);
});
