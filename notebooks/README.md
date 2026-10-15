# HI-Small exploratory notebook

`hi_small_eda.ipynb` profiles the full ledger and examines the saved two-payment candidate scan. It recomputes aggregate SQL results, checks them against the independent audit, and validates all saved candidate IDs. Database access is read-only. It does not rerun acquisition, import or the saved transaction-path scan.

The advanced sections quantify temporal distribution shifts, adjust the main/tail label-rate comparison for category mix, compare account and entity networks, and test two anomaly rankings with an earlier-fit/later-score split. [Methods and review decisions](../docs/eda-methods.md) explains the assumptions and evaluation boundaries.

Install the optional EDA environment from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[eda]'
```

Open the notebook in a notebook-capable editor and select this repository's `.venv/bin/python` kernel. Run cells in order. Or execute and export it with:

```sh
.venv/bin/python notebooks/execute_eda.py
```

The helper creates its kernel configuration under ignored `work/jupyter-runtime/`; it does not install a kernel into the user's home directory. It writes an executed notebook, an interactive HTML preview, ten standalone interactive figure pages, Plotly JSON specifications and an execution report to ignored `reports/eda/`. The tracked source notebook has cleared outputs so generated case-analysis artifacts stay outside Git.

All visualizations use Plotly. The notebook applies the user-selected [Deloitte Data Design system](https://claude.ai/artifact/8LsWY495eAgpPAUWCxd336) through `eda_design.py` and `eda_style.css`: semantic colour tokens, Open Sans, finding-first titles, quiet axes, source captions and black-header tables. The HTML preview hides code inputs for reading; the notebook retains all source cells. Plotly JavaScript and the licensed Open Sans Latin variable font are embedded for offline viewing. Some notebook editors require trusted outputs to render interactive HTML; Plotly MIME outputs are also included for compatible editors.

Editors can retain their own outer notebook typography and interface. Use the HTML preview for the complete page design. Plotly's SVG download contains the chart; carry its note and source caption with it when publishing elsewhere.

The scatter references use opaque square marks. The anomaly chart shows a seeded 5,000-profile reference plus every selected profile. Network concentration curves retain fewer than 2,000 display coordinates per curve, including exact endpoints and the top-1% boundary. All analytical summaries still use their complete stated populations. See [design review and provenance](../docs/eda-design-review.md).

Required local inputs:

- `data/hi-small.sqlite`, containing the full imported transaction CSV.
- `data/raw/full-hi-small/acquisition.json`.
- `data/raw/full-hi-small/HI-Small_Trans.csv`, `HI-Small_accounts.csv`, and `HI-Small_Patterns.txt`, each with its adjacent `.source.json` sidecar.
- `reports/hi-small-audit.json`, `reports/hi-small-scan.json`, `reports/hi-small-candidates.jsonl`, and `reports/hi-small-run-provenance.json`.

The notebook can also show the prior candidate verification and pattern-scope reports when they exist. These are local run artifacts, not files included in a fresh clone. See [the full-run method](../docs/full-hi-small-method.md) and [results](../docs/full-hi-small-results.md). If these files are missing, complete acquisition/import/audit/scan first; the notebook reports missing inputs explicitly.

The notebook finds the repository through its current directory and parents. If you open a copied notebook elsewhere, set `EMBEZZLEMENT_REPO_ROOT` to the absolute repository directory.

## Coverage and statistical limits

Ledger counts and category summaries use all 5,078,345 transaction rows. The amount-distribution plot uses all USD-paid label-1 rows and a deterministic systematic reference of USD-paid label-0 rows (`id % 100 == 0`). It is not a random sample, and the notebook does not use its proportions to estimate prevalence. It never combines monetary amounts across currencies.

The candidate section loads all 905 saved paths and distinguishes their 448 distinct transactions. It preserves exact amount strings and validates ratios with rational arithmetic; floating-point values are used only for plots and display. Candidate concentration is not an incident count or a loss estimate. The dataset's synthetic laundering label is not confirmed embezzlement ground truth.

The anomaly experiment uses all main-period USD-to-USD transactions, aggregated by sender account and day. It fits September 1–7 profiles and scores September 8–10 profiles after each day closes. It uses floating-point amount aggregates for exploratory features. Labels enter only post-ranking diagnostics. Full-period graph measures and retrospective distribution comparisons do not enter this model.

Environment versions are displayed in the notebook. The environment uses Python 3.9, pandas 2.3.3, numpy 2.0.2, Plotly 6.9.0 and scikit-learn 1.6.1. Per-cell timeout defaults to 300 seconds and can be increased with `--timeout` on slower machines.

Validate authored colours after execution:

```sh
.venv/bin/python notebooks/check_colours.py notebooks/hi_small_eda.ipynb notebooks/eda_design.py notebooks/eda_style.css reports/eda/figures/*.plotly.json
```

This checks authored styles and actual figure specifications. The bundled third-party Plotly JavaScript contains unused built-in palettes, so a literal colour scan of that vendor bundle does not measure the rendered chart style. The runtime helper separately checks chart colours and mark opacity. Font provenance and redistribution terms are saved under `notebooks/assets/`.
