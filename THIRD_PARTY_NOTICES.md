# Third-party notices and public analysis outputs

## IBM synthetic transaction data

Data provider: IBM. This project analyzes version 8 of [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), including the HI-Small transaction, account and pattern files. The publisher describes the data and its licence in the [IBM AML-Data repository](https://github.com/IBM/AML-Data).

IBM distributes the data under the [Community Data License Agreement – Sharing, Version 1.0](https://cdla.dev/sharing-1-0/) (`CDLA-Sharing-1.0`). IBM-derived records and identifiers reproduced in notebook examples and interactive figures retain that licence and attribution. The released outputs rearrange and aggregate source records, derive account roles from synthetic names, and calculate candidate paths, network measures and anomaly rankings. These are project transformations, not modifications endorsed by IBM. The repository does not apply a project-code licence to IBM data.

The raw CSV files and SQLite database are not distributed in this Git repository or the EDA release bundle. Acquisition links, schemas, limitations and source hashes are documented in the [data card](docs/ibm-data-card.md), [full-run method](docs/full-hi-small-method.md) and notebook outputs.

Research context: [Realistic Synthetic Financial Transactions for Anti-Money Laundering Models](https://arxiv.org/html/2306.16424v3). Synthetic laundering labels are not embezzlement labels or findings about real individuals.

## Plotly

The interactive HTML outputs embed Plotly.js through Plotly.py 6.9.0. Plotly is distributed under the MIT licence. Its copyright notices remain in the embedded JavaScript; the offline EDA bundle also includes the licence text. See [Plotly.py](https://github.com/plotly/plotly.py) and [Plotly.js](https://github.com/plotly/plotly.js).

## Open Sans

Copyright 2020 The Open Sans Project Authors. The embedded Open Sans Latin font is distributed under the SIL Open Font License 1.1. The source repository includes the full [licence](notebooks/assets/OpenSans-OFL.txt) and [provenance](notebooks/assets/README.md); the offline EDA bundle includes the licence text as well.

## Design and professional references

The presentation adapts the user-selected [Deloitte Data Design system](https://claude.ai/artifact/8LsWY495eAgpPAUWCxd336). No Deloitte logo or tagline is distributed. The analysis is independent research, and its draft label remains visible. References to ACFE, IBM and Deloitte do not imply certification, authorship or endorsement. See the [ACFE methodology](docs/acfe-methodology.md) and [design review](docs/eda-design-review.md).
