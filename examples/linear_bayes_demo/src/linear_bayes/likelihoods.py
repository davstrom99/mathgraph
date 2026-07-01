"""Likelihood helpers attached to graph nodes."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm, t


def gaussian_log_likelihood(
    X: np.ndarray,
    y: np.ndarray,
    beta: np.ndarray,
    sigma: float,
) -> float:
    """Return Gaussian log likelihood for graph node `likelihood.gaussian`."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    beta = np.asarray(beta, dtype=float)
    residual = y - X @ beta
    return float(np.sum(norm.logpdf(residual, loc=0.0, scale=sigma)))


def student_t_log_likelihood(
    X: np.ndarray,
    y: np.ndarray,
    beta: np.ndarray,
    sigma: float,
    nu: float,
) -> float:
    """Return Student-t log likelihood for graph node `likelihood.student_t`."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    beta = np.asarray(beta, dtype=float)
    residual = y - X @ beta
    return float(np.sum(t.logpdf(residual / sigma, df=nu) - np.log(sigma)))
