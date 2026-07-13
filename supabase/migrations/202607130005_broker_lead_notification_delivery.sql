-- Атомарная доставка уведомлений по заявкам ипотечного брокера.
--
-- Миграция добавляет промежуточный статус sending, счётчики попыток и RPC,
-- которые не позволяют двум Edge Function одновременно отправить одно сообщение.

alter table public.broker_leads
  add column if not exists notification_attempt_count integer not null default 0,
  add column if not exists notification_attempted_at timestamptz,
  add column if not exists notification_sent_at timestamptz,
  add column if not exists notification_last_error text;

alter table public.broker_leads
  drop constraint if exists broker_leads_notification_status_check;

alter table public.broker_leads
  add constraint broker_leads_notification_status_check
  check (notification_status in ('pending', 'sending', 'sent', 'failed', 'disabled'));

create index if not exists broker_leads_notification_queue_idx
  on public.broker_leads (notification_status, notification_attempted_at)
  where notification_status in ('pending', 'sending');

create or replace function public.claim_broker_lead_notification(
  p_lead_id uuid,
  p_request_id text
)
returns table (
  claimed boolean,
  current_status text,
  attempt_count integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_status text;
  v_attempt_count integer;
begin
  update public.broker_leads as leads
  set
    notification_status = 'sending',
    notification_attempt_count = leads.notification_attempt_count + 1,
    notification_attempted_at = now(),
    notification_last_error = null
  where leads.id = p_lead_id
    and leads.request_id = p_request_id
    and (
      leads.notification_status = 'pending'
      or (
        leads.notification_status = 'sending'
        and coalesce(leads.notification_attempted_at, '-infinity'::timestamptz) < now() - interval '15 minutes'
      )
    )
  returning leads.notification_status, leads.notification_attempt_count
  into v_status, v_attempt_count;

  if found then
    return query select true, v_status, v_attempt_count;
    return;
  end if;

  select leads.notification_status, leads.notification_attempt_count
  into v_status, v_attempt_count
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  return query select false, coalesce(v_status, 'missing'), coalesce(v_attempt_count, 0);
end;
$$;

create or replace function public.complete_broker_lead_notification(
  p_lead_id uuid,
  p_request_id text,
  p_success boolean,
  p_error text default null
)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_status text;
begin
  update public.broker_leads as leads
  set
    notification_status = case when p_success then 'sent' else 'failed' end,
    notification_sent_at = case when p_success then now() else leads.notification_sent_at end,
    notification_last_error = case
      when p_success then null
      else nullif(left(trim(coalesce(p_error, 'notification_failed')), 300), '')
    end
  where leads.id = p_lead_id
    and leads.request_id = p_request_id
    and leads.notification_status = 'sending'
  returning leads.notification_status
  into v_status;

  return coalesce(v_status, 'unchanged');
end;
$$;

revoke all on function public.claim_broker_lead_notification(uuid, text)
  from public, anon, authenticated;
grant execute on function public.claim_broker_lead_notification(uuid, text)
  to service_role;

revoke all on function public.complete_broker_lead_notification(uuid, text, boolean, text)
  from public, anon, authenticated;
grant execute on function public.complete_broker_lead_notification(uuid, text, boolean, text)
  to service_role;

comment on column public.broker_leads.notification_attempt_count is
  'Количество атомарно начатых попыток серверного уведомления';
comment on column public.broker_leads.notification_attempted_at is
  'Время последнего захвата уведомления обработчиком';
comment on column public.broker_leads.notification_sent_at is
  'Время подтверждённой успешной отправки уведомления';
comment on column public.broker_leads.notification_last_error is
  'Короткий безопасный код последней ошибки уведомления без секретов и stack trace';
comment on function public.claim_broker_lead_notification(uuid, text) is
  'Атомарно захватывает pending или зависшее sending-уведомление; предотвращает двойную отправку';
comment on function public.complete_broker_lead_notification(uuid, text, boolean, text) is
  'Завершает ранее захваченную попытку статусом sent или failed';