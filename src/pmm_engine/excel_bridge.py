"""JSON and xlwings handoff for the Excel front end."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from math import atan2, ceil, degrees, isfinite
from pathlib import Path
from typing import Any

from .builders import RectangularSectionInput, build_rectangular_section
from .interaction import (
    Demand,
    check_demand_on_contour,
    moment_contour_at_axial_load,
    pm_curve,
)
from .layout import US_BAR_DIAMETERS_IN


def calculate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate workbook-ready PMM results from a versioned input payload."""

    if payload.get("schema_version", 1) != 1:
        raise ValueError("Unsupported input schema version")
    raw_section = payload.get("section", {})
    inputs = RectangularSectionInput(
        width=float(raw_section.get("width_in", 20.0)),
        depth=float(raw_section.get("depth_in", 30.0)),
        concrete_strength=float(raw_section.get("fc_ksi", 4.0)),
        steel_yield_strength=float(raw_section.get("fy_ksi", 60.0)),
        clear_cover=float(raw_section.get("clear_cover_in", 2.0)),
        tie_bar_size=str(raw_section.get("tie_bar_size", "#4")),
        longitudinal_bar_size=str(raw_section.get("longitudinal_bar_size", "#8")),
        maximum_bar_spacing=float(raw_section.get("maximum_spacing_in", 6.0)),
        name=str(raw_section.get("name", "Excel rectangular section")),
    )
    angle_step = float(payload.get("analysis", {}).get("angle_step_deg", 5.0))
    section = build_rectangular_section(inputs)

    demands = [
        Demand(
            label=str(raw.get("label", f"D{index}")),
            axial_force=float(raw.get("pu_kip", 0.0)),
            moment_x=12.0 * float(raw.get("mux_kip_ft", 0.0)),
            moment_y=12.0 * float(raw.get("muy_kip_ft", 0.0)),
        )
        for index, raw in enumerate(payload.get("demands", []), start=1)
    ]
    contour_cache = {}
    for demand in demands:
        if demand.axial_force not in contour_cache:
            try:
                contour_cache[demand.axial_force] = moment_contour_at_axial_load(
                    section,
                    target_axial_force=demand.axial_force,
                    angle_step_deg=angle_step,
                )
            except ValueError:
                contour_cache[demand.axial_force] = ()

    demand_results = []
    contours = []
    for demand in demands:
        result = check_demand_on_contour(demand, contour_cache[demand.axial_force])
        capacity_radius = result.capacity_radius / 12.0
        safe_capacity_radius = capacity_radius if isfinite(capacity_radius) else None
        safe_dcr = result.dcr if isfinite(result.dcr) else None
        if not result.contour:
            note = "Axial demand is outside the attainable factored range"
        elif result.demand_radius <= 1e-12:
            note = "Zero moment demand; moment direction is undefined"
        elif safe_capacity_radius is None or safe_capacity_radius <= 0.0:
            note = "No valid radial intersection was found"
        else:
            note = ""
        demand_results.append(
            {
                "label": demand.label,
                "pu_kip": demand.axial_force,
                "mux_kip_ft": demand.moment_x / 12.0,
                "muy_kip_ft": demand.moment_y / 12.0,
                "moment_angle_deg": degrees(atan2(demand.moment_y, demand.moment_x)),
                "capacity_radius_kip_ft": safe_capacity_radius,
                "dcr": safe_dcr,
                "status": result.status,
                "note": note,
            }
        )
        contours.extend(
            {
                "demand_label": demand.label,
                "pu_kip": point.axial_force,
                "mx_kip_ft": point.moment_x / 12.0,
                "my_kip_ft": point.moment_y / 12.0,
                "phi": point.phi,
            }
            for point in result.contour
        )

    curve_x = pm_curve(section, positive_angle_deg=90.0)
    curve_y = pm_curve(section, positive_angle_deg=0.0)
    onion_rows = []
    if payload.get("analysis", {}).get("include_onion", False):
        onion_step = float(payload.get("analysis", {}).get("onion_angle_step_deg", 10.0))
        raw_levels = payload.get("analysis", {}).get("onion_levels_kip")
        if raw_levels is None:
            minimum = min(point.axial_force for point in curve_x)
            maximum = max(point.axial_force for point in curve_x)
            layer_count = int(payload.get("analysis", {}).get("onion_layer_count", 13))
            if not 3 <= layer_count <= 41:
                raise ValueError("3D onion layer count must be between 3 and 41")
            lower = 0.99 * minimum
            upper = 0.98 * maximum
            raw_levels = [
                lower + index * (upper - lower) / (layer_count - 1)
                for index in range(layer_count)
            ]
        for level in raw_levels:
            axial_level = float(level)
            if axial_level in contour_cache and abs(onion_step - angle_step) < 1e-12:
                layer = contour_cache[axial_level]
            else:
                try:
                    layer = moment_contour_at_axial_load(
                        section,
                        target_axial_force=axial_level,
                        angle_step_deg=onion_step,
                    )
                except ValueError:
                    continue
            onion_rows.append(
                {
                    "pu_kip": axial_level,
                    "points": [
                        {"mx_kip_ft": point.moment_x / 12.0, "my_kip_ft": point.moment_y / 12.0}
                        for point in layer
                    ],
                }
            )
    output = {
        "schema_version": 1,
        "units": {"force": "kip", "moment": "kip-ft", "length": "in"},
        "section": {
            **asdict(inputs),
            "centerline_cover": inputs.centerline_cover,
            "gross_area_in2": section.gross_area,
            "steel_area_in2": section.steel_area,
            "reinforcement_ratio": section.steel_area / section.gross_area,
            "bar_count": len(section.bars),
        },
        "bars": [
            {"label": bar.label, "x_in": bar.x, "y_in": bar.y, "area_in2": bar.area}
            for bar in section.bars
        ],
        "pm_x": [_curve_row(point, "x") for point in curve_x],
        "pm_y": [_curve_row(point, "y") for point in curve_y],
        "demands": demand_results,
        "contours": contours,
        "onion_contours": onion_rows,
        "assumptions": [
            "ACI 318-19 tied-member strength reduction factors",
            "Whitney equivalent rectangular concrete stress block",
            "Elastic-perfectly plastic reinforcing steel",
            "Clear cover is measured to the outside of transverse reinforcement",
            "DCR is a radial intersection with a direct biaxial capacity contour at Pu",
        ],
    }
    output["calculation_report"] = _calculation_report(output)
    return output


def _calculation_report(result: dict[str, Any]) -> list[list[str]]:
    section = result["section"]
    tie_diameter = US_BAR_DIAMETERS_IN[section["tie_bar_size"]]
    longitudinal_diameter = US_BAR_DIAMETERS_IN[section["longitudinal_bar_size"]]
    horizontal_count = ceil(
        (section["width"] - 2.0 * section["centerline_cover"])
        / section["maximum_bar_spacing"]
    ) + 1
    vertical_count = ceil(
        (section["depth"] - 2.0 * section["centerline_cover"])
        / section["maximum_bar_spacing"]
    ) + 1
    lines = [
        ["PMM ENGINE — SECTION STRENGTH CALCULATION"],
        ["ACI 318-19 | US customary units | Compression positive"],
        [""],
        ["1. GIVEN"],
        [f"Section: b = {section['width']:.3f} in, h = {section['depth']:.3f} in"],
        [f"Materials: f'c = {section['concrete_strength']:.3f} ksi, fy = {section['steel_yield_strength']:.3f} ksi"],
        [f"Reinforcement: {section['longitudinal_bar_size']} longitudinal bars; {section['tie_bar_size']} ties"],
        [f"Clear cover = {section['clear_cover']:.3f} in; maximum perimeter spacing = {section['maximum_bar_spacing']:.3f} in"],
        [""],
        ["2. SECTION AND BAR LAYOUT"],
        [f"Longitudinal bar centerline cover = cover + d_tie + d_bar/2 = {section['clear_cover']:.3f} + {tie_diameter:.3f} + {longitudinal_diameter:.3f}/2 = {section['centerline_cover']:.3f} in"],
        [f"Horizontal face bar count = ceil((b - 2c_bar)/s_max) + 1 = {horizontal_count}"],
        [f"Vertical face bar count = ceil((h - 2c_bar)/s_max) + 1 = {vertical_count}"],
        [f"Total unique perimeter bars = 2 n_h + 2(n_v - 2) = {section['bar_count']}"],
        [f"Ag = b h = {section['gross_area_in2']:.3f} in^2"],
        [f"Ast = sum Ab = {section['steel_area_in2']:.3f} in^2"],
        [f"rho_g = Ast/Ag = {section['reinforcement_ratio']:.5f} = {100.0 * section['reinforcement_ratio']:.3f}%"],
        [""],
        ["3. SECTIONAL STRENGTH METHOD"],
        ["Plane sections remain plane; maximum concrete compression strain = 0.003."],
        ["Concrete compression uses the Whitney block: 0.85 f'c over depth a = beta1 c."],
        ["Steel is elastic-perfectly plastic with Es = 29,000 ksi and |fs| <= fy."],
        ["For each neutral-axis orientation, sum axial force and biaxial moments about the gross centroid."],
        ["ACI phi is based on extreme net tensile strain; the tied-column compression limit is 0.80 phi P0."],
        [""],
        ["4. FACTORED DEMAND CHECKS"],
        ["DCR = demand moment-vector radius / radial capacity at the same Pu and moment direction."],
    ]
    for demand in result["demands"]:
        capacity_text = (
            f"{demand['capacity_radius_kip_ft']:.3f}"
            if demand["capacity_radius_kip_ft"] is not None
            else "N/A"
        )
        dcr_text = f"{demand['dcr']:.3f}" if demand["dcr"] is not None else "N/A"
        note_text = f"; {demand['note']}" if demand["note"] else ""
        lines.append(
            [
                f"{demand['label']}: Pu={demand['pu_kip']:.3f} kip, "
                f"Mux={demand['mux_kip_ft']:.3f} kip-ft, Muy={demand['muy_kip_ft']:.3f} kip-ft; "
                f"Mr,cap={capacity_text} kip-ft; "
                f"DCR={dcr_text} -> {demand['status']}{note_text}"
            ]
        )
    lines.extend(
        [
            [""],
            ["5. SCOPE LIMITATIONS"],
            ["Section strength only. Slenderness, second-order effects, shear, deep-beam strut-and-tie, anchorage, and detailing checks are excluded."],
        ]
    )
    return lines


def _curve_row(point, axis: str) -> dict[str, float | bool]:
    moment = point.moment_x if axis == "x" else point.moment_y
    return {
        "pu_kip": point.axial_force,
        "moment_kip_ft": moment / 12.0,
        "phi": point.phi,
        "eps_t": point.nominal.extreme_tensile_strain,
        "axial_cap_applied": point.axial_cap_applied,
    }


def run_workbook() -> None:
    """Read the caller workbook, calculate, and replace output sheets."""

    try:
        import xlwings as xw
    except ImportError as error:
        raise RuntimeError("Install the Excel extra with: pip install pmm-engine[excel]") from error

    book = xw.Book.caller()
    inputs_sheet = book.sheets["Inputs"]
    demands_sheet = book.sheets["Demands"]
    payload = {
        "schema_version": 1,
        "section": {
            "width_in": inputs_sheet.range("B4").value,
            "depth_in": inputs_sheet.range("B5").value,
            "fc_ksi": inputs_sheet.range("B6").value,
            "fy_ksi": inputs_sheet.range("B7").value,
            "clear_cover_in": inputs_sheet.range("B8").value,
            "tie_bar_size": inputs_sheet.range("B9").value,
            "longitudinal_bar_size": inputs_sheet.range("B10").value,
            "maximum_spacing_in": inputs_sheet.range("B11").value,
        },
        "analysis": {"angle_step_deg": inputs_sheet.range("B12").value},
        "demands": [],
    }
    demand_values = demands_sheet.range("A4").expand("table").value or []
    if demand_values and not isinstance(demand_values[0], list):
        demand_values = [demand_values]
    for row in demand_values:
        if row[0] in (None, ""):
            continue
        payload["demands"].append(
            {
                "label": row[0],
                "pu_kip": row[1] or 0.0,
                "mux_kip_ft": row[2] or 0.0,
                "muy_kip_ft": row[3] or 0.0,
            }
        )
    result = calculate_payload(payload)
    _write_workbook_results(book, result)


def _write_workbook_results(book, result: dict[str, Any]) -> None:
    results = book.sheets["Results"]
    rows = [
        [
            item["label"], item["pu_kip"], item["mux_kip_ft"], item["muy_kip_ft"],
            item["moment_angle_deg"], item["capacity_radius_kip_ft"], item["dcr"], item["status"],
        ]
        for item in result["demands"]
    ]
    results.range("A4:H1003").clear_contents()
    if rows:
        results.range("A4").value = rows

    pm_data = book.sheets["PM Data"]
    pm_rows = []
    for index in range(max(len(result["pm_x"]), len(result["pm_y"]))):
        x = result["pm_x"][index] if index < len(result["pm_x"]) else {}
        y = result["pm_y"][index] if index < len(result["pm_y"]) else {}
        pm_rows.append([x.get("moment_kip_ft"), x.get("pu_kip"), y.get("moment_kip_ft"), y.get("pu_kip")])
    pm_data.range("A4:D1000").clear_contents()
    pm_data.range("A4").value = pm_rows

    contours = book.sheets["Contours"]
    contour_rows = [[r["demand_label"], r["pu_kip"], r["mx_kip_ft"], r["my_kip_ft"], r["phi"]] for r in result["contours"]]
    contours.range("A4:E10000").clear_contents()
    if contour_rows:
        contours.range("A4").value = contour_rows

    calculations = book.sheets["Calculations"]
    calculations.range("A1:A200").clear_contents()
    calculations.range("A1").value = result["calculation_report"]
    calculations.autofit("r")


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        print("Usage: python -m pmm_engine.excel_bridge INPUT.json OUTPUT.json", file=sys.stderr)
        return 2
    input_path, output_path = map(Path, arguments)
    output_path.write_text(
        json.dumps(calculate_payload(json.loads(input_path.read_text())), indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
