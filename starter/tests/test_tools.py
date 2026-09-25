"""指标查询回归测试：闭区间与 KB-001 v3 指标定义。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from kbqa.tools import DataTools


def _make_tools(tmp_path: Path) -> DataTools:
    db = tmp_path / "clean.db"
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            """
            CREATE TABLE sales_clean (
                order_id TEXT, date TEXT, store_id TEXT, product_id TEXT,
                qty INTEGER, amount_cents INTEGER, payment TEXT, is_refund INTEGER
            )
            """
        )
        con.execute(
            """
            CREATE TABLE products (
                product_id TEXT PRIMARY KEY, product_name TEXT,
                product_category TEXT, unit_price REAL
            )
            """
        )
        con.executemany(
            "INSERT INTO products VALUES (?,?,?,?)",
            [("P01", "拉面", "主食", 10.0), ("P02", "沙拉", "轻食", 2.0)],
        )
        con.executemany(
            "INSERT INTO sales_clean VALUES (?,?,?,?,?,?,?,?)",
            [
                ("A", "2026-06-01", "S01", "P01", 2, 1000, "现金", 0),
                ("A", "2026-06-01", "S01", "P01", 1, 500, "现金", 0),
                ("B", "2026-06-01", "S01", "P01", 1, 300, "现金", 0),
                ("Z", "2026-06-01", "S01", "P02", 3, 0, "现金", 0),
                ("B", "2026-06-02", "S01", "P01", 1, -200, "现金", 1),
                ("C", "2026-06-03", "S01", "P01", 1, 900, "微信", 0),
                ("D", "2026-06-03", "S01", "P02", 1, 200, "微信", 0),
            ],
        )
        con.commit()
    finally:
        con.close()
    return DataTools(db)


@pytest.fixture()
def tools(tmp_path):
    instance = _make_tools(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def test_query_metrics_uses_closed_range_and_kb001_formulas(tools):
    metrics = tools.query_metrics("2026-06-01", "2026-06-02")

    assert metrics["net_revenue"] == 16.00
    assert metrics["refund_amount"] == 2.00
    assert metrics["orders"] == 2
    assert metrics["aov"] == 8.00
    assert metrics["qty"] == 3


def test_daily_metrics_keeps_refund_on_its_own_day(tools):
    days = {
        day["date"]: day
        for day in tools.daily_metrics("2026-06-01", "2026-06-02")["days"]
    }

    assert days["2026-06-01"]["net_revenue"] == 18.00
    assert days["2026-06-01"]["orders"] == 2
    assert days["2026-06-01"]["aov"] == 9.00

    assert days["2026-06-02"]["net_revenue"] == -2.00
    assert days["2026-06-02"]["orders"] == 0
    assert days["2026-06-02"]["aov"] is None


def test_zero_amount_rows_are_not_sales(tools):
    """amount=0 既不是销售行也不是退款行，不进入任何对外指标。"""
    metrics = tools.query_metrics("2026-06-01", "2026-06-02")
    assert metrics["orders"] == 2
    assert metrics["qty"] == 3

    days = {
        day["date"]: day
        for day in tools.daily_metrics("2026-06-01", "2026-06-02")["days"]
    }
    assert days["2026-06-01"]["orders"] == 2

    cash = tools.payment_mix("2026-06-01", "2026-06-02")["payments"]["现金"]
    assert cash["orders"] == 2
    assert cash["qty"] == 3

    products = tools.top_products("2026-06-01", "2026-06-02")["products"]
    assert {item["product_id"] for item in products} == {"P01"}

    assert tools.first_sale_date("P02") == "2026-06-03"
    prices = tools.unit_price_check("P02", "2026-06-01", "2026-06-02")
    assert prices["rows"] == 0
    assert prices["observed_unit_prices"] == {}
    assert prices["latest_price"] is None
