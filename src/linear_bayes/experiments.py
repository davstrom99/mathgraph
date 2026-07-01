"""Experiment helpers attached to experiment and validation graph nodes."""

from __future__ import annotations

from typing import Any

import numpy as np

from linear_bayes.estimators import beta_map_closed_form
from linear_bayes.simulate import simulate_gaussian_linear


def run_recovery_experiment(
    n_values: list[int],
    d: int,
    sigma: float,
    tau: float,
    beta_true: np.ndarray,
    seeds: list[int],
) -> dict[str, Any]:
    """Run synthetic recovery for graph node `experiment.gaussian_recovery`."""
    beta_true = np.asarray(beta_true, dtype=float)
    if beta_true.shape != (d,):
        raise ValueError(f"beta_true must have shape ({d},)")
    if not n_values:
        raise ValueError("n_values must not be empty")
    if not seeds:
        raise ValueError("seeds must not be empty")

    raw_errors: dict[str, list[float]] = {}
    mean_errors: list[float] = []
    std_errors: list[float] = []

    for n in n_values:
        errors = []
        for seed in seeds:
            X, y = simulate_gaussian_linear(n=n, d=d, beta=beta_true, sigma=sigma, seed=seed)
            beta_hat = beta_map_closed_form(X=X, y=y, sigma=sigma, tau=tau)
            errors.append(float(np.linalg.norm(beta_hat - beta_true)))
        raw_errors[str(n)] = errors
        mean_errors.append(float(np.mean(errors)))
        std_errors.append(float(np.std(errors, ddof=0)))

    return {
        "n_values": [int(n) for n in n_values],
        "mean_errors": mean_errors,
        "std_errors": std_errors,
        "raw_errors": raw_errors,
        "beta_true": beta_true.tolist(),
        "sigma": float(sigma),
        "tau": float(tau),
        "seeds": [int(seed) for seed in seeds],
    }
