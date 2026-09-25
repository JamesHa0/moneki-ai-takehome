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
        con.executemany(
            "INSERT INTO sales_clean VALUES (?,?,?,?,?,?,?,?)",
            [
                ("A", "2026-06-01", "S01", "P01", 2, 1000, "现金", 0),
                ("A", "2026-06-01", "S01", "P01", 1, 500, "现金", 0),
                ("B", "2026-06-01", "S01", "P01", 1, 300, "现金", 0),
                ("B", "2026-06-02", "S01", "P01", 1, -200, "现金", 1),
                ("C", "2026-06-03", "S01", "P01", 1, 900, "现金", 0),
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
