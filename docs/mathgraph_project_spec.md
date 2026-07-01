\# Project Request: Build a local mathematics-centered graph tool and first experiment



\## Core philosophy



The repository should be organized around the following principle:



> TeX is for human mathematical exposition.  

> Code is for execution.  

> The graph is for identity, dependency, traceability, and change impact.  

> Codex is allowed to change code only by respecting the graph.



The goal is to build a first useful local tool for managing research codebases where the mathematical specification is the central representation, and code, tests, experiments, plots, and TeX are attached to mathematical graph nodes and edges.



This first version should be small enough to understand, but not a toy. It should be useful for testing the workflow on a simple Bayesian linear Gaussian model, then deliberately changing the noise model to Student-t noise to see whether the graph helps identify all affected parts of the project.



Do not use Lean, Coq, Agda, Isabelle, or the Lean blueprint ecosystem in this first version.



\---



\# High-level goal



Build a local Python tool called `mathgraph`.



The tool should maintain a graph of mathematical objects and their relationships. The graph should be explicitly declared in YAML files. The graph should connect:



\- mathematical variables,

\- model assumptions,

\- likelihood/objective definitions,

\- estimators,

\- approximation methods,

\- validation tests,

\- experiments,

\- figures/outputs,

\- TeX references,

\- code implementations,

\- test files,

\- experiment result files.



The graph should support:



```bash

mathgraph check

mathgraph impact <node-id>

mathgraph coverage

mathgraph render

mathgraph node <node-id>

mathgraph open <node-id>



The first implementation should work locally in a normal repository without any external service.



Use:



Python

pydantic for schema validation

networkx for graph operations

PyYAML or ruamel.yaml for YAML parsing

Python AST/importlib inspection for validating code symbols

pathlib for file paths

pytest for tests

matplotlib for experiment plots

simple static HTML/CSS/JS for the clickable graph webpage

Graphviz DOT or Mermaid as the graph interchange/rendering format



Avoid heavy graph databases for now.



Repository structure



Create a repository with the following structure:



.

├── AGENTS.md

├── README.md

├── pyproject.toml

├── paper/

│   ├── main.tex

│   └── derivations.tex

├── mathgraph/

│   ├── graph.yaml

│   ├── schema.yaml

│   └── README.md

├── src/

│   ├── mathgraph\_tool/

│   │   ├── \_\_init\_\_.py

│   │   ├── cli.py

│   │   ├── schema.py

│   │   ├── loader.py

│   │   ├── checks.py

│   │   ├── impact.py

│   │   ├── coverage.py

│   │   ├── render.py

│   │   └── openers.py

│   └── linear\_bayes/

│       ├── \_\_init\_\_.py

│       ├── simulate.py

│       ├── estimators.py

│       ├── likelihoods.py

│       ├── diagnostics.py

│       └── experiments.py

├── experiments/

│   ├── run\_gaussian\_recovery.py

│   └── run\_student\_t\_change.py

├── results/

│   └── .gitkeep

├── tests/

│   ├── test\_mathgraph\_check.py

│   ├── test\_linear\_gaussian\_recovery.py

│   └── test\_graph\_references.py

├── web/

│   ├── index.html

│   ├── graph.json

│   ├── style.css

│   └── app.js

└── codex-skill/

&#x20;   └── mathgraph-centered-research/

&#x20;       ├── SKILL.md

&#x20;       ├── agents/

&#x20;       │   └── openai.yaml

&#x20;       └── references/

&#x20;           ├── workflow.md

&#x20;           ├── graph-schema.md

&#x20;           └── change-protocol.md



The codex-skill/ folder should contain the reusable skill instructions for future Codex/ChatGPT sessions.



Mathematical first experiment



Implement the first project around a Bayesian linear Gaussian model.



Model



Let



x

i

&#x09;​



∈R

d



be observed covariates and



y

i

&#x09;​



∈R



be observed responses.



Use the model:



y

i

&#x09;​



=x

i

⊤

&#x09;​



β+ε

i

&#x09;​



,ε

i

&#x09;​



∼N(0,σ

2

).



Prior:



β∼N(0,τ

2

I

d

&#x09;​



).



Assume initially that sigma^2 and tau^2 are known.



Derive the posterior:



p(β∣X,y)=N(μ

n

&#x09;​



,Σ

n

&#x09;​



)



where



Σ

n

&#x09;​



=(

σ

2

1

&#x09;​



X

⊤

X+

τ

2

1

&#x09;​



I

d

&#x09;​



)

−1



and



μ

n

&#x09;​



=Σ

n

&#x09;​



σ

2

1

&#x09;​



X

⊤

y.



Also include the MAP/ridge estimator:



β

^

&#x09;​



MAP

&#x09;​



=arg

β

min

&#x09;​



2σ

2

1

&#x09;​



∥y−Xβ∥

2

2

&#x09;​



\+

2τ

2

1

&#x09;​



∥β∥

2

2

&#x09;​



.



Implement:



data simulation,

posterior mean/covariance computation,

MAP estimator,

negative log posterior objective,

simple recovery experiment,

simple validation test.

Validation test



Include one validation type only, but make it descriptive.



The validation test should be called something like:



validation.synthetic\_recovery



It should verify that, for simulated data under the Gaussian model, the posterior mean or MAP estimator gets closer to the true coefficient vector as sample size increases.



For example, run several values of n, such as:



n\_values = \[20, 50, 100, 250, 500]



Compute:



∥

β

^

&#x09;​



n

&#x09;​



−β

0

&#x09;​



∥

2

&#x09;​





Repeat over several random seeds, plot mean and standard deviation of the error versus n, and save a JSON summary and a PNG plot.



This does not need to be a theorem. It is an empirical validation node attached to the estimator and simulator.



Student-t change experiment



Include a second experiment that changes the noise model to Student-t:



ε

i

&#x09;​



∼t

ν

&#x09;​



(0,σ)



The purpose is not necessarily to fully solve the Student-t posterior analytically. The purpose is to test the graph workflow.



Add a coarse node:



model.student\_t\_noise



and one approximation node:



approx.student\_t\_map



The approximation node should state that the estimator uses a numerical MAP approximation under Student-t likelihood and Gaussian prior.



Implement a simple Student-t negative log posterior and numerical optimization. This can use scipy.optimize.minimize.



The graph should reveal that changing the noise model from Gaussian to Student-t affects:



likelihood node,

posterior/objective node,

estimator node,

simulator node,

validation experiment,

plots/results,

possibly tests.



The command



mathgraph impact model.gaussian\_noise



or



mathgraph impact model.observation



should show downstream affected nodes, code files, tests, and experiment outputs.



Graph design



Use a small graph with coarse nodes.



Important: nodes should be coarse enough that the user can understand the whole graph visually. Do not create one node for every symbol or line of code.



However, every node must be unambiguous. Each node should be fully specified by:



its own fields,

its neighboring nodes,

incoming/outgoing edge descriptions,

TeX references,

code references where applicable.



Put detailed mathematical relationship information on edges rather than exploding the graph into too many tiny nodes.



Node types



Support these node kinds:



variable

assumption

objective

estimator

approximation

simulator

validation

experiment

figure

dataset

test

Parameters are variables. Priors, likelihoods, posterior declarations, and model assumptions are assumptions. Algorithms usually attach to estimator or approximation nodes.



Primitive variable invariant



Variables are the only primitive mathematical nodes.



A variable node defines only the existence and type/domain of an object, for example:



```text
x in R^d
beta in R^p
Sigma in S_{++}^d
y in R^n
```



Do not encode domains beyond the variable declaration, probability distributions, independence assumptions, or model assumptions inside variable nodes.



Random variables require two separate concepts:



1. A variable node for the object, such as `beta in R^p`.
2. An assumption node for the distribution, such as `beta ~ N(0, tau^2 I)`.



Every non-variable node must have incoming dependencies that specify it. If a node uses a mathematical object, that object must already exist as a variable node somewhere upstream.



Use the node `uses` field to declare primitive variable dependencies explicitly. If `uses` is omitted, `mathgraph check` may parse simple symbols from `statement` as a fallback. The checker should report unresolved symbols and variables that are used before they are upstream.



Do not over-engineer. These are enough for the first version.



Edge types



Support these edge kinds:



defines

assumes

depends\_on

derives

implements

approximates

validates

tests

generates

uses

affects



Each edge must support a TeX derivation reference. This is important.



Each edge should have fields like:



from: likelihood.gaussian

to: posterior.gaussian\_conjugate

kind: derives

description: >

&#x20; Combining the Gaussian likelihood with the Gaussian prior gives the closed-form

&#x20; Gaussian posterior for beta.

tex:

&#x20; file: paper/derivations.tex

&#x20; label: deriv:gaussian-posterior



For the first version, derivation formality is level 1:



the edge points to a TeX derivation,

the human researcher can click the edge/node and inspect the derivation,

Codex can also inspect the derivation text,

no formal proof assistant is required.

Example graph file



Use a single initial file:



mathgraph/graph.yaml



The first version can use one file rather than many files.



The graph should look approximately like this:



project:

&#x20; id: linear\_bayes\_demo

&#x20; title: Linear Bayesian Regression Demo

&#x20; tex\_root: paper/main.tex

&#x20; repo\_root: .



nodes:

&#x20; - id: var.X

&#x20;   kind: variable

&#x20;   title: Design matrix

&#x20;   symbol: X

&#x20;   statement: "Observed design matrix X in R^{n x d}."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: def:design-matrix



&#x20; - id: var.y

&#x20;   kind: variable

&#x20;   title: Response vector

&#x20;   symbol: y

&#x20;   statement: "Observed response vector y in R^n."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: def:response-vector



&#x20; - id: param.beta

&#x20;   kind: variable

&#x20;   title: Regression coefficients

&#x20;   symbol: "\\\\beta"

&#x20;   statement: "Unknown coefficient vector beta in R^d."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: def:beta



&#x20; - id: model.gaussian\_observation

&#x20;   kind: assumption

&#x20;   title: Gaussian linear observation model

&#x20;   statement: "y = X beta + epsilon, epsilon \~ N(0, sigma^2 I)."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: model:gaussian-observation

&#x20;   code:

&#x20;     - path: src/linear\_bayes/simulate.py

&#x20;       symbol: simulate\_gaussian\_linear



&#x20; - id: prior.gaussian\_beta

&#x20;   kind: assumption

&#x20;   title: Gaussian prior on beta

&#x20;   statement: "beta \~ N(0, tau^2 I\_d)."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: prior:gaussian-beta



&#x20; - id: likelihood.gaussian

&#x20;   kind: assumption

&#x20;   title: Gaussian likelihood

&#x20;   statement: "p(y | X, beta, sigma^2) under iid Gaussian noise."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: likelihood:gaussian

&#x20;   code:

&#x20;     - path: src/linear\_bayes/likelihoods.py

&#x20;       symbol: gaussian\_log\_likelihood



&#x20; - id: posterior.gaussian\_conjugate

&#x20;   kind: assumption

&#x20;   title: Closed-form Gaussian posterior

&#x20;   statement: "p(beta | X,y) = N(mu\_n, Sigma\_n)."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: posterior:gaussian-conjugate

&#x20;   code:

&#x20;     - path: src/linear\_bayes/estimators.py

&#x20;       symbol: gaussian\_posterior



&#x20; - id: estimator.beta\_map

&#x20;   kind: estimator

&#x20;   title: MAP estimator for beta

&#x20;   statement: "The MAP estimator minimizes the negative log posterior."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: estimator:beta-map

&#x20;   code:

&#x20;     - path: src/linear\_bayes/estimators.py

&#x20;       symbol: beta\_map\_closed\_form



&#x20; - id: validation.synthetic\_recovery

&#x20;   kind: validation

&#x20;   title: Synthetic recovery validation

&#x20;   statement: >

&#x20;     Empirical validation that posterior mean/MAP estimation error decreases

&#x20;     as sample size increases under data generated from the model.

&#x20;   code:

&#x20;     - path: tests/test\_linear\_gaussian\_recovery.py

&#x20;       symbol: test\_recovery\_improves\_with\_n



&#x20; - id: experiment.gaussian\_recovery

&#x20;   kind: experiment

&#x20;   title: Gaussian recovery experiment

&#x20;   statement: >

&#x20;     Runs synthetic recovery experiment over multiple sample sizes and seeds.

&#x20;   code:

&#x20;     - path: experiments/run\_gaussian\_recovery.py

&#x20;       symbol: main

&#x20;   outputs:

&#x20;     - path: results/gaussian\_recovery\_summary.json

&#x20;     - path: results/gaussian\_recovery\_error.png



&#x20; - id: model.student\_t\_noise

&#x20;   kind: assumption

&#x20;   title: Student-t noise observation model

&#x20;   statement: "y = X beta + epsilon, epsilon \~ StudentT\_nu(0, sigma)."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: model:student-t-noise

&#x20;   code:

&#x20;     - path: src/linear\_bayes/simulate.py

&#x20;       symbol: simulate\_student\_t\_linear



&#x20; - id: likelihood.student\_t

&#x20;   kind: assumption

&#x20;   title: Student-t likelihood

&#x20;   statement: "Student-t likelihood for robust regression."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: likelihood:student-t

&#x20;   code:

&#x20;     - path: src/linear\_bayes/likelihoods.py

&#x20;       symbol: student\_t\_log\_likelihood



&#x20; - id: approx.student\_t\_map

&#x20;   kind: approximation

&#x20;   title: Numerical MAP approximation under Student-t noise

&#x20;   statement: >

&#x20;     Approximation node: the posterior is optimized numerically using a

&#x20;     Student-t likelihood and Gaussian prior. This is an optimization-based

&#x20;     MAP approximation, not a closed-form conjugate posterior.

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: approx:student-t-map

&#x20;   code:

&#x20;     - path: src/linear\_bayes/estimators.py

&#x20;       symbol: student\_t\_map\_numerical



edges:

&#x20; - from: var.X

&#x20;   to: model.gaussian\_observation

&#x20;   kind: defines

&#x20;   description: "The Gaussian observation model uses X as the design matrix."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: edge:X-to-gaussian-model



&#x20; - from: var.y

&#x20;   to: model.gaussian\_observation

&#x20;   kind: defines

&#x20;   description: "The Gaussian observation model defines the distribution of y."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: edge:y-to-gaussian-model



&#x20; - from: param.beta

&#x20;   to: model.gaussian\_observation

&#x20;   kind: defines

&#x20;   description: "Beta is the unknown coefficient vector in the observation model."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: edge:beta-to-gaussian-model



&#x20; - from: model.gaussian\_observation

&#x20;   to: likelihood.gaussian

&#x20;   kind: derives

&#x20;   description: "The Gaussian observation model implies the Gaussian likelihood."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: deriv:gaussian-likelihood



&#x20; - from: likelihood.gaussian

&#x20;   to: posterior.gaussian\_conjugate

&#x20;   kind: derives

&#x20;   description: >

&#x20;     Combining the Gaussian likelihood with the Gaussian prior yields the

&#x20;     conjugate Gaussian posterior.

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: deriv:gaussian-posterior



&#x20; - from: prior.gaussian\_beta

&#x20;   to: posterior.gaussian\_conjugate

&#x20;   kind: derives

&#x20;   description: "The Gaussian prior is required for the closed-form posterior."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: deriv:gaussian-posterior



&#x20; - from: posterior.gaussian\_conjugate

&#x20;   to: estimator.beta\_map

&#x20;   kind: derives

&#x20;   description: >

&#x20;     The MAP estimator is the posterior mode. For the Gaussian posterior it

&#x20;     equals the posterior mean.

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: deriv:map-from-posterior



&#x20; - from: estimator.beta\_map

&#x20;   to: validation.synthetic\_recovery

&#x20;   kind: validates

&#x20;   description: >

&#x20;     The synthetic recovery validation checks whether the estimator approaches

&#x20;     the true coefficient vector as n increases under the assumed model.

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: validation:synthetic-recovery



&#x20; - from: validation.synthetic\_recovery

&#x20;   to: experiment.gaussian\_recovery

&#x20;   kind: tests

&#x20;   description: "The experiment executes the synthetic recovery validation."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: experiment:gaussian-recovery



&#x20; - from: model.student\_t\_noise

&#x20;   to: likelihood.student\_t

&#x20;   kind: derives

&#x20;   description: "The Student-t observation model implies the Student-t likelihood."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: deriv:student-t-likelihood



&#x20; - from: likelihood.student\_t

&#x20;   to: approx.student\_t\_map

&#x20;   kind: approximates

&#x20;   description: >

&#x20;     Since conjugacy is not used here, the estimator is implemented as a

&#x20;     numerical MAP approximation.

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: deriv:student-t-map-objective



&#x20; - from: prior.gaussian\_beta

&#x20;   to: approx.student\_t\_map

&#x20;   kind: assumes

&#x20;   description: "The Student-t MAP approximation keeps the Gaussian prior on beta."

&#x20;   tex:

&#x20;     file: paper/derivations.tex

&#x20;     label: deriv:student-t-map-objective



Codex may refine this schema, but preserve the spirit.



Tool commands



Implement a command-line interface.



Use package entry point:



\[project.scripts]

mathgraph = "mathgraph\_tool.cli:main"

mathgraph check



Checks that the graph is internally and externally consistent.



It should validate:



YAML syntax.

Required fields.

Node IDs are unique.

Edge endpoints exist.

Edge kinds are recognized.

Node kinds are recognized.

TeX files exist.

TeX labels exist in the referenced files.

Code files exist.

Referenced Python symbols exist.

Test files exist.

Output paths are valid or at least parent directories exist.

The graph has no accidental duplicate IDs.

The graph has no dangling implementation references.

Optional: warn about cycles unless the cycle uses affects.



The output should be human-readable and useful:



mathgraph check



OK: loaded 14 nodes and 13 edges.

OK: all edge endpoints exist.

OK: all TeX files exist.

OK: all referenced TeX labels exist.

OK: all code paths exist.

OK: all Python symbols exist.



Warnings:

\- experiment.gaussian\_recovery output results/gaussian\_recovery\_summary.json does not exist yet.



If there are errors, exit with nonzero status.



mathgraph impact <node-id>



Given a node, show downstream affected nodes.



Use graph traversal over directed edges.



By default include outgoing reachability over these edge kinds:



defines

assumes

depends\_on

derives

implements

approximates

validates

tests

generates

uses

affects



Output should group by node kind and include code/test/output references.



Example:



mathgraph impact model.gaussian\_observation



Affected mathematical nodes:

\- likelihood.gaussian

\- posterior.gaussian\_conjugate

\- estimator.beta\_map

\- validation.synthetic\_recovery

\- experiment.gaussian\_recovery



Affected code:

\- src/linear\_bayes/likelihoods.py::gaussian\_log\_likelihood

\- src/linear\_bayes/estimators.py::gaussian\_posterior

\- src/linear\_bayes/estimators.py::beta\_map\_closed\_form

\- experiments/run\_gaussian\_recovery.py::main



Affected tests:

\- tests/test\_linear\_gaussian\_recovery.py::test\_recovery\_improves\_with\_n



Affected outputs:

\- results/gaussian\_recovery\_summary.json

\- results/gaussian\_recovery\_error.png



Also include edge descriptions along the paths if --verbose is passed.



mathgraph coverage



Report how much of the graph is connected to code, TeX, tests, and outputs.



Example:



mathgraph coverage



Nodes: 14

Edges: 13



TeX coverage:

\- nodes with TeX references: 12/14

\- edges with TeX derivation references: 13/13



Implementation coverage:

\- nodes with code references: 8/14

\- estimators with implementation: 2/2

\- assumptions with implementation: 5/6

\- simulators with implementation: 0/0



Validation coverage:

\- estimators connected to validation: 1/2

\- experiments with outputs declared: 1/2



Unimplemented mathematical nodes:

\- prior.gaussian\_beta



Code references not connected to tests:

\- src/linear\_bayes/estimators.py::student\_t\_map\_numerical

mathgraph node <node-id>



Print a full node card:



Node: estimator.beta\_map

Kind: estimator

Title: MAP estimator for beta

Statement:

&#x20; The MAP estimator minimizes the negative log posterior.



TeX:

&#x20; paper/derivations.tex#estimator:beta-map



Code:

&#x20; src/linear\_bayes/estimators.py::beta\_map\_closed\_form



Incoming edges:

&#x20; posterior.gaussian\_conjugate --derives--> estimator.beta\_map

&#x20;   The MAP estimator is the posterior mode...



Outgoing edges:

&#x20; estimator.beta\_map --validates--> validation.synthetic\_recovery

&#x20;   The synthetic recovery validation checks...

mathgraph render



Generate a static website in web/.



The webpage should include:



a graph visualization,

clickable nodes,

node detail panel,

clickable links to:

TeX file and label,

code file and symbol,

tests,

experiment scripts,

result files,

edge derivation references.



The first version can be simple. It does not need to integrate with an IDE. Links may be ordinary relative file links such as:



../paper/derivations.tex

../src/linear\_bayes/estimators.py

../tests/test\_linear\_gaussian\_recovery.py

../results/gaussian\_recovery\_error.png



For each node, the web page should display:



ID,

kind,

title,

statement,

TeX references,

code references,

outputs,

incoming edges,

outgoing edges,

edge descriptions,

derivation TeX labels for edges.



The graph should be visually grouped or color-coded by kind if simple to do. Do not overcomplicate.



Prefer a dependency-free static webpage if possible. A simple graph.json, index.html, style.css, and app.js is enough.



It is acceptable to render the graph with Mermaid loaded from CDN, but also provide a fallback list/detail view so that the webpage still shows useful information if Mermaid does not load.



mathgraph open <node-id>



Optional but useful.



Print the local file paths and labels associated with a node. If practical, open the generated web page or relevant local files using the system browser/editor. Keep this command simple and robust.



TeX requirements



Create paper/main.tex and paper/derivations.tex.



The TeX does not need to be a complete paper, but should be coherent enough to inspect.



It should include:



Definitions of variables and parameters.

Gaussian observation model.

Gaussian prior.

Gaussian likelihood.

Posterior derivation.

MAP/ridge derivation.

Synthetic recovery validation description.

Student-t noise model.

Student-t likelihood.

Student-t numerical MAP approximation.

Derivation labels corresponding to graph edges.



Use labels that match the graph.



For example:



\\label{def:design-matrix}

\\label{model:gaussian-observation}

\\label{prior:gaussian-beta}

\\label{likelihood:gaussian}

\\label{posterior:gaussian-conjugate}

\\label{deriv:gaussian-posterior}

\\label{deriv:map-from-posterior}

\\label{validation:synthetic-recovery}

\\label{change:gaussian-to-student-t}

\\label{deriv:student-t-likelihood}

\\label{deriv:student-t-map-objective}



The graph checker should simply verify that the label string appears somewhere in the TeX file. It does not need full LaTeX parsing.



Python implementation details

linear\_bayes.simulate



Implement:



def simulate\_gaussian\_linear(

&#x20;   n: int,

&#x20;   d: int,

&#x20;   beta: np.ndarray,

&#x20;   sigma: float,

&#x20;   seed: int | None = None,

) -> tuple\[np.ndarray, np.ndarray]:

&#x20;   ...



and:



def simulate\_student\_t\_linear(

&#x20;   n: int,

&#x20;   d: int,

&#x20;   beta: np.ndarray,

&#x20;   sigma: float,

&#x20;   nu: float,

&#x20;   seed: int | None = None,

) -> tuple\[np.ndarray, np.ndarray]:

&#x20;   ...



Use standard normal covariates unless otherwise specified.



linear\_bayes.likelihoods



Implement:



def gaussian\_log\_likelihood(

&#x20;   X: np.ndarray,

&#x20;   y: np.ndarray,

&#x20;   beta: np.ndarray,

&#x20;   sigma: float,

) -> float:

&#x20;   ...



and:



def student\_t\_log\_likelihood(

&#x20;   X: np.ndarray,

&#x20;   y: np.ndarray,

&#x20;   beta: np.ndarray,

&#x20;   sigma: float,

&#x20;   nu: float,

) -> float:

&#x20;   ...



Use scipy if available. Otherwise implement the Student-t log density manually using scipy.special.gammaln.



linear\_bayes.estimators



Implement:



def gaussian\_posterior(

&#x20;   X: np.ndarray,

&#x20;   y: np.ndarray,

&#x20;   sigma: float,

&#x20;   tau: float,

) -> tuple\[np.ndarray, np.ndarray]:

&#x20;   ...



Return (mu\_n, Sigma\_n).



Implement:



def beta\_map\_closed\_form(

&#x20;   X: np.ndarray,

&#x20;   y: np.ndarray,

&#x20;   sigma: float,

&#x20;   tau: float,

) -> np.ndarray:

&#x20;   ...



This should equal the posterior mean.



Implement:



def negative\_log\_posterior\_gaussian(

&#x20;   beta: np.ndarray,

&#x20;   X: np.ndarray,

&#x20;   y: np.ndarray,

&#x20;   sigma: float,

&#x20;   tau: float,

) -> float:

&#x20;   ...



Implement:



def student\_t\_map\_numerical(

&#x20;   X: np.ndarray,

&#x20;   y: np.ndarray,

&#x20;   sigma: float,

&#x20;   tau: float,

&#x20;   nu: float,

&#x20;   beta0: np.ndarray | None = None,

) -> np.ndarray:

&#x20;   ...



Use scipy.optimize.minimize.



linear\_bayes.experiments



Implement helper functions for experiments:



def run\_recovery\_experiment(

&#x20;   n\_values: list\[int],

&#x20;   d: int,

&#x20;   sigma: float,

&#x20;   tau: float,

&#x20;   beta\_true: np.ndarray,

&#x20;   seeds: list\[int],

) -> dict:

&#x20;   ...



Return a JSON-serializable dictionary with:



n values,

mean errors,

std errors,

all raw errors,

beta true,

sigma,

tau,

seeds.



Save plots separately in the experiment script.



Experiment scripts

Gaussian recovery



experiments/run\_gaussian\_recovery.py



Should:



choose a true beta, e.g. \[1.0, -0.5, 0.25],

run several sample sizes,

run several seeds,

compute posterior mean/MAP,

compute error norm,

save results/gaussian\_recovery\_summary.json,

save results/gaussian\_recovery\_error.png.



The plot should show mean error versus n, optionally with error bars.



Student-t change



experiments/run\_student\_t\_change.py



Should:



simulate Student-t data,

run Gaussian MAP and Student-t MAP,

compare coefficient error under heavy-tailed noise,

save results/student\_t\_change\_summary.json,

save results/student\_t\_change\_error.png.



This experiment is mainly for testing graph impact and alternative-branch traceability.



Tests



Implement tests for both the tool and the model.



Graph tests



tests/test\_mathgraph\_check.py



Should run the checker on mathgraph/graph.yaml and assert no hard errors.



tests/test\_graph\_references.py



Should assert that:



every TeX reference exists,

every code path exists,

every Python symbol exists.



These tests may call the same internal functions as mathgraph check.



Estimator test



tests/test\_linear\_gaussian\_recovery.py



Implement:



def test\_recovery\_improves\_with\_n():

&#x20;   ...



This should be robust and not flaky. For example:



use fixed seeds,

compare average error at small n and large n,

assert large-n error is smaller than small-n error by a reasonable margin.



Do not make the threshold too strict.



Also test:



def test\_closed\_form\_map\_equals\_posterior\_mean():

&#x20;   ...

Documentation

README.md



Include:



purpose of the project,

the philosophy,

installation,

running checks,

running experiments,

rendering webpage,

testing the Gaussian-to-Student-t change workflow.



Example commands:



pip install -e ".\[dev]"

mathgraph check

mathgraph coverage

mathgraph impact model.gaussian\_observation

pytest

python experiments/run\_gaussian\_recovery.py

python experiments/run\_student\_t\_change.py

mathgraph render

python -m http.server 8000 -d web



Then open:



http://localhost:8000

AGENTS.md



Create an AGENTS.md for Codex with the graph-centered rules.



It should say:



\# Repository Rules for Codex



This repository is mathgraph-centered.



Before editing code:

1\. Identify the relevant mathgraph node or nodes.

2\. If changing mathematical behavior, run or inspect `mathgraph impact <node-id>`.

3\. Update the graph before or together with code changes.

4\. Every nontrivial function must implement, approximate, validate, simulate, test, or generate output for a mathgraph node.

5\. Every estimator must have a validation path.

6\. Every edge expressing a mathematical relationship must have a TeX derivation reference.

7\. Do not add orphan code.

8\. Do not silently change model assumptions.

9\. After changes, run:

&#x20;  - `mathgraph check`

&#x20;  - relevant tests

&#x20;  - relevant experiments if behavior changed

10\. Report:

&#x20;  - changed graph nodes,

&#x20;  - changed TeX labels,

&#x20;  - changed code symbols,

&#x20;  - changed tests,

&#x20;  - downstream affected nodes.

Codex Skill



Create a reusable skill in:



codex-skill/mathgraph-centered-research/



The purpose of the skill is to instruct future Codex/ChatGPT sessions how to work in repositories that use this mathgraph-centered workflow.



codex-skill/mathgraph-centered-research/SKILL.md



Use this frontmatter:



\---

name: mathgraph-centered-research

description: mathematics-centered research workflow for codebases organized around an explicit graph of mathematical objects, derivations, implementations, tests, experiments, and outputs. use when working in repositories with a mathgraph/graph.yaml file, commands like mathgraph check/impact/coverage/render, TeX derivation references, or when asked to implement, modify, validate, or trace code from mathematical model definitions.

\---



Then include concise instructions:



\# Mathgraph-Centered Research Workflow



Use this skill when the repository contains a mathgraph specification or when the user wants code changes grounded in mathematical definitions.



Core principle:



TeX is for human mathematical exposition.

Code is for execution.

The graph is for identity, dependency, traceability, and change impact.

Codex is allowed to change code only by respecting the graph.



\## Required workflow



Before editing code:



1\. Locate `mathgraph/graph.yaml`.

2\. Identify the relevant graph node or nodes.

3\. Inspect the node statement, TeX references, code references, incoming edges, and outgoing edges.

4\. If changing behavior, run or reason through `mathgraph impact <node-id>`.

5\. Update graph, TeX, code, tests, and experiments consistently.



\## Rules



\- Do not add nontrivial code without attaching it to a graph node.

\- Do not change mathematical assumptions silently.

\- Every estimator must be connected to at least one validation node.

\- Every mathematical edge must include a TeX derivation reference.

\- Prefer coarse graph nodes with detailed edge descriptions.

\- Keep nodes unambiguous: a node should be fully specified by its own fields, neighboring nodes, and edge descriptions.

\- When adding an alternative assumption, create a sibling branch over shared variables and inspect downstream impact from the shared variables.

\- When introducing an approximation, create an `approximation` node and describe exactly what is approximated.



\## Standard commands



Run when relevant:



```bash

mathgraph check

mathgraph coverage

mathgraph impact <node-id>

mathgraph node <node-id>

pytest



Run after graph or documentation changes:



mathgraph render

Change report



At the end of a task, report:



graph nodes changed,

TeX labels changed,

code symbols changed,

tests changed,

experiments changed,

downstream nodes affected,

commands run and results.

When asked to implement a new estimator

Create or update the estimator node.

Attach TeX definition/derivation.

Attach implementation symbol.

Add or update validation node.

Add or update experiment node if needed.

Run mathgraph check.

Run relevant tests.

When asked to change a model assumption

Identify the existing model/assumption node.

Add the new model/assumption node.

Add incoming edges from the shared variable nodes and any assumptions that specify the new branch.

Run mathgraph impact <shared-variable-node-id> when comparing branch-level effects.

Update all affected likelihoods, posteriors, estimators, simulations, validations, experiments, and outputs.

Update TeX derivation references.

Run checks and tests.



\## `agents/openai.yaml`



Create simple metadata:



```yaml

interface:

&#x20; display\_name: Mathgraph Centered Research

&#x20; short\_description: Work with math-centered research repositories using graph-linked TeX, code, tests, and experiments.

&#x20; icon: graph

&#x20; accent\_color: blue

Skill references



Create:



codex-skill/mathgraph-centered-research/references/workflow.md

codex-skill/mathgraph-centered-research/references/graph-schema.md

codex-skill/mathgraph-centered-research/references/change-protocol.md



These can repeat and expand the workflow, but keep SKILL.md concise.



The skill does not need to include the whole tool implementation. The tool lives in the repository. The skill tells Codex how to use the tool and how to behave.



Implementation priorities



Implement in this order:



Phase 1: Graph schema and checker

Create pydantic models.

Load YAML graph.

Validate node/edge structure.

Validate TeX references.

Validate code paths and Python symbols.

Implement mathgraph check.

Add tests for the checker.

Phase 2: Demo mathematical model

Write TeX derivations.

Implement simulation, likelihood, posterior, MAP estimator.

Add Gaussian recovery experiment.

Add tests.

Phase 3: Impact and coverage

Build networkx graph.

Implement mathgraph impact.

Implement mathgraph coverage.

Ensure output is readable and useful.

Phase 4: Static webpage

Export graph to web/graph.json.

Build web/index.html, web/style.css, web/app.js.

Make nodes clickable.

Show node detail panel.

Show incoming/outgoing edges and derivation references.

Link to TeX/code/tests/outputs.

Phase 5: Student-t change workflow

Add Student-t model node.

Add Student-t likelihood node.

Add approximation node.

Add TeX derivations.

Implement Student-t simulator, likelihood, and numerical MAP.

Add Student-t comparison experiment.

Run mathgraph impact model.gaussian\_observation and verify that affected components are visible.

Phase 6: Skill and documentation

Write AGENTS.md.

Write README.md.

Create codex-skill/mathgraph-centered-research/.

Add SKILL.md, agents/openai.yaml, and reference docs.

Document how to use the skill with this repository.

Acceptance criteria



The project is successful when the following commands work:



pip install -e ".\[dev]"

mathgraph check

mathgraph coverage

mathgraph node estimator.beta\_map

mathgraph impact model.gaussian\_observation

pytest

python experiments/run\_gaussian\_recovery.py

python experiments/run\_student\_t\_change.py

mathgraph render



The following files should be generated or present:



results/gaussian\_recovery\_summary.json

results/gaussian\_recovery\_error.png

results/student\_t\_change\_summary.json

results/student\_t\_change\_error.png

web/index.html

web/graph.json

codex-skill/mathgraph-centered-research/SKILL.md

AGENTS.md



The graph webpage should allow clicking a node and seeing:



mathematical statement,

TeX reference,

code implementation,

tests,

outputs,

incoming edges,

outgoing edges,

derivation labels.



The tool should make it clear what is affected when the Gaussian noise assumption is replaced by Student-t noise.



Important design constraints

Keep graph nodes coarse.

Put detailed relationship information on edges.

Every mathematical edge must have a TeX derivation reference.

Every node should be unambiguous from itself plus its neighbors.

Avoid orphan code.

Avoid silent mathematical changes.

Prefer simple local files over databases.

Keep the first version understandable.

Make the tool useful immediately.

Do not use Lean or formal theorem proving in this version.

Final report expected from Codex



After implementation, provide a final report containing:



Summary of implemented components.

Repository structure.

Graph node/edge summary.

Commands run and whether they passed.

Example output from:

mathgraph check

mathgraph coverage

mathgraph impact model.gaussian\_observation

Description of Gaussian recovery experiment results.

Description of Student-t change experiment results.

How to open the webpage.

How to use the Codex skill.

Known limitations and next improvements.



\---



I would use this as the first Codex instruction almost exactly as written. The key thing is that Codex should build the tool and the toy project together, because the tool will otherwise become abstract and poorly tested.



One extra instruction I would personally add at the top when pasting to Codex is:



```markdown

Before writing code, first produce an implementation plan with milestones and file-level design. Then implement phase by phase. After each phase, run the relevant checks/tests and update the plan.



That gives you a controlled implementation rather than one giant code dump.

