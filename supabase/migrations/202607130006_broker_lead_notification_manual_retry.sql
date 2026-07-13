-- Безопасный ручной повтор уведомлений и агрегированный контроль очереди.
--
-- Миграция не включает Supabase endpoint и не отправляет сообщения сама.
-- Ручной retry разрешён только для failed, причина выбирается из белого списка,
-- а состояние очереди возвращается без имени, телефона, текста заявки и URL.

alter table public.broker_leads
  add column if not exists notification_manual_retry_count integer not null default 0,
  add column if not exists notification_manual_retry_requested_at timestamptz,
  add column if not exists notification_manual_retry_reason_code text;

alter table public.broker_leads
  drop constraint if exists broker_leads_notification_retry_reason_check;

alter table public.broker_leads
  add constraint broker_leads_notification_retry_reason_check
  check (
    notification_manual_retry_reason_code is null
    or notification_manual_retry_reason_code in (
      'telegram_config_fixed',
      'telegram_temporary_error',
      'notification_summary_fixed',
      'manual_recovery'
    )
  );

create index if not exists broker_leads_notification_failed_idx
  on public.broker_leads (notification_attempted_at, notification_manual_retry_requested_at)
  where notification_status = 'failed';

create or replace function public.request_broker_lead_notification_retry(
  p_lead_id uuid,
  p_request_id text,
  p_reason_code text
)
returns table (
  retry_requested boolean,
  current_status text,
  retry_count integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_reason_code text := lower(trim(coalesce(p_reason_code, '')));
  v_retry_count integer;
  v_attempt_count integer;
  v_status text;
begin
  if v_reason_code not in (
    'telegram_config_fixed',
    'telegram_temporary_error',
    'notification_summary_fixed',
    'manual_recovery'
  ) then
    raise exception 'invalid_notification_retry_reason';
  end if;

  update public.broker_leads as leads
  set
    notification_status = 'pending',
    notification_manual_retry_count = leads.notification_manual_retry_count + 1,
    notification_manual_retry_requested_at = now(),
    notification_manual_retry_reason_code = v_reason_code
  where leads.id = p_lead_id
    and leads.request_id = p_request_id
    and leads.notification_status = 'failed'
  returning
    leads.notification_manual_retry_count,
    leads.notification_attempt_count,
    leads.notification_status
  into v_retry_count, v_attempt_count, v_status;

  if found then
    insert into public.broker_lead_events (
      lead_id,
      request_id,
      event_type,
      event_title,
      event_comment,
      payload
    ) values (
      p_lead_id,
      p_request_id,
      'notification_retry_requested',
      'Запрошен ручной повтор уведомления',
      'Уведомление переведено из failed в pending',
      jsonb_build_object(
        'reason_code', v_reason_code,
        'manual_retry_count', v_retry_count,
        'previous_attempt_count', coalesce(v_attempt_count, 0)
      )
    );

    return query select true, v_status, v_retry_count;
    return;
  end if;

  select
    leads.notification_status,
    leads.notification_manual_retry_count
  into v_status, v_retry_count
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  return query select false, coalesce(v_status, 'missing'), coalesce(v_retry_count, 0);
end;
$$;

create or replace function public.broker_lead_notification_queue_health()
returns table (
  notification_status text,
  lead_count bigint,
  oldest_lead_at timestamptz,
  oldest_attempted_at timestamptz,
  stale_count bigint,
  max_attempt_count integer,
  total_manual_retries bigint
)
language sql
security definer
set search_path = public
stable
as $$
  select
    leads.notification_status,
    count(*)::bigint as lead_count,
    min(coalesce(leads.submitted_at, leads.created_at)) as oldest_lead_at,
    min(leads.notification_attempted_at) as oldest_attempted_at,
    count(*) filter (
      where leads.notification_status = 'sending'
        and coalesce(leads.notification_attempted_at, '-infinity'::timestamptz) < now() - interval '15 minutes'
    )::bigint as stale_count,
    max(leads.notification_attempt_count)::integer as max_attempt_count,
    sum(leads.notification_manual_retry_count)::bigint as total_manual_retries
  from public.broker_leads as leads
  group by leads.notification_status
  order by case leads.notification_status
    when 'failed' then 1
    when 'sending' then 2
    when 'pending' then 3
    when 'sent' then 4
    when 'disabled' then 5
    else 6
  end;
$$;

revoke all on function public.request_broker_lead_notification_retry(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.request_broker_lead_notification_retry(uuid, text, text)
  to service_role;

revoke all on function public.broker_lead_notification_queue_health()
  from public, anon, authenticated;
grant execute on function public.broker_lead_notification_queue_health()
  to service_role;

comment on column public.broker_leads.notification_manual_retry_count is
  'Количество подтверждённых ручных возвратов failed-уведомления в pending';
comment on column public.broker_leads.notification_manual_retry_requested_at is
  'Время последнего административного запроса на повтор уведомления';
comment on column public.broker_leads.notification_manual_retry_reason_code is
  'Технический код причины ручного retry из фиксированного белого списка';
comment on function public.request_broker_lead_notification_retry(uuid, text, text) is
  'Переводит только failed-уведомление в pending и пишет обезличенное операционное событие';
comment on function public.broker_lead_notification_queue_health() is
  'Возвращает агрегированное состояние очереди уведомлений без персональных данных';