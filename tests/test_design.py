from pytest import approx

from pmm_engine import (
    ACI31819,
    CircularSectionInput,
    Demand,
    RectangularSectionInput,
    build_circular_section,
    build_rectangular_section,
    check_demand,
    design_capacity,
    nominal_capacity,
)
from pmm_engine.design import nominal_concentric_compression


def build_section():
    return build_rectangular_section(RectangularSectionInput())


def test_clear_cover_and_tie_size_generate_expected_fourteen_bars() -> None:
    inputs = RectangularSectionInput()
    section = build_rectangular_section(inputs)
    assert inputs.centerline_cover == approx(3.0)
    assert len(section.bars) == 14
    assert section.steel_area == approx(14 * 0.79)


def test_circular_section_uses_uniform_perimeter_bar_ring() -> None:
    inputs = CircularSectionInput(diameter=24.0)
    section = build_circular_section(inputs)
    assert len(section.regions[0].polygon.exterior) == 96
    assert len(section.bars) == 10
    assert section.gross_area == approx(3.141592653589793 * 12.0**2, rel=8e-4)
    radii = [(bar.x**2 + bar.y**2) ** 0.5 for bar in section.bars]
    assert radii == approx([9.0] * 10)


def test_aci_phi_limits_and_transition() -> None:
    code = ACI31819(transverse_reinforcement="tied")
    yield_strain = 60.0 / 29_000.0
    assert code.phi(extreme_tensile_strain=0.0, yield_strain=yield_strain) == 0.65
    assert code.phi(
        extreme_tensile_strain=yield_strain + 0.003,
        yield_strain=yield_strain,
    ) == 0.90
    assert code.phi(
        extreme_tensile_strain=yield_strain + 0.0015,
        yield_strain=yield_strain,
    ) == approx(0.775)


def test_tied_axial_cap_is_point_eight_times_phi_p0() -> None:
    section = build_section()
    nominal = nominal_capacity(
        section, neutral_axis_angle_deg=90.0, neutral_axis_depth=1e9
    )
    design = design_capacity(section, nominal)
    assert design.axial_cap_applied
    assert design.axial_force == approx(
        0.80 * 0.65 * nominal_concentric_compression(section), rel=1e-10
    )


def test_biaxial_dcr_is_symmetric_for_swapped_axes_of_square_section() -> None:
    section = build_rectangular_section(
        RectangularSectionInput(width=24.0, depth=24.0)
    )
    first = check_demand(
        section, Demand("A", 400.0, 2_000.0, 1_000.0), angle_step_deg=10.0
    )
    second = check_demand(
        section, Demand("B", 400.0, 1_000.0, 2_000.0), angle_step_deg=10.0
    )
    assert first.dcr == approx(second.dcr, rel=1e-8)


def test_demand_status_uses_direct_biaxial_contour() -> None:
    section = build_section()
    low = check_demand(
        section, Demand("low", 0.0, 12.0, 12.0), angle_step_deg=10.0
    )
    high = check_demand(
        section, Demand("high", 0.0, 120_000.0, 120_000.0), angle_step_deg=10.0
    )
    assert low.status == "OK"
    assert low.dcr < 1.0
    assert high.status == "NG"
    assert high.dcr > 1.0
