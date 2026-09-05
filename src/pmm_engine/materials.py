"""Material definitions for nominal section mechanics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConcreteMaterial:
    """Equivalent rectangular concrete stress-block material."""

    fc: float
    eps_cu: float = 0.003
    alpha1: float = 0.85
    beta1: float | None = None

    def __post_init__(self) -> None:
        if self.fc <= 0.0:
            raise ValueError("Concrete compressive strength must be positive")
        if self.eps_cu <= 0.0:
            raise ValueError("Concrete ultimate strain must be positive")
        if self.alpha1 <= 0.0:
            raise ValueError("Concrete stress-block factor must be positive")
        if self.beta1 is None:
            object.__setattr__(self, "beta1", aci_beta1(self.fc))
        elif not 0.0 < self.beta1 <= 1.0:
            raise ValueError("Concrete beta1 must be between zero and one")

    @property
    def block_stress(self) -> float:
        return self.alpha1 * self.fc


@dataclass(frozen=True)
class SteelMaterial:
    """Symmetric elastic-perfectly plastic reinforcing steel."""

    fy: float
    elastic_modulus: float = 29_000.0

    def __post_init__(self) -> None:
        if self.fy <= 0.0:
            raise ValueError("Steel yield strength must be positive")
        if self.elastic_modulus <= 0.0:
            raise ValueError("Steel elastic modulus must be positive")

    def stress(self, strain: float) -> float:
        elastic_stress = self.elastic_modulus * strain
        return max(-self.fy, min(self.fy, elastic_stress))


def aci_beta1(fc_ksi: float) -> float:
    """Return the ACI equivalent-block beta1 for ``fc`` expressed in ksi."""

    if fc_ksi <= 4.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksi - 4.0))
