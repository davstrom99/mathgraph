"""Estimators and objectives attached to graph nodes."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from linear_bayes.likelihoods import student_t_log_likelihood


def gaussian_posterior(
    X: np.ndarray,
    y: np.ndarray,
    sigma: float,
    tau: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (mu_n, Sigma_n) for graph node `posterior.gaussian_conjugate`."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    _validate_posterior_inputs(X, y, sigma, tau)

    d = X.shape[1]
    precision = (X.T @ X) / sigma**2 + np.eye(d) / tau**2
    rhs = (X.T @ y) / sigma**2
    sigma_n = np.linalg.inv(precision)
    mu_n = np.linalg.solve(precision, rhs)
    return mu_n, sigma_n


def negative_log_posterior_gaussian(
    beta: np.ndarray,
    X: np.ndarray,
    y: np.ndarray,
    sigma: float,
    tau: float,
) -> float:
    """Evaluate the objective for graph node `objective.gaussian_negative_log_posterior`."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    beta = np.asarray(beta, dtype=float)
    _validate_posterior_inputs(X, y, sigma, tau, beta=beta)

    residual = y - X @ beta
    data_term = 0.5 * np.dot(residual, residual) / sigma**2
    prior_term = 0.5 * np.dot(beta, beta) / tau**2
    return float(data_term + prior_term)


def beta_map_closed_form(
    X: np.ndarray,
    y: np.ndarray,
    sigma: float,
    tau: float,
) -> np.ndarray:
    """Return the closed-form MAP estimator for graph node `estimator.beta_map`."""
    mu_n, _ = gaussian_posterior(X, y, sigma, tau)
    return mu_n


def _validate_posterior_inputs(
    X: np.ndarray,
    y: np.ndarray,
    sigma: float,
    tau: float,
    beta: np.ndarray | None = None,
) -> None:
    if X.ndim != 2:
        raise ValueError("X must be a two-dimensional array")
    if y.ndim != 1:
        raise ValueError("y must be a one-dimensional array")
    if X.shape[0] != y.shape[0]:
        raise ValueError("X and y must have the same number of rows")
    if X.shape[1] == 0:
        raise ValueError("X must have at least one column")
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if tau <= 0:
        raise ValueError("tau must be positive")
    if beta is not None:
        if beta.ndim != 1:
            raise ValueError("beta must be a one-dimensional array")
        if beta.shape[0] != X.shape[1]:
            raise ValueError("beta length must match X columns")


def student_t_map_numerical(
    X: np.ndarray,
    y: np.ndarray,
    sigma: float,
    tau: float,
    nu: float,
    initial_beta: np.ndarray | None = None,
    maxiter: int = 1000,
) -> np.ndarray:
    """Return the numerical MAP approximation for graph node `approx.student_t_map`."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if initial_beta is None:
        initial_beta = beta_map_closed_form(X=X, y=y, sigma=sigma, tau=tau)
    initial_beta = np.asarray(initial_beta, dtype=float)
    _validate_posterior_inputs(X, y, sigma, tau, beta=initial_beta)
    if nu <= 0:
        raise ValueError("nu must be positive")
    if maxiter <= 0:
        raise ValueError("maxiter must be positive")

    def objective(beta: np.ndarray) -> float:
        prior_penalty = 0.5 * np.dot(beta, beta) / tau**2
        return float(
            -student_t_log_likelihood(X=X, y=y, beta=beta, sigma=sigma, nu=nu)
            + prior_penalty
        )

    result = minimize(
        objective,
        initial_beta,
        method="L-BFGS-B",
        options={"maxiter": int(maxiter), "ftol": 1e-10, "gtol": 1e-6},
    )
    if not result.success:
        raise RuntimeError(f"Student-t MAP optimization failed: {result.message}")
    return np.asarray(result.x, dtype=float)
