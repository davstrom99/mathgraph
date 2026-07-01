"""Likelihood functions attached to graph assumption nodes."""

from __future__ import annotations

import numpy as np
from scipy.special import gammaln


def gaussian_log_likelihood(
    X: np.ndarray,
    y: np.ndarray,
    beta: np.ndarray,
    sigma: float,
) -> float:
    """Evaluate the log likelihood attached to graph node `likelihood.gaussian`."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    beta = np.asarray(beta, dtype=float)
    _validate_regression_inputs(X, y, beta)
    if sigma <= 0:
        raise ValueError("sigma must be positive")

    residual = y - X @ beta
    n = y.shape[0]
    return float(
        -0.5 * n * np.log(2.0 * np.pi * sigma**2)
        -0.5 * np.dot(residual, residual) / sigma**2
    )


def _validate_regression_inputs(X: np.ndarray, y: np.ndarray, beta: np.ndarray) -> None:
    if X.ndim != 2:
        raise ValueError("X must be a two-dimensional array")
    if y.ndim != 1:
        raise ValueError("y must be a one-dimensional array")
    if beta.ndim != 1:
        raise ValueError("beta must be a one-dimensional array")
    if X.shape[0] != y.shape[0]:
        raise ValueError("X and y must have the same number of rows")
    if X.shape[1] != beta.shape[0]:
        raise ValueError("X columns must match beta length")


def student_t_log_likelihood(
    X: np.ndarray,
    y: np.ndarray,
    beta: np.ndarray,
    sigma: float,
    nu: float,
) -> float:
    """Evaluate the log likelihood attached to graph node `likelihood.student_t`."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    beta = np.asarray(beta, dtype=float)
    _validate_regression_inputs(X, y, beta)
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if nu <= 0:
        raise ValueError("nu must be positive")

    residual = y - X @ beta
    scaled_squared = (residual / sigma) ** 2
    normalizer = (
        gammaln((nu + 1.0) / 2.0)
        - gammaln(nu / 2.0)
        - 0.5 * np.log(nu * np.pi)
        - np.log(sigma)
    )
    log_density = normalizer - 0.5 * (nu + 1.0) * np.log1p(scaled_squared / nu)
    return float(np.sum(log_density))
