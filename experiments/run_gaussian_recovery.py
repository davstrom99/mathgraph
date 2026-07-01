"""Run the Gaussian synthetic recovery experiment.

Attached graph node: `experiment.gaussian_recovery`.
Declared outputs:
- results/gaussian_recovery_summary.json
- results/gaussian_recovery_error.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from linear_bayes.experiments import run_recovery_experiment


BETA_TRUE = np.array([1.0, -0.5, 0.25])
N_VALUES = [20, 50, 100, 250, 500]
SEEDS = list(range(25))
SIGMA = 1.0
TAU = 10.0
SUMMARY_PATH = Path("results/gaussian_recovery_summary.json")
PLOT_PATH = Path("results/gaussian_recovery_error.png")


def main(
    summary_path: Path = SUMMARY_PATH,
    plot_path: Path = PLOT_PATH,
) -> None:
    """Run and save outputs for graph node `experiment.gaussian_recovery`."""
    result = run_recovery_experiment(
        n_values=N_VALUES,
        d=BETA_TRUE.size,
        sigma=SIGMA,
        tau=TAU,
        beta_true=BETA_TRUE,
        seeds=SEEDS,
    )

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    plot_path.parent.mkdir(parents=True, exist_ok=True)

    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _save_error_plot(result, plot_path)

    first_error = result["mean_errors"][0]
    last_error = result["mean_errors"][-1]
    print(f"Wrote {summary_path}")
    print(f"Wrote {plot_path}")
    print(f"Mean error: n={N_VALUES[0]} -> {first_error:.4f}, n={N_VALUES[-1]} -> {last_error:.4f}")


def _save_error_plot(result: dict, plot_path: Path) -> None:
    n_values = np.asarray(result["n_values"], dtype=float)
    mean_errors = np.asarray(result["mean_errors"], dtype=float)
    std_errors = np.asarray(result["std_errors"], dtype=float)

    fig, ax = plt.subplots(figsize=(7.0, 4.5), constrained_layout=True)
    ax.errorbar(
        n_values,
        mean_errors,
        yerr=std_errors,
        marker="o",
        linewidth=2.0,
        capsize=4,
        color="#1f77b4",
        ecolor="#8fb9dc",
    )
    ax.set_xscale("log")
    ax.set_xlabel("sample size n")
    ax.set_ylabel(r"$\|\hat{\beta}_{MAP} - \beta_0\|_2$")
    ax.set_title("Gaussian synthetic recovery")
    ax.grid(True, which="both", alpha=0.3)
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
