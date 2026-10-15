# EDA methods and review decisions

Three specialist data-science reviews extended the original HI-Small profile. These methods explore the supplied synthetic ledger; they do not establish embezzlement or certify an operational detector. ACFE informs the evidence requirements in [the methodology review](acfe-methodology.md). The statistical and machine-learning methods are project choices, not ACFE-prescribed tests or thresholds.

| Review | Gap in the original notebook | Added analysis |
| --- | --- | --- |
| Statistical validity | The temporal profile showed a sharp change without measuring category shifts or adjusting for the category mix. | Base-2 Jensen–Shannon distances, label-conditioned retrospective comparisons, and direct standardization using main-period category rates. |
| Network structure | Account rows did not describe distinct counterparty relationships or connections between accounts of one entity. | Directed degree, reciprocity, same-entity transfers, and transaction-count concentration at account and publisher-entity levels. |
| Anomaly detection | The notebook examined one saved path rule without an independent behavioral ranking. | An upper-tail reference score and Isolation Forest, fitted on September 1–7 and scored on September 8–10 outgoing USD-to-USD account-days. |

## Observed results

- The main-to-tail joint currency/format Jensen–Shannon distance is **0.8572**; the label-0-only distance is **0.8564**. All 1,108 tail rows use ACH. Holding main-window category rates fixed gives **7.07** label-1 rows under format adjustment or **8.70** under joint currency/format adjustment, versus **655** observed. Category mix alone does not reproduce the tail label rate.
- The full network has **515,088 observed accounts** and **166,207 publisher entities**. **70,122** transfers connect different accounts of the same entity. Reciprocity is **1.14%** at account level and **3.51%** at entity level. The top 1% of observed nodes generate **20.99%** and **27.17%** of outgoing transaction rows, respectively.
- The anomaly experiment fits **430,805** account-days and scores **152,383** later account-days. Of those later profiles, **456** contain a labeled laundering outgoing transaction. Each method selects **1,524** profiles and includes **7** positive profiles: **0.459%** selected positive share and **1.535%** capture of positive account-days. Their lists overlap on **524** profiles. Neither method has higher positive capture at this fixed budget.
- The baseline has **653** equal-score profiles at its cutoff; the deterministic tie order selects **625** and excludes **28**. That arbitrary tie decision matters when interpreting its review list. The forest has one profile at its cutoff, with no excluded cutoff ties.

These are descriptive observations on scoped synthetic data. The network and anomaly sections count different units and populations; their results are not directly comparable to the saved two-payment path rule's transaction-label overlap.

## Cross-review corrections

The statistical reviewer caught a step-direction error in the network survival curve. The corrected curve places the lower survival share immediately after a degree threshold; a `[1, 5]` fixture checks its plotted vertices. Cross-review also clarified which network metrics include self-links, renamed unseen-account counts to account-days, and removed wording that could imply a preregistered experiment. The distance implementation matches SciPy on 50 independently generated comparisons.

## Interpretation and evaluation boundaries

- Full-ledger category and network summaries describe the complete supplied population. Transactions share accounts and entities; the notebook does not treat millions of rows as independent random observations or attach sampling confidence intervals to these totals.
- Jensen–Shannon distance measures a change in category shares, not fraud probability. Daily comparisons with the pooled main period are retrospective and include the reference day during that period.
- Direct standardization holds the main-period category label rates fixed while replacing category shares with tail shares. The decomposition is an arithmetic comparison, not a causal explanation. Every tail category must have a main-period reference rate.
- Network edges collapse repeated payments for counterparty counts. Reciprocity requires a reverse pair anywhere in the full snapshot; it does not require time order, matching money, matching currency, or an actual round trip. Full-period network measures must not become earlier-date predictive features.
- Anomaly profiles use daily outgoing USD-to-USD activity and become available after the day closes. Training is unlabeled and may contain illicit activity. The same account may appear in both date periods; the experiment measures later behavior in a shared customer population.
- The anomaly features, transforms, random seed, model settings and top-1% workload budget are fixed before AML-label diagnostics. The later batch determines its own rank cutoff, so this is a retrospective review budget rather than an online alert threshold.
- SQL floating-point amount aggregates support exploratory model features only. The original exact amounts remain available for reconciliation; model totals are not loss estimates or traced funds.
- Post-ranking positive shares and capture rates use account-days containing a labeled laundering outgoing transaction. They do not measure embezzlement accuracy, individual guilt, or independent fraud incidents.

## Reproduction

See [notebook setup and execution](../notebooks/README.md). The source notebook has cleared outputs; the execution helper writes the executed notebook, HTML preview, charts and execution report under ignored `reports/eda/`. Each added section reconciles its population and checks its own invariants during execution. Environment versions appear in the notebook.

The notebook links primary method references where it introduces each method. Useful next validation would use a separately generated or genuinely later dataset, stable peer groups, evidence-backed entity relationships, and predefined review budgets. Vendor, employee, invoice, receipt and approval evidence remain necessary for an embezzlement investigation.

The current Plotly execution completed **58 cells**, including **34 code cells** and **10 interactive figures**, with **zero errors** in **313.0 seconds**. Source cells and the source/theme hashes match the executed notebook and execution report; the tracked source has cleared outputs. The prior offline browser review confirmed all ten figures render with Open Sans, exact-count hover labels and working zoom/reset controls. The Colab adapter passed seven fixture checks; a browser check rendered two independent HTML frames and verified zoom. A signed-in hosted Colab run has not been performed. All **119** existing repository tests passed. [Presentation review](eda-design-review.md) describes the design-system conversion; analytical queries and model settings remain unchanged.
