"""Business metric calculations for the e-commerce sales analysis.

Every function here takes an already loaded, filtered and joined DataFrame
(see data_loader.py for that step) and returns an aggregated metric or
metric table. Keeping these two concerns separate means a new metric can be
added without touching how data is loaded, and vice versa.

None of the functions in this module apply a qualitative judgment (e.g.
labeling a result "good" or "bad") - they report what the data says and
leave interpretation to the analyst reading the notebook.
"""

from __future__ import annotations

import pandas as pd


def pct_change(current: float, previous: float) -> float | None:
    """Percent change from `previous` to `current`.

    Args:
        current: The later value.
        previous: The earlier value being compared against.

    Returns:
        Percent change as a number (e.g. 12.5 for +12.5%), or None if
        `previous` is zero, missing, or NaN, since the change is undefined
        in that case.
    """
    if previous is None or pd.isna(previous) or previous == 0:
        return None
    return (current - previous) / previous * 100


def revenue_summary(
    sales: pd.DataFrame, comparison_sales: pd.DataFrame | None = None
) -> dict:
    """Compute headline revenue metrics for a sales period.

    Args:
        sales: Item-level sales DataFrame for the analysis period.
        comparison_sales: Item-level sales DataFrame for a comparison
            period, or None to skip period-over-period changes.

    Returns:
        Dict with total_revenue, total_orders, total_items and
        avg_order_value for the analysis period. If comparison_sales is
        given, also includes the same three metrics for the comparison
        period plus revenue_change_pct, order_count_change_pct and
        avg_order_value_change_pct.
    """
    total_revenue = sales["price"].sum()
    total_orders = sales["order_id"].nunique()
    total_items = len(sales)
    avg_order_value = sales.groupby("order_id")["price"].sum().mean()

    summary = {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "total_items": total_items,
        "avg_order_value": avg_order_value,
    }

    if comparison_sales is not None:
        comparison_revenue = comparison_sales["price"].sum()
        comparison_orders = comparison_sales["order_id"].nunique()
        comparison_aov = comparison_sales.groupby("order_id")["price"].sum().mean()

        summary.update(
            {
                "comparison_total_revenue": comparison_revenue,
                "comparison_total_orders": comparison_orders,
                "comparison_avg_order_value": comparison_aov,
                "revenue_change_pct": pct_change(total_revenue, comparison_revenue),
                "order_count_change_pct": pct_change(total_orders, comparison_orders),
                "avg_order_value_change_pct": pct_change(avg_order_value, comparison_aov),
            }
        )

    return summary


def monthly_revenue_trend(
    sales: pd.DataFrame, date_column: str = "order_purchase_timestamp"
) -> pd.DataFrame:
    """Aggregate revenue by calendar month with month-over-month growth.

    Groups by year-month period rather than month alone, so the trend is
    correct even when the input spans more than one calendar year.

    Args:
        sales: Item-level sales DataFrame with a parsed datetime column.
        date_column: Name of the timestamp column to group by.

    Returns:
        DataFrame with one row per month present in the data, sorted
        chronologically, with columns: period (e.g. "2023-04"), revenue,
        and revenue_change_pct (month-over-month percent change; NaN for
        the first month).
    """
    period = sales[date_column].dt.to_period("M")
    monthly = sales.groupby(period)["price"].sum().rename("revenue").reset_index()
    monthly[date_column] = monthly[date_column].astype(str)
    monthly = monthly.rename(columns={date_column: "period"})
    monthly["revenue_change_pct"] = monthly["revenue"].pct_change() * 100
    return monthly


def average_monthly_growth_rate(monthly_trend: pd.DataFrame) -> float:
    """Average month-over-month revenue growth rate across a period.

    Args:
        monthly_trend: Output of monthly_revenue_trend(), with a
            revenue_change_pct column.

    Returns:
        Mean of revenue_change_pct across all months that have a prior
        month to compare against (the first month's NaN is excluded). NaN
        if fewer than two months are present.
    """
    return monthly_trend["revenue_change_pct"].mean()


def product_category_performance(sales_with_category: pd.DataFrame) -> pd.DataFrame:
    """Rank product categories by revenue.

    Args:
        sales_with_category: Item-level sales DataFrame including a
            product_category_name column (see
            data_loader.merge_product_category).

    Returns:
        DataFrame sorted descending by revenue, with columns
        product_category_name, revenue and revenue_share_pct.
    """
    by_category = (
        sales_with_category.groupby("product_category_name")["price"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"price": "revenue"})
    )
    by_category["revenue_share_pct"] = (
        by_category["revenue"] / by_category["revenue"].sum() * 100
    )
    return by_category


def geographic_performance(sales_with_state: pd.DataFrame) -> pd.DataFrame:
    """Rank customer states by revenue.

    Args:
        sales_with_state: Item-level sales DataFrame including a
            customer_state column (see data_loader.merge_customer_state).

    Returns:
        DataFrame sorted descending by revenue, with columns
        customer_state, revenue and revenue_share_pct.
    """
    by_state = (
        sales_with_state.groupby("customer_state")["price"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"price": "revenue"})
    )
    by_state["revenue_share_pct"] = by_state["revenue"] / by_state["revenue"].sum() * 100
    return by_state


def review_score_distribution(sales_with_reviews: pd.DataFrame) -> pd.Series:
    """Normalized distribution of review scores, one row per order.

    Args:
        sales_with_reviews: Sales DataFrame including order_id and
            review_score (see data_loader.merge_review_scores). May contain
            multiple item rows per order; these are deduplicated to order
            level before counting.

    Returns:
        Series indexed by review_score (ascending) with the share of
        orders at each score.
    """
    order_level = sales_with_reviews[["order_id", "review_score"]].drop_duplicates(
        "order_id"
    )
    return order_level["review_score"].value_counts(normalize=True).sort_index()


def delivery_performance(sales_with_delivery: pd.DataFrame) -> dict:
    """Summarize delivery speed for a sales period.

    Args:
        sales_with_delivery: Sales DataFrame including order_id and
            delivery_speed_days (see data_loader.add_delivery_speed). May
            contain multiple item rows per order; these are deduplicated to
            order level before averaging.

    Returns:
        Dict with avg_delivery_days and median_delivery_days.
    """
    order_level = sales_with_delivery[["order_id", "delivery_speed_days"]].drop_duplicates(
        "order_id"
    )
    return {
        "avg_delivery_days": order_level["delivery_speed_days"].mean(),
        "median_delivery_days": order_level["delivery_speed_days"].median(),
    }


def review_score_by_delivery_bucket(
    sales_with_delivery_and_review: pd.DataFrame,
    bucket_column: str = "delivery_time_bucket",
) -> pd.DataFrame:
    """Average review score for each delivery-time bucket.

    Args:
        sales_with_delivery_and_review: Sales DataFrame including order_id,
            review_score and a delivery-time bucket column (see
            data_loader.categorize_delivery_speed). May contain multiple
            item rows per order; these are deduplicated to order level
            first.
        bucket_column: Name of the delivery-time bucket column.

    Returns:
        DataFrame with one row per bucket: the bucket column,
        avg_review_score and order_count.
    """
    order_level = sales_with_delivery_and_review[
        ["order_id", bucket_column, "review_score"]
    ].drop_duplicates("order_id")
    return (
        order_level.groupby(bucket_column)["review_score"]
        .agg(avg_review_score="mean", order_count="count")
        .reset_index()
    )


def order_status_distribution(orders: pd.DataFrame) -> pd.Series:
    """Normalized distribution of order statuses.

    Args:
        orders: Orders DataFrame already filtered to the desired period,
            with an order_status column.

    Returns:
        Series indexed by order_status with the share of orders in each
        status, sorted descending.
    """
    return orders["order_status"].value_counts(normalize=True).sort_values(ascending=False)
