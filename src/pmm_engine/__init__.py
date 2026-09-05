"""Public API for the PMM Engine mechanics kernel."""

from .builders import (
    CircularSectionInput,
    RectangularSectionInput,
    build_circular_section,
    build_rectangular_section,
)
from .design import ACI31819, DesignCapacityPoint, design_capacity
from .fiber import ConcreteFiber, FiberMesh, fiber_nominal_capacity, mesh_section
from .geometry import Polygon, polygon_area_centroid
from .interaction import (
    Demand,
    DemandResult,
    check_demand,
    check_demand_on_contour,
    moment_contour_at_axial_load,
    pm_curve,
)
from .layout import (
    circular_perimeter_bars,
    longitudinal_bar_centerline_cover,
    rectangular_perimeter_bars,
)
from .materials import ConcreteMaterial, SteelMaterial
from .section import ConcreteRegion, Rebar, Section
from .solver import CapacityPoint, capacity_at_axial_load, nominal_capacity

__all__ = [
    "ACI31819",
    "CapacityPoint",
    "ConcreteFiber",
    "ConcreteMaterial",
    "CircularSectionInput",
    "ConcreteRegion",
    "Demand",
    "DemandResult",
    "DesignCapacityPoint",
    "FiberMesh",
    "Polygon",
    "Rebar",
    "RectangularSectionInput",
    "Section",
    "SteelMaterial",
    "build_rectangular_section",
    "build_circular_section",
    "capacity_at_axial_load",
    "check_demand",
    "check_demand_on_contour",
    "circular_perimeter_bars",
    "design_capacity",
    "fiber_nominal_capacity",
    "longitudinal_bar_centerline_cover",
    "mesh_section",
    "moment_contour_at_axial_load",
    "nominal_capacity",
    "pm_curve",
    "polygon_area_centroid",
    "rectangular_perimeter_bars",
]
