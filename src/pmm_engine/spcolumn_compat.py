"""Compatibility adapter for the legacy Stage 4 spColumn file workflow.

The Stage 4 workbook owns orchestration, input-file creation, result parsing,
stress checks, and charts.  This module replaces only the analysis executable:
it reads the workbook-generated CTI file and writes the text artifacts consumed
by the existing VBA.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import cos, hypot, log10, radians, sin, sqrt
import os
from pathlib import Path
import tempfile

Point = tuple[float, float]


@dataclass(frozen=True)
class CTIInput:
    project: str
    column_id: str
    engineer: str
    axis: int
    concrete_strength: float
    concrete_modulus: float
    concrete_block_stress: float
    beta1: float
    concrete_ultimate_strain: float
    steel_yield_strength: float
    steel_modulus: float
    axial_limit_ratio: float
    tension_phi: float
    compression_phi: float
    vertices: tuple[Point, ...]
    bars: tuple[tuple[float, float, float], ...]
    loads: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class SectionProperties:
    area: float
    centroid_x: float
    centroid_y: float
    inertia_x: float
    inertia_y: float
    steel_area: float


@dataclass(frozen=True)
class CapacityState:
    axial_force: float
    moment_x: float
    moment_y: float
    neutral_axis_depth: float
    neutral_axis_angle: float
    tension_depth: float
    extreme_tensile_strain: float
    phi: float


@dataclass(frozen=True)
class DemandCheck:
    load_number: int
    axial_force: float
    moment_x: float
    moment_y: float
    failure: str | None
    capacity_moment_x: float | None = None
    capacity_moment_y: float | None = None
    neutral_axis_depth: float | None = None
    extreme_tensile_strain: float | None = None
    phi: float | None = None
    dcr: float | None = None


@dataclass(frozen=True)
class CompatibilityArtifacts:
    report_text: str
    factored_text: str
    error_text: str | None
    input_sha256: str
    demand_count: int


def parse_cti(text: str) -> CTIInput:
    """Parse the subset of spColumn CTI used by the Stage 4 workbook."""

    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1]
            current = sections.setdefault(name, [])
        elif current is not None and line:
            current.append(line)

    def one(name: str) -> str:
        values = sections.get(name)
        if not values:
            raise ValueError(f"CTI section [{name}] is missing or empty")
        return values[0]

    user_options = _csv_numbers(one("User Options"))
    if len(user_options) < 20:
        raise ValueError("CTI [User Options] does not contain 20 fields")
    axis = int(user_options[3])
    if axis not in {0, 1, 2}:
        raise ValueError("Only X, Y, and biaxial CTI runs are supported")

    material = _csv_numbers(one("Material Properties"))
    if len(material) < 7:
        raise ValueError("CTI [Material Properties] does not contain 7 fields")
    reductions = _csv_numbers(one("Reduction Factors"))
    if len(reductions) < 3:
        raise ValueError("CTI [Reduction Factors] does not contain 3 fields")

    external = sections.get("External Points", [])
    if len(external) < 3 or int(external[0]) != 1:
        raise ValueError("Exactly one external concrete region is required")
    point_count = int(external[1])
    raw_vertices = tuple(_csv_point(line) for line in external[2 : 2 + point_count])
    if len(raw_vertices) != point_count:
        raise ValueError("CTI external-point count does not match its data")
    vertices = raw_vertices[:-1] if raw_vertices[0] == raw_vertices[-1] else raw_vertices
    if len(vertices) < 3:
        raise ValueError("CTI concrete region requires at least three vertices")

    internal = sections.get("Internal Points", ["0"])
    if int(internal[0]) != 0:
        raise ValueError("Internal concrete voids are not yet supported by this adapter")

    bars_section = sections.get("Reinforcement Bars", [])
    if not bars_section:
        raise ValueError("CTI [Reinforcement Bars] is missing")
    bar_count = int(bars_section[0])
    bars = tuple(_csv_bar(line) for line in bars_section[1 : 1 + bar_count])
    if len(bars) != bar_count:
        raise ValueError("CTI reinforcement-bar count does not match its data")

    loads_section = sections.get("Factored Loads", [])
    if not loads_section:
        raise ValueError("CTI [Factored Loads] is missing")
    load_count = int(loads_section[0])
    loads = tuple(_csv_load(line) for line in loads_section[1 : 1 + load_count])
    if len(loads) != load_count:
        raise ValueError("CTI factored-load count does not match its data")

    return CTIInput(
        project=one("Project"),
        column_id=one("Column ID"),
        engineer=one("Engineer"),
        axis=axis,
        concrete_strength=material[0],
        concrete_modulus=material[1],
        concrete_block_stress=material[2],
        beta1=material[3],
        concrete_ultimate_strain=material[4],
        steel_yield_strength=material[5],
        steel_modulus=material[6],
        axial_limit_ratio=reductions[0],
        tension_phi=reductions[1],
        compression_phi=reductions[2],
        vertices=vertices,
        bars=bars,
        loads=loads,
    )


def analyze_cti(text: str, *, depth_sample_count: int = 241) -> CompatibilityArtifacts:
    """Analyze CTI text and return the three legacy Stage 4 artifacts."""

    if depth_sample_count < 81:
        raise ValueError("depth_sample_count must be at least 81")
    model = parse_cti(text)
    solver = _PreparedSection(model)
    if model.axis == 2:
        curves = solver.capacity_curves(depth_sample_count)
        checks = tuple(
            _check_demand(model, solver, curves, number, load)
            for number, load in enumerate(model.loads, start=1)
        )
        factored = _format_factored_surface(model, solver, curves)
        report = _format_biaxial_report(model, solver.properties, checks)
    else:
        checks = ()
        factored = _format_uniaxial_factored(model, solver)
        report = _format_uniaxial_report(model, solver)
    failed = any(item.failure is not None or (item.dcr or 0.0) > 1.0 for item in checks)
    return CompatibilityArtifacts(
        report_text=report,
        factored_text=factored,
        error_text=("1. Section capacity exceeded. Revise design!\n" if failed else None),
        input_sha256=sha256(text.encode("utf-8")).hexdigest(),
        demand_count=len(model.loads),
    )


def run_cti_file(input_path: str | Path) -> dict[str, object]:
    """Analyze one CTI file and atomically publish legacy output files."""

    source = Path(input_path).expanduser().resolve(strict=True)
    if source.suffix.lower() != ".cti":
        raise ValueError("input_path must name a .cti file")
    text = source.read_text(encoding="utf-8-sig")
    artifacts = analyze_cti(text)
    stem = source.with_suffix("")
    report_path = stem.with_suffix(".out")
    factored_path = source.with_name(stem.name + "-factored.txt")
    error_path = source.with_name(stem.name + ".txt - error.log")
    _atomic_write(report_path, artifacts.report_text)
    _atomic_write(factored_path, artifacts.factored_text)
    if artifacts.error_text is None:
        error_path.unlink(missing_ok=True)
    else:
        _atomic_write(error_path, artifacts.error_text)
    return {
        "input_path": str(source),
        "output_path": str(report_path),
        "factored_path": str(factored_path),
        "error_path": str(error_path) if artifacts.error_text is not None else None,
        "input_sha256": artifacts.input_sha256,
        "demand_count": artifacts.demand_count,
    }


class _PreparedSection:
    def __init__(self, model: CTIInput) -> None:
        self.model = model
        self.triangles = _triangulate(model.vertices)
        self.bar_inside_concrete = tuple(
            _point_in_polygon((x, y), model.vertices) for _area, x, y in model.bars
        )
        self.properties = _section_properties(model.vertices, model.bars)
        self.reference_x = self.properties.centroid_x
        self.reference_y = self.properties.centroid_y
        self.block_stress = model.concrete_block_stress
        self.yield_strain = model.steel_yield_strength / model.steel_modulus
        self.axial_minimum = (
            -model.tension_phi * model.steel_yield_strength * self.properties.steel_area
        )
        nominal_p0 = self.block_stress * self.properties.area + sum(
            (model.steel_yield_strength - self.block_stress) * area
            for area, _x, _y in model.bars
        )
        self.factored_concentric_maximum = model.compression_phi * nominal_p0
        self.axial_maximum = (
            model.axial_limit_ratio * self.factored_concentric_maximum
        )

    def response(self, sp_angle: float, depth: float) -> CapacityState:
        model = self.model
        # spColumn's NA-angle zero and moment signs differ from the mechanics
        # kernel convention.  The mapping below was verified against the
        # PMM-A1--L1 v10.10 factored surface supplied with the workbook.
        engine_angle = (sp_angle - 90.0) % 360.0
        angle = radians(engine_angle)
        nx, ny = cos(angle), sin(angle)
        projections = tuple(nx * x + ny * y for x, y in model.vertices)
        maximum_projection = max(projections)
        block_offset = maximum_projection - model.beta1 * depth
        neutral_axis_offset = maximum_projection - depth

        force = 0.0
        moment_x = 0.0
        moment_y = 0.0
        for triangle in self.triangles:
            clipped = _clip_ring(triangle, nx, ny, block_offset)
            if len(clipped) < 3:
                continue
            try:
                area, cx, cy = _ring_properties(clipped)[:3]
            except ValueError:
                continue
            concrete_force = self.block_stress * area
            force += concrete_force
            moment_x += concrete_force * (cy - self.reference_y)
            moment_y -= concrete_force * (cx - self.reference_x)

        minimum_bar_projection = maximum_projection
        extreme_tensile_strain = 0.0
        for (area, x, y), inside_concrete in zip(
            model.bars, self.bar_inside_concrete
        ):
            projection = nx * x + ny * y
            minimum_bar_projection = min(minimum_bar_projection, projection)
            strain = model.concrete_ultimate_strain * (
                projection - neutral_axis_offset
            ) / depth
            extreme_tensile_strain = max(extreme_tensile_strain, -strain)
            steel_stress = max(
                -model.steel_yield_strength,
                min(model.steel_yield_strength, model.steel_modulus * strain),
            )
            net_force = area * steel_stress
            if inside_concrete and projection >= block_offset:
                net_force -= area * self.block_stress
            force += net_force
            moment_x += net_force * (y - self.reference_y)
            moment_y -= net_force * (x - self.reference_x)

        phi = self.phi(extreme_tensile_strain)
        return CapacityState(
            axial_force=phi * force,
            # Convert both moments back to the spColumn/ETABS workbook signs.
            moment_x=-phi * moment_x / 12.0,
            moment_y=-phi * moment_y / 12.0,
            neutral_axis_depth=depth,
            neutral_axis_angle=sp_angle % 360.0,
            tension_depth=maximum_projection - minimum_bar_projection,
            extreme_tensile_strain=extreme_tensile_strain,
            phi=phi,
        )

    def phi(self, tensile_strain: float) -> float:
        model = self.model
        if tensile_strain <= self.yield_strain:
            return model.compression_phi
        if tensile_strain >= self.yield_strain + 0.003:
            return model.tension_phi
        fraction = (tensile_strain - self.yield_strain) / 0.003
        return model.compression_phi + fraction * (
            model.tension_phi - model.compression_phi
        )

    def capacity_curves(
        self, depth_sample_count: int
    ) -> dict[float, tuple[CapacityState, ...]]:
        curves: dict[float, tuple[CapacityState, ...]] = {}
        for sp_angle in range(0, 360, 10):
            angle = radians((sp_angle - 90.0) % 360.0)
            projections = [
                cos(angle) * x + sin(angle) * y for x, y in self.model.vertices
            ]
            section_depth = max(projections) - min(projections)
            depths = _logspace(
                section_depth * 1.0e-6,
                section_depth * 1.0e3,
                depth_sample_count,
            )
            states = tuple(self.response(float(sp_angle), depth) for depth in depths)
            curves[float(sp_angle)] = states
        return curves

    def exact_at_axial(
        self, sp_angle: float, target: float, *, allow_concentric_maximum: bool = False
    ) -> CapacityState:
        upper_limit = (
            self.factored_concentric_maximum
            if allow_concentric_maximum
            else self.axial_maximum
        )
        if target < self.axial_minimum - 1.0e-6 or target > upper_limit + 1.0e-6:
            raise ValueError("Axial force is outside the attainable range")
        angle = radians((sp_angle - 90.0) % 360.0)
        projections = [
            cos(angle) * x + sin(angle) * y for x, y in self.model.vertices
        ]
        section_depth = max(projections) - min(projections)
        lower_depth = max(section_depth * 1.0e-9, 1.0e-12)
        upper_depth = max(section_depth, 1.0)
        lower = self.response(sp_angle, lower_depth)
        upper = self.response(sp_angle, upper_depth)
        while upper.axial_force < target and upper_depth < section_depth * 1.0e9:
            upper_depth *= 2.0
            upper = self.response(sp_angle, upper_depth)
        best = lower if abs(lower.axial_force - target) < abs(upper.axial_force - target) else upper
        tolerance = max(abs(target), self.axial_maximum, 1.0) * 1.0e-9
        for _ in range(100):
            middle_depth = 0.5 * (lower_depth + upper_depth)
            middle = self.response(sp_angle, middle_depth)
            if abs(middle.axial_force - target) < abs(best.axial_force - target):
                best = middle
            if abs(middle.axial_force - target) <= tolerance:
                return middle
            if middle.axial_force < target:
                lower_depth = middle_depth
            else:
                upper_depth = middle_depth
        return best


def _check_demand(
    model: CTIInput,
    solver: _PreparedSection,
    curves: dict[float, tuple[CapacityState, ...]],
    number: int,
    load: tuple[float, float, float],
) -> DemandCheck:
    axial, moment_x, moment_y = load
    if axial < solver.axial_minimum - 1.0e-5:
        return DemandCheck(number, axial, moment_x, moment_y, "Pmin")
    if axial > solver.axial_maximum + 1.0e-5:
        return DemandCheck(number, axial, moment_x, moment_y, "Pmax")

    contour = tuple(
        _refined_at_axial(solver, angle, curves[angle], axial)
        for angle in sorted(curves)
    )
    demand_radius = hypot(moment_x, moment_y)
    if demand_radius <= 1.0e-12:
        state = contour[0]
        return DemandCheck(
            number,
            axial,
            moment_x,
            moment_y,
            None,
            0.0,
            0.0,
            state.neutral_axis_depth,
            state.extreme_tensile_strain,
            state.phi,
            0.0,
        )
    direction = (moment_x / demand_radius, moment_y / demand_radius)
    intersections: list[tuple[float, int, float]] = []
    for index, start_state in enumerate(contour):
        end_state = contour[(index + 1) % len(contour)]
        start = (start_state.moment_x, start_state.moment_y)
        segment = (
            end_state.moment_x - start_state.moment_x,
            end_state.moment_y - start_state.moment_y,
        )
        denominator = _cross(direction, segment)
        if abs(denominator) <= 1.0e-12:
            continue
        ray_distance = _cross(start, segment) / denominator
        segment_fraction = _cross(start, direction) / denominator
        if ray_distance > 1.0e-9 and -1.0e-9 <= segment_fraction <= 1.0 + 1.0e-9:
            intersections.append((ray_distance, index, segment_fraction))
    if not intersections:
        return DemandCheck(number, axial, moment_x, moment_y, "skew")
    # The ACI phi transition can fold a sampled contour back across the same
    # demand ray. spColumn's moment-capacity method uses the outer strength
    # envelope and explicitly omits the artificial transition-zone increase.
    capacity_radius, index, fraction = max(intersections)
    start = contour[index]
    end = contour[(index + 1) % len(contour)]
    depth = _lerp(start.neutral_axis_depth, end.neutral_axis_depth, fraction)
    tensile_strain = _lerp(
        start.extreme_tensile_strain, end.extreme_tensile_strain, fraction
    )
    yield_strain = model.steel_yield_strength / model.steel_modulus
    if tensile_strain <= yield_strain:
        phi = model.compression_phi
    elif tensile_strain >= yield_strain + 0.003:
        phi = model.tension_phi
    else:
        phi = model.compression_phi + (
            (tensile_strain - yield_strain)
            / 0.003
            * (model.tension_phi - model.compression_phi)
        )
    dcr = demand_radius / capacity_radius
    return DemandCheck(
        number,
        axial,
        moment_x,
        moment_y,
        None,
        direction[0] * capacity_radius,
        direction[1] * capacity_radius,
        depth,
        tensile_strain,
        phi,
        dcr,
    )


def _refined_at_axial(
    solver: _PreparedSection,
    angle: float,
    curve: tuple[CapacityState, ...],
    target: float,
    *,
    iterations: int = 10,
) -> CapacityState:
    """Refine a prepared P-M curve locally without repeating global bracketing."""

    if target <= curve[0].axial_force:
        return curve[0]
    crossings = [
        index
        for index in range(1, len(curve))
        if curve[index - 1].axial_force <= target <= curve[index].axial_force
    ]
    if not crossings:
        return curve[-1]
    index = crossings[-1]
    low = curve[index - 1]
    high = curve[index]
    if abs(high.axial_force - low.axial_force) <= 1.0e-12:
        return high
    low_depth = low.neutral_axis_depth
    high_depth = high.neutral_axis_depth
    best = low if abs(low.axial_force - target) < abs(high.axial_force - target) else high
    for _ in range(iterations):
        middle_depth = 0.5 * (low_depth + high_depth)
        middle = solver.response(angle, middle_depth)
        if abs(middle.axial_force - target) < abs(best.axial_force - target):
            best = middle
        if middle.axial_force < target:
            low_depth = middle_depth
        else:
            high_depth = middle_depth
    return best


def _format_biaxial_report(
    model: CTIInput,
    properties: SectionProperties,
    checks: tuple[DemandCheck, ...],
) -> str:
    lines = _report_preamble(model, properties)
    lines.extend(
        [
            "6. Factored Loads and Moments with Corresponding Capacity Ratios",
            "================================================================",
            'NOTE: Calculations are based on "Moment Capacity" Method.',
            "",
            "No.  ------------Demand-------------  -----------Capacity------------  Parameters at Capacity-  Capacity",
            "            Pu        Mux        Muy        phiPn     phiMnx     phiMny  NA Depth       et   phi     Ratio",
            "           kip       k-ft       k-ft        kip       k-ft       k-ft        in",
            "---  --------- ---------- ----------  --------- ---------- ----------  -------- -------- -----  -------- -",
        ]
    )
    for item in checks:
        if item.failure in {"Pmin", "Pmax"}:
            operator = "<" if item.failure == "Pmin" else ">"
            lines.append(
                f"{item.load_number:3d} {item.axial_force:10.2f} {item.moment_x:10.2f} "
                f"{item.moment_y:10.2f}  Pu {operator} {item.failure}     (N/A)"
                f"                                         >1.00 #"
            )
        elif item.failure == "skew":
            lines.append(
                f"{item.load_number:3d} {item.axial_force:10.2f} {item.moment_x:10.2f} "
                f"{item.moment_y:10.2f} {item.axial_force:10.2f}     (N/A)"
                f"                                         >1.00 #"
            )
        else:
            assert item.capacity_moment_x is not None
            assert item.capacity_moment_y is not None
            assert item.neutral_axis_depth is not None
            assert item.extreme_tensile_strain is not None
            assert item.phi is not None
            assert item.dcr is not None
            failed = " #" if item.dcr > 1.0 else ""
            lines.append(
                f"{item.load_number:3d} {item.axial_force:10.2f} {item.moment_x:10.2f} "
                f"{item.moment_y:10.2f} {item.axial_force:10.2f} "
                f"{item.capacity_moment_x:10.2f} {item.capacity_moment_y:10.2f} "
                f"{item.neutral_axis_depth:9.2f} {item.extreme_tensile_strain:8.5f} "
                f"{item.phi:5.3f} {item.dcr:9.2f}{failed}"
            )
    return "\n".join(lines) + "\n"


def _report_preamble(model: CTIInput, properties: SectionProperties) -> list[str]:
    radius_x = sqrt(properties.inertia_x / properties.area)
    radius_y = sqrt(properties.inertia_y / properties.area)
    return [
        " PMM ENGINE spColumn Stage 4 compatibility output v10.00",
        " STRUCTUREPOINT output-contract marker v10-compatible",
        f"Project          {model.project}",
        f"Column ID        {model.column_id}",
        f"Engineer         {model.engineer}",
        "",
        "3. Section",
        "==========",
        "3.1. Shape and Properties",
        "Type     Irregular",
        f"Ag    {properties.area:.8g}  in^2",
        f"Ix    {properties.inertia_x:.8g}  in^4",
        f"Iy    {properties.inertia_y:.8g}  in^4",
        f"rx    {radius_x:.8g}  in",
        f"ry    {radius_y:.8g}  in",
        f"Xo    {properties.centroid_x:.8g}  in",
        f"Yo    {properties.centroid_y:.8g}  in",
        "",
        # Keep the legacy token positions: local_4GetResults reads the fifth
        # whitespace-delimited field as As. Adding an '=' shifts the numeric
        # field and propagates #VALUE! into Design Summary columns AM, U, AR.
        f"Total steel area, As       {properties.steel_area:.8g}  in^2",
        "",
    ]


def _format_uniaxial_report(model: CTIInput, solver: _PreparedSection) -> str:
    positive_angle, negative_angle = ((0.0, 180.0) if model.axis == 0 else (90.0, 270.0))
    target = model.loads[0][0]
    positive = solver.exact_at_axial(positive_angle, target)
    negative = solver.exact_at_axial(negative_angle, target)
    component = "phiMnx" if model.axis == 0 else "phiMny"
    lines = _report_preamble(model, solver.properties)
    lines.extend(
        [
            "6. Axial Loads and Corresponding Moment Capacities",
            "==================================================",
            "",
            f"No     phiPn       {component}  NA Depth  dt Depth       et      phi",
            "       kip       k-ft        in        in",
            "-- ------- ---------- --------- --------- --------- ------",
        ]
    )
    for number, state in enumerate((positive, negative), start=1):
        moment = state.moment_x if model.axis == 0 else state.moment_y
        lines.append(
            f"{number:2d} {target:7.1f} {moment:10.2f} {state.neutral_axis_depth:9.3f} "
            f"{state.tension_depth:9.3f} {state.extreme_tensile_strain:8.5f} {state.phi:6.3f}"
        )
    return "\n".join(lines) + "\n"


def _format_factored_surface(
    model: CTIInput,
    solver: _PreparedSection,
    curves: dict[float, tuple[CapacityState, ...]],
) -> str:
    positive = [
        solver.factored_concentric_maximum * (1.0 - index / 49.0)
        for index in range(50)
    ]
    # spColumn substitutes the capped axial strength and 0.1 f'c Ag into two
    # otherwise evenly spaced positive-P surface levels.
    positive[10] = solver.axial_maximum
    positive[40] = 0.1 * model.concrete_strength * solver.properties.area
    negative = [solver.axial_minimum * index / 20.0 for index in range(1, 21)]
    levels = positive + negative
    lines = [
        "Axial Force\tMoment X\tMoment Y\tN.A. Depth\tN.A. Angle\tD_t\teps_t\tPhi Factor"
    ]
    for axial in levels:
        for angle in sorted(curves):
            state = (
                solver.exact_at_axial(
                    angle, axial, allow_concentric_maximum=True
                )
                if axial == solver.factored_concentric_maximum
                else _refined_at_axial(solver, angle, curves[angle], axial)
            )
            lines.append(
                f"{axial:.7f}\t{state.moment_x:.7f}\t{state.moment_y:.7f}\t"
                f"{state.neutral_axis_depth:.7f}\t{angle:.7f}\t{state.tension_depth:.7f}\t"
                f"{state.extreme_tensile_strain:.7f}\t{solver.phi(state.extreme_tensile_strain):.7f}"
            )
    return "\n".join(lines) + "\n"


def _format_uniaxial_factored(model: CTIInput, solver: _PreparedSection) -> str:
    target = model.loads[0][0]
    angles = (0.0, 180.0) if model.axis == 0 else (90.0, 270.0)
    states = [solver.exact_at_axial(angle, target) for angle in angles]
    lines = [
        "Axial Force\tMoment X\tMoment Y\tN.A. Depth\tN.A. Angle\tD_t\teps_t\tPhi Factor"
    ]
    for state in states:
        lines.append(
            f"{target:.7f}\t{state.moment_x:.7f}\t{state.moment_y:.7f}\t"
            f"{state.neutral_axis_depth:.7f}\t{state.neutral_axis_angle:.7f}\t"
            f"{state.tension_depth:.7f}\t{state.extreme_tensile_strain:.7f}\t{state.phi:.7f}"
        )
    return "\n".join(lines) + "\n"


def _section_properties(
    vertices: tuple[Point, ...], bars: tuple[tuple[float, float, float], ...]
) -> SectionProperties:
    area, cx, cy, origin_ix, origin_iy = _ring_properties(vertices)
    return SectionProperties(
        area=area,
        centroid_x=cx,
        centroid_y=cy,
        inertia_x=origin_ix - area * cy * cy,
        inertia_y=origin_iy - area * cx * cx,
        steel_area=sum(item[0] for item in bars),
    )


def _ring_properties(vertices: tuple[Point, ...] | list[Point]) -> tuple[float, float, float, float, float]:
    cross_sum = first_x = first_y = inertia_x = inertia_y = 0.0
    for index, (x1, y1) in enumerate(vertices):
        x2, y2 = vertices[(index + 1) % len(vertices)]
        cross = x1 * y2 - x2 * y1
        cross_sum += cross
        first_x += (x1 + x2) * cross
        first_y += (y1 + y2) * cross
        inertia_x += (y1 * y1 + y1 * y2 + y2 * y2) * cross
        inertia_y += (x1 * x1 + x1 * x2 + x2 * x2) * cross
    signed_area = 0.5 * cross_sum
    if abs(signed_area) <= 1.0e-12:
        raise ValueError("Concrete polygon has zero area")
    sign = 1.0 if signed_area > 0.0 else -1.0
    area = abs(signed_area)
    return (
        area,
        first_x / (6.0 * signed_area),
        first_y / (6.0 * signed_area),
        sign * inertia_x / 12.0,
        sign * inertia_y / 12.0,
    )


def _triangulate(vertices: tuple[Point, ...]) -> tuple[tuple[Point, Point, Point], ...]:
    points = list(vertices)
    if _signed_area(points) < 0.0:
        points.reverse()
    indices = list(range(len(points)))
    triangles: list[tuple[Point, Point, Point]] = []
    while len(indices) > 3:
        for position, middle in enumerate(indices):
            before = indices[position - 1]
            after = indices[(position + 1) % len(indices)]
            a, b, c = points[before], points[middle], points[after]
            if _turn(a, b, c) <= 1.0e-10:
                continue
            if any(
                _point_in_triangle(points[item], a, b, c)
                for item in indices
                if item not in {before, middle, after}
            ):
                continue
            triangles.append((a, b, c))
            indices.pop(position)
            break
        else:
            raise ValueError("Concrete polygon could not be triangulated")
    triangles.append(tuple(points[item] for item in indices))
    return tuple(triangles)


def _clip_ring(
    vertices: tuple[Point, ...] | list[Point], nx: float, ny: float, offset: float
) -> tuple[Point, ...]:
    output: list[Point] = []
    for index, start in enumerate(vertices):
        end = vertices[(index + 1) % len(vertices)]
        start_distance = nx * start[0] + ny * start[1] - offset
        end_distance = nx * end[0] + ny * end[1] - offset
        start_inside = start_distance >= -1.0e-12
        end_inside = end_distance >= -1.0e-12
        if start_inside and end_inside:
            output.append(end)
        elif start_inside != end_inside:
            fraction = start_distance / (start_distance - end_distance)
            intersection = (
                start[0] + fraction * (end[0] - start[0]),
                start[1] + fraction * (end[1] - start[1]),
            )
            output.append(intersection)
            if end_inside:
                output.append(end)
    return tuple(output)


def _point_in_triangle(point: Point, a: Point, b: Point, c: Point) -> bool:
    return (
        _turn(a, b, point) >= -1.0e-10
        and _turn(b, c, point) >= -1.0e-10
        and _turn(c, a, point) >= -1.0e-10
    )


def _point_in_polygon(point: Point, vertices: tuple[Point, ...]) -> bool:
    """Return true for points inside or on the boundary of a simple ring."""

    x, y = point
    inside = False
    for index, (x1, y1) in enumerate(vertices):
        x2, y2 = vertices[(index + 1) % len(vertices)]
        cross = _turn((x1, y1), (x2, y2), point)
        if (
            abs(cross) <= 1.0e-9
            and min(x1, x2) - 1.0e-9 <= x <= max(x1, x2) + 1.0e-9
            and min(y1, y2) - 1.0e-9 <= y <= max(y1, y2) + 1.0e-9
        ):
            return True
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if crossing_x > x:
                inside = not inside
    return inside


def _turn(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _signed_area(vertices: list[Point]) -> float:
    return 0.5 * sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(vertices, vertices[1:] + vertices[:1])
    )


def _logspace(start: float, stop: float, count: int) -> tuple[float, ...]:
    low = log10(start)
    step = (log10(stop) - low) / (count - 1)
    return tuple(10.0 ** (low + index * step) for index in range(count))


def _csv_numbers(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",")]


def _csv_point(value: str) -> Point:
    fields = _csv_numbers(value)
    if len(fields) != 2:
        raise ValueError("CTI point rows must contain x,y")
    return fields[0], fields[1]


def _csv_bar(value: str) -> tuple[float, float, float]:
    fields = _csv_numbers(value)
    if len(fields) != 3 or fields[0] <= 0.0:
        raise ValueError("CTI bar rows must contain positive area,x,y")
    return fields[0], fields[1], fields[2]


def _csv_load(value: str) -> tuple[float, float, float]:
    fields = _csv_numbers(value)
    if len(fields) != 3:
        raise ValueError("CTI load rows must contain P,Mx,My")
    return fields[0], fields[1], fields[2]


def _cross(first: Point, second: Point) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _lerp(start: float, end: float, fraction: float) -> float:
    return start + fraction * (end - start)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        # The legacy Stage 4 parser uses VBA ``Line Input #``. Its record
        # scanning depends on Windows CRLF terminators; LF-only output is read
        # as one long record and eventually raises Runtime error 62 while
        # searching for the STRUCTUREPOINT version marker.
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\r\n") as stream:
            stream.write(content)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
