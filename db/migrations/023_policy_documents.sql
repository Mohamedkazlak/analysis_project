-- Policy documents table for demo corpus (no embeddings / RAG retrieval).

create table if not exists public.policy_documents (
  id text primary key,
  title text not null,
  language text not null check (language in ('en', 'ar')),
  body text not null,
  effective_date date not null,
  is_synthetic boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists policy_documents_set_updated_at on public.policy_documents;
create trigger policy_documents_set_updated_at
  before update on public.policy_documents
  for each row execute function set_updated_at();

alter table public.policy_documents enable row level security;
alter table public.policy_documents force row level security;

drop policy if exists policy_documents_read on public.policy_documents;
create policy policy_documents_read on public.policy_documents
  for select using (
    (select (current_app_account()).role) is not null
  );

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'app_user') then
    grant select on public.policy_documents to app_user;
  end if;
end $$;

comment on table public.policy_documents is
  'Bilingual policy corpus for demo. Facts stay in SQL; no vector retrieval in this PoC.';
