"""Simulation routines attached to graph assumption nodes."""

from __future__ import annotations

import numpy as np


def simulate_gaussian_linear(
    n: int,
    d: int,
    beta: np.ndarray,
    sigma: float,
    seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate data attached to graph node `model.gaussian_observation`."""
    beta = np.asarray(beta, dtype=float)
    if n <= 0:
        raise ValueError("n must be positive")
    if d <= 0:
        raise ValueError("d must be positive")
    if beta.shape != (d,):
        raise ValueError(f"beta must have shape ({d},)")
    if sigma <= 0:
        raise ValueError("sigma must be positive")

    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    noise = rng.normal(loc=0.0, scale=sigma, size=n)
    y = X @ beta + noise
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
    beta = np.asarray(beta, dtype=float)
    if n <= 0:
        raise ValueError("n must be positive")
    if d <= 0:
        raise ValueError("d must be positive")
    if beta.shape != (d,):
        raise ValueError(f"beta must have shape ({d},)")
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if nu <= 0:
        raise ValueError("nu must be positive")

    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    noise = sigma * rng.standard_t(df=nu, size=n)
    y = X @ beta + noise
    return X, y
