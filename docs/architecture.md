# Architecture

BNU Analytics is a role-scoped assessment reporting system. Production data
flows in one direction:

```text
React / TanStack Router + Query
        |
        |  JWT + analytics filters (sector / college / curriculum / student)
        v
FastAPI routers
        |
        |  UserContext from live user_accounts (not the JWT role claim)
        v
Services
        |
        v
Repositories (parameterized SQL + aggregations)
        |
        v
PostgreSQL / Supabase
        |
        +--> Row Level Security (`app.current_user_id`)
        +--> views such as `v_exam_attempts`
```

The frontend is not a security boundary. Role, scope, sector, college,
curriculum and student identifiers sent by the browser are treated as filter
hints. Authorization is applied in FastAPI against the authenticated account
and again in PostgreSQL RLS.

## Source of truth

- Schema: `db/schema.sql` (fresh install) and `db/migrations/` (existing DBs)
- Application data: PostgreSQL. There is no production mock-data path.
- Official GPA / transcript numbers: `backend/services/gpa.py` and
  `backend/repositories/transcript.py`. React only displays API results.

## Database connection

`DATABASE_URL` is used as supplied. The process does not rewrite the username.
In production the connected role must not have `BYPASSRLS` (Supabase `postgres`
does). Create `app_user`, set its password out of band, and put that role in
`DATABASE_URL` using the exact username your host documents (direct connections
typically use `app_user`; a pooler may require a different form). Migrations
that need DDL should use `DATABASE_ADMIN_URL`.

## Analytics filters

Shared shape:

- `sectorId` → `org_units.level = 'sector'`
- `collegeId` → `org_units.level = 'program'` (UI label is “college”)
- `curriculumId` → `courses.id`
- `studentId` → `students.id`

University-wide senior management must select sector and college before
analytics endpoints return data. Other roles have defaults injected from their
authorized `scope_id` and cannot expand that scope.

Filter options (`GET /api/filter-options`) return only values the caller may
use. Student lists are limited for the UI and, for professors, restricted to
assigned teaching enrollments. Search (`q`) is required once the page is full;
the limit is not a security control.

## AI layer

Dashboard KPIs are repository queries. Insights, warnings, and current
standing are computed from those numbers. `POST /api/chat` is a separate RAG
path: the model may draft SQL, the API validates and scopes it, and RLS
runs it. The model explains authorized rows. It does not choose permissions
or invent metrics.

See `docs/ai.md` and `backend/README.md`.

## Caching

AI results use an in-process TTL cache (`backend/services/ai_cache.py`) with
a bounded size. Cache keys include `user_id`, `person_id`, role, scope,
filters, current academic year, term and a data version so one user’s result
cannot be served to another. The cache is not shared across multiple API
workers and is not a security boundary.

## Local run

Frontend:

```sh
npm install
npm run dev
```

Backend (from `backend/`):

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Put DATABASE_URL and JWT_SECRET in backend/.env (or the repo-root .env)
uvicorn main:app --reload
```

Apply schema or migrations before first use. See `docs/data-model.md`.

## Query performance (measured)

On the seeded local dataset (~200 attempts), `EXPLAIN ANALYZE` of the
management overview attempt aggregate, professor student-option join, and
college-by-sector list completed in **0.4 ms**, **0.16 ms**, and **0.01 ms**.
The college list uses `org_units_level_parent_id_idx`. Seq scans on
`exam_attempts` / `enrollments` were on tables of a few hundred rows; no extra
indexes were added without evidence.
