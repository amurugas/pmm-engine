"""Convenience builders that turn design inputs into mechanics models."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Polygon
from .layout import (
    US_BAR_AREAS_IN2,
    longitudinal_bar_centerline_cover,
    rectangular_perimeter_bars,
)
from .materials import ConcreteMaterial, SteelMaterial
from .section import ConcreteRegion, Section


@dataclass(frozen=True)
class RectangularSectionInput:
    width: float = 20.0
    depth: float = 30.0
    concrete_strength: float = 4.0
    steel_yield_strength: float = 60.0
    clear_cover: float = 2.0
    tie_bar_size: str = "#4"
    longitudinal_bar_size: str = "#8"
    maximum_bar_spacing: float = 6.0
    name: str = "20x30 rectangular section"

    @property
    def centerline_cover(self) -> float:
        return longitudinal_bar_centerline_cover(
            clear_cover=self.clear_cover,
            tie_bar_size=self.tie_bar_size,
            longitudinal_bar_size=self.longitudinal_bar_size,
        )


def build_rectangular_section(inputs: RectangularSectionInput) -> Section:
    if inputs.tie_bar_size not in {"#3", "#4", "#5", "#6"}:
        raise ValueError("Tie bar size must be one of #3, #4, #5, or #6")
    try:
        bar_area = US_BAR_AREAS_IN2[inputs.longitudinal_bar_size]
    except KeyError as error:
        raise ValueError(
            f"Unsupported longitudinal bar size: {inputs.longitudinal_bar_size}"
        ) from error

    concrete = ConcreteMaterial(fc=inputs.concrete_strength)
    steel = SteelMaterial(fy=inputs.steel_yield_strength)
    half_width = 0.5 * inputs.width
    half_depth = 0.5 * inputs.depth
    rectangle = Polygon(
        exterior=(
            (-half_width, -half_depth),
            (half_width, -half_depth),
            (half_width, half_depth),
            (-half_width, half_depth),
        )
    )
    bars = rectangular_perimeter_bars(
        width=inputs.width,
        depth=inputs.depth,
        centerline_cover=inputs.centerline_cover,
        maximum_spacing=inputs.maximum_bar_spacing,
        bar_area=bar_area,
        material=steel,
    )
    return Section(
        regions=(ConcreteRegion(polygon=rectangle, material=concrete),),
        bars=bars,
        name=inputs.name,
    )
