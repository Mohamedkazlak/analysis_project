# FastAPI backend

One application serves the dashboard, analytics, and RAG chat. PostgreSQL
row-level security is the last boundary. The model only sees rows that both
the API and the database already allowed.

```text
React
  → POST /auth/login with user id and password
  → JWT (user id only)
  → live user_accounts lookup on every request
  → UserContext (role + scope + assignment)
  → repositories or RAG
  → PostgreSQL, with app.current_user_id set
  → RLS
```

## Run

Copy `../.env.example` to `backend/.env` and fill in `DATABASE_URL` and
`JWT_SECRET`. Do not commit that file.

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Run from this directory. Interactive docs: `/docs`.

Apply schema changes with `python run_migration.py` (uses `db/migrations/`
and `DATABASE_ADMIN_URL` when set). Issue login keys with
`python issue_api_keys.py`. Raw keys are written to `.api-keys.local`, which
is gitignored.

## Authentication

`POST /auth/login` accepts `{ "id", "password" }`. The password is checked
against `user_accounts.password_hash`. The account must also have an active
API key; the client does not send that key. A revoked, expired, or missing
key is rejected. The server stores only the SHA-256 hash on `api_keys`. Keys
left over from the old RAG tests have no user id and cannot log in.

The response is a short-lived JWT plus a display profile. The token's only
authorization claim is `user_id`. `GET /auth/me` and every other route call
`get_live_user()`, which reloads role, scope, and assigned courses from the
database. Changing a role in `user_accounts` takes effect on the next request.
An inactive account is rejected.

Later requests send `Authorization: Bearer <JWT>`. The API key is not a
session credential.

## Authorization

Role decides what kind of data is visible. Scope decides which organization
it belongs to. Professors are further limited to `staff_course_assignments`.
Students are limited to their own record.

| Account            | Role                    | Scope                 | Data                                                       |
| ------------------ | ----------------------- | --------------------- | ---------------------------------------------------------- |
| President / VP     | `senior_management`     | university            | All sectors, colleges, courses, students, exams, integrity |
| Sector dean        | `senior_management`     | sector                | That sector only                                           |
| Program director   | `program_director`      | program (college)     | That college                                               |
| Academic affairs   | `academic_affairs`      | program (college)     | That college's academic data, not integrity operations     |
| Professor          | `professor`             | assigned courses      | Those courses, their enrollments, exams, and students      |
| Academic integrity | `it_academic_integrity` | university operations | Exam monitoring and integrity flags, not transcripts       |
| Student            | `student`               | own record            | Own courses, grades, exams, and chat context               |

In this database, College is `org_units.level = program`. There is no separate
faculty or department table. Sector deans use `scope_level = sector`.

The same `UserContext` is passed to dashboard services and to RAG. There is
no second identity type.

## Dashboards and AI

Dashboard numbers come from repository SQL. Insights, warnings, current
standing, and recommendations are computed from those numbers in Python.
Warnings are threshold rules (pass mark, attendance, integrity signals), not
model inventions.

`AI_NARRATIVE_ENABLED=true` lets the model rephrase that text. A rewrite that
introduces a number the metrics did not contain is discarded. If the model is
unavailable, the deterministic text is kept.

Predictions are the current-standing figures in `services/predictions.py`.
The model may explain them. It does not calculate them.

## RAG chat

`POST /api/chat` is the only chat route.

1. The domain gate refuses questions the role is not allowed to ask.
2. The model may draft one `SELECT`, using only that role's tables.
3. `rag/sql_guard.py` rejects mutating SQL, multiple statements, comments,
   subqueries, `UNION`, and tables outside the role.
4. A scope predicate is added for sector, college, assigned courses, or the
   student's own id.
5. The query runs on the shared pool in a read-only transaction with
   `app.current_user_id` set, so RLS still applies.
6. The model explains the returned rows. Empty results stay empty.

Generated SQL is not returned to the client. Question, role, scoped SQL,
row count, latency, model, and success are written through `log_chat_query`
into `chat_query_log`. Result rows and raw API keys are not stored.

Reference notes included in the prompt are filtered by role and scope first.
A student does not receive integrity or university-leadership notes.

## Database

`DATABASE_URL` must be a role that does not bypass RLS (`app_user`).
`DATABASE_ADMIN_URL` is only for migrations and key issuance.

`api_keys` and `chat_query_log` have RLS forced and no direct privileges for
`app_user`, `anon`, or `authenticated`. Login and audit logging go through
`SECURITY DEFINER` functions with a fixed `search_path`. `get_user_for_login`
is not granted to the API role.

See [authorization](../docs/authorization.md) for the filter and RLS map.
