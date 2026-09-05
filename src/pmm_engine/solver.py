"""Nominal axial-flexural section analysis."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin

from .geometry import (
    Polygon,
    clip_polygon_half_plane,
    point_in_polygon,
    polygon_area_centroid,
    projection_bounds,
)
from .section import Section


@dataclass(frozen=True)
class BarResponse:
    label: str
    x: float
    y: float
    strain: float
    stress: float
    force: float
    concrete_displacement_force: float


@dataclass(frozen=True)
class CapacityPoint:
    axial_force: float
    moment_x: float
    moment_y: float
    neutral_axis_angle_deg: float
    neutral_axis_depth: float
    neutral_axis_offset: float
    extreme_tensile_strain: float
    concrete_force: float
    bar_responses: tuple[BarResponse, ...]


def nominal_capacity(
    section: Section, *, neutral_axis_angle_deg: float, neutral_axis_depth: float
) -> CapacityPoint:
    """Calculate a nominal capacity point for a neutral-axis strain state."""

    if neutral_axis_depth <= 0.0:
        raise ValueError("Neutral-axis depth must be positive")

    ultimate_strains = {region.material.eps_cu for region in section.regions}
    if len(ultimate_strains) != 1:
        raise ValueError(
            "All concrete regions must currently use the same ultimate strain"
        )
    concrete_ultimate_strain = ultimate_strains.pop()

    angle = radians(neutral_axis_angle_deg)
    normal = (cos(angle), sin(angle))
    maximum_projection = max(
        projection_bounds(region.polygon, normal)[1] for region in section.regions
    )
    neutral_axis_offset = maximum_projection - neutral_axis_depth

    axial_force = 0.0
    moment_x = 0.0
    moment_y = 0.0
    concrete_force = 0.0

    # Each concrete material may have a distinct beta1 and block stress.
    block_limits: list[tuple[Polygon, float, float]] = []
    for region in section.regions:
        block_depth = region.material.beta1 * neutral_axis_depth
        block_offset = maximum_projection - block_depth
        block_limits.append(
            (region.polygon, block_offset, region.material.block_stress)
        )
        clipped = clip_polygon_half_plane(region.polygon, normal, block_offset)
        if clipped is None:
            continue
        area, cx, cy = polygon_area_centroid(clipped)
        force = region.material.block_stress * area
        concrete_force += force
        axial_force += force
        moment_x += force * (cy - section.reference_y)
        moment_y -= force * (cx - section.reference_x)

    responses: list[BarResponse] = []
    extreme_tensile_strain = 0.0
    for bar in section.bars:
        projection = normal[0] * bar.x + normal[1] * bar.y
        strain = concrete_ultimate_strain * (
            projection - neutral_axis_offset
        ) / neutral_axis_depth
        stress = bar.material.stress(strain)
        steel_force = stress * bar.area
        displacement_force = 0.0

        # Current sections use non-overlapping concrete regions. If a bar falls
        # in a region's active block, remove the gross concrete assigned to its
        # area before adding the steel force.
        for polygon, block_offset, block_stress in block_limits:
            if (
                point_in_polygon((bar.x, bar.y), polygon)
                and projection >= block_offset
            ):
                displacement_force = block_stress * bar.area
                break

        net_force = steel_force - displacement_force
        axial_force += net_force
        moment_x += net_force * (bar.y - section.reference_y)
        moment_y -= net_force * (bar.x - section.reference_x)
        extreme_tensile_strain = max(extreme_tensile_strain, -strain)
        responses.append(
            BarResponse(
                label=bar.label,
                x=bar.x,
                y=bar.y,
                strain=strain,
                stress=stress,
                force=steel_force,
                concrete_displacement_force=displacement_force,
            )
        )

    return CapacityPoint(
        axial_force=axial_force,
        moment_x=moment_x,
        moment_y=moment_y,
        neutral_axis_angle_deg=neutral_axis_angle_deg,
        neutral_axis_depth=neutral_axis_depth,
        neutral_axis_offset=neutral_axis_offset,
        extreme_tensile_strain=extreme_tensile_strain,
        concrete_force=concrete_force,
        bar_responses=tuple(responses),
    )


def capacity_at_axial_load(
    section: Section,
    *,
    neutral_axis_angle_deg: float,
    target_axial_force: float,
    relative_tolerance: float = 1e-9,
    maximum_iterations: int = 200,
) -> CapacityPoint:
    """Solve neutral-axis depth for a target nominal axial force.

    This bracketed uniaxial building block will later be coupled with an angle
    solver for direct arbitrary-section biaxial demand checks.
    """

    angle = radians(neutral_axis_angle_deg)
    normal = (cos(angle), sin(angle))
    minimum_projection = min(
        projection_bounds(region.polygon, normal)[0] for region in section.regions
    )
    maximum_projection = max(
        projection_bounds(region.polygon, normal)[1] for region in section.regions
    )
    projected_depth = maximum_projection - minimum_projection

    lower_depth = max(projected_depth * 1e-9, 1e-12)
    upper_depth = max(projected_depth, 1.0)
    lower = nominal_capacity(
        section,
        neutral_axis_angle_deg=neutral_axis_angle_deg,
        neutral_axis_depth=lower_depth,
    )
    upper = nominal_capacity(
        section,
        neutral_axis_angle_deg=neutral_axis_angle_deg,
        neutral_axis_depth=upper_depth,
    )

    while upper.axial_force < target_axial_force and upper_depth < projected_depth * 1e9:
        upper_depth *= 2.0
        upper = nominal_capacity(
            section,
            neutral_axis_angle_deg=neutral_axis_angle_deg,
            neutral_axis_depth=upper_depth,
        )

    if not lower.axial_force <= target_axial_force <= upper.axial_force:
        raise ValueError(
            "Target axial force is outside the attainable nominal section range"
        )

    force_scale = max(abs(target_axial_force), section.gross_area, 1.0)
    for _ in range(maximum_iterations):
        middle_depth = 0.5 * (lower_depth + upper_depth)
        middle = nominal_capacity(
            section,
            neutral_axis_angle_deg=neutral_axis_angle_deg,
            neutral_axis_depth=middle_depth,
        )
        if abs(middle.axial_force - target_axial_force) <= relative_tolerance * force_scale:
            return middle
        if middle.axial_force < target_axial_force:
            lower_depth = middle_depth
        else:
            upper_depth = middle_depth

    raise RuntimeError("Axial-force equilibrium did not converge")
