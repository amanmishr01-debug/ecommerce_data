"""Data loading and preparation utilities for the e-commerce sales analysis.

Reads the raw CSV extracts, joins them into an item-level sales dataset, and
provides general-purpose helpers for filtering that dataset to a given
period and enriching it with product, geographic, review and delivery
information. All functions are pure (they return new DataFrames rather than
mutating their inputs) so they can be composed freely in a notebook or script.
"""

from __future__ import annotations

import os

import pandas as pd

RAW_FILES = {
    "orders": "orders_dataset.csv",
    "order_items": "order_items_dataset.csv",
    "products": "products_dataset.csv",
    "customers": "customers_dataset.csv",
    "reviews": "order_reviews_dataset.csv",
}


def load_raw_data(data_path: str) -> dict[str, pd.DataFrame]:
    """Load the raw e-commerce CSV extracts.

    Args:
        data_path: Directory containing the raw dataset CSV files.

    Returns:
        Dictionary keyed by dataset name ("orders", "order_items",
        "products", "customers", "reviews") mapping to its DataFrame.
    """
    return {
        name: pd.read_csv(os.path.join(data_path, filename))
        for name, filename in RAW_FILES.items()
    }


def build_sales_dataset(orders: pd.DataFrame, order_items: pd.DataFrame) -> pd.DataFrame:
    """Build an item-level sales dataset by joining orders and order items.

    Parses the purchase and delivery timestamp columns to datetime so that
    downstream filtering and aggregation can rely on them being real
    timestamps rather than strings.

    Args:
        orders: Raw orders DataFrame (one row per order).
        order_items: Raw order items DataFrame (one row per line item).

    Returns:
        Item-level DataFrame with one row per order line item, carrying
        order status and date columns from the parent order.
    """
    sales = order_items[["order_id", "order_item_id", "product_id", "price"]].merge(
        orders[
            [
                "order_id",
                "customer_id",
                "order_status",
                "order_purchase_timestamp",
                "order_delivered_customer_date",
            ]
        ],
        on="order_id",
        how="left",
    )
    sales["order_purchase_timestamp"] = pd.to_datetime(sales["order_purchase_timestamp"])
    sales["order_delivered_customer_date"] = pd.to_datetime(sales["order_delivered_customer_date"])
    return sales


def filter_by_period(
    df: pd.DataFrame,
    date_column: str,
    year: int | None = None,
    month: int | None = None,
) -> pd.DataFrame:
    """Filter any DataFrame to rows within a calendar year and/or month.

    This is the single filtering primitive used for both the raw orders
    table and the joined sales dataset, so the analysis period can be
    reconfigured in one place.

    Args:
        df: DataFrame containing a timestamp column.
        date_column: Name of the column holding order timestamps.
        year: Calendar year to keep, or None to keep every year.
        month: Calendar month (1-12) to keep, or None to keep every month.

    Returns:
        A filtered copy of df. If both year and month are None, an
        unfiltered copy of df is returned.
    """
    filtered = df
    if year is not None:
        filtered = filtered[filtered[date_column].dt.year == year]
    if month is not None:
        filtered = filtered[filtered[date_column].dt.month == month]
    return filtered.copy()


def filter_by_date_range(df: pd.DataFrame, date_column: str, start_date, end_date) -> pd.DataFrame:
    """Filter any DataFrame to rows within an inclusive calendar date range.

    Unlike filter_by_period (which matches a whole year and/or month), this
    accepts arbitrary start and end dates, as used by an interactive date
    range picker.

    Args:
        df: DataFrame containing a timestamp column.
        date_column: Name of the column holding order timestamps.
        start_date: First calendar date to include (a date or datetime).
        end_date: Last calendar date to include, inclusive (a date or
            datetime).

    Returns:
        A filtered copy of df.
    """
    dates = df[date_column].dt.date
    mask = (dates >= pd.Timestamp(start_date).date()) & (dates <= pd.Timestamp(end_date).date())
    return df[mask].copy()


def previous_period(start_date, end_date) -> tuple:
    """Compute the immediately preceding period of the same length.

    Given a current analysis period, returns the date range of equal length
    ending the day before the current period starts, for period-over-period
    comparisons (e.g. "last 30 days" vs "the 30 days before that").

    Args:
        start_date: Start date of the current period.
        end_date: End date of the current period (inclusive).

    Returns:
        (previous_start_date, previous_end_date) tuple of dates, inclusive.
    """
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    period_length = end_ts - start_ts
    previous_end = start_ts - pd.Timedelta(days=1)
    previous_start = previous_end - period_length
    return previous_start.date(), previous_end.date()


def filter_by_status(sales: pd.DataFrame, status: str = "delivered") -> pd.DataFrame:
    """Filter the sales dataset to a single order status.

    Args:
        sales: Item-level sales DataFrame with an order_status column.
        status: Order status to keep (e.g. "delivered").

    Returns:
        A filtered copy of sales.
    """
    return sales[sales["order_status"] == status].copy()


def add_delivery_speed(sales: pd.DataFrame) -> pd.DataFrame:
    """Add a delivery_speed_days column (days from purchase to delivery).

    Rows where the order has not been delivered (missing delivery date)
    get a missing (NaN) delivery speed.

    Args:
        sales: Sales DataFrame with order_purchase_timestamp and
            order_delivered_customer_date columns already parsed to
            datetime.

    Returns:
        Copy of sales with an added delivery_speed_days column.
    """
    sales = sales.copy()
    sales["delivery_speed_days"] = (
        sales["order_delivered_customer_date"] - sales["order_purchase_timestamp"]
    ).dt.days
    return sales


def categorize_delivery_speed(
    days: float,
    bin_edges: tuple[int, ...] = (3, 7),
) -> str:
    """Bucket a delivery time in days into labeled ranges.

    Bucket boundaries are a parameter rather than a fixed rule, so the
    granularity of the breakdown can be adjusted per analysis without
    editing this function.

    Args:
        days: Delivery time in days.
        bin_edges: Ascending inclusive upper bounds for all but the last
            bucket. The default (3, 7) produces buckets "1-3 days",
            "4-7 days" and "8+ days".

    Returns:
        The label of the bucket the given day count falls into, or "unknown"
        if days is missing.
    """
    if pd.isna(days):
        return "unknown"

    lower = 1
    for edge in bin_edges:
        if days <= edge:
            return f"{lower}-{edge} days" if lower != edge else f"{edge} days"
        lower = edge + 1
    return f"{lower}+ days"


def merge_product_category(sales: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Attach product_category_name to each sales row.

    Args:
        sales: Item-level sales DataFrame with a product_id column.
        products: Raw products DataFrame.

    Returns:
        Copy of sales with an added product_category_name column. Rows
        whose product_id has no match in products get a missing category.
    """
    return sales.merge(
        products[["product_id", "product_category_name"]], on="product_id", how="left"
    )


def merge_customer_state(sales: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Attach customer_state to each sales row.

    Args:
        sales: Item-level sales DataFrame with a customer_id column.
        customers: Raw customers DataFrame.

    Returns:
        Copy of sales with an added customer_state column. Rows whose
        customer_id has no match in customers get a missing state.
    """
    return sales.merge(
        customers[["customer_id", "customer_state"]], on="customer_id", how="left"
    )


def merge_review_scores(sales: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """Attach review_score to each sales row for orders that have a review.

    Uses an inner join: orders without a matching review are dropped, since
    review-based metrics (satisfaction, delivery-speed-vs-review) are only
    meaningful for reviewed orders.

    Args:
        sales: Item-level sales DataFrame with an order_id column.
        reviews: Raw order reviews DataFrame.

    Returns:
        Copy of sales restricted to rows with a matching review, with an
        added review_score column.
    """
    review_scores = reviews[["order_id", "review_score"]].drop_duplicates("order_id")
    return sales.merge(review_scores, on="order_id", how="inner")
