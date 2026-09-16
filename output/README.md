# E-commerce Sales Analysis

A configurable analysis of e-commerce order, product, customer and review
data. The original exploratory notebook (`EDA.ipynb`) has been refactored
into `EDA_Refactored.ipynb` plus two reusable Python modules, and the same
modules power an interactive Streamlit dashboard (`dashboard.py`). The
analysis can be re-run for any year, month, or comparison period without
editing the underlying logic.

## Contents

| File | Purpose |
|---|---|
| `dashboard.py` | Interactive Streamlit dashboard: KPI cards, revenue trend, category/geographic breakdowns, and satisfaction vs. delivery time, all driven by a single date range filter. |
| `EDA_Refactored.ipynb` | The analysis notebook: configuration, data preparation, metrics, charts, and a summary of observations. |
| `data_loader.py` | Loads the raw CSVs and provides general-purpose functions for filtering, joining and enriching the sales dataset (by period, status, product category, customer state, review score, delivery speed). |
| `business_metrics.py` | Computes metrics and metric tables (revenue, monthly trend, product/geographic performance, review distribution, delivery performance) from an already prepared dataset. |
| `requirements.txt` | Python dependencies needed to run the notebook and dashboard. |
| `.streamlit/config.toml` | Pins the dashboard to a light theme, independent of the viewer's OS/browser dark mode setting. |
| `EDA.ipynb` | The original, unrefactored exploratory notebook, kept for reference. |

## Setup

```bash
pip install -r requirements.txt
```

The notebook expects the raw dataset CSVs (`orders_dataset.csv`,
`order_items_dataset.csv`, `products_dataset.csv`, `customers_dataset.csv`,
`order_reviews_dataset.csv`) in a folder referenced by the `DATA_PATH`
variable in the notebook's Configuration cell. By default this points to
`../ecommerce_data`; change it if your data lives elsewhere.

## Running the analysis

Launch Jupyter from this directory (so `data_loader.py` and
`business_metrics.py` are importable) and run `EDA_Refactored.ipynb` top to
bottom:

```bash
jupyter notebook EDA_Refactored.ipynb
```

## Reconfiguring for a different period

All of the following live in one cell in Section 2 (Data Loading &
Configuration) of the notebook:

```python
DATA_PATH = "../ecommerce_data"
ANALYSIS_YEAR = 2023
ANALYSIS_MONTH = None       # 1-12, or None for the full year
COMPARISON_YEAR = 2022
COMPARISON_MONTH = None     # 1-12, or None for the full year
ORDER_STATUS = "delivered"  # order status considered a completed sale
```

Change any of these and re-run the notebook; every metric, chart and the
final summary recompute from the new configuration. Set `COMPARISON_YEAR` to
`None` to run the analysis without a comparison period.

## Running the dashboard

Launch Streamlit from this directory (so `data_loader.py` and
`business_metrics.py` are importable):

```bash
streamlit run dashboard.py
```

Use the date range picker in the top-right corner to set the analysis
period; every KPI card and chart recomputes from that selection. The
dashboard compares the selected period against the immediately preceding
period of the same length (e.g. selecting all of 2023 compares it to all of
2022; selecting a 30-day range compares it to the 30 days before that).

Note: the sample dataset contains only two stray order rows dated in 2021.
Selecting a period whose comparison period falls in 2021 (e.g. analyzing all
of 2022) will produce very large percent-change figures, since the
comparison base is nearly zero. This is a property of the sample data, not
a bug in the dashboard.

## Extending the analysis

- **New metric**: add a function to `business_metrics.py` with a docstring
  describing its inputs and outputs, then call it from a new cell in
  Section 5 of the notebook.
- **New data source or join**: add a loading or merge function to
  `data_loader.py` following the pattern of the existing `merge_*`
  functions (take a DataFrame, return a new DataFrame, don't mutate the
  input).
- **New dataset entirely**: point `DATA_PATH` at a folder with the same file
  names and column structure described in the notebook's Data Dictionary
  section; no code changes are required as long as the column names match.
- **New dashboard card or chart**: `dashboard.py` reuses the same
  `data_loader`/`business_metrics` functions as the notebook, plus small
  presentation helpers (`format_currency_short`, `nice_ticks`,
  `render_metric_card`, `apply_axis_style`) for consistent formatting and
  styling. Add a new metric or chart by calling the relevant
  `business_metrics` function and one of these helpers, following the
  pattern of the existing KPI cards and charts.
