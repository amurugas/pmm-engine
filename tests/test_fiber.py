from math import hypot

from pytest import approx

from pmm_engine import (
    capacity_at_axial_load,
    fiber_nominal_capacity,
    mesh_section,
)

from examples.rectangular_20x30 import build_section


def test_rectangular_grid_preserves_gross_area() -> None:
    section = build_section()
    for divisions in (10, 20, 40):
        mesh = mesh_section(
            section, divisions_along_longest_dimension=divisions
        )
        assert mesh.represented_area == approx(section.gross_area, rel=1e-12)


def test_fine_fiber_mesh_approaches_shape_solution_at_same_strain_plane() -> None:
    section = build_section()
    shape = capacity_at_axial_load(
        section,
        neutral_axis_angle_deg=37.0,
        target_axial_force=1_000.0,
    )
    mesh = mesh_section(section, divisions_along_longest_dimension=160)
    fiber = fiber_nominal_capacity(
        section,
        mesh,
        neutral_axis_angle_deg=37.0,
        neutral_axis_depth=shape.neutral_axis_depth,
    )

    shape_magnitude = hypot(shape.moment_x, shape.moment_y)
    fiber_magnitude = hypot(fiber.moment_x, fiber.moment_y)
    assert fiber.axial_force == approx(shape.axial_force, rel=0.01)
    assert fiber_magnitude == approx(shape_magnitude, rel=0.01)


def test_bar_responses_are_identical_between_backends() -> None:
    section = build_section()
    mesh = mesh_section(section, divisions_along_longest_dimension=20)
    shape = capacity_at_axial_load(
        section, neutral_axis_angle_deg=90.0, target_axial_force=0.0
    )
    fiber = fiber_nominal_capacity(
        section,
        mesh,
        neutral_axis_angle_deg=90.0,
        neutral_axis_depth=shape.neutral_axis_depth,
    )
    for shape_bar, fiber_bar in zip(shape.bar_responses, fiber.bar_responses):
        assert fiber_bar.strain == approx(shape_bar.strain)
        assert fiber_bar.stress == approx(shape_bar.stress)
        assert fiber_bar.force == approx(shape_bar.force)
