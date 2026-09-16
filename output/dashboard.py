"""Streamlit dashboard for the e-commerce sales analysis.

Reuses data_loader.py and business_metrics.py for all data preparation and
metric calculation. This file only handles layout, styling and the
period-over-period comparison logic specific to the interactive dashboard
(e.g. picking a "previous period" of equal length to whatever date range is
selected in the filter).
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import data_loader as dl
import business_metrics as bm

DATA_PATH = "../ecommerce_data"

# Chart colors, assigned by role and reused across every chart and card.
PRIMARY_COLOR = "#2a78d6"
COMPARISON_COLOR = "#eb6834"
GOOD_COLOR = "#0ca30c"
CRITICAL_COLOR = "#d03b3b"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#898781"
TEXT_COLOR = "#0b0b0b"
STAR_COLOR = "#eda100"
SEQUENTIAL_SCALE = [
    "#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#1c5cab", "#0d366b",
]

st.set_page_config(page_title="E-commerce Sales Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .metric-card {
        background-color: #fcfcfb;
        border: 1px solid #e1e0d9;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #52514e;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        margin-bottom: 0.35rem;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 600;
        color: #0b0b0b;
        line-height: 1.2;
    }
    .metric-trend {
        font-size: 0.95rem;
        font-weight: 600;
        margin-top: 0.35rem;
    }
    .metric-stars {
        font-size: 1.6rem;
        letter-spacing: 0.1em;
        margin-top: 0.2rem;
    }
    .chart-card {
        background-color: #fcfcfb;
        border: 1px solid #e1e0d9;
        border-radius: 8px;
        padding: 0.75rem 1rem 0.25rem 1rem;
    }
    .chart-card-title {
        font-size: 1.0rem;
        font-weight: 600;
        color: #0b0b0b;
        margin-bottom: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data loading (cached so the raw CSVs are only read once per session)
# ---------------------------------------------------------------------------
@st.cache_data
def get_raw_data():
    return dl.load_raw_data(DATA_PATH)


@st.cache_data
def get_sales_dataset():
    raw = get_raw_data()
    return dl.build_sales_dataset(raw["orders"], raw["order_items"])


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def format_currency_short(value: float) -> str:
    """Format a dollar amount as e.g. $300K or $2.1M."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        formatted = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{sign}${formatted}M"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.0f}K"
    return f"{sign}${value:,.0f}"


def nice_ticks(max_value: float, n: int = 5) -> list:
    """Evenly spaced, round-numbered tick values from 0 to above max_value."""
    if max_value <= 0:
        return [0]
    raw_step = max_value / n
    magnitude = 10 ** math.floor(math.log10(raw_step))
    residual = raw_step / magnitude
    if residual > 5:
        step = 10 * magnitude
    elif residual > 2:
        step = 5 * magnitude
    elif residual > 1:
        step = 2 * magnitude
    else:
        step = magnitude
    ticks = []
    t = 0.0
    while t <= max_value + step:
        ticks.append(t)
        t += step
    return ticks


def trend_html(change_pct: float | None, higher_is_better: bool = True) -> str:
    """Build a colored arrow + percent-change span for a KPI card."""
    if change_pct is None or pd.isna(change_pct):
        return '<span class="metric-trend" style="color:#898781;">No comparison data</span>'
    is_increase = change_pct >= 0
    is_good = is_increase if higher_is_better else not is_increase
    color = GOOD_COLOR if is_good else CRITICAL_COLOR
    arrow = "▲" if is_increase else "▼"
    return f'<span class="metric-trend" style="color:{color};">{arrow} {change_pct:+.2f}%</span>'


def render_metric_card(column, label: str, value: str, trend_pct=None, higher_is_better: bool = True):
    trend = trend_html(trend_pct, higher_is_better) if trend_pct is not None else ""
    column.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {trend}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_star_card(column, score: float):
    full_stars = int(round(score))
    stars = "★" * full_stars + "☆" * (5 - full_stars)
    column.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{score:.2f}</div>
            <div class="metric-stars" style="color:{STAR_COLOR};">{stars}</div>
            <div class="metric-label">Average Review Score</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_axis_style(fig, **kwargs):
    margin = kwargs.pop("margin", dict(l=10, r=10, t=10, b=10))
    fig.update_layout(
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="#fcfcfb",
        font_color=TEXT_COLOR,
        margin=margin,
        **kwargs,
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    return fig


# ---------------------------------------------------------------------------
# Header: title + global date range filter
# ---------------------------------------------------------------------------
sales_all = get_sales_dataset()
raw = get_raw_data()

data_min = sales_all["order_purchase_timestamp"].min().date()
data_max = sales_all["order_purchase_timestamp"].max().date()
default_start = max(data_min, pd.Timestamp("2023-01-01").date())
default_end = min(data_max, pd.Timestamp("2023-12-31").date())

header_left, header_right = st.columns([3, 1])
with header_left:
    st.markdown("## E-commerce Sales Dashboard")
with header_right:
    date_range = st.date_input(
        "Date range",
        value=(default_start, default_end),
        min_value=data_min,
        max_value=data_max,
    )

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, default_end

previous_start, previous_end = dl.previous_period(start_date, end_date)
period_label = f"{start_date:%b %d, %Y} - {end_date:%b %d, %Y}"

# ---------------------------------------------------------------------------
# Filtered datasets for the current and previous periods
# ---------------------------------------------------------------------------
current_sales = dl.filter_by_status(
    dl.filter_by_date_range(sales_all, "order_purchase_timestamp", start_date, end_date)
)
previous_sales = dl.filter_by_status(
    dl.filter_by_date_range(sales_all, "order_purchase_timestamp", previous_start, previous_end)
)

revenue = bm.revenue_summary(current_sales, previous_sales if len(previous_sales) else None)
monthly_trend_current = bm.monthly_revenue_trend(current_sales)
monthly_trend_previous = bm.monthly_revenue_trend(previous_sales) if len(previous_sales) else pd.DataFrame()
monthly_growth = bm.average_monthly_growth_rate(monthly_trend_current)

current_delivery = dl.add_delivery_speed(current_sales)
previous_delivery = dl.add_delivery_speed(previous_sales)
delivery_current = bm.delivery_performance(current_delivery)
delivery_previous = bm.delivery_performance(previous_delivery) if len(previous_sales) else {}
delivery_change_pct = bm.pct_change(
    delivery_current["avg_delivery_days"], delivery_previous.get("avg_delivery_days")
) if delivery_previous else None

current_reviewed = dl.merge_review_scores(current_sales, raw["reviews"])
review_distribution = bm.review_score_distribution(current_reviewed)
avg_review_score = (
    (review_distribution.index.to_series() * review_distribution.values).sum()
    if len(review_distribution)
    else float("nan")
)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
kpi_cols = st.columns(4)
render_metric_card(
    kpi_cols[0], "Total Revenue", format_currency_short(revenue["total_revenue"]),
    revenue.get("revenue_change_pct"), higher_is_better=True,
)
growth_color = GOOD_COLOR if (pd.notna(monthly_growth) and monthly_growth >= 0) else CRITICAL_COLOR
kpi_cols[1].markdown(
    f"""
    <div class="metric-card">
        <div class="metric-label">Monthly Growth</div>
        <div class="metric-value" style="color:{growth_color};">
            {f"{monthly_growth:+.2f}%" if pd.notna(monthly_growth) else "N/A"}
        </div>
        <span class="metric-trend" style="color:#898781;">Avg. month-over-month</span>
    </div>
    """,
    unsafe_allow_html=True,
)
render_metric_card(
    kpi_cols[2], "Average Order Value", format_currency_short(revenue["avg_order_value"]),
    revenue.get("avg_order_value_change_pct"), higher_is_better=True,
)
render_metric_card(
    kpi_cols[3], "Total Orders", f"{revenue['total_orders']:,}",
    revenue.get("order_count_change_pct"), higher_is_better=True,
)

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Charts grid (2x2)
# ---------------------------------------------------------------------------
row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

# Revenue trend: solid current period, dashed previous period
with row1_col1:
    st.markdown('<div class="chart-card"><div class="chart-card-title">Revenue Trend</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(range(1, len(monthly_trend_current) + 1)),
            y=monthly_trend_current["revenue"],
            mode="lines+markers",
            name="Current period",
            line=dict(color=PRIMARY_COLOR, width=2.5),
            text=monthly_trend_current["period"],
            hovertemplate="%{text}<br>Revenue: $%{y:,.0f}<extra>Current</extra>",
        )
    )
    if len(monthly_trend_previous):
        fig.add_trace(
            go.Scatter(
                x=list(range(1, len(monthly_trend_previous) + 1)),
                y=monthly_trend_previous["revenue"],
                mode="lines+markers",
                name="Previous period",
                line=dict(color=COMPARISON_COLOR, width=2, dash="dash"),
                text=monthly_trend_previous["period"],
                hovertemplate="%{text}<br>Revenue: $%{y:,.0f}<extra>Previous</extra>",
            )
        )
    max_revenue = max(
        monthly_trend_current["revenue"].max() if len(monthly_trend_current) else 0,
        monthly_trend_previous["revenue"].max() if len(monthly_trend_previous) else 0,
    )
    y_ticks = nice_ticks(max_revenue)
    fig.update_layout(
        xaxis_title="Month of period",
        yaxis_title="Revenue",
        xaxis=dict(showgrid=True, gridcolor=GRID_COLOR, dtick=1),
        yaxis=dict(
            showgrid=True, gridcolor=GRID_COLOR, tickmode="array",
            tickvals=y_ticks, ticktext=[format_currency_short(v) for v in y_ticks],
            range=[0, y_ticks[-1]],
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=380,
    )
    apply_axis_style(fig)
    st.plotly_chart(fig, use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

# Top 10 categories by revenue
with row1_col2:
    st.markdown('<div class="chart-card"><div class="chart-card-title">Top 10 Categories by Revenue</div>', unsafe_allow_html=True)
    sales_by_category = bm.product_category_performance(
        dl.merge_product_category(current_sales, raw["products"])
    ).head(10).sort_values("revenue", ascending=True)
    x_ticks = nice_ticks(sales_by_category["revenue"].max() if len(sales_by_category) else 0)
    fig = px.bar(
        sales_by_category,
        x="revenue",
        y="product_category_name",
        orientation="h",
        color="revenue",
        color_continuous_scale=SEQUENTIAL_SCALE,
        text=sales_by_category["revenue"].apply(format_currency_short),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        xaxis_title="Revenue",
        yaxis_title="",
        xaxis=dict(
            showgrid=True, gridcolor=GRID_COLOR, tickmode="array",
            tickvals=x_ticks, ticktext=[format_currency_short(v) for v in x_ticks],
            range=[0, x_ticks[-1] * 1.2],
        ),
        coloraxis_showscale=False,
        height=380,
    )
    apply_axis_style(fig, margin=dict(l=10, r=40, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

# Revenue by state choropleth
with row2_col1:
    st.markdown('<div class="chart-card"><div class="chart-card-title">Revenue by State</div>', unsafe_allow_html=True)
    sales_by_state = bm.geographic_performance(
        dl.merge_customer_state(current_sales, raw["customers"])
    )
    fig = px.choropleth(
        sales_by_state,
        locations="customer_state",
        color="revenue",
        locationmode="USA-states",
        scope="usa",
        color_continuous_scale=SEQUENTIAL_SCALE,
        labels={"revenue": "Revenue"},
    )
    state_ticks = nice_ticks(sales_by_state["revenue"].max() if len(sales_by_state) else 0, n=4)
    fig.update_layout(
        height=380,
        coloraxis_colorbar=dict(
            title="Revenue", tickmode="array",
            tickvals=state_ticks, ticktext=[format_currency_short(v) for v in state_ticks],
        ),
    )
    apply_axis_style(fig, geo=dict(bgcolor="#fcfcfb"))
    st.plotly_chart(fig, use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

# Satisfaction vs delivery time
with row2_col2:
    st.markdown('<div class="chart-card"><div class="chart-card-title">Satisfaction vs Delivery Time</div>', unsafe_allow_html=True)
    current_with_bucket = current_reviewed.copy()
    current_with_bucket = dl.add_delivery_speed(current_with_bucket)
    current_with_bucket["delivery_time_bucket"] = current_with_bucket["delivery_speed_days"].apply(
        dl.categorize_delivery_speed
    )
    review_by_bucket = bm.review_score_by_delivery_bucket(current_with_bucket)
    fig = px.bar(
        review_by_bucket,
        x="delivery_time_bucket",
        y="avg_review_score",
        color_discrete_sequence=[PRIMARY_COLOR],
    )
    fig.update_layout(
        xaxis_title="Delivery Time",
        yaxis_title="Average Review Score",
        yaxis=dict(range=[0, 5], showgrid=True, gridcolor=GRID_COLOR),
        height=380,
    )
    apply_axis_style(fig)
    st.plotly_chart(fig, use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Bottom row
# ---------------------------------------------------------------------------
bottom_cols = st.columns(2)
render_metric_card(
    bottom_cols[0],
    "Average Delivery Time",
    f"{delivery_current['avg_delivery_days']:.1f} days",
    delivery_change_pct,
    higher_is_better=False,
)
render_star_card(bottom_cols[1], avg_review_score)

st.caption(f"Showing data for {period_label}, compared to {previous_start:%b %d, %Y} - {previous_end:%b %d, %Y}.")
