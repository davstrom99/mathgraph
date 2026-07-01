"""Tests attached to Student-t alternative-branch graph nodes."""

import json
import importlib.util
from pathlib import Path

import numpy as np
from scipy.stats import t

from linear_bayes.estimators import beta_map_closed_form, student_t_map_numerical
from linear_bayes.likelihoods import student_t_log_likelihood
from linear_bayes.simulate import simulate_student_t_linear


def test_student_t_simulation_has_heavy_tailed_residuals():
    """Validation attached to graph node `model.student_t_noise`."""
    beta_true = np.array([1.0, -0.5, 0.25])
    X, y = simulate_student_t_linear(
        n=4000,
        d=3,
        beta=beta_true,
        sigma=1.0,
        nu=3.0,
        seed=11,
    )

    residual = y - X @ beta_true

    assert X.shape == (4000, 3)
    assert y.shape == (4000,)
    assert np.mean(np.abs(residual) > 3.0) > 0.02


def test_student_t_log_likelihood_matches_scipy_density():
    """Validation attached to graph node `likelihood.student_t`."""
    X = np.array([[1.0, 0.0], [1.0, 2.0], [-1.0, 1.0]])
    y = np.array([0.5, 1.25, -0.25])
    beta = np.array([0.4, 0.2])
    sigma = 0.7
    nu = 4.0

    residual = y - X @ beta
    expected = float(np.sum(t.logpdf(residual / sigma, df=nu) - np.log(sigma)))

    assert np.isclose(
        student_t_log_likelihood(X=X, y=y, beta=beta, sigma=sigma, nu=nu),
        expected,
    )


def test_student_t_map_handles_outlier_better_than_gaussian_map():
    """Validation attached to graph node `approx.student_t_map`."""
    beta_true = np.array([1.0])
    X = np.ones((12, 1))
    y = np.ones(12)
    y[-1] = 30.0

    gaussian_beta = beta_map_closed_form(X=X, y=y, sigma=1.0, tau=10.0)
    student_t_beta = student_t_map_numerical(X=X, y=y, sigma=1.0, tau=10.0, nu=3.0)

    assert abs(student_t_beta[0] - beta_true[0]) < abs(gaussian_beta[0] - beta_true[0])
    assert abs(student_t_beta[0] - beta_true[0]) < 0.25


def test_student_t_change_script_writes_declared_outputs(tmp_path):
    """Validation attached to graph node `experiment.student_t_change`."""
    script_path = Path("experiments/run_student_t_change.py").resolve()
    spec = importlib.util.spec_from_file_location("run_student_t_change", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    summary_path = tmp_path / "student_t_change_summary.json"
    plot_path = tmp_path / "student_t_change_error.png"
    module.main(summary_path=summary_path, plot_path=plot_path)

    assert summary_path.exists()
    assert plot_path.exists()
    assert plot_path.stat().st_size > 0

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["nu"] == 3.0
    assert summary["mean_student_t_error"] < summary["mean_gaussian_error"]
    assert summary["student_t_better_fraction"] > 0.5
