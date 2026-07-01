"""Tests attached to Gaussian posterior, MAP, and validation graph nodes."""

import numpy as np

from linear_bayes.estimators import (
    beta_map_closed_form,
    gaussian_posterior,
    negative_log_posterior_gaussian,
)
from linear_bayes.experiments import run_recovery_experiment
from linear_bayes.simulate import simulate_gaussian_linear


def test_closed_form_map_equals_posterior_mean():
    """Validation attached to graph node `estimator.beta_map`."""
    beta_true = np.array([1.0, -0.5, 0.25])
    X, y = simulate_gaussian_linear(n=80, d=3, beta=beta_true, sigma=0.7, seed=3)

    posterior_mean, posterior_cov = gaussian_posterior(X, y, sigma=0.7, tau=5.0)
    beta_map = beta_map_closed_form(X, y, sigma=0.7, tau=5.0)

    assert posterior_cov.shape == (3, 3)
    assert np.allclose(beta_map, posterior_mean)

    perturbed = beta_map + np.array([0.15, -0.1, 0.05])
    assert negative_log_posterior_gaussian(beta_map, X, y, sigma=0.7, tau=5.0) < (
        negative_log_posterior_gaussian(perturbed, X, y, sigma=0.7, tau=5.0)
    )


def test_recovery_improves_with_n():
    """Validation attached to graph node `validation.synthetic_recovery`."""
    beta_true = np.array([1.0, -0.5, 0.25])
    result = run_recovery_experiment(
        n_values=[20, 500],
        d=3,
        sigma=1.0,
        tau=10.0,
        beta_true=beta_true,
        seeds=list(range(30)),
    )

    small_n_error, large_n_error = result["mean_errors"]

    assert large_n_error < small_n_error * 0.6
    assert set(result) == {
        "n_values",
        "mean_errors",
        "std_errors",
        "raw_errors",
        "beta_true",
        "sigma",
        "tau",
        "seeds",
    }
