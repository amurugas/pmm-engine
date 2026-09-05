"""Reinforcing bar layout helpers."""

from __future__ import annotations

from math import ceil, cos, pi, sin

from .materials import SteelMaterial
from .section import Rebar

US_BAR_AREAS_IN2 = {
    "#3": 0.11,
    "#4": 0.20,
    "#5": 0.31,
    "#6": 0.44,
    "#7": 0.60,
    "#8": 0.79,
    "#9": 1.00,
    "#10": 1.27,
    "#11": 1.56,
    "#14": 2.25,
    "#18": 4.00,
}

US_BAR_DIAMETERS_IN = {
    "#3": 0.375,
    "#4": 0.500,
    "#5": 0.625,
    "#6": 0.750,
    "#7": 0.875,
    "#8": 1.000,
    "#9": 1.128,
    "#10": 1.270,
    "#11": 1.410,
    "#14": 1.693,
    "#18": 2.257,
}


def longitudinal_bar_centerline_cover(
    *, clear_cover: float, tie_bar_size: str, longitudinal_bar_size: str
) -> float:
    """Convert clear cover to a longitudinal-bar centerline offset.

    ``clear_cover`` is measured from the concrete face to the outside of the
    transverse reinforcement.
    """

    if clear_cover < 0.0:
        raise ValueError("Clear cover cannot be negative")
    try:
        tie_diameter = US_BAR_DIAMETERS_IN[tie_bar_size]
        longitudinal_diameter = US_BAR_DIAMETERS_IN[longitudinal_bar_size]
    except KeyError as error:
        raise ValueError(f"Unsupported US reinforcing bar size: {error.args[0]}") from error
    return clear_cover + tie_diameter + 0.5 * longitudinal_diameter


def rectangular_perimeter_bars(
    *,
    width: float,
    depth: float,
    centerline_cover: float,
    maximum_spacing: float,
    bar_area: float,
    material: SteelMaterial,
    label_prefix: str = "B",
) -> tuple[Rebar, ...]:
    """Place bars around a rectangle with spacing no greater than requested.

    Bars are evenly redistributed on each face. Corner bars are shared by the
    adjoining faces and returned only once.
    """

    if width <= 0.0 or depth <= 0.0:
        raise ValueError("Section dimensions must be positive")
    if centerline_cover <= 0.0:
        raise ValueError("Centerline cover must be positive")
    if 2.0 * centerline_cover >= min(width, depth):
        raise ValueError("Centerline cover leaves no valid reinforcing perimeter")
    if maximum_spacing <= 0.0:
        raise ValueError("Maximum bar spacing must be positive")

    x_left = -width / 2.0 + centerline_cover
    x_right = width / 2.0 - centerline_cover
    y_bottom = -depth / 2.0 + centerline_cover
    y_top = depth / 2.0 - centerline_cover

    horizontal_count = ceil((x_right - x_left) / maximum_spacing) + 1
    vertical_count = ceil((y_top - y_bottom) / maximum_spacing) + 1

    coordinates: list[tuple[float, float]] = []
    coordinates.extend((x, y_top) for x in _linspace(x_left, x_right, horizontal_count))
    coordinates.extend(
        (x_right, y)
        for y in _linspace(y_top, y_bottom, vertical_count)[1:]
    )
    coordinates.extend(
        (x, y_bottom)
        for x in _linspace(x_right, x_left, horizontal_count)[1:]
    )
    coordinates.extend(
        (x_left, y)
        for y in _linspace(y_bottom, y_top, vertical_count)[1:-1]
    )

    return tuple(
        Rebar(
            x=x,
            y=y,
            area=bar_area,
            material=material,
            label=f"{label_prefix}{index}",
        )
        for index, (x, y) in enumerate(coordinates, start=1)
    )


def circular_perimeter_bars(
    *,
    diameter: float,
    centerline_cover: float,
    maximum_spacing: float,
    bar_area: float,
    material: SteelMaterial,
    label_prefix: str = "B",
) -> tuple[Rebar, ...]:
    """Place bars uniformly on a circular centerline ring."""

    if diameter <= 0.0:
        raise ValueError("Section diameter must be positive")
    if centerline_cover <= 0.0:
        raise ValueError("Centerline cover must be positive")
    if 2.0 * centerline_cover >= diameter:
        raise ValueError("Centerline cover leaves no valid reinforcing ring")
    if maximum_spacing <= 0.0:
        raise ValueError("Maximum bar spacing must be positive")

    radius = diameter / 2.0 - centerline_cover
    count = max(4, ceil(2.0 * pi * radius / maximum_spacing))
    return tuple(
        Rebar(
            x=radius * cos(pi / 2.0 - 2.0 * pi * index / count),
            y=radius * sin(pi / 2.0 - 2.0 * pi * index / count),
            area=bar_area,
            material=material,
            label=f"{label_prefix}{index + 1}",
        )
        for index in range(count)
    )


def _linspace(start: float, stop: float, count: int) -> list[float]:
    if count < 2:
        return [start]
    step = (stop - start) / (count - 1)
    return [start + index * step for index in range(count)]
