import asyncio
from unittest.mock import AsyncMock, patch

from schemas.filters import AnalyticsFilters
from services import ai_cache
from services.ai_insights import get_ai_decision
from tests.helpers import make_scope, make_user


def setup_function():
    ai_cache.clear()


def test_cache_keys_isolate_users_and_filters():
    a = make_user(make_scope(user_id="u1", role="senior_management"))
    b = make_user(make_scope(user_id="u2", role="senior_management"))
    filters = AnalyticsFilters(sector_id="sec-a", college_id="col-a")
    key_a = ai_cache.make_cache_key(a, filters)
    key_b = ai_cache.make_cache_key(b, filters)
    assert key_a != key_b
    other_filters = AnalyticsFilters(sector_id="sec-b", college_id="col-a")
    assert ai_cache.make_cache_key(a, filters) != ai_cache.make_cache_key(
        a, other_filters
    )


def test_cache_evicts_when_full():
    ai_cache.clear()
    original = ai_cache._MAX_ENTRIES
    ai_cache._MAX_ENTRIES = 2
    try:
        ctx_a = make_user(make_scope(user_id="u-a"))
        ctx_b = make_user(make_scope(user_id="u-b"))
        ctx_c = make_user(make_scope(user_id="u-c"))
        filters = AnalyticsFilters(sector_id="sec-a", college_id="col-a")
        ai_cache.set(ai_cache.make_cache_key(ctx_a, filters), {"n": 1}, ttl=60)
        ai_cache.set(ai_cache.make_cache_key(ctx_b, filters), {"n": 2}, ttl=60)
        ai_cache.set(ai_cache.make_cache_key(ctx_c, filters), {"n": 3}, ttl=60)
        assert len(ai_cache._CACHE) <= 2
    finally:
        ai_cache._MAX_ENTRIES = original
        ai_cache.clear()

    async def run():
        ctx = make_user(make_scope())
        filters = AnalyticsFilters(sector_id="sec-a", college_id="col-a")

        async def boom(coro, timeout):
            if hasattr(coro, "close"):
                coro.close()
            raise asyncio.TimeoutError

        with patch("services.ai_insights.asyncio.wait_for", side_effect=boom):
            result = await get_ai_decision(ctx, AsyncMock(), filters)
        assert result["status"] == "timeout"
        assert result["insight"] is None
        assert "longer than expected" in result["message"]

    asyncio.run(run())


def test_ai_decision_loads_shared_context_once_and_keeps_filters():
    async def run():
        ctx = make_user(make_scope())
        filters = AnalyticsFilters(sector_id="sec-a", college_id="col-a")
        overview = {
            "passRateByCollege": [
                {"college": "CS", "passRate": 61, "participants": 40, "courses": 2}
            ],
            "passRateByCourse": [
                {"course": "CS201", "passRate": 58, "participants": 20}
            ],
            "kpis": [],
            "insight": "",
        }
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=1)
        db.fetch = AsyncMock(return_value=[])
        with patch(
            "services.ai_insights.load_ai_context", new_callable=AsyncMock
        ) as loader:
            loader.return_value = {"overview": overview}
            result = await get_ai_decision(ctx, db, filters)
        assert loader.await_count == 1
        assert loader.await_args.args[2] is filters
        assert result["status"] == "ok"
        assert result["insight"]["headline"]
        assert result["prediction"]["kind"] == "current_standing"
        assert result["prediction"]["rows"]
        recs = result["recommendations"]
        assert recs is None or recs["items"]
        if recs:
            assert recs["items"][0]["basedOn"]["evidence"]

    asyncio.run(run())


def test_cache_evicts_when_full():
    original = ai_cache._MAX_ENTRIES
    ai_cache._MAX_ENTRIES = 2
    try:
        ctx_a = make_user(make_scope(user_id="u-a"))
        ctx_b = make_user(make_scope(user_id="u-b"))
        ctx_c = make_user(make_scope(user_id="u-c"))
        filters = AnalyticsFilters(sector_id="sec-a", college_id="col-a")
        ai_cache.set(ai_cache.make_cache_key(ctx_a, filters), {"n": 1}, ttl=60)
        ai_cache.set(ai_cache.make_cache_key(ctx_b, filters), {"n": 2}, ttl=60)
        ai_cache.set(ai_cache.make_cache_key(ctx_c, filters), {"n": 3}, ttl=60)
        assert len(ai_cache._CACHE) <= 2
    finally:
        ai_cache._MAX_ENTRIES = original
        ai_cache.clear()
