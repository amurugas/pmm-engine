"""ACI 318-19 strength-reduction and axial-limit layer."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import point_in_polygon, polygon_area_centroid
from .section import Section
from .solver import CapacityPoint


@dataclass(frozen=True)
class ACI31819:
    """ACI 318-19 flexure/axial strength settings for nonprestressed members."""

    transverse_reinforcement: str = "tied"

    def __post_init__(self) -> None:
        if self.transverse_reinforcement not in {"tied", "spiral"}:
            raise ValueError("Transverse reinforcement must be 'tied' or 'spiral'")

    @property
    def compression_phi(self) -> float:
        return 0.65 if self.transverse_reinforcement == "tied" else 0.75

    @property
    def axial_limit_ratio(self) -> float:
        return 0.80 if self.transverse_reinforcement == "tied" else 0.85

    def phi(self, *, extreme_tensile_strain: float, yield_strain: float) -> float:
        lower = self.compression_phi
        upper = 0.90
        if extreme_tensile_strain <= yield_strain:
            return lower
        if extreme_tensile_strain >= yield_strain + 0.003:
            return upper
        return lower + (upper - lower) * (
            (extreme_tensile_strain - yield_strain) / 0.003
        )


@dataclass(frozen=True)
class DesignCapacityPoint:
    nominal: CapacityPoint
    phi: float
    axial_force: float
    moment_x: float
    moment_y: float
    axial_cap: float
    axial_cap_applied: bool


def nominal_concentric_compression(section: Section) -> float:
    """Return P0 using the Whitney block and displaced-concrete convention."""

    force = sum(
        region.material.block_stress * polygon_area_centroid(region.polygon)[0]
        for region in section.regions
    )
    for bar in section.bars:
        containing = next(
            (
                region
                for region in section.regions
                if point_in_polygon((bar.x, bar.y), region.polygon)
            ),
            None,
        )
        displacement = containing.material.block_stress * bar.area if containing else 0.0
        force += bar.material.fy * bar.area - displacement
    return force


def design_capacity(
    section: Section, nominal: CapacityPoint, code: ACI31819 = ACI31819()
) -> DesignCapacityPoint:
    yield_strains = {bar.material.fy / bar.material.elastic_modulus for bar in section.bars}
    if len(yield_strains) > 1:
        raise ValueError("ACI phi calculation currently requires one steel yield strain")
    yield_strain = yield_strains.pop() if yield_strains else 60.0 / 29_000.0
    phi = code.phi(
        extreme_tensile_strain=nominal.extreme_tensile_strain,
        yield_strain=yield_strain,
    )
    uncapped_axial = phi * nominal.axial_force
    axial_cap = (
        code.axial_limit_ratio
        * code.compression_phi
        * nominal_concentric_compression(section)
    )
    axial_force = min(uncapped_axial, axial_cap)
    return DesignCapacityPoint(
        nominal=nominal,
        phi=phi,
        axial_force=axial_force,
        moment_x=phi * nominal.moment_x,
        moment_y=phi * nominal.moment_y,
        axial_cap=axial_cap,
        axial_cap_applied=uncapped_axial > axial_cap,
    )
