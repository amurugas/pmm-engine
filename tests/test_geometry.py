from pytest import approx, raises

from pmm_engine.geometry import (
    Polygon,
    clip_polygon_half_plane,
    point_in_polygon,
    polygon_area_centroid,
)


def test_rectangle_area_and_centroid_are_winding_independent() -> None:
    vertices = ((-10.0, -15.0), (10.0, -15.0), (10.0, 15.0), (-10.0, 15.0))
    for ring in (vertices, tuple(reversed(vertices))):
        area, cx, cy = polygon_area_centroid(Polygon(exterior=ring))
        assert area == approx(600.0)
        assert cx == approx(0.0)
        assert cy == approx(0.0)


def test_half_plane_clip_returns_top_six_inches() -> None:
    polygon = Polygon(
        exterior=((-10.0, -15.0), (10.0, -15.0), (10.0, 15.0), (-10.0, 15.0))
    )
    clipped = clip_polygon_half_plane(polygon, (0.0, 1.0), 9.0)
    assert clipped is not None
    area, cx, cy = polygon_area_centroid(clipped)
    assert area == approx(120.0)
    assert cx == approx(0.0)
    assert cy == approx(12.0)


def test_zero_area_polygon_is_rejected() -> None:
    with raises(ValueError, match="zero area"):
        Polygon(exterior=((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)))


def test_point_in_polygon_respects_hole() -> None:
    polygon = Polygon(
        exterior=((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
        holes=(((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)),),
    )
    assert point_in_polygon((4.0, 0.0), polygon)
    assert not point_in_polygon((0.0, 0.0), polygon)
    assert not point_in_polygon((6.0, 0.0), polygon)
