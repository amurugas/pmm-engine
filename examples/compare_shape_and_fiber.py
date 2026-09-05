"""Convergence study for analytical shape and midpoint fiber integration."""

from __future__ import annotations

from math import atan2, degrees, hypot

from pmm_engine import (
    capacity_at_axial_load,
    fiber_nominal_capacity,
    mesh_section,
)

from rectangular_20x30 import build_section


def percent_error(value: float, reference: float) -> float:
    return 100.0 * (value - reference) / abs(reference)


def main() -> None:
    section = build_section()
    cases = (
        ("Pure Mx", 90.0, 0.0),
        ("Pure My", 0.0, 0.0),
        ("Oblique", 37.0, 1_000.0),
    )
    divisions = (10, 20, 40, 80, 160)

    print(section.name)
    print(
        "Same strain plane and material laws are used for both backends; "
        "only concrete integration changes."
    )
    for name, angle, axial_force in cases:
        shape = capacity_at_axial_load(
            section,
            neutral_axis_angle_deg=angle,
            target_axial_force=axial_force,
        )
        shape_magnitude = hypot(shape.moment_x, shape.moment_y)
        shape_direction = degrees(atan2(shape.moment_y, shape.moment_x))
        print(
            f"\n{name}: theta={angle:.1f} deg, c={shape.neutral_axis_depth:.5f} in, "
            f"P={shape.axial_force:.3f} kip, |M|={shape_magnitude / 12.0:.3f} kip-ft"
        )
        print(
            " divs  fibers  cell(in)  area err(%)  P residual(k)  "
            "|M| err(%)  dir err(deg)"
        )
        for count in divisions:
            mesh = mesh_section(
                section, divisions_along_longest_dimension=count
            )
            fiber = fiber_nominal_capacity(
                section,
                mesh,
                neutral_axis_angle_deg=angle,
                neutral_axis_depth=shape.neutral_axis_depth,
            )
            fiber_magnitude = hypot(fiber.moment_x, fiber.moment_y)
            fiber_direction = degrees(atan2(fiber.moment_y, fiber.moment_x))
            print(
                f"{count:5d} {len(mesh.fibers):7d} {mesh.target_size:9.4f} "
                f"{100.0 * mesh.area_error_ratio:12.5f} "
                f"{fiber.axial_force - shape.axial_force:14.4f} "
                f"{percent_error(fiber_magnitude, shape_magnitude):11.5f} "
                f"{fiber_direction - shape_direction:13.5f}"
            )


if __name__ == "__main__":
    main()
