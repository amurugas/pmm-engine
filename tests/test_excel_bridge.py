import json

from pmm_engine.excel_bridge import calculate_payload


def test_payload_returns_workbook_ready_results() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {},
            "analysis": {"angle_step_deg": 10.0},
            "demands": [
                {"label": "LC-1", "pu_kip": 400.0, "mux_kip_ft": 200.0, "muy_kip_ft": 50.0}
            ],
        }
    )
    assert result["section"]["bar_count"] == 14
    assert result["section"]["centerline_cover"] == 3.0
    assert len(result["pm_x"]) == 123
    assert len(result["pm_y"]) == 123
    assert result["demands"][0]["label"] == "LC-1"
    assert result["demands"][0]["dcr"] > 0.0
    assert len(result["contours"]) == 36
    report = "\n".join(row[0] for row in result["calculation_report"])
    assert "2. SECTION AND BAR LAYOUT" in report
    assert "DCR=" in report
    assert "deep-beam strut-and-tie" in report


def test_zero_moment_and_out_of_range_demands_are_strict_json_safe() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {},
            "analysis": {"angle_step_deg": 10.0},
            "demands": [
                {"label": "zero", "pu_kip": 0.0, "mux_kip_ft": 0.0, "muy_kip_ft": 0.0},
                {"label": "outside", "pu_kip": 100_000.0, "mux_kip_ft": 1.0, "muy_kip_ft": 1.0},
            ],
        }
    )
    assert result["demands"][0]["dcr"] == 0.0
    assert result["demands"][0]["capacity_radius_kip_ft"] is None
    assert result["demands"][1]["dcr"] is None
    assert result["demands"][1]["status"] == "NG"
    json.dumps(result, allow_nan=False)
