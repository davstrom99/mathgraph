from mathgraph_tool.cli import main


def test_node_command_prints_node_card(capsys):
    exit_code = main(["node", "estimator.beta_map"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Node: estimator.beta_map" in output
    assert "Kind: estimator" in output
    assert "Incoming edges:" in output
    assert "Outgoing edges:" in output
    assert "deriv:map-from-posterior" in output
    assert "examples/linear_bayes_demo/src/linear_bayes/estimators.py::beta_map_closed_form" in output


def test_impact_command_groups_downstream_references(capsys):
    exit_code = main(["impact", "model.gaussian_observation"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Impact from: model.gaussian_observation" in output
    assert "Affected mathematical nodes:" in output
    assert "likelihood.gaussian" in output
    assert "posterior.gaussian_conjugate" in output
    assert "Affected code symbols:" in output
    assert "examples/linear_bayes_demo/src/linear_bayes/likelihoods.py::gaussian_log_likelihood" in output
    assert "Affected tests:" in output
    assert "examples/linear_bayes_demo/tests/test_linear_gaussian_recovery.py::test_recovery_improves_with_n" in output
    assert "Affected experiments:" in output
    assert "experiment.gaussian_recovery" in output
    assert "Affected outputs:" in output
    assert "examples/linear_bayes_demo/results/gaussian_recovery_summary.json" in output
    assert "model.student_t_noise" not in output
    assert "approx.student_t_map" not in output
    assert "examples/linear_bayes_demo/results/student_t_change_summary.json" not in output


def test_impact_from_shared_variable_reaches_both_model_branches(capsys):
    exit_code = main(["impact", "param.sigma"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Impact from: param.sigma" in output
    assert "model.gaussian_observation" in output
    assert "model.student_t_noise" in output
    assert "likelihood.gaussian" in output
    assert "likelihood.student_t" in output
    assert "examples/linear_bayes_demo/results/gaussian_recovery_summary.json" in output
    assert "examples/linear_bayes_demo/results/student_t_change_summary.json" in output


def test_verbose_impact_command_prints_edge_paths(capsys):
    exit_code = main(["impact", "model.gaussian_observation", "--verbose"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Edge paths:" in output
    assert "model.gaussian_observation --derives--> likelihood.gaussian" in output
    assert "model.gaussian_observation --replaces--> model.student_t_noise" not in output
    assert "model.student_t_noise" not in output
    assert "The Gaussian observation model implies the Gaussian likelihood." in output
    assert "mathgraph/paper/derivations/gaussian_likelihood.tex#deriv:gaussian-likelihood" in output


def test_coverage_command_reports_core_sections(capsys):
    exit_code = main(["coverage"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Nodes: 26" in output
    assert "Edges: 31" in output
    assert "TeX coverage:" in output
    assert "Implementation coverage:" in output
    assert "Validation coverage:" in output
    assert "Unimplemented mathematical nodes:" in output
    assert "prior.gaussian_beta" in output
    assert "Orphan or suspicious references:" in output
    assert "Orphan code symbols:" in output
    assert "- none" in output
