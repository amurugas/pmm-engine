from math import hypot

from pytest import approx

from pmm_engine import SteelMaterial, rectangular_perimeter_bars
from pmm_engine.layout import US_BAR_AREAS_IN2


def test_20x30_perimeter_layout() -> None:
    bars = rectangular_perimeter_bars(
        width=20.0,
        depth=30.0,
        centerline_cover=2.0,
        maximum_spacing=6.0,
        bar_area=US_BAR_AREAS_IN2["#8"],
        material=SteelMaterial(fy=60.0),
    )

    assert len(bars) == 16
    assert sum(bar.area for bar in bars) == approx(12.64)
    assert len({(bar.x, bar.y) for bar in bars}) == 16

    cyclic = list(bars) + [bars[0]]
    spacings = [
        hypot(second.x - first.x, second.y - first.y)
        for first, second in zip(cyclic, cyclic[1:])
    ]
    assert max(spacings) <= 6.0 + 1e-12
