"""Starter section: 20 x 30 in with #8 bars at <= 6 in around perimeter."""

from pmm_engine import (
    ACI31819,
    RectangularSectionInput,
    build_rectangular_section,
    capacity_at_axial_load,
    design_capacity,
)


def build_section():
    return build_rectangular_section(
        RectangularSectionInput(
            width=20.0,
            depth=30.0,
            concrete_strength=4.0,
            steel_yield_strength=60.0,
            clear_cover=2.0,
            tie_bar_size="#4",
            longitudinal_bar_size="#8",
            maximum_bar_spacing=6.0,
            name="20x30 - #8 perimeter at 6 in max",
        )
    )


def main() -> None:
    section = build_section()
    pure_bending_x = capacity_at_axial_load(
        section,
        neutral_axis_angle_deg=90.0,
        target_axial_force=0.0,
    )
    pure_bending_y = capacity_at_axial_load(
        section,
        neutral_axis_angle_deg=0.0,
        target_axial_force=0.0,
    )
    design_x = design_capacity(section, pure_bending_x, ACI31819())
    design_y = design_capacity(section, pure_bending_y, ACI31819())

    print(section.name)
    print(f"Gross area: {section.gross_area:.2f} in^2")
    print("Clear cover: 2.00 in to outside of #4 ties")
    print("Longitudinal-bar centerline cover: 3.00 in")
    print(f"Bars: {len(section.bars)} #8")
    print(f"Steel area: {section.steel_area:.2f} in^2")
    print(f"Reinforcement ratio: {100.0 * section.steel_area / section.gross_area:.3f}%")
    print(
        "Nominal pure bending about x: "
        f"Pn={pure_bending_x.axial_force:.6f} kip, "
        f"Mnx={pure_bending_x.moment_x / 12.0:.2f} kip-ft"
    )
    print(
        "Nominal pure bending about y: "
        f"Pn={pure_bending_y.axial_force:.6f} kip, "
        f"Mny={pure_bending_y.moment_y / 12.0:.2f} kip-ft"
    )
    print(f"ACI factored pure bending about x: {design_x.moment_x / 12.0:.2f} kip-ft")
    print(f"ACI factored pure bending about y: {design_y.moment_y / 12.0:.2f} kip-ft")


if __name__ == "__main__":
    main()
