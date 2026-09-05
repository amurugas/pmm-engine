"""Factored PM curves, biaxial contours, and demand/capacity ratios."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, log10, radians, sin

from .design import ACI31819, DesignCapacityPoint, design_capacity
from .geometry import projection_bounds
from .section import Section
from .solver import nominal_capacity


@dataclass(frozen=True)
class Demand:
    label: str
    axial_force: float
    moment_x: float
    moment_y: float


@dataclass(frozen=True)
class DemandResult:
    demand: Demand
    capacity_radius: float
    demand_radius: float
    dcr: float
    status: str
    contour: tuple[DesignCapacityPoint, ...]


def factored_capacity_at_axial_load(
    section: Section,
    *,
    neutral_axis_angle_deg: float,
    target_axial_force: float,
    code: ACI31819 = ACI31819(),
    relative_tolerance: float = 1e-8,
    maximum_iterations: int = 160,
) -> DesignCapacityPoint:
    """Solve a factored capacity point at Pu for a fixed NA orientation."""

    angle = radians(neutral_axis_angle_deg)
    normal = (cos(angle), sin(angle))
    minima = []
    maxima = []
    for region in section.regions:
        low, high = projection_bounds(region.polygon, normal)
        minima.append(low)
        maxima.append(high)
    projected_depth = max(maxima) - min(minima)
    lower_depth = max(projected_depth * 1e-9, 1e-12)
    upper_depth = max(projected_depth, 1.0)

    def response(depth: float) -> DesignCapacityPoint:
        return design_capacity(
            section,
            nominal_capacity(
                section,
                neutral_axis_angle_deg=neutral_axis_angle_deg,
                neutral_axis_depth=depth,
            ),
            code,
        )

    lower = response(lower_depth)
    upper = response(upper_depth)
    while upper.axial_force < target_axial_force and upper_depth < projected_depth * 1e9:
        upper_depth *= 2.0
        upper = response(upper_depth)

    if target_axial_force > upper.axial_cap * (1.0 + relative_tolerance):
        raise ValueError("Factored axial demand exceeds the ACI axial compression limit")
    if target_axial_force < lower.axial_force:
        raise ValueError("Factored axial demand is below the attainable tension limit")

    force_scale = max(abs(target_axial_force), upper.axial_cap, 1.0)
    for _ in range(maximum_iterations):
        middle_depth = 0.5 * (lower_depth + upper_depth)
        middle = response(middle_depth)
        residual = middle.axial_force - target_axial_force
        if abs(residual) <= relative_tolerance * force_scale:
            return middle
        if residual < 0.0:
            lower_depth = middle_depth
        else:
            upper_depth = middle_depth
    raise RuntimeError("Factored axial-force equilibrium did not converge")


def moment_contour_at_axial_load(
    section: Section,
    *,
    target_axial_force: float,
    angle_step_deg: float = 5.0,
    code: ACI31819 = ACI31819(),
) -> tuple[DesignCapacityPoint, ...]:
    if not 0.0 < angle_step_deg <= 90.0:
        raise ValueError("Angle step must be greater than 0 and no greater than 90 degrees")
    count = max(4, int(round(360.0 / angle_step_deg)))
    return tuple(
        factored_capacity_at_axial_load(
            section,
            neutral_axis_angle_deg=index * 360.0 / count,
            target_axial_force=target_axial_force,
            code=code,
        )
        for index in range(count)
    )


def check_demand(
    section: Section,
    demand: Demand,
    *,
    angle_step_deg: float = 5.0,
    code: ACI31819 = ACI31819(),
) -> DemandResult:
    radius = hypot(demand.moment_x, demand.moment_y)
    try:
        contour = moment_contour_at_axial_load(
            section,
            target_axial_force=demand.axial_force,
            angle_step_deg=angle_step_deg,
            code=code,
        )
    except ValueError:
        return DemandResult(demand, 0.0, radius, float("inf"), "NG", ())

    return check_demand_on_contour(demand, contour)


def check_demand_on_contour(
    demand: Demand, contour: tuple[DesignCapacityPoint, ...]
) -> DemandResult:
    """Check a demand against an already-computed constant-Pu contour."""

    radius = hypot(demand.moment_x, demand.moment_y)
    if not contour:
        return DemandResult(demand, 0.0, radius, float("inf"), "NG", ())
    if radius <= 1e-12:
        return DemandResult(demand, float("inf"), 0.0, 0.0, "OK", contour)
    direction = (demand.moment_x / radius, demand.moment_y / radius)
    capacity_radius = _ray_polygon_capacity(contour, direction)
    dcr = radius / capacity_radius if capacity_radius > 0.0 else float("inf")
    return DemandResult(
        demand=demand,
        capacity_radius=capacity_radius,
        demand_radius=radius,
        dcr=dcr,
        status="OK" if dcr <= 1.0 else "NG",
        contour=contour,
    )


def pm_curve(
    section: Section,
    *,
    positive_angle_deg: float,
    point_count_per_branch: int = 61,
    code: ACI31819 = ACI31819(),
) -> tuple[DesignCapacityPoint, ...]:
    """Return a closed two-branch factored P-M curve."""

    if point_count_per_branch < 3:
        raise ValueError("A PM branch needs at least three points")
    depth = _projected_depth(section, positive_angle_deg)
    depths = _logspace(depth * 1e-5, depth * 1e4, point_count_per_branch)
    positive = [
        design_capacity(
            section,
            nominal_capacity(
                section,
                neutral_axis_angle_deg=positive_angle_deg,
                neutral_axis_depth=value,
            ),
            code,
        )
        for value in depths
    ]
    negative = [
        design_capacity(
            section,
            nominal_capacity(
                section,
                neutral_axis_angle_deg=positive_angle_deg + 180.0,
                neutral_axis_depth=value,
            ),
            code,
        )
        for value in reversed(depths)
    ]
    return tuple(positive + negative + [positive[0]])


def _projected_depth(section: Section, angle_deg: float) -> float:
    angle = radians(angle_deg)
    normal = (cos(angle), sin(angle))
    lows, highs = zip(*(projection_bounds(r.polygon, normal) for r in section.regions))
    return max(highs) - min(lows)


def _logspace(start: float, stop: float, count: int) -> list[float]:
    low = log10(start)
    step = (log10(stop) - low) / (count - 1)
    return [10.0 ** (low + index * step) for index in range(count)]


def _ray_polygon_capacity(
    contour: tuple[DesignCapacityPoint, ...], direction: tuple[float, float]
) -> float:
    intersections: list[float] = []
    coordinates = [(point.moment_x, point.moment_y) for point in contour]
    for index, start in enumerate(coordinates):
        end = coordinates[(index + 1) % len(coordinates)]
        segment = (end[0] - start[0], end[1] - start[1])
        denominator = _cross(direction, segment)
        if abs(denominator) <= 1e-12:
            continue
        ray_distance = _cross(start, segment) / denominator
        segment_fraction = _cross(start, direction) / denominator
        if ray_distance >= -1e-9 and -1e-9 <= segment_fraction <= 1.0 + 1e-9:
            intersections.append(max(0.0, ray_distance))
    if not intersections:
        return 0.0
    return min(value for value in intersections if value > 1e-9)


def _cross(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[1] - first[1] * second[0]
