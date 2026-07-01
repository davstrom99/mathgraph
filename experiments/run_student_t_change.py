"""Run the Student-t model-change experiment.

Attached graph node: `experiment.student_t_change`.
Declared outputs:
- results/student_t_change_summary.json
- results/student_t_change_error.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from linear_bayes.estimators import beta_map_closed_form, student_t_map_numerical
from linear_bayes.simulate import simulate_student_t_linear


BETA_TRUE = np.array([1.0, -0.5, 0.25])
N = 120
SEEDS = list(range(40))
SIGMA = 1.0
TAU = 10.0
NU = 3.0
SUMMARY_PATH = Path("results/student_t_change_summary.json")
PLOT_PATH = Path("results/student_t_change_error.png")


def main(
    summary_path: Path = SUMMARY_PATH,
    plot_path: Path = PLOT_PATH,
) -> None:
    """Run and save outputs for graph node `experiment.student_t_change`."""
    gaussian_errors: list[float] = []
    student_t_errors: list[float] = []

    for seed in SEEDS:
        X, y = simulate_student_t_linear(
            n=N,
            d=BETA_TRUE.size,
            beta=BETA_TRUE,
            sigma=SIGMA,
            nu=NU,
            seed=seed,
        )
        gaussian_beta = beta_map_closed_form(X=X, y=y, sigma=SIGMA, tau=TAU)
        student_t_beta = student_t_map_numerical(X=X, y=y, sigma=SIGMA, tau=TAU, nu=NU)
        gaussian_errors.append(float(np.linalg.norm(gaussian_beta - BETA_TRUE)))
        student_t_errors.append(float(np.linalg.norm(student_t_beta - BETA_TRUE)))

    summary = {
        "beta_true": BETA_TRUE.tolist(),
        "n": N,
        "sigma": SIGMA,
        "tau": TAU,
        "nu": NU,
        "seeds": SEEDS,
        "gaussian_errors": gaussian_errors,
        "student_t_errors": student_t_errors,
        "mean_gaussian_error": float(np.mean(gaussian_errors)),
        "mean_student_t_error": float(np.mean(student_t_errors)),
        "median_gaussian_error": float(np.median(gaussian_errors)),
        "median_student_t_error": float(np.median(student_t_errors)),
        "student_t_better_fraction": float(
            np.mean(np.asarray(student_t_errors) < np.asarray(gaussian_errors))
        ),
    }

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(7.0, 4.5), constrained_layout=True)
    positions = np.array([0, 1], dtype=float)
    ax.boxplot(
        [gaussian_errors, student_t_errors],
        positions=positions,
        widths=0.45,
        patch_artist=True,
        boxprops={"facecolor": "#dbeafe", "edgecolor": "#2563eb"},
        medianprops={"color": "#111827", "linewidth": 2.0},
        whiskerprops={"color": "#64748b"},
        capprops={"color": "#64748b"},
    )
    for index, values in enumerate([gaussian_errors, student_t_errors]):
        jitter = np.linspace(-0.08, 0.08, num=len(values))
        ax.scatter(
            np.full(len(values), positions[index]) + jitter,
            values,
            s=18,
            alpha=0.65,
            color="#0f766e" if index else "#b45309",
        )
    ax.set_xticks(positions, ["Gaussian MAP", "Student-t MAP"])
    ax.set_ylabel(r"$\|\hat{\beta} - \beta_0\|_2$")
    ax.set_title("Student-t model-change recovery under heavy-tailed noise")
    ax.grid(True, axis="y", alpha=0.3)
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)

    print(f"Wrote {summary_path}")
    print(f"Wrote {plot_path}")
    print(
        "Mean coefficient error: "
        f"Gaussian MAP {summary['mean_gaussian_error']:.4f}, "
        f"Student-t MAP {summary['mean_student_t_error']:.4f}"
    )


if __name__ == "__main__":
    main()
