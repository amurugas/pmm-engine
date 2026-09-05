from pmm_engine.webapp import ASSETS, WEB_ROOT


def test_web_assets_exist() -> None:
    assert all((WEB_ROOT / item[0]).is_file() for item in ASSETS.values())


def test_chart_inspection_controls_are_shipped() -> None:
    html = (WEB_ROOT / "index.html").read_text()
    javascript = (WEB_ROOT / "app.js").read_text()
    for control in (
        "three-zoom",
        "three-zoom-value",
        "reset-view",
        "export-png",
        "chart-tooltip",
        "beam-id",
        "section-shape",
        "diameter",
    ):
        assert f'id="{control}"' in html
    assert "capacityIntersection" in javascript
    assert 'demand.dcr <= 0.90 + 1e-9' in javascript
    assert 'demand.dcr <= 1.00 + 1e-9' in javascript
    assert "max_contour_axial_residual_kip" in javascript
    assert "fitFactor" in javascript
    assert "load-inside" in javascript
    assert "load-outside" in javascript
    assert "demand-label" not in javascript
    assert 'id="show-grid"' not in html
    assert 'id="export-svg"' not in html
    assert 'data-view="response"' in html
    assert 'id="response-load"' in html
    assert html.index('data-view="three"') < html.index('data-view="response"')
    assert "clippedLineToPolygon" in javascript
    assert 'fetch("/api/v1/report"' in javascript


def test_http_server_has_no_result_cache() -> None:
    source = (WEB_ROOT.parent / "webapp.py").read_text()
    assert "AnalysisCache" not in source
    assert '"cached": False' in source
