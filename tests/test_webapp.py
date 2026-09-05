from pmm_engine.webapp import AnalysisCache, ASSETS, WEB_ROOT


def test_web_assets_exist() -> None:
    assert all((WEB_ROOT / item[0]).is_file() for item in ASSETS.values())


def test_analysis_cache_reuses_identical_payload() -> None:
    cache = AnalysisCache(maximum_entries=2)
    payload = {
        "schema_version": 1,
        "section": {},
        "analysis": {"angle_step_deg": 10.0},
        "demands": [],
    }
    first, first_cached, first_hash = cache.calculate(payload)
    second, second_cached, second_hash = cache.calculate(payload)
    assert not first_cached
    assert second_cached
    assert first is second
    assert first_hash == second_hash
