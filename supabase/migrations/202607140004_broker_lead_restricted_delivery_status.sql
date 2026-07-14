-- Браузерно-совместимый статус доставки для заявок с ограниченной обработкой.
--
-- Operational guard использует внутренний blocker `restricted`, но публичная Edge Function
-- уже поддерживает безопасный статус `disabled`. Эта миграция не включает endpoint и не
-- отправляет сообщения: она только не позволяет restricted/hold/anonymized заявке быть
-- ошибочно нормализованной браузером в `pending` при повторном request_id.

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
set search_path = ''
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
    and leads.processing_restricted = false
    and leads.retention_hold = false
    and leads.anonymized_at is null
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

  select
    case
      when leads.processing_restricted
        or leads.retention_hold
        or leads.anonymized_at is not null
        then 'disabled'::text
      else leads.notification_status
    end,
    leads.notification_attempt_count
  into v_status, v_attempt_count
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  return query select
    false,
    coalesce(v_status, 'missing'),
    coalesce(v_attempt_count, 0);
end;
$$;

revoke all on function public.claim_broker_lead_notification(uuid, text)
  from public, anon, authenticated;
grant execute on function public.claim_broker_lead_notification(uuid, text)
  to service_role;

comment on function public.claim_broker_lead_notification(uuid, text) is
  'Захватывает только разрешённое уведомление; для restricted/hold/anonymized заявки возвращает browser-safe disabled без новой попытки';
