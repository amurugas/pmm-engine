import json

import pytest

from pmm_engine.excel_bridge import calculate_payload


def test_payload_returns_workbook_ready_results() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {"beam_id": "B-42"},
            "analysis": {"angle_step_deg": 10.0},
            "demands": [
                {"label": "LC-1", "pu_kip": 400.0, "mux_kip_ft": 200.0, "muy_kip_ft": 50.0}
            ],
        }
    )
    assert result["section"]["bar_count"] == 14
    assert result["section"]["beam_id"] == "B-42"
    assert result["section"]["name"] == "B-42"
    assert result["section"]["centerline_cover"] == 3.0
    assert len(result["pm_x"]) == 123
    assert len(result["pm_y"]) == 123
    assert result["demands"][0]["label"] == "LC-1"
    assert result["demands"][0]["dcr"] > 0.0
    assert len(result["contours"]) == 36
    assert result["response_diagrams"] == []
    assert result["analysis"]["integration_method"] == "shape"
    assert result["analysis"]["concrete_model"] == "whitney"
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


def test_circular_section_payload_is_workbook_ready() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {
                "beam_id": "C-12",
                "shape": "circular",
                "diameter_in": 24.0,
            },
            "analysis": {"angle_step_deg": 30.0},
            "demands": [
                {"label": "LC-C", "pu_kip": 400.0, "mux_kip_ft": 100.0, "muy_kip_ft": 50.0}
            ],
        }
    )
    assert result["section"]["shape"] == "circular"
    assert result["section"]["diameter"] == 24.0
    assert result["section"]["width"] == result["section"]["depth"] == 24.0
    assert result["section"]["bar_count"] == 10
    assert len(result["contours"]) == 12
    json.dumps(result, allow_nan=False)


def test_radial_dcr_thresholds_for_pure_mx_demands() -> None:
    baseline = calculate_payload(
        {
            "schema_version": 1,
            "section": {},
            "analysis": {"angle_step_deg": 10.0},
            "demands": [
                {"label": "baseline", "pu_kip": 500.0, "mux_kip_ft": 1.0, "muy_kip_ft": 0.0}
            ],
        }
    )
    radius = baseline["demands"][0]["capacity_radius_kip_ft"]
    assert radius is not None

    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {},
            "analysis": {"angle_step_deg": 10.0},
            "demands": [
                {"label": "green", "pu_kip": 500.0, "mux_kip_ft": 0.90 * radius, "muy_kip_ft": 0.0},
                {"label": "amber", "pu_kip": 500.0, "mux_kip_ft": radius, "muy_kip_ft": 0.0},
                {"label": "red", "pu_kip": 500.0, "mux_kip_ft": 1.01 * radius, "muy_kip_ft": 0.0},
            ],
        }
    )
    assert result["demands"][0]["dcr"] == pytest.approx(0.90)
    assert result["demands"][1]["dcr"] == pytest.approx(1.00)
    assert result["demands"][2]["dcr"] == pytest.approx(1.01)
    assert [item["status"] for item in result["demands"]] == ["OK", "OK", "NG"]


def test_fiber_analysis_is_wired_through_pmm_and_dcr_results() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {},
            "analysis": {
                "concrete_model": "whitney",
                "integration_method": "fiber",
                "fiber_divisions": 10,
                "angle_step_deg": 90.0,
            },
            "demands": [
                {
                    "label": "fiber-check",
                    "pu_kip": 0.0,
                    "mux_kip_ft": 100.0,
                    "muy_kip_ft": 0.0,
                }
            ],
        }
    )
    assert result["analysis"]["integration_method"] == "fiber"
    assert result["analysis"]["fiber_count"] > 0
    assert result["analysis"]["fiber_target_size_in"] > 0.0
    assert result["demands"][0]["dcr"] > 0.0
    assert result["demands"][0]["max_contour_axial_residual_kip"] >= 0.0
    assert len(result["contours"]) == 4
    assert "axial_residual_kip" in result["contours"][0]
    report = "\n".join(row[0] for row in result["calculation_report"])
    assert "Concrete fiber mesh" in report
    json.dumps(result, allow_nan=False)


def test_selected_load_response_diagram_uses_a_solved_capacity_state() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {},
            "analysis": {
                "angle_step_deg": 10.0,
                "include_response_diagrams": True,
            },
            "demands": [
                {
                    "label": "response",
                    "pu_kip": 500.0,
                    "mux_kip_ft": 300.0,
                    "muy_kip_ft": 100.0,
                }
            ],
        }
    )
    response = result["response_diagrams"][0]
    assert response["available"]
    assert response["direction_error_deg"] <= 10.0
    assert response["maximum_concrete_strain"] == pytest.approx(0.003)
    assert response["block_stress_ksi"] == pytest.approx(3.4)
    assert len(response["bars"]) == result["section"]["bar_count"]
    assert response["steel"]["yield_strain"] == pytest.approx(60.0 / 29_000.0)
    assert response["note"].startswith("Closest solved orientation")
    json.dumps(response, allow_nan=False)


def test_unimplemented_concrete_model_is_rejected_explicitly() -> None:
    with pytest.raises(ValueError, match="not implemented"):
        calculate_payload(
            {
                "schema_version": 1,
                "section": {},
                "analysis": {"concrete_model": "razvi"},
                "demands": [],
            }
        )
