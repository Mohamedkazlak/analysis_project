-- Sign-in sends the account id and password. The client does not send an API
-- key. The password hash is returned only when that account has an active key.
-- record_password_login stamps last_used_at after the password check succeeds.

create or replace function account_password_for_login(p_user_id text)
returns text
language plpgsql
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
begin
  if p_user_id is null or btrim(p_user_id) = '' then
    return null;
  end if;
  select * into acct from user_accounts where id = p_user_id;
  if not found or acct.is_active is not true or acct.password_hash is null then
    return null;
  end if;
  if not exists (
    select 1
    from api_keys
    where user_id = p_user_id
      and is_active is true
      and revoked_at is null
      and (expires_at is null or expires_at > now())
  ) then
    return null;
  end if;
  return acct.password_hash;
end;
$$;

create or replace function record_password_login(p_user_id text)
returns table (user_id text)
language plpgsql
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
  key_id text;
begin
  if p_user_id is null or btrim(p_user_id) = '' then
    return;
  end if;
  select * into acct from user_accounts where id = p_user_id;
  if not found or acct.is_active is not true or acct.password_hash is null then
    return;
  end if;
  select k.id into key_id
  from api_keys k
  where k.user_id = p_user_id
    and k.is_active is true
    and k.revoked_at is null
    and (k.expires_at is null or k.expires_at > now())
  order by k.created_at desc
  limit 1;
  if key_id is null then
    return;
  end if;
  update api_keys set last_used_at = now() where id = key_id;
  return query select acct.id;
end;
$$;

revoke all on function account_password_for_login(text) from public;
revoke all on function record_password_login(text) from public;

do $$
declare
  api_role text;
begin
  if exists (select 1 from pg_roles where rolname = 'app_user') then
    grant execute on function account_password_for_login(text) to app_user;
    grant execute on function record_password_login(text) to app_user;
  end if;
  foreach api_role in array array['anon', 'authenticated', 'service_role'] loop
    if exists (select 1 from pg_roles where rolname = api_role) then
      execute format(
        'revoke all on function public.account_password_for_login(text) from %I',
        api_role
      );
      execute format(
        'revoke all on function public.record_password_login(text) from %I',
        api_role
      );
    end if;
  end loop;
end $$;
