# AI layer

Dashboard numbers are deterministic. The model may explain them, and it may
draft a chat query, but it does not invent metrics, warnings, or permissions.

## Request path

Dashboard KPIs, charts and tables load through their own FastAPI endpoints.

AI is a separate React Query:

`getAiDecision(filters)` → `POST /api/ai/decision`

The dashboard renders immediately. AI shows a skeleton, then content, or a
non-blocking message if it is slow or unavailable.

## Combined decision

One backend orchestration (`get_ai_decision`) loads `load_ai_context` once
for the authenticated role and current filters, then derives:

- insight
- current standing
- structured recommendations with “Based on” evidence

The previous three parallel endpoints (`/api/insights`, `/api/predictions`,
`/api/recommendations`) still exist but each now reuses the combined path.

```text
POST /api/ai/decision
        ↓
validate filters
        ↓
load one filtered context
        ↓
insight + current standing + recommendations
        ↓
cache
```

## Why the old path timed out

Root cause (not “the model was slow”):

1. The UI fired three heavy requests at once.
2. Each request re-ran the same management / integrity / item-analysis work.
3. Integrity and related helpers loaded broad attempt sets and grouped them
   in Python.
4. The connection pool held a connection for the whole request with no
   statement timeout, so overlapping calls queued behind each other.

Fixes: one shared context, SQL aggregation (including integrity medians / IP
grouping and a SQL `LIMIT` on top flagged attempts), `statement_timeout`,
`asyncio.wait_for` budget (`AI_BUDGET_SECONDS`, default 8), frontend
`AbortController` (~12s), and a short in-process cache.

Do not “fix” remaining slowness by raising those timeouts.

## Current standing vs prediction

When fewer than three yearly transcript averages exist in the authorized
scope, the UI label is **Current standing**, `kind` is `current_standing`,
and the copy states that the numbers are not a forecast.

When three or more yearly averages exist in that same scope, `kind` is
`forecast`. The value comes from ordinary least squares on those averages
(`ols_linear_v1` in `backend/services/predictions.py`): next-period estimate,
observation count, and a residual interval. The model only narrates that
result. Yearly averages are filtered with the same scope as the rest of
analytics, not from a global history query.

## Filters

AI uses the same `AnalyticsFilters` as the dashboard. Cache keys include the
authenticated user, role, scope, filters, academic year, term and data
version. The cache is not a security boundary.

The university president landing view, with no sector and no college selected,
describes the whole university from the SQL totals (student pass rate,
attendance, students who sat, exams). Choosing a sector or a college narrows
those sentences to that scope. Sector deans stay inside their sector.

## Limitations

- Dashboard KPIs and warning rules are deterministic. The model does not
  create them.
- Optional narrative rephrasing (`AI_NARRATIVE_ENABLED`) sends the SQL
  sentences to the model in one call. A sentence is discarded when it
  introduces a number that was not in the metrics, and the SQL wording stays.
- Chat (`POST /api/chat`) can call an OpenAI-compatible model. SQL is
  validated and scoped before execution. Empty results are reported as empty.
- In-process cache only (single instance, bounded eviction).
- Integrity “risk scores” are fused from recorded signals, not a trained model.
- Unit tests mock the model. They do not measure production model latency.
