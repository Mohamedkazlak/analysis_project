-- API-key login bound to user_accounts, chat audit columns, and lock-down
-- of api_keys / chat_query_log. Role and scope stay on user_accounts.
-- Unbound keys (including test-suite and permission-test keys) cannot log in.

alter table user_accounts
  add column if not exists is_active boolean not null default true;

create or replace function current_app_account()
returns user_accounts
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
declare
  rec user_accounts;
  uid text;
begin
  uid := nullif(current_setting('app.current_user_id', true), '');
  if uid is null then
    return null;
  end if;
  select * into rec from user_accounts where id = uid;
  if not found then
    return null;
  end if;
  rec.password_hash := null;
  if rec.is_active is not true then
    return null;
  end if;
  return rec;
end;
$$;

create table if not exists public.api_keys (
  id text primary key default gen_random_uuid()::text,
  key_prefix text not null,
  key_hash text not null,
  label text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  last_used_at timestamptz,
  revoked_at timestamptz,
  expires_at timestamptz,
  user_id text,
  role app_role,
  scope_id text,
  person_id text,
  student_id text
);

alter table public.api_keys add column if not exists user_id text;
alter table public.api_keys add column if not exists key_prefix text;
alter table public.api_keys add column if not exists key_hash text;
alter table public.api_keys add column if not exists is_active boolean not null default true;
alter table public.api_keys add column if not exists expires_at timestamptz;
alter table public.api_keys add column if not exists revoked_at timestamptz;
alter table public.api_keys add column if not exists last_used_at timestamptz;
alter table public.api_keys add column if not exists label text;
alter table public.api_keys add column if not exists role app_role;
alter table public.api_keys add column if not exists scope_id text;
alter table public.api_keys add column if not exists person_id text;
alter table public.api_keys add column if not exists student_id text;

create unique index if not exists api_keys_key_hash_key on public.api_keys (key_hash);
create index if not exists api_keys_user_id_idx on public.api_keys (user_id);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'api_keys_user_id_fkey') then
    alter table public.api_keys
      add constraint api_keys_user_id_fkey
      foreign key (user_id) references public.user_accounts (id) on delete cascade;
  end if;
  if not exists (select 1 from pg_constraint where conname = 'api_keys_scope_id_fkey') then
    alter table public.api_keys
      add constraint api_keys_scope_id_fkey
      foreign key (scope_id) references public.org_units (id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'api_keys_person_id_fkey') then
    alter table public.api_keys
      add constraint api_keys_person_id_fkey
      foreign key (person_id) references public.people (id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'api_keys_student_id_fkey') then
    alter table public.api_keys
      add constraint api_keys_student_id_fkey
      foreign key (student_id) references public.students (id);
  end if;
end $$;

update public.api_keys
set is_active = false,
    revoked_at = coalesce(revoked_at, now())
where user_id is null
  and (is_active or revoked_at is null);

create table if not exists public.chat_query_log (
  id bigint generated always as identity primary key,
  user_id text,
  api_key_id text,
  role app_role not null,
  question text not null,
  generated_sql text,
  row_count integer,
  error_message text,
  latency_ms integer,
  model text,
  success boolean,
  created_at timestamptz not null default now()
);

alter table public.chat_query_log add column if not exists user_id text;
alter table public.chat_query_log add column if not exists latency_ms integer;
alter table public.chat_query_log add column if not exists model text;
alter table public.chat_query_log add column if not exists success boolean;
alter table public.chat_query_log add column if not exists error_message text;

create index if not exists chat_query_log_user_id_idx on public.chat_query_log (user_id);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'chat_query_log_user_id_fkey') then
    alter table public.chat_query_log
      add constraint chat_query_log_user_id_fkey
      foreign key (user_id) references public.user_accounts (id) on delete set null;
  end if;
end $$;

create or replace function authenticate_api_key(p_key_hash text)
returns table (user_id text)
language plpgsql
security definer
set search_path = public
set row_security = off
as $$
declare
  key_row api_keys;
  acct user_accounts;
begin
  if p_key_hash is null or length(p_key_hash) <> 64 then
    return;
  end if;
  select * into key_row
  from api_keys
  where key_hash = p_key_hash;
  if not found
     or key_row.is_active is not true
     or key_row.revoked_at is not null
     or key_row.user_id is null
     or (key_row.expires_at is not null and key_row.expires_at <= now()) then
    return;
  end if;
  select * into acct from user_accounts where id = key_row.user_id;
  if not found or acct.is_active is not true then
    return;
  end if;
  update api_keys set last_used_at = now() where id = key_row.id;
  return query select acct.id;
end;
$$;

create or replace function log_chat_query(
  p_user_id text,
  p_role text,
  p_question text,
  p_generated_sql text,
  p_row_count integer,
  p_error_message text,
  p_latency_ms integer,
  p_model text,
  p_success boolean
) returns void
language plpgsql
security definer
set search_path = public
set row_security = off
as $$
declare
  session_uid text;
begin
  session_uid := nullif(current_setting('app.current_user_id', true), '');
  if session_uid is null or session_uid is distinct from p_user_id then
    raise exception 'chat log rejected';
  end if;
  if not exists (
    select 1 from user_accounts where id = p_user_id and is_active
  ) then
    raise exception 'chat log rejected';
  end if;
  insert into chat_query_log (
    user_id, role, question, generated_sql, row_count, error_message,
    latency_ms, model, success
  ) values (
    p_user_id,
    p_role::app_role,
    left(coalesce(p_question, ''), 2000),
    left(p_generated_sql, 4000),
    p_row_count,
    left(p_error_message, 500),
    p_latency_ms,
    left(p_model, 100),
    p_success
  );
end;
$$;

comment on function authenticate_api_key(text) is
  'Login by key hash. Unbound, revoked, expired, and inactive keys return no row.';

revoke all on function authenticate_api_key(text) from public;
revoke all on function log_chat_query(text, text, text, text, integer, text, integer, text, boolean) from public;

do $$
begin
  if exists (
    select 1 from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'get_user_for_login'
  ) then
    revoke all on function public.get_user_for_login(text) from public;
  end if;
end $$;

do $$
declare
  api_role text;
begin
  if exists (select 1 from pg_roles where rolname = 'app_user') then
    grant execute on function authenticate_api_key(text) to app_user;
    grant execute on function log_chat_query(text, text, text, text, integer, text, integer, text, boolean) to app_user;
    if exists (
      select 1 from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
      where n.nspname = 'public' and p.proname = 'get_user_for_login'
    ) then
      revoke all on function public.get_user_for_login(text) from app_user;
    end if;
  end if;
  foreach api_role in array array['anon', 'authenticated', 'service_role'] loop
    if exists (select 1 from pg_roles where rolname = api_role) then
      execute format('revoke all on function public.authenticate_api_key(text) from %I', api_role);
      execute format(
        'revoke all on function public.log_chat_query(text, text, text, text, integer, text, integer, text, boolean) from %I',
        api_role
      );
      if exists (
        select 1 from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.proname = 'get_user_for_login'
      ) then
        execute format('revoke all on function public.get_user_for_login(text) from %I', api_role);
      end if;
    end if;
  end loop;
end $$;

alter table public.api_keys enable row level security;
alter table public.api_keys force row level security;
alter table public.chat_query_log enable row level security;
alter table public.chat_query_log force row level security;

drop policy if exists api_keys_app_user_all on public.api_keys;
drop policy if exists chat_query_log_app_user_all on public.chat_query_log;

revoke all on table public.api_keys from public;
revoke all on table public.chat_query_log from public;

do $$
declare
  api_role text;
begin
  foreach api_role in array array['anon', 'authenticated', 'service_role', 'app_user'] loop
    if exists (select 1 from pg_roles where rolname = api_role) then
      execute format('revoke all on table public.api_keys from %I', api_role);
      execute format('revoke all on table public.chat_query_log from %I', api_role);
    end if;
  end loop;
end $$;
