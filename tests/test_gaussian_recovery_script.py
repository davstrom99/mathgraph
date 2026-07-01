import json
import importlib.util
from pathlib import Path


def _load_script_main():
    script_path = Path("experiments/run_gaussian_recovery.py").resolve()
    spec = importlib.util.spec_from_file_location("run_gaussian_recovery", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def test_gaussian_recovery_script_writes_declared_outputs(tmp_path):
    main = _load_script_main()
    summary_path = tmp_path / "gaussian_recovery_summary.json"
    plot_path = tmp_path / "gaussian_recovery_error.png"

    main(summary_path=summary_path, plot_path=plot_path)

    assert summary_path.exists()
    assert plot_path.exists()
    assert plot_path.stat().st_size > 0

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["n_values"] == [20, 50, 100, 250, 500]
    assert summary["mean_errors"][-1] < summary["mean_errors"][0]
