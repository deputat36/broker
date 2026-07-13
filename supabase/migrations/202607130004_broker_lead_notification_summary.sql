-- Защищённая серверная сводка заявки для Telegram и будущих CRM-уведомлений.
--
-- Функция читает только уже сохранённую строку broker_leads и использует
-- очищенные preparation-поля из миграции 202607130003. Публичный доступ
-- запрещён; вызывать функцию может только service_role.

create or replace function public.broker_lead_notification_summary(
  p_lead_id uuid
)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_lead public.broker_leads%rowtype;
  v_preparation_text text := '';
  v_completed_text text := '';
begin
  select *
  into v_lead
  from public.broker_leads
  where id = p_lead_id;

  if not found then
    raise exception 'broker_lead_not_found';
  end if;

  if jsonb_typeof(v_lead.preparation_completed) = 'array' then
    select string_agg(left(trim(value), 180), '; ' order by ordinality)
    into v_completed_text
    from jsonb_array_elements_text(v_lead.preparation_completed)
      with ordinality as completed(value, ordinality)
    where trim(value) <> '';
  end if;

  if coalesce(v_lead.journey_type, '') <> ''
    or coalesce(v_lead.journey_stage, '') <> ''
    or coalesce(v_lead.journey_scenario_slug, '') <> ''
    or coalesce(v_completed_text, '') <> ''
    or coalesce(v_lead.remaining_questions, '') <> '' then
    v_preparation_text := concat(
      E'\n\nПОДГОТОВКА ДО ОБРАЩЕНИЯ',
      E'\nТип маршрута: ', coalesce(nullif(v_lead.journey_type, ''), 'не указан'),
      E'\nЭтап: ', coalesce(nullif(v_lead.journey_stage, ''), 'не указан'),
      E'\nСценарий: ', coalesce(nullif(v_lead.journey_scenario_slug, ''), 'не указан'),
      E'\nЧто уже проверено: ', coalesce(nullif(v_completed_text, ''), 'не отмечено'),
      E'\nЧто осталось уточнить: ', coalesce(nullif(v_lead.remaining_questions, ''), 'не указано')
    );
  end if;

  return concat(
    'Новая заявка ипотечному брокеру',
    E'\nID: ', coalesce(v_lead.request_id, v_lead.id::text),
    E'\nИмя: ', coalesce(v_lead.client_name, ''),
    E'\nТелефон: ', coalesce(v_lead.phone, ''),
    E'\nГород: ', coalesce(v_lead.city, ''),
    E'\nСвязь: ', coalesce(v_lead.preferred_contact, v_lead.contact_time, ''),
    E'\nЗадача: ', coalesce(v_lead.scenario, v_lead.mortgage_goal, ''),
    E'\nОбъект: ', coalesce(v_lead.object_type, v_lead.property_type, ''),
    E'\nСтоимость: ', coalesce(v_lead.object_price_text, ''),
    E'\nВзнос: ', coalesce(v_lead.down_payment_text, ''),
    E'\nДоход: ', coalesce(v_lead.income_type, ''),
    E'\nПриоритет: ', coalesce(v_lead.technical_priority, ''),
    E'\nИсточник: ', coalesce(v_lead.source_page, v_lead.page_url, ''),
    v_preparation_text
  );
end;
$$;

revoke all on function public.broker_lead_notification_summary(uuid)
  from public, anon, authenticated;
grant execute on function public.broker_lead_notification_summary(uuid)
  to service_role;

comment on function public.broker_lead_notification_summary(uuid) is
  'Формирует ограниченную серверную сводку заявки и подготовки для Telegram или CRM; доступ только service_role';
