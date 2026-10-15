# HI-Small exploratory notebook

`hi_small_eda.ipynb` profiles the full ledger and examines the saved two-payment candidate scan. It recomputes aggregate SQL results, checks them against the independent audit, and validates all saved candidate IDs. Database access is read-only. It does not rerun acquisition, import or detection.

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

The helper creates its kernel configuration under ignored `work/jupyter-runtime/`; it does not install a kernel into the user's home directory. It writes an executed notebook, static HTML preview, figures and an execution report to ignored `reports/eda/`. The tracked source notebook has cleared outputs so generated case-analysis artifacts stay outside Git.

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

Environment versions are displayed in the notebook. The verified execution used Python 3.9, pandas 2.3.3, numpy 2.0.2 and matplotlib 3.9.4. Per-cell timeout defaults to 300 seconds and can be increased with `--timeout` on slower machines.
