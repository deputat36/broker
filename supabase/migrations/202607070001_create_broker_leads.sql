-- Таблица заявок для сайта ипотечного брокера.
-- Миграция подготовлена для отдельного осознанного применения в Supabase.
-- Не затрагивает существующие таблицы leader, nav, parket и другие рабочие модули.

create table if not exists public.broker_leads (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  status text not null default 'new',
  source text not null default 'site',
  source_page text,

  client_name text,
  phone text not null,
  city text,
  contact_time text,

  mortgage_goal text,
  property_type text,
  property_price numeric(14,2),
  down_payment numeric(14,2),
  monthly_income numeric(14,2),
  has_matkapital boolean,
  has_bad_credit_history boolean,
  has_previous_rejection boolean,

  comment text,
  consent_accepted boolean not null default false,

  utm_source text,
  utm_medium text,
  utm_campaign text,
  utm_content text,
  utm_term text,

  user_agent text,
  page_title text
);

comment on table public.broker_leads is 'Заявки с сайта ипотечного брокера Татьяны Стерликовой';
comment on column public.broker_leads.consent_accepted is 'Пользователь подтвердил согласие на обработку персональных данных';

create index if not exists broker_leads_created_at_idx on public.broker_leads (created_at desc);
create index if not exists broker_leads_status_idx on public.broker_leads (status);
create index if not exists broker_leads_phone_idx on public.broker_leads (phone);

alter table public.broker_leads enable row level security;

create policy "broker_leads_service_role_all"
  on public.broker_leads
  for all
  to service_role
  using (true)
  with check (true);

-- Публичную вставку через anon лучше включать только после антиспама и проверки формы.
-- Если заявка будет отправляться через Edge Function с service_role, политика для anon не нужна.
--
-- create policy "broker_leads_anon_insert"
--   on public.broker_leads
--   for insert
--   to anon
--   with check (
--     phone is not null
--     and length(trim(phone)) >= 10
--     and consent_accepted = true
--   );

create or replace function public.set_broker_leads_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists broker_leads_set_updated_at on public.broker_leads;
create trigger broker_leads_set_updated_at
before update on public.broker_leads
for each row
execute function public.set_broker_leads_updated_at();
