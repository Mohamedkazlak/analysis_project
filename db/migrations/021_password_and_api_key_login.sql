-- Password login also requires an active API key for that same account.
-- The function returns the password hash only when the key belongs to the
-- user. It does not record last_used_at; authenticate_api_key does that
-- after the password check succeeds.

create or replace function account_password_for_key(p_user_id text, p_key_hash text)
returns text
language plpgsql
security definer
set search_path = public
set row_security = off
as $$
declare
  key_row api_keys;
  acct user_accounts;
begin
  if p_user_id is null or btrim(p_user_id) = ''
     or p_key_hash is null or length(p_key_hash) <> 64 then
    return null;
  end if;
  select * into key_row from api_keys where key_hash = p_key_hash;
  if not found
     or key_row.user_id is distinct from p_user_id
     or key_row.is_active is not true
     or key_row.revoked_at is not null
     or (key_row.expires_at is not null and key_row.expires_at <= now()) then
    return null;
  end if;
  select * into acct from user_accounts where id = p_user_id;
  if not found or acct.is_active is not true or acct.password_hash is null then
    return null;
  end if;
  return acct.password_hash;
end;
$$;

revoke all on function account_password_for_key(text, text) from public;

do $$
declare
  api_role text;
begin
  if exists (select 1 from pg_roles where rolname = 'app_user') then
    grant execute on function account_password_for_key(text, text) to app_user;
  end if;
  foreach api_role in array array['anon', 'authenticated', 'service_role'] loop
    if exists (select 1 from pg_roles where rolname = api_role) then
      execute format(
        'revoke all on function public.account_password_for_key(text, text) from %I',
        api_role
      );
    end if;
  end loop;
end $$;
