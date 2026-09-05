"""Concrete section and discrete reinforcement data models."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Polygon, polygon_area_centroid
from .materials import ConcreteMaterial, SteelMaterial


@dataclass(frozen=True)
class ConcreteRegion:
    polygon: Polygon
    material: ConcreteMaterial


@dataclass(frozen=True)
class Rebar:
    x: float
    y: float
    area: float
    material: SteelMaterial
    label: str = ""

    def __post_init__(self) -> None:
        if self.area <= 0.0:
            raise ValueError("Reinforcing bar area must be positive")


@dataclass(frozen=True)
class Section:
    regions: tuple[ConcreteRegion, ...]
    bars: tuple[Rebar, ...] = ()
    reference_x: float | None = None
    reference_y: float | None = None
    name: str = ""

    def __post_init__(self) -> None:
        if not self.regions:
            raise ValueError("A section requires at least one concrete region")
        if self.reference_x is None or self.reference_y is None:
            area = 0.0
            first_x = 0.0
            first_y = 0.0
            for region in self.regions:
                region_area, cx, cy = polygon_area_centroid(region.polygon)
                area += region_area
                first_x += region_area * cx
                first_y += region_area * cy
            if self.reference_x is None:
                object.__setattr__(self, "reference_x", first_x / area)
            if self.reference_y is None:
                object.__setattr__(self, "reference_y", first_y / area)

    @property
    def gross_area(self) -> float:
        return sum(polygon_area_centroid(region.polygon)[0] for region in self.regions)

    @property
    def steel_area(self) -> float:
        return sum(bar.area for bar in self.bars)
