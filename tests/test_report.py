from io import BytesIO

from pypdf import PdfReader

from pmm_engine.excel_bridge import calculate_payload
from pmm_engine.report import _axis_ticks, _line_box_intersections, build_pdf_report


def test_pdf_report_contains_structured_tables_and_selected_response() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {"beam_id": "B-PDF"},
            "analysis": {
                "angle_step_deg": 10.0,
                "include_response_diagrams": True,
            },
            "demands": [
                {
                    "label": "PDF-LC",
                    "pu_kip": 500.0,
                    "mux_kip_ft": 300.0,
                    "muy_kip_ft": 100.0,
                }
            ],
        }
    )
    content = build_pdf_report(
        result,
        selected_load_label="PDF-LC",
        input_hash="1" * 64,
    )
    assert content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) == 6
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "1. General Information" in text
    assert "Beam ID: B-PDF" in text
    assert "5. Factored Loads and Corresponding Capacity Ratios" in text
    assert "6.2 Constant-Pu biaxial interaction" in text
    assert "6.3 Controlling Section Strain and Stress" in text
    assert "Design idealization - not a constitutive stress-strain curve" in text


def test_pdf_chart_ticks_and_neutral_axis_clipping_helpers() -> None:
    assert _axis_ticks(-500.0, 500.0) == [-400.0, -200.0, 0.0, 200.0, 400.0]
    segment = _line_box_intersections((0.0, 0.0), (1.0, 0.5), (-10.0, 10.0), (-5.0, 5.0))
    assert segment == ((-10.0, -5.0), (10.0, 5.0))


def test_pdf_report_supports_circular_sections() -> None:
    result = calculate_payload(
        {
            "schema_version": 1,
            "section": {"beam_id": "C-PDF", "shape": "circular", "diameter_in": 24.0},
            "analysis": {"angle_step_deg": 30.0},
            "demands": [],
        }
    )
    reader = PdfReader(BytesIO(build_pdf_report(result)))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Beam ID: C-PDF" in text
    assert "Circular" in text
    assert "Diameter 24.00 in" in text
