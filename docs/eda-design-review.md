# EDA design review

Design reference: [Deloitte Data Design](https://claude.ai/artifact/8LsWY495eAgpPAUWCxd336), read on 15 October 2026, including its overview, chart/table rules, writing rules and Python styling asset. This is a local research application of that system, not official brand approval or Deloitte-authored analysis.

## Critical issues found (now fixed)

| # | Rule broken | Where | Fix applied |
| --- | --- | --- | --- |
| 1 | Exact guide colours only; no opacity blends | Scatter marks and guide lines | Opaque Plotly marks and exact semantic tokens replace alpha blends. |
| 2 | Comparing groups follows the prescribed order | Multiseries profiles and networks | Series use Deloitte Green, Deep Green, Blue 4, Teal 4 in order. |
| 3 | Text never in a chart colour | Distribution-shift end labels | Data labels use black; axes and captions use Cool Gray 11. |
| 4 | Fonts: Open Sans in notebooks and HTML | Chart and notebook typography | Licensed Open Sans is embedded for offline viewing. |
| 5 | A source line on every chart | Figure framing | Every figure includes scope, units, a note where needed, and a truthful project-analysis source caption. |
| 6 | Column names are plain words | Raw diagnostic column names | Display headers remove underscores; source data and formatting keys stay unchanged. |
| 7 | Quiet structure; no shadows or decorative motifs | HTML export and scatter markers | White surfaces, square table edges, thin horizontal rules and square data marks. |
| 8 | User requires Plotly visualizations | All ten figures | Matplotlib is removed from the notebook and optional EDA dependencies; every figure has Plotly MIME, HTML and JSON output. |

## Brand specifications now used

- `surface`/white `#FFFFFF`; `text`/black `#000000`; `text-muted`/Cool Gray 11 `#53565A`; `line` and `chart-rest`/Cool Gray 4 `#BBBCBC`.
- `chart-focus`/Deloitte Green `#86BC25`; comparison groups continue with Deep Green `#046A38`, Blue 4 `#0076A8`, Teal 4 `#00ABAB`.
- Open Sans, weights 400, 600 and 700; a four-pixel spacing base; flat surfaces and square corners.
- No circle motif, recreated logo or tagline. Scatter squares represent observations, not decoration.
- Source captions identify project analysis of IBM synthetic data. They do not falsely attribute this work to Deloitte.

## Optional improvements

Consider a separately approved publication template before external use. The HTML preview already keeps dense charts and tables inside their own horizontal scroll regions on narrow screens. Exact full-population tables accompany display sampling; future graphical additions should preserve that separation. Plotly's native SVG download exports the chart; include the HTML note and source caption when reusing that image elsewhere.

## Writing check

Titles state findings in sentence case. Scope and units appear below titles. Table headers use plain words, numeric formats preserve relevant precision, and source captions distinguish observations from allegations. The draft label is visible. Research terminology retains employee/customer references where these describe the data; it does not relabel them as Deloitte personnel or clients.

## Approval flags

| Item | Why it needs review |
| --- | --- |
| External brand use | The reference is practical guidance, not official approval. The notebook carries “Draft for Brand, Legal, Risk and Independence review.” |
| Logo and tagline | Neither is used; approved artwork or wording would be needed before adding either. |
| Third-party runtime | Plotly's bundled JavaScript contains unused palette literals. The colour gate checks authored code, CSS and actual figure specifications; browser checks verify the rendered output. |

## Final quality check

**Pass for local implementation.** The final run completed 33 code cells and ten interactive Plotly figures with zero errors and no PNG figure outputs. The colour gate passes for the notebook source, theme, CSS and all ten figure specifications. Browser checks confirm all ten charts, 27 tables, ten source captions, loaded Open Sans, working hover/zoom/reset, no page-wide horizontal overflow at the checked viewport, and no console errors or warnings. Automatic margins fix the clipped recipient labels; the repeated-Run-All test confirms exactly one offline Plotly bundle per run. All 119 repository tests pass. External brand approval remains subject to the flags above.

Colour check: PASS (authored source, theme and figure specifications).
