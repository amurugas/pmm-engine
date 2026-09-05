"""Small, dependency-free polygon operations used by the mechanics kernel.

The half-plane clipper is sufficient for the initial convex-section milestone.
Production support for arbitrary concave and multi-part geometry will use a
robust geometry backend such as Shapely behind the same public abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Iterable, Sequence

Point = tuple[float, float]


@dataclass(frozen=True)
class Polygon:
    """A polygon defined by one exterior ring and optional interior holes."""

    exterior: tuple[Point, ...]
    holes: tuple[tuple[Point, ...], ...] = ()

    def __post_init__(self) -> None:
        _validate_ring(self.exterior, "exterior")
        for index, hole in enumerate(self.holes):
            _validate_ring(hole, f"hole {index}")


def _validate_ring(vertices: Sequence[Point], name: str) -> None:
    if len(vertices) < 3:
        raise ValueError(f"Polygon {name} requires at least three vertices")
    if isclose(abs(_signed_area(vertices)), 0.0, abs_tol=1e-12):
        raise ValueError(f"Polygon {name} has zero area")


def _signed_area(vertices: Sequence[Point]) -> float:
    twice_area = 0.0
    for (x1, y1), (x2, y2) in _edges(vertices):
        twice_area += x1 * y2 - x2 * y1
    return 0.5 * twice_area


def _ring_area_centroid(vertices: Sequence[Point]) -> tuple[float, float, float]:
    cross_sum = 0.0
    cx_sum = 0.0
    cy_sum = 0.0
    for (x1, y1), (x2, y2) in _edges(vertices):
        cross = x1 * y2 - x2 * y1
        cross_sum += cross
        cx_sum += (x1 + x2) * cross
        cy_sum += (y1 + y2) * cross

    signed_area = 0.5 * cross_sum
    if isclose(signed_area, 0.0, abs_tol=1e-14):
        raise ValueError("Cannot calculate the centroid of a zero-area polygon")
    cx = cx_sum / (6.0 * signed_area)
    cy = cy_sum / (6.0 * signed_area)
    return abs(signed_area), cx, cy


def polygon_area_centroid(polygon: Polygon) -> tuple[float, float, float]:
    """Return net area and centroid, independent of ring winding direction."""

    outer_area, outer_x, outer_y = _ring_area_centroid(polygon.exterior)
    area = outer_area
    first_x = outer_area * outer_x
    first_y = outer_area * outer_y

    for hole in polygon.holes:
        hole_area, hole_x, hole_y = _ring_area_centroid(hole)
        area -= hole_area
        first_x -= hole_area * hole_x
        first_y -= hole_area * hole_y

    if area <= 0.0:
        raise ValueError("Polygon holes remove all exterior area")
    return area, first_x / area, first_y / area


def clip_polygon_half_plane(
    polygon: Polygon,
    normal: Point,
    offset: float,
    *,
    tolerance: float = 1e-12,
) -> Polygon | None:
    """Clip a polygon to points satisfying ``dot(normal, point) >= offset``.

    The dependency-free implementation is exact for convex rings. It is also
    useful for many concave rings, but a robust geometry backend is planned
    before arbitrary concave geometry is declared production-ready.
    """

    exterior = _clip_ring(polygon.exterior, normal, offset, tolerance)
    if len(exterior) < 3 or isclose(abs(_signed_area(exterior)), 0.0, abs_tol=1e-12):
        return None

    holes: list[tuple[Point, ...]] = []
    for hole in polygon.holes:
        clipped = _clip_ring(hole, normal, offset, tolerance)
        if len(clipped) >= 3 and not isclose(
            abs(_signed_area(clipped)), 0.0, abs_tol=1e-12
        ):
            holes.append(clipped)
    return Polygon(exterior=exterior, holes=tuple(holes))


def projection_bounds(polygon: Polygon, normal: Point) -> tuple[float, float]:
    values = [_dot(normal, vertex) for vertex in polygon.exterior]
    return min(values), max(values)


def polygon_bounds(polygon: Polygon) -> tuple[float, float, float, float]:
    """Return ``min_x, min_y, max_x, max_y`` for the exterior ring."""

    x_values = [point[0] for point in polygon.exterior]
    y_values = [point[1] for point in polygon.exterior]
    return min(x_values), min(y_values), max(x_values), max(y_values)


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Return whether a point is inside the exterior and outside every hole."""

    return _point_in_ring(point, polygon.exterior) and not any(
        _point_in_ring(point, hole) for hole in polygon.holes
    )


def _clip_ring(
    vertices: Sequence[Point], normal: Point, offset: float, tolerance: float
) -> tuple[Point, ...]:
    output: list[Point] = []
    for start, end in _edges(vertices):
        start_distance = _dot(normal, start) - offset
        end_distance = _dot(normal, end) - offset
        start_inside = start_distance >= -tolerance
        end_inside = end_distance >= -tolerance

        if start_inside and end_inside:
            output.append(end)
        elif start_inside and not end_inside:
            output.append(_intersection(start, end, start_distance, end_distance))
        elif not start_inside and end_inside:
            output.append(_intersection(start, end, start_distance, end_distance))
            output.append(end)

    return _deduplicate(output, tolerance)


def _intersection(
    start: Point, end: Point, start_distance: float, end_distance: float
) -> Point:
    fraction = start_distance / (start_distance - end_distance)
    return (
        start[0] + fraction * (end[0] - start[0]),
        start[1] + fraction * (end[1] - start[1]),
    )


def _deduplicate(vertices: Iterable[Point], tolerance: float) -> tuple[Point, ...]:
    result: list[Point] = []
    for point in vertices:
        if not result or not _points_close(result[-1], point, tolerance):
            result.append(point)
    if len(result) > 1 and _points_close(result[0], result[-1], tolerance):
        result.pop()
    return tuple(result)


def _points_close(first: Point, second: Point, tolerance: float) -> bool:
    return abs(first[0] - second[0]) <= tolerance and abs(
        first[1] - second[1]
    ) <= tolerance


def _dot(first: Point, second: Point) -> float:
    return first[0] * second[0] + first[1] * second[1]


def _point_in_ring(point: Point, vertices: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in _edges(vertices):
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) <= 1e-12 and min(x1, x2) - 1e-12 <= x <= max(
            x1, x2
        ) + 1e-12 and min(y1, y2) - 1e-12 <= y <= max(y1, y2) + 1e-12:
            return True
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if crossing_x > x:
                inside = not inside
    return inside


def _edges(vertices: Sequence[Point]) -> Iterable[tuple[Point, Point]]:
    for index, start in enumerate(vertices):
        yield start, vertices[(index + 1) % len(vertices)]
