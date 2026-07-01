"""Simulation helpers attached to graph nodes."""

from __future__ import annotations

import numpy as np
from scipy.stats import t


def simulate_gaussian_linear(
    n: int,
    d: int,
    beta: np.ndarray,
    sigma: float,
    seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate data attached to graph node `model.gaussian_observation`."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    noise = rng.normal(scale=sigma, size=n)
    y = X @ np.asarray(beta, dtype=float) + noise
    return X, y


def simulate_student_t_linear(
    n: int,
    d: int,
    beta: np.ndarray,
    sigma: float,
    nu: float,
    seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate data attached to graph node `model.student_t_noise`."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    noise = t.rvs(df=nu, loc=0.0, scale=sigma, size=n, random_state=rng)
    y = X @ np.asarray(beta, dtype=float) + np.asarray(noise, dtype=float)
    return X, y
