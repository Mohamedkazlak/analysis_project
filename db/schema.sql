-- BNU Analytics — PostgreSQL schema
-- This is the reproducible source of truth for the database. The production
-- application reads through FastAPI → repositories → this model. Row-Level
-- Security is the database-level access boundary; application filter
-- validation is an additional boundary and must never be weaker than RLS.
--
-- Identifiers are stable text keys (uni-bnu, c1, s7, e1, …) so demo seed rows
-- stay stable across rebuilds. Prefer bigint identity or UUIDv7 if you later
-- ingest a live SIS; keep these values in a `code` column.
--
-- Org mapping used by analytics filters:
--   sector     = org_units.level = 'sector'
--   college    = org_units.level = 'program'
--   curriculum = courses.id
--   student    = students.id
--
-- Requires PostgreSQL 15+ (security_invoker views).
--
-- Fresh install:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/schema.sql
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/seed.sql
-- Existing databases: python backend/run_migration.py (the runner owns the
-- transaction; files in db/migrations/ must not BEGIN/COMMIT themselves).

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

do $$ begin
  create type org_level as enum ('university', 'sector', 'program');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type app_role as enum (
    'senior_management',
    'program_director',
    'academic_affairs',
    'professor',
    'it_academic_integrity',
    'student'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type student_status as enum ('active', 'graduated', 'withdrawn');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type exam_status as enum ('scheduled', 'in_progress', 'closing', 'closed');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type attempt_status as enum ('absent', 'in_progress', 'submitted', 'void');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type integrity_flag_type as enum (
    'multiple_attempts',
    'fast_submission',
    'late_start',
    'shared_ip',
    'similar_answers'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type academic_standing as enum (
    'Excellent',
    'Good standing',
    'Watch list',
    'At risk'
  );
exception when duplicate_object then null;
end $$;

-- requirement_level_type is text constrained to curriculum-report values
-- ('college', 'university'). It is not an invented sector/core/elective enum.

-- ---------------------------------------------------------------------------
-- Shared trigger
-- ---------------------------------------------------------------------------

create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Organization
-- ---------------------------------------------------------------------------

create table if not exists org_units (
  id text primary key,
  parent_id text references org_units (id) on delete restrict,
  level org_level not null,
  code text not null unique,
  name text not null,
  title_for_role text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint org_units_university_root check (
    (level = 'university' and parent_id is null)
    or (level <> 'university' and parent_id is not null)
  )
);

create index if not exists org_units_parent_id_idx on org_units (parent_id);
create index if not exists org_units_level_idx on org_units (level);
-- Cascading college lists: WHERE level = 'program' AND parent_id = :sector
create index if not exists org_units_level_parent_id_idx on org_units (level, parent_id);

drop trigger if exists org_units_set_updated_at on org_units;
create trigger org_units_set_updated_at
  before update on org_units
  for each row execute function set_updated_at();

create table if not exists institution_settings (
  org_unit_id text primary key references org_units (id) on delete cascade,
  pass_mark numeric(5, 2) not null default 60
    check (pass_mark >= 0 and pass_mark <= 100),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Calendar
-- ---------------------------------------------------------------------------

create table if not exists academic_years (
  id text primary key,
  label text not null unique,
  start_date date not null,
  end_date date not null,
  is_current boolean not null default false,
  constraint academic_years_dates check (end_date > start_date)
);

create unique index if not exists academic_years_one_current_idx
  on academic_years (is_current)
  where is_current;

create table if not exists terms (
  id text primary key,
  academic_year_id text not null references academic_years (id) on delete cascade,
  code text not null,
  name text not null,
  start_date date not null,
  end_date date not null,
  unique (academic_year_id, code),
  constraint terms_dates check (end_date > start_date)
);

create index if not exists terms_academic_year_id_idx on terms (academic_year_id);

-- ---------------------------------------------------------------------------
-- People
-- ---------------------------------------------------------------------------

create table if not exists people (
  id text primary key,
  full_name text not null,
  email text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists people_set_updated_at on people;
create trigger people_set_updated_at
  before update on people
  for each row execute function set_updated_at();

create table if not exists staff (
  person_id text primary key references people (id) on delete cascade,
  title text not null,
  org_unit_id text references org_units (id) on delete set null
);

create index if not exists staff_org_unit_id_idx on staff (org_unit_id);

create table if not exists students (
  id text primary key,
  person_id text not null unique references people (id) on delete restrict,
  student_number text not null unique,
  program_id text not null references org_units (id) on delete restrict,
  section text not null,
  cohort_year smallint not null,
  status student_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint students_program_is_program check (section <> '')
);

create index if not exists students_program_id_idx on students (program_id);
create index if not exists students_section_idx on students (program_id, section);

drop trigger if exists students_set_updated_at on students;
create trigger students_set_updated_at
  before update on students
  for each row execute function set_updated_at();

create table if not exists user_accounts (
  id text primary key,
  person_id text not null references people (id) on delete cascade,
  role app_role not null,
  scope_id text references org_units (id) on delete set null,
  student_id text references students (id) on delete set null,
  password_hash text,
  is_demo boolean not null default false,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (person_id, role),
  constraint user_accounts_student_role check (
    (role = 'student' and student_id is not null)
    or (role <> 'student' and student_id is null)
  )
);

create index if not exists user_accounts_person_id_idx on user_accounts (person_id);
create index if not exists user_accounts_scope_id_idx on user_accounts (scope_id);
create index if not exists user_accounts_role_idx on user_accounts (role);
create index if not exists user_accounts_student_id_idx
  on user_accounts (student_id)
  where student_id is not null;

-- Login secrets. role/scope columns are not authoritative; user_accounts is.
create table if not exists api_keys (
  id text primary key default gen_random_uuid()::text,
  user_id text references user_accounts (id) on delete cascade,
  key_prefix text not null,
  key_hash text not null unique,
  label text,
  is_active boolean not null default true,
  expires_at timestamptz,
  revoked_at timestamptz,
  last_used_at timestamptz,
  created_at timestamptz not null default now(),
  role app_role,
  scope_id text references org_units (id),
  person_id text references people (id),
  student_id text references students (id)
);

create index if not exists api_keys_user_id_idx on api_keys (user_id);
drop index if exists api_keys_user_id_key;

comment on table api_keys is
  'API key login. Only key_hash is stored. Role and scope are read from user_accounts.';

create table if not exists chat_query_log (
  id bigint generated always as identity primary key,
  user_id text references user_accounts (id) on delete set null,
  api_key_id text references api_keys (id) on delete set null,
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

create index if not exists chat_query_log_user_id_idx on chat_query_log (user_id);

alter table api_keys enable row level security;
alter table chat_query_log enable row level security;

-- ---------------------------------------------------------------------------
-- Curriculum
-- ---------------------------------------------------------------------------

create table if not exists courses (
  id text primary key,
  program_id text not null references org_units (id) on delete restrict,
  code text not null,
  name text not null,
  credits smallint not null default 3 check (credits between 1 and 12),
  year_level smallint not null default 1 check (year_level between 1 and 6),
  requirement_level_type text not null default 'college'
    check (requirement_level_type in ('college', 'university')),
  counted_in_cumulative_gpa boolean not null default true,
  pass_fail_subject boolean not null default false,
  unique (program_id, code)
);

create index if not exists courses_program_id_idx on courses (program_id);

comment on column courses.requirement_level_type is
  'Curriculum-report requirement level: college or university. Default college is a placeholder until authoritative metadata is imported.';
comment on column courses.counted_in_cumulative_gpa is
  'When false the course is excluded from cumulative GPA. Independent of pass_fail_subject.';
comment on column courses.pass_fail_subject is
  'When true the course does not contribute letter-grade quality points to cumulative GPA.';

create table if not exists course_offerings (
  id text primary key,
  course_id text not null references courses (id) on delete cascade,
  academic_year_id text not null references academic_years (id) on delete restrict,
  term_id text not null references terms (id) on delete restrict,
  instructor_id text not null references people (id) on delete restrict,
  unique (course_id, academic_year_id, term_id)
);

create index if not exists course_offerings_course_id_idx on course_offerings (course_id);
create index if not exists course_offerings_instructor_id_idx on course_offerings (instructor_id);
create index if not exists course_offerings_term_id_idx on course_offerings (term_id);
create index if not exists course_offerings_academic_year_id_idx on course_offerings (academic_year_id);

create table if not exists course_sections (
  id text primary key,
  offering_id text not null references course_offerings (id) on delete cascade,
  code text not null,
  unique (offering_id, code)
);

create index if not exists course_sections_offering_id_idx on course_sections (offering_id);

create table if not exists staff_course_assignments (
  staff_person_id text not null references staff (person_id) on delete cascade,
  course_id text not null references courses (id) on delete cascade,
  primary key (staff_person_id, course_id)
);

create index if not exists staff_course_assignments_course_id_idx
  on staff_course_assignments (course_id);

create table if not exists enrollments (
  id text primary key,
  student_id text not null references students (id) on delete cascade,
  offering_id text not null references course_offerings (id) on delete cascade,
  section_id text not null references course_sections (id) on delete restrict,
  enrolled_at timestamptz not null default now(),
  unique (student_id, offering_id),
  constraint enrollments_id_student_id_key unique (id, student_id)
);

create index if not exists enrollments_offering_id_idx on enrollments (offering_id);
create index if not exists enrollments_section_id_idx on enrollments (section_id);
create index if not exists enrollments_student_id_idx on enrollments (student_id);

-- ---------------------------------------------------------------------------
-- Assessment
-- ---------------------------------------------------------------------------

create table if not exists exams (
  id text primary key,
  offering_id text not null references course_offerings (id) on delete cascade,
  title text not null,
  scheduled_at timestamptz not null,
  duration_minutes smallint not null default 90 check (duration_minutes > 0),
  question_count smallint not null check (question_count > 0),
  pass_mark numeric(5, 2) not null default 60 check (pass_mark >= 0 and pass_mark <= 100),
  status exam_status not null default 'closed',
  is_synthetic boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists exams_offering_id_idx on exams (offering_id);
create index if not exists exams_scheduled_at_idx on exams (scheduled_at);
create index if not exists exams_status_idx on exams (status);

create table if not exists questions (
  id text primary key,
  exam_id text not null references exams (id) on delete cascade,
  number smallint not null,
  topic text not null,
  prompt text not null,
  max_score numeric(6, 2) not null default 1 check (max_score > 0),
  is_synthetic boolean not null default false,
  unique (exam_id, number)
);

create index if not exists questions_exam_id_idx on questions (exam_id);

create table if not exists exam_attempts (
  id text primary key,
  exam_id text not null references exams (id) on delete cascade,
  student_id text not null references students (id) on delete cascade,
  enrollment_id text not null references enrollments (id) on delete cascade,
  score numeric(5, 2) check (score is null or (score >= 0 and score <= 100)),
  time_taken_min smallint,
  started_at timestamptz,
  ended_at timestamptz,
  ip inet,
  device text,
  attempt_count smallint not null default 1 check (attempt_count >= 1),
  late_start boolean not null default false,
  status attempt_status not null,
  is_synthetic boolean not null default false,
  unique (exam_id, student_id),
  constraint exam_attempts_times check (
    ended_at is null or started_at is null or ended_at >= started_at
  ),
  constraint exam_attempts_absent_score check (
    (status = 'absent' and score is null)
    or (status <> 'absent')
  ),
  constraint exam_attempts_enrollment_student_fk
    foreign key (enrollment_id, student_id)
    references enrollments (id, student_id)
);

create index if not exists exam_attempts_exam_id_idx on exam_attempts (exam_id);
create index if not exists exam_attempts_student_id_idx on exam_attempts (student_id);
create index if not exists exam_attempts_enrollment_id_idx on exam_attempts (enrollment_id);
create index if not exists exam_attempts_status_idx on exam_attempts (status);
-- Pass-rate and class-average queries always constrain both exam and status.
create index if not exists exam_attempts_exam_id_status_idx
  on exam_attempts (exam_id, status);

create table if not exists attempt_answers (
  attempt_id text not null references exam_attempts (id) on delete cascade,
  question_id text not null references questions (id) on delete cascade,
  is_correct boolean not null,
  points numeric(6, 2),
  is_synthetic boolean not null default false,
  primary key (attempt_id, question_id)
);

create index if not exists attempt_answers_question_id_idx on attempt_answers (question_id);

create table if not exists integrity_flags (
  id text primary key,
  attempt_id text not null references exam_attempts (id) on delete cascade,
  flag_type integrity_flag_type not null,
  detail text,
  is_synthetic boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists integrity_flags_attempt_id_idx on integrity_flags (attempt_id);
create index if not exists integrity_flags_flag_type_idx on integrity_flags (flag_type);

create table if not exists transcript_entries (
  id text primary key,
  student_id text not null references students (id) on delete cascade,
  course_id text not null references courses (id) on delete restrict,
  academic_year_id text not null references academic_years (id) on delete restrict,
  average numeric(5, 2) not null check (average >= 0 and average <= 100),
  letter_grade text not null,
  credits smallint not null check (credits between 1 and 12),
  is_synthetic boolean not null default false,
  unique (student_id, course_id, academic_year_id)
);

create index if not exists transcript_entries_student_id_idx on transcript_entries (student_id);
create index if not exists transcript_entries_academic_year_id_idx
  on transcript_entries (academic_year_id);
create index if not exists transcript_entries_course_id_idx on transcript_entries (course_id);

-- ---------------------------------------------------------------------------
-- Views (security_invoker so RLS on base tables still applies)
-- ---------------------------------------------------------------------------

create or replace view v_courses_current
  with (security_invoker = true)
as
select
  c.id,
  c.code,
  c.name,
  c.credits,
  c.year_level,
  c.program_id,
  p.name as program,
  p.parent_id as sector_id,
  s.name as sector,
  o.id as offering_id,
  o.instructor_id,
  ins.full_name as instructor,
  o.academic_year_id,
  o.term_id,
  (
    select count(*)::int
    from enrollments e
    where e.offering_id = o.id
  ) as enrolled
from course_offerings o
join courses c on c.id = o.course_id
join org_units p on p.id = c.program_id
join org_units s on s.id = p.parent_id
join people ins on ins.id = o.instructor_id;

create or replace view v_students
  with (security_invoker = true)
as
select
  st.id,
  st.person_id,
  st.student_number,
  pe.full_name as name,
  st.program_id,
  p.name as program,
  p.parent_id as sector_id,
  sec.name as sector,
  st.section,
  st.cohort_year,
  st.status
from students st
join people pe on pe.id = st.person_id
join org_units p on p.id = st.program_id
join org_units sec on sec.id = p.parent_id;

create or replace view v_exam_attempts
  with (security_invoker = true)
as
select
  a.id,
  a.exam_id,
  a.student_id,
  st.section,
  pe.full_name as student_name,
  a.enrollment_id,
  a.score,
  a.time_taken_min,
  a.started_at,
  a.ended_at,
  host(a.ip) as ip,
  a.device,
  a.attempt_count,
  a.late_start,
  a.status,
  (a.status <> 'absent') as participated,
  p.id as program_id,
  p.name as program,
  sec.id as sector_id,
  sec.name as sector,
  c.id as course_id,
  c.code as course_code,
  x.title as exam_title,
  x.scheduled_at
from exam_attempts a
join students st on st.id = a.student_id
join people pe on pe.id = st.person_id
join org_units p on p.id = st.program_id
join org_units sec on sec.id = p.parent_id
join exams x on x.id = a.exam_id
join course_offerings o on o.id = x.offering_id
join courses c on c.id = o.course_id;

create or replace view v_item_stats
  with (security_invoker = true)
as
select
  q.id,
  q.exam_id,
  q.number,
  q.topic,
  q.prompt,
  c.code || ' · ' || split_part(x.title, ' — ', 1) as exam_label,
  round(
    100.0 * avg((ans.is_correct)::int),
    0
  ) as pct_correct,
  round(
    1.0 * avg((ans.is_correct)::int),
    2
  ) as difficulty_index
from questions q
join exams x on x.id = q.exam_id
join course_offerings o on o.id = x.offering_id
join courses c on c.id = o.course_id
left join attempt_answers ans on ans.question_id = q.id
group by q.id, q.exam_id, q.number, q.topic, q.prompt, c.code, x.title;

-- ---------------------------------------------------------------------------
-- Scope helpers (used by RLS)
-- SECURITY DEFINER + row_security=off so policies never join RLS tables
-- directly (that recurses under FORCE ROW LEVEL SECURITY).
-- ---------------------------------------------------------------------------

create or replace function org_descendants(root_id text)
returns setof text
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  with recursive tree as (
    select id from org_units where id = root_id
    union all
    select child.id
    from org_units child
    join tree on child.parent_id = tree.id
  )
  select id from tree;
$$;

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

-- President / VP (university): every program.
-- Sector dean: programs whose parent is the sector.
-- Program director / college academic affairs: their program only.
-- Professor, student, IT: empty here — they use dedicated helpers.
create or replace function current_visible_program_ids()
returns setof text
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
  node org_units;
begin
  acct := current_app_account();
  if acct is null or acct.scope_id is null then
    return;
  end if;
  if acct.role not in ('senior_management', 'program_director', 'academic_affairs') then
    return;
  end if;
  select * into node from org_units where id = acct.scope_id;
  if not found then
    return;
  end if;
  if node.level = 'university' then
    return query select id from org_units where level = 'program';
  elsif node.level = 'sector' then
    return query select id from org_units where parent_id = node.id and level = 'program';
  else
    return query select node.id;
  end if;
end;
$$;

create or replace function current_visible_org_unit_ids()
returns setof text
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  with acct as (
    select * from current_app_account()
  )
  select u.id
  from org_units u, acct
  where acct.id is not null
    and u.level = 'university'

  union

  select acct.scope_id
  from acct
  where acct.id is not null
    and acct.scope_id is not null

  union

  select u.id
  from org_units u, acct
  where acct.role = 'it_academic_integrity'

  union

  select u.id
  from org_units u, acct
  join org_units n on n.id = acct.scope_id
  where acct.role = 'senior_management'
    and n.level = 'university'

  union

  select u.id
  from org_units u, acct
  join org_units n on n.id = acct.scope_id
  where acct.role = 'senior_management'
    and n.level = 'sector'
    and u.level = 'program'
    and u.parent_id = n.id

  union

  select n.parent_id
  from acct
  join org_units n on n.id = acct.scope_id
  where acct.role = 'senior_management'
    and n.level not in ('university', 'sector')
    and n.parent_id is not null

  union

  select n.parent_id
  from acct
  join org_units n on n.id = acct.scope_id
  where acct.role in ('program_director', 'academic_affairs')
    and n.parent_id is not null

  union

  select p.id
  from acct
  join staff_course_assignments sca on sca.staff_person_id = acct.person_id
  join courses c on c.id = sca.course_id
  join org_units p on p.id = c.program_id
  where acct.role = 'professor'

  union

  select p.parent_id
  from acct
  join staff_course_assignments sca on sca.staff_person_id = acct.person_id
  join courses c on c.id = sca.course_id
  join org_units p on p.id = c.program_id
  where acct.role = 'professor'
    and p.parent_id is not null

  union

  select p.id
  from acct
  join students s on s.id = acct.student_id
  join org_units p on p.id = s.program_id
  where acct.role = 'student'

  union

  select p.parent_id
  from acct
  join students s on s.id = acct.student_id
  join org_units p on p.id = s.program_id
  where acct.role = 'student'
    and p.parent_id is not null
$$;

create or replace function org_unit_is_visible(p_id text)
returns boolean
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select coalesce(p_id in (select current_visible_org_unit_ids()), false);
$$;

create or replace function current_professor_course_ids()
returns setof text
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select sca.course_id
  from staff_course_assignments sca
  where sca.staff_person_id = (current_app_account()).person_id;
$$;

create or replace function current_student_course_ids()
returns setof text
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select o.course_id
  from enrollments e
  join course_offerings o on o.id = e.offering_id
  where e.student_id = (current_app_account()).student_id;
$$;

create or replace function current_visible_student_ids()
returns setof text
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
begin
  acct := current_app_account();
  if acct is null then
    return;
  end if;
  if acct.role = 'student' then
    return query
      select acct.student_id
      where acct.student_id is not null;
    return;
  end if;
  if acct.role = 'professor' then
    return query
      select distinct e.student_id
      from staff_course_assignments sca
      join course_offerings o on o.course_id = sca.course_id
      join enrollments e on e.offering_id = o.id
      where sca.staff_person_id = acct.person_id;
    return;
  end if;
  if acct.role = 'it_academic_integrity' then
    return query
      select distinct a.student_id from exam_attempts a
      union
      select distinct a.student_id
      from integrity_flags f
      join exam_attempts a on a.id = f.attempt_id;
    return;
  end if;
  return query
    select s.id
    from students s
    where s.program_id in (select current_visible_program_ids());
end;
$$;

create or replace function current_visible_course_ids()
returns setof text
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
begin
  acct := current_app_account();
  if acct is null then
    return;
  end if;
  if acct.role = 'professor' then
    return query
      select sca.course_id
      from staff_course_assignments sca
      where sca.staff_person_id = acct.person_id;
    return;
  end if;
  if acct.role = 'student' then
    return query
      select o.course_id
      from enrollments e
      join course_offerings o on o.id = e.offering_id
      where e.student_id = acct.student_id;
    return;
  end if;
  if acct.role = 'it_academic_integrity' then
    return query
      select distinct o.course_id
      from course_offerings o
      join exams x on x.offering_id = o.id;
    return;
  end if;
  return query
    select c.id
    from courses c
    where c.program_id in (select current_visible_program_ids());
end;
$$;

create or replace function current_visible_offering_ids()
returns setof text
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select o.id
  from course_offerings o
  where o.course_id in (select current_visible_course_ids());
$$;

create or replace function current_visible_exam_ids()
returns setof text
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select x.id
  from exams x
  where x.offering_id in (select current_visible_offering_ids());
$$;

create or replace function current_visible_attempt_ids()
returns setof text
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
begin
  acct := current_app_account();
  if acct is null then
    return;
  end if;
  if acct.role = 'professor' then
    return query
      select a.id
      from exam_attempts a
      join exams x on x.id = a.exam_id
      join course_offerings o on o.id = x.offering_id
      join staff_course_assignments sca
        on sca.course_id = o.course_id
       and sca.staff_person_id = acct.person_id
      where a.student_id in (
        select e.student_id
        from staff_course_assignments assigned
        join course_offerings eo on eo.course_id = assigned.course_id
        join enrollments e on e.offering_id = eo.id
        where assigned.staff_person_id = acct.person_id
      );
    return;
  end if;
  return query
    select a.id
    from exam_attempts a
    where a.student_id in (select current_visible_student_ids());
end;
$$;

create or replace function current_visible_person_ids()
returns setof text
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
begin
  acct := current_app_account();
  if acct is null then
    return;
  end if;
  return query
    select acct.person_id
    where acct.person_id is not null;
  if acct.role = 'student' then
    return;
  end if;
  return query
    select s.person_id
    from students s
    where s.id in (select current_visible_student_ids());
  if acct.role = 'professor' then
    -- Own teaching identity only. Other faculty in the college are out of scope.
    return query
      select o.instructor_id
      from course_offerings o
      where o.course_id in (select current_visible_course_ids())
        and o.instructor_id is not null;
    return;
  end if;
  return query
    select st.person_id
    from staff st
    where st.person_id = acct.person_id
       or st.org_unit_id in (select current_visible_org_unit_ids());
  return query
    select o.instructor_id
    from course_offerings o
    where o.course_id in (select current_visible_course_ids());
end;
$$;

create or replace function student_is_visible(p_id text)
returns boolean
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select coalesce(p_id in (select current_visible_student_ids()), false);
$$;

create or replace function course_is_visible(p_id text)
returns boolean
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select coalesce(p_id in (select current_visible_course_ids()), false);
$$;

create or replace function offering_is_visible(p_id text)
returns boolean
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select coalesce(p_id in (select current_visible_offering_ids()), false);
$$;

create or replace function exam_is_visible(p_id text)
returns boolean
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select coalesce(p_id in (select current_visible_exam_ids()), false);
$$;

create or replace function exam_attempt_is_visible(p_student_id text, p_exam_id text)
returns boolean
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select coalesce(
    p_student_id in (select current_visible_student_ids())
    and (
      (select (current_app_account()).role) is distinct from 'professor'
      or p_exam_id in (
        select x.id
        from exams x
        join course_offerings o on o.id = x.offering_id
        join staff_course_assignments sca
          on sca.course_id = o.course_id
         and sca.staff_person_id = (select (current_app_account()).person_id)
      )
    ),
    false
  );
$$;

create or replace function attempt_is_visible(p_id text)
returns boolean
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select coalesce(p_id in (select current_visible_attempt_ids()), false);
$$;

-- Class average for a student's own dashboard without leaking other rows.
create or replace function exam_class_average(p_exam_id text)
returns numeric
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
declare
  acct user_accounts;
  result numeric;
begin
  acct := current_app_account();
  if acct is null then
    return null;
  end if;
  if acct.role = 'student' then
    if not exists (
      select 1 from exam_attempts a
      where a.exam_id = p_exam_id and a.student_id = acct.student_id
    ) then
      return null;
    end if;
  elsif not coalesce(exam_is_visible(p_exam_id), false) then
    return null;
  end if;
  select round(avg(score)::numeric, 1) into result
  from exam_attempts
  where exam_id = p_exam_id and status <> 'absent' and score is not null;
  return result;
end;
$$;

-- ---------------------------------------------------------------------------
-- Row level security
-- Policies use uncorrelated IN (SELECT current_visible_*_ids()) so PostgreSQL
-- can InitPlan authorization once per statement. Boolean helpers remain for
-- SQL/RPC callers and wrap those sets.
-- ---------------------------------------------------------------------------

alter table org_units enable row level security;
alter table institution_settings enable row level security;
alter table academic_years enable row level security;
alter table terms enable row level security;
alter table people enable row level security;
alter table staff enable row level security;
alter table students enable row level security;
alter table user_accounts enable row level security;
alter table courses enable row level security;
alter table course_offerings enable row level security;
alter table course_sections enable row level security;
alter table staff_course_assignments enable row level security;
alter table enrollments enable row level security;
alter table exams enable row level security;
alter table questions enable row level security;
alter table exam_attempts enable row level security;
alter table attempt_answers enable row level security;
alter table integrity_flags enable row level security;
alter table transcript_entries enable row level security;

drop policy if exists org_units_read on org_units;
create policy org_units_read on org_units
  for select using (id in (select current_visible_org_unit_ids()));

drop policy if exists institution_settings_read on institution_settings;
create policy institution_settings_read on institution_settings
  for select using (org_unit_id in (select current_visible_org_unit_ids()));

drop policy if exists academic_years_read on academic_years;
create policy academic_years_read on academic_years
  for select using ((select (current_app_account()).id) is not null);

drop policy if exists terms_read on terms;
create policy terms_read on terms
  for select using ((select (current_app_account()).id) is not null);

drop policy if exists people_read on people;
create policy people_read on people
  for select using (id in (select current_visible_person_ids()));

drop policy if exists staff_read on staff;
create policy staff_read on staff
  for select using (
    (select (current_app_account()).role) is distinct from 'student'
    and person_id in (select current_visible_person_ids())
  );

drop policy if exists students_read on students;
create policy students_read on students
  for select using (id in (select current_visible_student_ids()));

drop policy if exists user_accounts_read on user_accounts;
create policy user_accounts_read on user_accounts
  for select using (id = (select (current_app_account()).id));

drop policy if exists courses_read on courses;
create policy courses_read on courses
  for select using (id in (select current_visible_course_ids()));

drop policy if exists course_offerings_read on course_offerings;
create policy course_offerings_read on course_offerings
  for select using (course_id in (select current_visible_course_ids()));

drop policy if exists course_sections_read on course_sections;
create policy course_sections_read on course_sections
  for select using (offering_id in (select current_visible_offering_ids()));

drop policy if exists staff_course_assignments_read on staff_course_assignments;
create policy staff_course_assignments_read on staff_course_assignments
  for select using (
    (select (current_app_account()).role) not in ('student', 'it_academic_integrity')
    and (
      (
        (select (current_app_account()).role) = 'professor'
        and staff_person_id = (select (current_app_account()).person_id)
      )
      or (
        (select (current_app_account()).role) is distinct from 'professor'
        and course_id in (select current_visible_course_ids())
      )
    )
  );

drop policy if exists enrollments_read on enrollments;
create policy enrollments_read on enrollments
  for select using (
    (select (current_app_account()).role) is distinct from 'it_academic_integrity'
    and student_id in (select current_visible_student_ids())
    and (
      (select (current_app_account()).role) is distinct from 'professor'
      or offering_id in (select current_visible_offering_ids())
    )
  );

drop policy if exists exams_read on exams;
create policy exams_read on exams
  for select using (offering_id in (select current_visible_offering_ids()));

drop policy if exists questions_read on questions;
create policy questions_read on questions
  for select using (exam_id in (select current_visible_exam_ids()));

drop policy if exists exam_attempts_read on exam_attempts;
create policy exam_attempts_read on exam_attempts
  for select using (
    student_id in (select current_visible_student_ids())
    and (
      (select (current_app_account()).role) is distinct from 'professor'
      or exam_id in (select current_visible_exam_ids())
    )
  );

drop policy if exists attempt_answers_read on attempt_answers;
create policy attempt_answers_read on attempt_answers
  for select using (attempt_id in (select current_visible_attempt_ids()));

drop policy if exists integrity_flags_read on integrity_flags;
create policy integrity_flags_read on integrity_flags
  for select using (
    (select (current_app_account()).role) = 'it_academic_integrity'
    or (
      (select (current_app_account()).role) in (
        'senior_management',
        'program_director',
        'academic_affairs',
        'professor'
      )
      and exists (
        select 1
        from exam_attempts a
        where a.id = integrity_flags.attempt_id
      )
    )
  );

drop policy if exists transcript_entries_read on transcript_entries;
create policy transcript_entries_read on transcript_entries
  for select using (
    (select (current_app_account()).role) is distinct from 'it_academic_integrity'
    and student_id in (select current_visible_student_ids())
  );

comment on table org_units is 'University → sector → program tree. scope_id on user_accounts points here. Analytics "college" = program-level row.';
comment on table courses is 'Catalog curriculum. requirement_level_type is college|university. counted_in_cumulative_gpa / pass_fail_subject drive GPA eligibility and must not be inferred from year_level or course ids.';
comment on table enrollments is 'A student may sit an exam only through an enrollment on that offering.';
comment on table exam_attempts is 'Roster row per enrollment × exam; status=absent means no sitting.';
comment on table transcript_entries is 'Closed academic-year grades when live exam rows are not kept.';
comment on column exams.is_synthetic is 'True for generated demo assessment rows; false for imported university records.';
comment on function current_app_account() is 'Reads app.current_user_id (user_accounts.id). Password hash is never returned. Inactive accounts are not visible. Set in the API session.';
comment on function student_is_visible(text) is 'Whether the session role may see this student row.';
comment on function course_is_visible(text) is 'Whether the session role may see this course row.';
comment on function org_unit_is_visible(text) is
  'Whether the session role may see this org_units row. Wrapper over current_visible_org_unit_ids().';
comment on function current_visible_student_ids() is
  'Session-visible student ids. STABLE SECURITY DEFINER, RLS off. Used as an uncorrelated IN-list so RLS can InitPlan once per statement.';
comment on function current_visible_course_ids() is
  'Session-visible course ids. STABLE SECURITY DEFINER, RLS off.';
comment on function current_visible_org_unit_ids() is
  'Session-visible org unit ids computed as a set. Does not call org_unit_is_visible() per row.';
comment on function current_visible_attempt_ids() is
  'Session-visible exam_attempt ids. Professor rows also require the exam course to be assigned.';
comment on function current_visible_person_ids() is
  'Session-visible people. Professors see themselves, assigned students, and instructors of assigned courses — not other faculty.';

-- ---------------------------------------------------------------------------
-- Login + class-average helpers (SECURITY DEFINER, RLS off)
-- ---------------------------------------------------------------------------

create or replace function get_user_for_login(p_id text)
returns table (
    id text,
    person_id text,
    role app_role,
    scope_id text,
    student_id text,
    password_hash text
)
language plpgsql
stable
security definer
set search_path = public
set row_security = off
as $$
begin
    return query
    select u.id, u.person_id, u.role, u.scope_id, u.student_id, u.password_hash
    from user_accounts u
    where u.id = p_id;
end;
$$;

create or replace function get_exam_averages(exam_ids text[])
returns table (exam_id text, avg_score numeric)
language sql
stable
security definer
set search_path = public
set row_security = off
as $$
  select a.exam_id, avg(a.score) as avg_score
  from exam_attempts a
  where a.exam_id = any(exam_ids)
    and a.status <> 'absent'
    and a.score is not null
    and (
      a.exam_id in (select current_visible_exam_ids())
      or exists (
        select 1
        from exam_attempts mine
        where mine.exam_id = a.exam_id
          and mine.student_id = (select (current_app_account()).student_id)
      )
    )
  group by a.exam_id;
$$;

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
comment on function account_password_for_login(text) is
  'Password hash for an active account that has an active API key. The client does not send the key.';
comment on function record_password_login(text) is
  'After a successful password check, stamps last_used_at on that account''s newest active API key.';
comment on function log_chat_query(text, text, text, text, integer, text, integer, text, boolean) is
  'Inserts one chat audit row for the session user. Does not store result rows.';

-- ---------------------------------------------------------------------------
-- Application role, FORCE RLS, grants
-- app_user is the recommended least-privilege LOGIN role. This script does
-- not set a password. Operators set it out of band, then point DATABASE_URL
-- at that role. The API never rewrites DATABASE_URL usernames.
--   ALTER ROLE app_user LOGIN PASSWORD '...';
-- ---------------------------------------------------------------------------

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_user') then
    create role app_user login;
  end if;
end
$$;

grant usage on schema public to app_user;
grant select on all tables in schema public to app_user;
revoke insert, update, delete on all tables in schema public from app_user;
revoke all on table api_keys from app_user;
revoke all on table chat_query_log from app_user;
revoke all on table api_keys from public;
revoke all on table chat_query_log from public;
alter default privileges in schema public grant select on tables to app_user;

alter table org_units force row level security;
alter table institution_settings force row level security;
alter table academic_years force row level security;
alter table terms force row level security;
alter table people force row level security;
alter table staff force row level security;
alter table students force row level security;
alter table user_accounts force row level security;
alter table courses force row level security;
alter table course_offerings force row level security;
alter table course_sections force row level security;
alter table staff_course_assignments force row level security;
alter table enrollments force row level security;
alter table exams force row level security;
alter table questions force row level security;
alter table exam_attempts force row level security;
alter table attempt_answers force row level security;
alter table integrity_flags force row level security;
alter table transcript_entries force row level security;
alter table api_keys force row level security;
alter table chat_query_log force row level security;

revoke all on function org_descendants(text) from public;
revoke all on function current_app_account() from public;
revoke all on function current_visible_program_ids() from public;
revoke all on function org_unit_is_visible(text) from public;
revoke all on function current_professor_course_ids() from public;
revoke all on function current_student_course_ids() from public;
revoke all on function current_visible_student_ids() from public;
revoke all on function current_visible_course_ids() from public;
revoke all on function current_visible_org_unit_ids() from public;
revoke all on function current_visible_offering_ids() from public;
revoke all on function current_visible_exam_ids() from public;
revoke all on function current_visible_attempt_ids() from public;
revoke all on function current_visible_person_ids() from public;
revoke all on function student_is_visible(text) from public;
revoke all on function course_is_visible(text) from public;
revoke all on function offering_is_visible(text) from public;
revoke all on function exam_is_visible(text) from public;
revoke all on function exam_attempt_is_visible(text, text) from public;
revoke all on function attempt_is_visible(text) from public;
revoke all on function exam_class_average(text) from public;
revoke all on function get_user_for_login(text) from public;
revoke all on function get_exam_averages(text[]) from public;
revoke all on function authenticate_api_key(text) from public;
revoke all on function account_password_for_key(text, text) from public;
revoke all on function account_password_for_login(text) from public;
revoke all on function record_password_login(text) from public;
revoke all on function log_chat_query(text, text, text, text, integer, text, integer, text, boolean) from public;

grant execute on function org_descendants(text) to app_user;
grant execute on function current_app_account() to app_user;
grant execute on function current_visible_program_ids() to app_user;
grant execute on function org_unit_is_visible(text) to app_user;
grant execute on function current_professor_course_ids() to app_user;
grant execute on function current_student_course_ids() to app_user;
grant execute on function current_visible_student_ids() to app_user;
grant execute on function current_visible_course_ids() to app_user;
grant execute on function current_visible_org_unit_ids() to app_user;
grant execute on function current_visible_offering_ids() to app_user;
grant execute on function current_visible_exam_ids() to app_user;
grant execute on function current_visible_attempt_ids() to app_user;
grant execute on function current_visible_person_ids() to app_user;
grant execute on function student_is_visible(text) to app_user;
grant execute on function course_is_visible(text) to app_user;
grant execute on function offering_is_visible(text) to app_user;
grant execute on function exam_is_visible(text) to app_user;
grant execute on function exam_attempt_is_visible(text, text) to app_user;
grant execute on function attempt_is_visible(text) to app_user;
grant execute on function exam_class_average(text) to app_user;
grant execute on function get_exam_averages(text[]) to app_user;
grant execute on function authenticate_api_key(text) to app_user;
grant execute on function account_password_for_key(text, text) to app_user;
grant execute on function account_password_for_login(text) to app_user;
grant execute on function record_password_login(text) to app_user;
grant execute on function log_chat_query(text, text, text, text, integer, text, integer, text, boolean) to app_user;

do $$
declare
  api_role text;
  fn text;
  sigs text[] := array[
    'org_descendants(text)',
    'current_app_account()',
    'current_visible_program_ids()',
    'org_unit_is_visible(text)',
    'current_professor_course_ids()',
    'current_student_course_ids()',
    'current_visible_student_ids()',
    'current_visible_course_ids()',
    'current_visible_org_unit_ids()',
    'current_visible_offering_ids()',
    'current_visible_exam_ids()',
    'current_visible_attempt_ids()',
    'current_visible_person_ids()',
    'student_is_visible(text)',
    'course_is_visible(text)',
    'offering_is_visible(text)',
    'exam_is_visible(text)',
    'exam_attempt_is_visible(text, text)',
    'attempt_is_visible(text)',
    'exam_class_average(text)',
    'get_user_for_login(text)',
    'get_exam_averages(text[])',
    'authenticate_api_key(text)',
    'account_password_for_key(text, text)',
    'account_password_for_login(text)',
    'record_password_login(text)',
    'log_chat_query(text, text, text, text, integer, text, integer, text, boolean)'
  ];
begin
  foreach api_role in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = api_role) then
      foreach fn in array sigs loop
        execute format('revoke all on function %s from %I', fn, api_role);
      end loop;
    end if;
  end loop;
end $$;

do $$
declare
  api_role text;
begin
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

create table if not exists public.schema_migrations (
  version text primary key,
  filename text not null,
  applied_at timestamptz not null default now()
);

commit;
