"""Structured PDF calculation report for PMM Engine results."""

from __future__ import annotations

from io import BytesIO
from math import ceil, cos, floor, hypot, log10, pi, radians, sin
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = letter
LEFT = 54.0
RIGHT = PAGE_WIDTH - 54.0
TOP = PAGE_HEIGHT - 104.0
INK = colors.HexColor("#1f2d37")
HEADER = colors.Color(51 / 255, 51 / 255, 51 / 255)
MUTED = colors.HexColor("#697780")
ACCENT = colors.Color(115 / 255, 139 / 255, 193 / 255)
GRID = colors.HexColor("#d9e7ec")
PALE = colors.Color(115 / 255, 139 / 255, 193 / 255)
BLOCK = colors.HexColor("#bddae5")
RED = colors.HexColor("#c74335")


def build_pdf_report(
    result: dict[str, Any], *, selected_load_label: str | None = None, input_hash: str = ""
) -> bytes:
    """Return a polished, print-ready PDF for one PMM analysis result."""

    stream = BytesIO()
    drawing = canvas.Canvas(stream, pagesize=letter, pageCompression=1)
    drawing.setTitle("PMM Engine Section Capacity Report")
    drawing.setAuthor("PMM Engine")
    page_number = 0

    def begin_page() -> None:
        nonlocal page_number
        page_number += 1
        _header(drawing, result, page_number, input_hash)

    def end_page() -> None:
        _footer(drawing, page_number)
        drawing.showPage()

    begin_page()
    _summary_page(drawing, result)
    end_page()

    begin_page()
    _section_page(drawing, result)
    end_page()

    demand_chunks = list(_chunks(result["demands"], 28)) or [[]]
    for chunk_index, demands in enumerate(demand_chunks):
        begin_page()
        _demand_page(drawing, result, demands, continued=chunk_index > 0)
        end_page()

    begin_page()
    _pm_page(drawing, result)
    end_page()

    selected_index = _selected_index(result, selected_load_label)
    if result["demands"]:
        begin_page()
        _mxmy_page(drawing, result, selected_index)
        end_page()

        responses = result.get("response_diagrams", [])
        if selected_index < len(responses) and responses[selected_index].get("available"):
            begin_page()
            _response_page(drawing, result, selected_index)
            end_page()

    drawing.save()
    return stream.getvalue()


def _header(
    drawing: canvas.Canvas,
    result: dict[str, Any],
    page_number: int,
    input_hash: str,
) -> None:
    drawing.setFillColor(HEADER)
    drawing.setFont("Helvetica-Bold", 16)
    drawing.drawString(LEFT, PAGE_HEIGHT - 50, "PMM")
    drawing.setFont("Helvetica", 16)
    drawing.drawString(LEFT + 39, PAGE_HEIGHT - 50, "Engine")
    drawing.setFillColor(ACCENT)
    drawing.setFont("Helvetica-Bold", 7.5)
    drawing.drawString(LEFT, PAGE_HEIGHT - 63, "REINFORCED CONCRETE SECTION CAPACITY")
    drawing.setFillColor(HEADER)
    drawing.setFont("Helvetica-Bold", 10.5)
    drawing.drawRightString(RIGHT, PAGE_HEIGHT - 50, "ACI 318-19")
    drawing.setFillColor(MUTED)
    drawing.setFont("Helvetica", 7.5)
    drawing.drawRightString(RIGHT, PAGE_HEIGHT - 63, f"Page {page_number}")
    drawing.setStrokeColor(HEADER)
    drawing.setLineWidth(1.2)
    drawing.line(LEFT, PAGE_HEIGHT - 71, RIGHT, PAGE_HEIGHT - 71)
    section = result["section"]
    drawing.setFont("Helvetica", 6.8)
    drawing.drawString(
        LEFT + 42,
        PAGE_HEIGHT - 91,
        f"Beam ID: {section.get('beam_id', section['name'])}  |  Units: kip, kip-ft, in  |  Analysis: {result['analysis']['integration_method']}",
    )
    if input_hash:
        drawing.drawRightString(RIGHT, PAGE_HEIGHT - 91, f"Input SHA-256: {input_hash[:16]}...")


def _footer(drawing: canvas.Canvas, page_number: int) -> None:
    drawing.setStrokeColor(HEADER)
    drawing.setLineWidth(1.0)
    drawing.line(LEFT, 35, RIGHT, 35)
    drawing.setFillColor(MUTED)
    drawing.setFont("Helvetica", 7)
    drawing.drawString(LEFT, 23, "Section strength only - see scope limitations in this report.")
    drawing.drawRightString(RIGHT, 23, str(page_number))


def _heading(drawing: canvas.Canvas, text: str, y: float, level: int = 1) -> float:
    drawing.setFillColor(HEADER)
    drawing.setFont("Helvetica-Bold", 10.5 if level == 1 else 9.5)
    drawing.drawString(LEFT + (10 if level > 1 else 0), y, text)
    return y - (18 if level == 1 else 15)


def _table(
    drawing: canvas.Canvas,
    rows: list[list[str]],
    x: float,
    y: float,
    widths: list[float],
    *,
    row_height: float = 15.0,
    header_rows: int = 0,
    right_columns: set[int] | None = None,
) -> float:
    right_columns = right_columns or set()
    total_width = sum(widths)
    for row_index, row in enumerate(rows):
        top = y - row_index * row_height
        if row_index < header_rows:
            drawing.setFillColor(PALE)
            drawing.rect(x, top - row_height, total_width, row_height, fill=1, stroke=0)
            drawing.setFont("Helvetica-Bold", 7.2)
        else:
            drawing.setFont("Helvetica", 7.2)
            if row_index % 2 == 0:
                drawing.setFillColor(colors.HexColor("#f8fafb"))
                drawing.rect(x, top - row_height, total_width, row_height, fill=1, stroke=0)
        drawing.setFillColor(HEADER if row_index < header_rows else INK)
        cursor = x
        for column, (value, width) in enumerate(zip(row, widths)):
            text = str(value)
            if column in right_columns:
                drawing.drawRightString(cursor + width - 4, top - row_height + 4, text)
            else:
                drawing.drawString(cursor + 4, top - row_height + 4, text)
            cursor += width
        drawing.setStrokeColor(colors.HexColor("#b7c0c5"))
        drawing.setLineWidth(0.35)
        drawing.line(x, top - row_height, x + total_width, top - row_height)
    drawing.setStrokeColor(colors.HexColor("#8e989e"))
    drawing.rect(x, y - len(rows) * row_height, total_width, len(rows) * row_height, fill=0, stroke=1)
    return y - len(rows) * row_height


def _summary_page(drawing: canvas.Canvas, result: dict[str, Any]) -> None:
    section = result["section"]
    analysis = result["analysis"]
    y = _heading(drawing, "1. General Information", TOP)
    general = [
        ["Beam ID", section.get("beam_id", section["name"])],
        ["Design code", "ACI 318-19"],
        ["Run option", "Factored PMM strength"],
        ["Capacity method", "Radial contour intersection at constant Pu"],
        ["Concrete integration", analysis["integration_method"].title()],
        ["Neutral-axis increment", f"{analysis['angle_step_deg']:.3f} deg"],
        ["Slenderness", "Not considered"],
    ]
    y = _table(drawing, general, LEFT + 10, y, [140, 250], right_columns={1}) - 24

    y = _heading(drawing, "2. Material Properties", y)
    y = _heading(drawing, "2.1 Concrete", y, 2)
    concrete = [
        ["Property", "Value"],
        ["Concrete strength, f'c", f"{section['concrete_strength']:.3f} ksi"],
        ["Maximum compression strain, eps_cu", "0.003 in/in"],
        ["Equivalent block stress", f"{0.85 * section['concrete_strength']:.3f} ksi"],
        ["Equivalent block beta1", f"{_beta1(section['concrete_strength']):.3f}"],
    ]
    y = _table(drawing, concrete, LEFT + 10, y, [210, 180], header_rows=1, right_columns={1}) - 18
    y = _heading(drawing, "2.2 Reinforcing steel", y, 2)
    steel = [
        ["Property", "Value"],
        ["Yield strength, fy", f"{section['steel_yield_strength']:.3f} ksi"],
        ["Elastic modulus, Es", "29,000 ksi"],
        ["Yield strain, eps_y", f"{section['steel_yield_strength'] / 29000.0:.7f} in/in"],
        ["Stress model", "Elastic-perfectly plastic"],
    ]
    y = _table(drawing, steel, LEFT + 10, y, [210, 180], header_rows=1, right_columns={1}) - 24

    y = _heading(drawing, "3. Section", y)
    width, depth = section["width"], section["depth"]
    if section["shape"] == "circular":
        diameter = section["diameter"]
        dimension_rows = [
            ["Section type", "Circular"],
            ["Diameter", f"{diameter:.3f} in"],
            ["Gross area, Ag", f"{section['gross_area_in2']:.3f} in2"],
            ["Ix", f"{pi * diameter**4 / 64.0:.3f} in4"],
            ["Iy", f"{pi * diameter**4 / 64.0:.3f} in4"],
        ]
    else:
        dimension_rows = [
            ["Section type", "Rectangular"],
            ["Width x depth", f"{width:.3f} x {depth:.3f} in"],
            ["Gross area, Ag", f"{section['gross_area_in2']:.3f} in2"],
            ["Ix", f"{width * depth**3 / 12.0:.3f} in4"],
            ["Iy", f"{depth * width**3 / 12.0:.3f} in4"],
        ]
    properties = [
        ["Property", "Value"],
        *dimension_rows,
        ["Reference centroid", "x = 0.000 in, y = 0.000 in"],
    ]
    _table(drawing, properties, LEFT + 10, y, [210, 180], header_rows=1, right_columns={1})


def _section_page(drawing: canvas.Canvas, result: dict[str, Any]) -> None:
    section = result["section"]
    y = _heading(drawing, "3.1 Section Figure", TOP)
    _draw_section(drawing, result, LEFT + 20, y - 235, 220, 220)
    drawing.setFont("Helvetica-Bold", 7.5)
    drawing.setFillColor(INK)
    drawing.drawCentredString(LEFT + 130, y - 246, "Figure 1: Reinforced concrete section")

    x = LEFT + 275
    y2 = y - 6
    dimensions = (
        f"Diameter {section['diameter']:.2f} in"
        if section["shape"] == "circular"
        else f"{section['width']:.2f} x {section['depth']:.2f} in"
    )
    rows = [
        ["Section summary", "Value"],
        ["Shape", section["shape"].title()],
        ["Dimensions", dimensions],
        ["Clear cover", f"{section['clear_cover']:.3f} in"],
        ["Bar centerline cover", f"{section['centerline_cover']:.3f} in"],
        ["Longitudinal bars", f"{section['bar_count']} - {section['longitudinal_bar_size']}"],
        ["Steel area, Ast", f"{section['steel_area_in2']:.3f} in2"],
        ["Reinforcement ratio", f"{100 * section['reinforcement_ratio']:.3f}%"],
        ["Tie size", section["tie_bar_size"]],
    ]
    _table(drawing, rows, x, y2, [105, 105], header_rows=1, right_columns={1})

    y3 = y - 285
    y3 = _heading(drawing, "4. Reinforcement - Bars Provided", y3)
    bar_rows = [["Bar", "X (in)", "Y (in)", "Area (in2)"]]
    bar_rows.extend(
        [bar["label"], f"{bar['x_in']:.3f}", f"{bar['y_in']:.3f}", f"{bar['area_in2']:.3f}"]
        for bar in result["bars"]
    )
    _table(
        drawing,
        bar_rows,
        LEFT + 10,
        y3,
        [90, 100, 100, 110],
        row_height=13,
        header_rows=1,
        right_columns={1, 2, 3},
    )


def _demand_page(
    drawing: canvas.Canvas,
    result: dict[str, Any],
    demands: list[dict[str, Any]],
    *,
    continued: bool,
) -> None:
    title = "5. Factored Loads and Corresponding Capacity Ratios"
    if continued:
        title += " (continued)"
    y = _heading(drawing, title, TOP)
    drawing.setFillColor(MUTED)
    drawing.setFont("Helvetica", 7)
    drawing.drawString(LEFT, y + 3, "DCR is the demand moment radius divided by radial capacity at the same Pu.")
    y -= 13
    rows = [["Load", "Pu", "Mux", "Muy", "Mr,cap", "DCR", "Status", "Note"]]
    for demand in demands:
        rows.append(
            [
                demand["label"],
                f"{demand['pu_kip']:.2f}",
                f"{demand['mux_kip_ft']:.2f}",
                f"{demand['muy_kip_ft']:.2f}",
                _optional(demand["capacity_radius_kip_ft"], 2),
                _optional(demand["dcr"], 3),
                demand["status"],
                demand["note"][:34],
            ]
        )
    _table(
        drawing,
        rows,
        LEFT,
        y,
        [62, 55, 55, 55, 62, 45, 45, 125],
        row_height=17,
        header_rows=1,
        right_columns={1, 2, 3, 4, 5},
    )
    drawing.setFont("Helvetica", 6.8)
    drawing.setFillColor(MUTED)
    drawing.drawString(LEFT, 74, "Moments are kip-ft; axial forces are kip. Compression is positive.")


def _pm_page(drawing: canvas.Canvas, result: dict[str, Any]) -> None:
    y = _heading(drawing, "6. Diagrams", TOP)
    drawing.setFont("Helvetica-BoldOblique", 9.5)
    drawing.drawString(LEFT + 10, y, "6.1 Factored P-M interaction diagrams")
    demands = result["demands"]
    _draw_xy_chart(
        drawing,
        result["pm_x"],
        [(item["mux_kip_ft"], item["pu_kip"], item["dcr"]) for item in demands],
        LEFT + 16,
        395,
        470,
        235,
        "Mx (kip-ft)",
        "Pu (kip)",
        x_key="moment_kip_ft",
        y_key="pu_kip",
    )
    _draw_xy_chart(
        drawing,
        result["pm_y"],
        [(item["muy_kip_ft"], item["pu_kip"], item["dcr"]) for item in demands],
        LEFT + 16,
        120,
        470,
        235,
        "My (kip-ft)",
        "Pu (kip)",
        x_key="moment_kip_ft",
        y_key="pu_kip",
    )


def _mxmy_page(drawing: canvas.Canvas, result: dict[str, Any], selected_index: int) -> None:
    demand = result["demands"][selected_index]
    y = _heading(drawing, "6.2 Constant-Pu biaxial interaction", TOP)
    drawing.setFont("Helvetica-BoldOblique", 9.5)
    drawing.drawString(LEFT + 10, y, f"Mx-My at Pu = {demand['pu_kip']:.3f} kip - {demand['label']}")
    contour = [
        item for item in result["contours"] if item["demand_label"] == demand["label"]
    ]
    _draw_section(drawing, result, LEFT + 5, 405, 150, 190)
    _draw_xy_chart(
        drawing,
        contour,
        [(demand["mux_kip_ft"], demand["muy_kip_ft"], demand["dcr"])],
        LEFT + 175,
        315,
        330,
        320,
        "Mx (kip-ft)",
        "My (kip-ft)",
        x_key="mx_kip_ft",
        y_key="my_kip_ft",
    )
    rows = [
        ["Load", "Pu", "Mux", "Muy", "Capacity radius", "DCR", "Status"],
        [
            demand["label"],
            f"{demand['pu_kip']:.3f}",
            f"{demand['mux_kip_ft']:.3f}",
            f"{demand['muy_kip_ft']:.3f}",
            _optional(demand["capacity_radius_kip_ft"], 3),
            _optional(demand["dcr"], 3),
            demand["status"],
        ],
    ]
    _table(drawing, rows, LEFT + 10, 270, [70, 62, 62, 62, 98, 55, 55], header_rows=1, right_columns={1, 2, 3, 4, 5})


def _response_page(drawing: canvas.Canvas, result: dict[str, Any], selected_index: int) -> None:
    response = result["response_diagrams"][selected_index]
    y = _heading(drawing, "6.3 Controlling Section Strain and Stress", TOP)
    drawing.setFont("Helvetica-BoldOblique", 9.5)
    drawing.drawString(LEFT + 10, y, f"Selected load: {response['load_label']} - {response['classification']}")
    drawing.setFont("Helvetica", 6.8)
    drawing.setFillColor(MUTED)
    drawing.drawString(LEFT + 10, y - 13, response["note"])
    _draw_response_section(drawing, response, LEFT + 5, 395, 235, 235)
    _draw_strain(drawing, response, LEFT + 270, 395, 235, 235)
    _draw_block(drawing, response, LEFT + 5, 105, 235, 235)
    _draw_steel(drawing, response, LEFT + 270, 105, 235, 235)


def _draw_section(
    drawing: canvas.Canvas, result: dict[str, Any], x: float, y: float, width: float, height: float
) -> None:
    section = result["section"]
    scale = min((width - 24) / section["width"], (height - 32) / section["depth"])
    cx, cy = x + width / 2, y + height / 2
    w, h = section["width"] * scale, section["depth"] * scale
    drawing.setFillColor(colors.HexColor("#e5e8e9"))
    drawing.setStrokeColor(INK)
    if section["shape"] == "circular":
        drawing.circle(cx, cy, w / 2, fill=1, stroke=1)
    else:
        drawing.rect(cx - w / 2, cy - h / 2, w, h, fill=1, stroke=1)
    drawing.setFillColor(colors.black)
    for bar in result["bars"]:
        radius = max(2.2, (bar["area_in2"] / 3.14159) ** 0.5 * scale)
        drawing.circle(cx + bar["x_in"] * scale, cy + bar["y_in"] * scale, radius, fill=1, stroke=0)
    drawing.setFont("Helvetica-Bold", 7)
    drawing.setFillColor(INK)
    dimensions = (
        f"Diameter {section['diameter']:.2f} in"
        if section["shape"] == "circular"
        else f"{section['width']:.2f} x {section['depth']:.2f} in"
    )
    drawing.drawCentredString(cx, y + 3, dimensions)


def _draw_xy_chart(
    drawing: canvas.Canvas,
    data: list[dict[str, Any]],
    loads: list[tuple[float, float, float | None]],
    x: float,
    y: float,
    width: float,
    height: float,
    x_label: str,
    y_label: str,
    *,
    x_key: str,
    y_key: str,
) -> None:
    if not data:
        drawing.setFont("Helvetica", 8)
        drawing.drawString(x, y + height / 2, "No capacity data available at this axial load.")
        return
    values_x = [item[x_key] for item in data] + [item[0] for item in loads]
    values_y = [item[y_key] for item in data] + [item[1] for item in loads]
    minimum_x, maximum_x = min(values_x), max(values_x)
    minimum_y, maximum_y = min(values_y), max(values_y)
    pad_x = max(1.0, (maximum_x - minimum_x) * 0.08)
    pad_y = max(1.0, (maximum_y - minimum_y) * 0.08)
    minimum_x, maximum_x = _nice_domain(minimum_x - pad_x, maximum_x + pad_x)
    minimum_y, maximum_y = _nice_domain(minimum_y - pad_y, maximum_y + pad_y)
    left, right, bottom, top = x + 48, x + width - 12, y + 31, y + height - 12
    sx = lambda value: left + (value - minimum_x) * (right - left) / (maximum_x - minimum_x)
    sy = lambda value: bottom + (value - minimum_y) * (top - bottom) / (maximum_y - minimum_y)
    x_ticks = _axis_ticks(minimum_x, maximum_x)
    y_ticks = _axis_ticks(minimum_y, maximum_y)
    drawing.setStrokeColor(GRID)
    drawing.setLineWidth(0.5)
    for value in x_ticks:
        drawing.line(sx(value), bottom, sx(value), top)
    for value in y_ticks:
        drawing.line(left, sy(value), right, sy(value))
    drawing.setFillColor(MUTED)
    drawing.setFont("Helvetica", 5.8)
    x_step = _nice_step(maximum_x - minimum_x)
    y_step = _nice_step(maximum_y - minimum_y)
    for value in x_ticks:
        drawing.drawCentredString(sx(value), bottom - 9, _axis_value(value, x_step))
    for value in y_ticks:
        drawing.drawRightString(left - 4, sy(value) - 2, _axis_value(value, y_step))
    drawing.setStrokeColor(INK)
    drawing.setLineWidth(0.8)
    x_axis = sy(0.0) if minimum_y <= 0 <= maximum_y else bottom
    y_axis = sx(0.0) if minimum_x <= 0 <= maximum_x else left
    drawing.line(left, x_axis, right, x_axis)
    drawing.line(y_axis, bottom, y_axis, top)
    drawing.setStrokeColor(ACCENT)
    drawing.setLineWidth(1.4)
    path = drawing.beginPath()
    path.moveTo(sx(data[0][x_key]), sy(data[0][y_key]))
    for item in data[1:]:
        path.lineTo(sx(item[x_key]), sy(item[y_key]))
    if x_key == "mx_kip_ft" and y_key == "my_kip_ft" and len(data) > 2:
        path.close()
    drawing.drawPath(path, stroke=1, fill=0)
    for load_x, load_y, dcr in loads:
        drawing.setFillColor(RED if dcr is None or dcr > 1.0 else colors.black)
        drawing.circle(sx(load_x), sy(load_y), 2.5, fill=1, stroke=0)
    drawing.setFillColor(INK)
    drawing.setFont("Helvetica", 7)
    drawing.drawCentredString((left + right) / 2, y + 7, x_label)
    drawing.saveState()
    drawing.translate(x + 8, (bottom + top) / 2)
    drawing.rotate(90)
    drawing.drawCentredString(0, 0, y_label)
    drawing.restoreState()


def _draw_response_section(
    drawing: canvas.Canvas, response: dict[str, Any], x: float, y: float, width: float, height: float
) -> None:
    _panel(drawing, x, y, width, height, "Section strain plane")
    points = [point for polygon in response["section_outlines"] for point in polygon]
    x_min, x_max = min(point["x_in"] for point in points), max(point["x_in"] for point in points)
    y_min, y_max = min(point["y_in"] for point in points), max(point["y_in"] for point in points)
    scale = min((width - 45) / (x_max - x_min), (height - 55) / (y_max - y_min))
    cx, cy = x + width / 2, y + height / 2 - 5
    sx = lambda value: cx + (value - (x_min + x_max) / 2) * scale
    sy = lambda value: cy + (value - (y_min + y_max) / 2) * scale
    boundary = response["section_outlines"][0]
    boundary_path = drawing.beginPath()
    boundary_path.moveTo(sx(boundary[0]["x_in"]), sy(boundary[0]["y_in"]))
    for point in boundary[1:]:
        boundary_path.lineTo(sx(point["x_in"]), sy(point["y_in"]))
    boundary_path.close()
    drawing.saveState()
    drawing.clipPath(boundary_path, stroke=0, fill=0)
    drawing.setFillColor(BLOCK)
    drawing.setStrokeColor(ACCENT)
    for polygon in response["block_polygons"]:
        path = drawing.beginPath()
        path.moveTo(sx(polygon[0]["x_in"]), sy(polygon[0]["y_in"]))
        for point in polygon[1:]:
            path.lineTo(sx(point["x_in"]), sy(point["y_in"]))
        path.close()
        drawing.drawPath(path, fill=1, stroke=1)
    drawing.setFillColor(colors.black)
    for bar in response["bars"]:
        drawing.circle(sx(bar["x_in"]), sy(bar["y_in"]), 2.5, fill=1, stroke=0)
    normal = response["normal"]
    if response["projection_min_in"] <= response["neutral_axis_offset_in"] <= response["projection_max_in"]:
        tangent = (-normal["y"], normal["x"])
        center = (normal["x"] * response["neutral_axis_offset_in"], normal["y"] * response["neutral_axis_offset_in"])
        segment = _line_box_intersections(center, tangent, (x_min, x_max), (y_min, y_max))
        if segment is not None:
            drawing.setStrokeColor(RED)
            drawing.setDash(5, 3)
            drawing.line(sx(segment[0][0]), sy(segment[0][1]), sx(segment[1][0]), sy(segment[1][1]))
            drawing.setDash()
    drawing.restoreState()
    drawing.setStrokeColor(INK)
    drawing.setLineWidth(1.1)
    for polygon in response["section_outlines"]:
        outline = drawing.beginPath()
        outline.moveTo(sx(polygon[0]["x_in"]), sy(polygon[0]["y_in"]))
        for point in polygon[1:]:
            outline.lineTo(sx(point["x_in"]), sy(point["y_in"]))
        outline.close()
        drawing.drawPath(outline, fill=0, stroke=1)


def _draw_strain(
    drawing: canvas.Canvas, response: dict[str, Any], x: float, y: float, width: float, height: float
) -> None:
    _panel(drawing, x, y, width, height, "Section strain distribution")
    values = [response["minimum_section_strain"], response["maximum_concrete_strain"], 0.0]
    values.extend(bar["strain"] for bar in response["bars"])
    low, high = min(values), max(values)
    pad = max(0.0002, (high - low) * 0.12)
    left, right, bottom, top = x + 34, x + width - 12, y + 28, y + height - 35
    sx = lambda value: left + (value - low + pad) * (right - left) / (high - low + 2 * pad)
    sy = lambda value: bottom + (value - response["projection_min_in"]) * (top - bottom) / (response["projection_max_in"] - response["projection_min_in"])
    drawing.setStrokeColor(INK)
    drawing.line(sx(0), bottom, sx(0), top)
    drawing.setStrokeColor(colors.HexColor("#2c756a"))
    drawing.setLineWidth(1.6)
    drawing.line(sx(response["minimum_section_strain"]), bottom, sx(response["maximum_concrete_strain"]), top)
    drawing.setFillColor(colors.black)
    for bar in response["bars"]:
        drawing.circle(sx(bar["strain"]), sy(bar["projection_in"]), 1.8, fill=1, stroke=0)
    drawing.setFillColor(MUTED)
    drawing.setFont("Helvetica", 6.5)
    drawing.drawCentredString((left + right) / 2, y + 8, "strain, eps (in/in)")


def _draw_block(
    drawing: canvas.Canvas, response: dict[str, Any], x: float, y: float, width: float, height: float
) -> None:
    _panel(drawing, x, y, width, height, "ACI equivalent stress block")
    left, right, bottom, top = x + 45, x + width - 18, y + 40, y + height - 38
    sy = lambda value: bottom + (value - response["projection_min_in"]) * (top - bottom) / (response["projection_max_in"] - response["projection_min_in"])
    active = max(response["projection_min_in"], response["block_offset_in"])
    drawing.setFillColor(BLOCK)
    drawing.setStrokeColor(ACCENT)
    drawing.rect(left, sy(active), right - left, top - sy(active), fill=1, stroke=1)
    drawing.setFillColor(INK)
    drawing.setFont("Helvetica", 7)
    drawing.drawCentredString((left + right) / 2, top - 12, f"0.85 f'c = {response['block_stress_ksi']:.3f} ksi")
    drawing.setFillColor(MUTED)
    drawing.setFont("Helvetica", 6.3)
    drawing.drawString(x + 10, y + 21, f"a = beta1 c = {response['block_depth_in']:.3f} in")
    drawing.drawString(x + 10, y + 10, "Design idealization - not a constitutive stress-strain curve")


def _draw_steel(
    drawing: canvas.Canvas, response: dict[str, Any], x: float, y: float, width: float, height: float
) -> None:
    _panel(drawing, x, y, width, height, "Steel stress-strain")
    steel = response["steel"]
    strains = [bar["strain"] for bar in response["bars"]]
    strains.extend([-2.5 * steel["yield_strain"], 2.5 * steel["yield_strain"]])
    low, high = min(strains), max(strains)
    left, right, bottom, top = x + 35, x + width - 12, y + 30, y + height - 35
    sx = lambda value: left + (value - low) * (right - left) / (high - low)
    sy = lambda value: bottom + (value + 1.15 * steel["fy_ksi"]) * (top - bottom) / (2.3 * steel["fy_ksi"])
    drawing.setStrokeColor(INK)
    drawing.line(sx(0), bottom, sx(0), top)
    drawing.line(left, sy(0), right, sy(0))
    values = sorted({low, -steel["yield_strain"], 0.0, steel["yield_strain"], high})
    drawing.setStrokeColor(colors.HexColor("#334b61"))
    drawing.setLineWidth(1.6)
    path = drawing.beginPath()
    for index, strain in enumerate(values):
        stress = max(-steel["fy_ksi"], min(steel["fy_ksi"], steel["elastic_modulus_ksi"] * strain))
        if index == 0:
            path.moveTo(sx(strain), sy(stress))
        else:
            path.lineTo(sx(strain), sy(stress))
    drawing.drawPath(path, fill=0, stroke=1)
    drawing.setFillColor(colors.black)
    for bar in response["bars"]:
        drawing.circle(sx(bar["strain"]), sy(bar["stress_ksi"]), 1.8, fill=1, stroke=0)
    drawing.setFillColor(MUTED)
    drawing.setFont("Helvetica", 6.5)
    drawing.drawCentredString((left + right) / 2, y + 9, "steel strain, eps_s (in/in)")


def _panel(
    drawing: canvas.Canvas, x: float, y: float, width: float, height: float, title: str
) -> None:
    drawing.setFillColor(colors.HexColor("#fbfcfd"))
    drawing.setStrokeColor(colors.HexColor("#d7e0e5"))
    drawing.roundRect(x, y, width, height, 3, fill=1, stroke=1)
    drawing.setFillColor(INK)
    drawing.setFont("Helvetica-Bold", 8.5)
    drawing.drawString(x + 9, y + height - 16, title)


def _selected_index(result: dict[str, Any], selected_label: str | None) -> int:
    if selected_label is not None:
        for index, demand in enumerate(result["demands"]):
            if demand["label"] == selected_label:
                return index
    return 0


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _optional(value: float | None, digits: int) -> str:
    return "N/A" if value is None else f"{value:.{digits}f}"


def _nice_step(span: float, count: int = 5) -> float:
    raw = max(1e-12, span / count)
    power = 10.0 ** floor(log10(raw))
    ratio = raw / power
    factor = 1.0 if ratio <= 1 else 2.0 if ratio <= 2 else 5.0 if ratio <= 5 else 10.0
    return factor * power


def _nice_domain(minimum: float, maximum: float) -> tuple[float, float]:
    if maximum <= minimum:
        padding = max(1.0, abs(minimum) * 0.1)
        minimum -= padding
        maximum += padding
    step = _nice_step(maximum - minimum)
    return floor(minimum / step) * step, ceil(maximum / step) * step


def _axis_ticks(minimum: float, maximum: float) -> list[float]:
    step = _nice_step(maximum - minimum)
    value = ceil((minimum - step * 1e-9) / step) * step
    values: list[float] = []
    while value <= maximum + step * 1e-9 and len(values) < 20:
        values.append(0.0 if abs(value) < step * 1e-9 else value)
        value += step
    return values


def _axis_value(value: float, step: float) -> str:
    digits = max(0, min(5, -floor(log10(step)))) if step < 1.0 else 0
    return f"{value:.{digits}f}"


def _line_box_intersections(
    center: tuple[float, float],
    direction: tuple[float, float],
    x_bounds: tuple[float, float],
    y_bounds: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    points: list[tuple[float, float]] = []
    epsilon = 1e-9

    def add(x_value: float, y_value: float) -> None:
        if not (
            x_bounds[0] - epsilon <= x_value <= x_bounds[1] + epsilon
            and y_bounds[0] - epsilon <= y_value <= y_bounds[1] + epsilon
        ):
            return
        if not any(hypot(x_value - x, y_value - y) < epsilon for x, y in points):
            points.append((x_value, y_value))

    if abs(direction[0]) > epsilon:
        for x_value in x_bounds:
            parameter = (x_value - center[0]) / direction[0]
            add(x_value, center[1] + parameter * direction[1])
    if abs(direction[1]) > epsilon:
        for y_value in y_bounds:
            parameter = (y_value - center[1]) / direction[1]
            add(center[0] + parameter * direction[0], y_value)
    if len(points) < 2:
        return None
    points.sort(
        key=lambda point: (point[0] - center[0]) * direction[0]
        + (point[1] - center[1]) * direction[1]
    )
    return points[0], points[-1]


def _beta1(fc_ksi: float) -> float:
    if fc_ksi <= 4.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksi - 4.0))
