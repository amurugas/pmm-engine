"""Grid-based concrete fiber integration.

This backend intentionally uses the same Whitney-style concrete block and the
same discrete reinforcing bars as the analytical shape backend. Comparisons
therefore isolate spatial integration error rather than material-model error.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, cos, radians, sin

from .geometry import point_in_polygon, polygon_bounds, projection_bounds
from .materials import ConcreteMaterial
from .section import Section
from .solver import BarResponse, CapacityPoint


@dataclass(frozen=True)
class ConcreteFiber:
    x: float
    y: float
    area: float
    material: ConcreteMaterial


@dataclass(frozen=True)
class FiberMesh:
    fibers: tuple[ConcreteFiber, ...]
    target_size: float
    represented_area: float
    exact_area: float

    @property
    def area_error_ratio(self) -> float:
        return (self.represented_area - self.exact_area) / self.exact_area


def mesh_section(
    section: Section, *, divisions_along_longest_dimension: int
) -> FiberMesh:
    """Create a midpoint grid of concrete fibers for every concrete region."""

    if divisions_along_longest_dimension < 2:
        raise ValueError("At least two divisions are required")

    global_min_x = min(polygon_bounds(region.polygon)[0] for region in section.regions)
    global_min_y = min(polygon_bounds(region.polygon)[1] for region in section.regions)
    global_max_x = max(polygon_bounds(region.polygon)[2] for region in section.regions)
    global_max_y = max(polygon_bounds(region.polygon)[3] for region in section.regions)
    longest_dimension = max(
        global_max_x - global_min_x, global_max_y - global_min_y
    )
    target_size = longest_dimension / divisions_along_longest_dimension

    fibers: list[ConcreteFiber] = []
    for region in section.regions:
        min_x, min_y, max_x, max_y = polygon_bounds(region.polygon)
        count_x = max(1, ceil((max_x - min_x) / target_size))
        count_y = max(1, ceil((max_y - min_y) / target_size))
        cell_width = (max_x - min_x) / count_x
        cell_height = (max_y - min_y) / count_y
        cell_area = cell_width * cell_height
        for row in range(count_y):
            y = min_y + (row + 0.5) * cell_height
            for column in range(count_x):
                x = min_x + (column + 0.5) * cell_width
                if point_in_polygon((x, y), region.polygon):
                    fibers.append(
                        ConcreteFiber(
                            x=x,
                            y=y,
                            area=cell_area,
                            material=region.material,
                        )
                    )

    represented_area = sum(fiber.area for fiber in fibers)
    return FiberMesh(
        fibers=tuple(fibers),
        target_size=target_size,
        represented_area=represented_area,
        exact_area=section.gross_area,
    )


def fiber_nominal_capacity(
    section: Section,
    mesh: FiberMesh,
    *,
    neutral_axis_angle_deg: float,
    neutral_axis_depth: float,
) -> CapacityPoint:
    """Calculate nominal resultants by midpoint integration of concrete fibers."""

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

    for fiber in mesh.fibers:
        projection = normal[0] * fiber.x + normal[1] * fiber.y
        block_offset = maximum_projection - fiber.material.beta1 * neutral_axis_depth
        if projection < block_offset:
            continue
        force = fiber.material.block_stress * fiber.area
        concrete_force += force
        axial_force += force
        moment_x += force * (fiber.y - section.reference_y)
        moment_y -= force * (fiber.x - section.reference_x)

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
        for region in section.regions:
            block_offset = (
                maximum_projection - region.material.beta1 * neutral_axis_depth
            )
            if (
                point_in_polygon((bar.x, bar.y), region.polygon)
                and projection >= block_offset
            ):
                displacement_force = region.material.block_stress * bar.area
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
