from pytest import approx

from pmm_engine import (
    ConcreteMaterial,
    ConcreteRegion,
    Polygon,
    Section,
    SteelMaterial,
    capacity_at_axial_load,
    nominal_capacity,
    rectangular_perimeter_bars,
)
from pmm_engine.layout import US_BAR_AREAS_IN2


def build_section() -> Section:
    concrete = ConcreteMaterial(fc=4.0)
    steel = SteelMaterial(fy=60.0)
    polygon = Polygon(
        exterior=((-10.0, -15.0), (10.0, -15.0), (10.0, 15.0), (-10.0, 15.0))
    )
    bars = rectangular_perimeter_bars(
        width=20.0,
        depth=30.0,
        centerline_cover=2.0,
        maximum_spacing=6.0,
        bar_area=US_BAR_AREAS_IN2["#8"],
        material=steel,
    )
    return Section(
        regions=(ConcreteRegion(polygon=polygon, material=concrete),), bars=bars
    )


def test_large_neutral_axis_depth_approaches_nominal_concentric_capacity() -> None:
    section = build_section()
    point = nominal_capacity(
        section, neutral_axis_angle_deg=90.0, neutral_axis_depth=30.0e8
    )
    expected = 0.85 * 4.0 * (600.0 - 12.64) + 60.0 * 12.64
    assert point.axial_force == approx(expected, rel=1e-6)
    assert point.moment_x == approx(0.0, abs=1e-3)
    assert point.moment_y == approx(0.0, abs=1e-6)


def test_pure_bending_solution_satisfies_axial_equilibrium() -> None:
    section = build_section()
    point = capacity_at_axial_load(
        section, neutral_axis_angle_deg=90.0, target_axial_force=0.0
    )
    assert point.axial_force == approx(0.0, abs=1e-6)
    assert point.moment_x > 0.0
    assert point.moment_x / 12.0 == approx(781.24, abs=0.01)
    assert point.moment_y == approx(0.0, abs=1e-8)


def test_symmetric_section_has_equal_positive_and_negative_x_capacity() -> None:
    section = build_section()
    positive = capacity_at_axial_load(
        section, neutral_axis_angle_deg=90.0, target_axial_force=0.0
    )
    negative = capacity_at_axial_load(
        section, neutral_axis_angle_deg=-90.0, target_axial_force=0.0
    )
    assert positive.moment_x == approx(-negative.moment_x, rel=1e-10)
    assert positive.extreme_tensile_strain == approx(
        negative.extreme_tensile_strain, rel=1e-10
    )
