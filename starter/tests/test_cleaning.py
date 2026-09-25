"""清洗口径回归测试：KB-001 v3 §2 规范化 + §3 六条剔除。

断言全部打在本文件自造的迷你数据上，因此与随包数据无关，换掉 data/ 之后依然成立。
随包数据的期望值（18290、8/150/30/10/40/100）只留在注释里，不写成断言。
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from kbqa.cleaning import build_clean_db

#: 每一行**只违反一条**剔除规则 → 六个计数的归属没有歧义，
#: 任何正确实现都必然得到同样的数字。
SALES = [
    # ── 合法行，必须保留 ────────────────────────────────────────────
    ("o1",  "2026-06-01",  "S01",  "P01", "2",  "38.00",         "现金"),
    ("o2",  "2026/6/2",    "s02 ", "p02", "1",  "¥38.00",        "微信"),  # 规范化三连
    ("o3",  "03-06-2026",  "S01",  "P01", "1",  "38.00",         "现金"),  # 日在前
    ("o4",  "2026-06-04",  "S01",  "P01", "1",  "\u3000¥38.00 ", "现金"),  # 全角空格
    ("o20", "2026-06-05",  "S01",  "P01", "1",  "38.00",         "现金"),  # 多行单第 1 行
    ("o20", "2026-06-05",  "S01",  "P02", "1",  "25.00",         "现金"),  # 多行单第 2 行
    ("o21", "2026-06-06",  "S01",  "P01", "1",  "-38.00",        "现金"),  # 退款行
    ("o22", "2026-06-07",  "S01",  "P01", "1",  "38.00",         "现金"),  # 同单同商品，
    ("o22", "2026-06-07",  "S01",  "P01", "1",  "38.00",         "微信"),  # 支付方式不同
    ("o23", "2026/6/8",    "s01 ", "P01", "1",  "¥38.00",        "现金"),  # 规范化后与下一行
    ("o23", "2026-06-08",  "S01",  "P01", "1",  "38.00",         "现金"),  # 七字段完全相同
    ("o24", "2026-6-9",    "S01",  "P01", "1",  "38.00",         "现金"),  # 连字符不补零
    ("o25", "6-06-2026",   "S01",  "P01", "1",  "38.00",         "现金"),  # 日在前且不补零
    # ── 规则 1：日期解析不了（4 行）──────────────────────────────────
    ("o5",  "",            "S01",  "P01", "1",  "38.00", "现金"),
    ("o6",  "N/A",         "S01",  "P01", "1",  "38.00", "现金"),
    ("o7",  "2026-13-45",  "S01",  "P01", "1",  "38.00", "现金"),  # 格式对、日期非法
    ("o7b", "2026-02-30",  "S01",  "P01", "1",  "38.00", "现金"),  # 月份合法但日期非法
    # ── 规则 2：amount 为空（2 行）───────────────────────────────────
    ("o8",  "2026-06-01",  "S01",  "P01", "2",  "",    "现金"),
    ("o9",  "2026-06-01",  "S01",  "P01", "2",  "   ", "现金"),
    # ── 规则 3：qty <= 0（2 行）─────────────────────────────────────
    ("o10", "2026-06-01",  "S01",  "P01", "0",  "38.00", "现金"),
    ("o11", "2026-06-01",  "S01",  "P01", "-1", "38.00", "现金"),
    # ── 规则 4：门店脏外键（1 行，规范化救不回来）─────────────────────
    ("o12", "2026-06-01",  "X99",  "P01", "1",  "38.00", "现金"),
    # ── 规则 5：商品脏外键（1 行）───────────────────────────────────
    ("o13", "2026-06-01",  "S01",  "Z99", "1",  "38.00", "现金"),
    # ── 规则 6：七字段完全相同的重复行（1 行）────────────────────────
    ("o1",  "2026-06-01",  "S01",  "P01", "2",  "38.00", "现金"),
]

REMOVED_BY_RULE = {
    "1_unparseable_date": 4,
    "2_empty_amount": 2,
    "3_qty_le_zero": 2,
    "4_store_not_in_stores": 1,
    "5_product_not_in_products": 1,
    "6_duplicate_row": 2,
}


def _make_source(tmp_path: Path) -> Path:
    src = tmp_path / "pos.db"
    con = sqlite3.connect(str(src))
    try:
        con.executescript(
            "CREATE TABLE stores (store_id TEXT PRIMARY KEY, store_name TEXT, category TEXT, district TEXT);"
            "CREATE TABLE products (product_id TEXT PRIMARY KEY, product_name TEXT, product_category TEXT, unit_price REAL);"
            "CREATE TABLE sales (order_id TEXT, date TEXT, store_id TEXT, product_id TEXT,"
            "                    qty TEXT, amount TEXT, payment TEXT);"
        )
        con.executemany(
            "INSERT INTO stores VALUES (?,?,?,?)",
            [("S01", "一号店", "拉面", "A区"), ("S02", "二号店", "轻食", "B区")],
        )
        con.executemany(
            "INSERT INTO products VALUES (?,?,?,?)",
            [("P01", "拉面", "主食", 38.0), ("P02", "沙拉", "轻食", 25.0)],
        )
        # qty / amount 一律以字符串入库 —— 真实 POS 导出就是文本，解析器也按文本处理
        con.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?)", SALES)
        con.commit()
    finally:
        con.close()
    return src


def _rows(db: Path, sql: str) -> list[dict]:
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql)]
    finally:
        con.close()


@pytest.fixture()
def cleaned(tmp_path):
    """把迷你源库按口径清洗一遍，返回（清洗台账, 清洗表路径）。"""
    dst = tmp_path / "clean.db"
    report = build_clean_db(_make_source(tmp_path), dst)
    return report, dst


def test_removal_counts(cleaned):
    report, _ = cleaned
    for rule, expected in REMOVED_BY_RULE.items():
        assert report.removed[rule] == expected, rule
    assert report.raw_rows == len(SALES)
    assert sum(report.removed.values()) == report.raw_rows - report.kept_rows
    # 辅助自洽：计数之和必须等于 raw − kept
    assert report.kept_rows == len(SALES) - sum(REMOVED_BY_RULE.values())
    assert report.kept_sales_rows == 11
    assert report.kept_refund_rows == 1


def test_cleaned_table_invariants(cleaned):
    """KB-001 的硬约束：换成任何一份数据都必须成立。"""
    _, dst = cleaned
    stores = {r["store_id"] for r in _rows(dst, "SELECT store_id FROM stores")}
    products = {r["product_id"] for r in _rows(dst, "SELECT product_id FROM products")}
    rows = _rows(dst, "SELECT * FROM sales_clean")
    assert rows

    seen = set()
    for row in rows:
        try:
            day = date.fromisoformat(row["date"])
        except (TypeError, ValueError):
            pytest.fail("清洗后仍留着无法解析的日期：%r" % (row,))
        assert day.isoformat() == row["date"], row
        assert row["qty"] > 0, row
        assert row["store_id"] in stores, "脏门店外键没剔掉：%r" % (row,)
        assert row["product_id"] in products, "脏商品外键没剔掉：%r" % (row,)
        assert row["store_id"] == row["store_id"].strip().upper(), row
        assert row["product_id"] == row["product_id"].strip().upper(), row
        key = (row["order_id"], row["date"], row["store_id"], row["product_id"],
               row["qty"], row["amount_cents"], row["payment"])
        assert key not in seen, "七字段完全相同的重复行没去重：%r" % (key,)
        seen.add(key)


def test_recoverable_dirty_values_are_normalised_not_dropped(cleaned):
    """可恢复的脏写法要先规范化再判外键，顺序反了会误删真实订单。"""
    _, dst = cleaned
    by_order = {row["order_id"]: row for row in _rows(dst, "SELECT * FROM sales_clean")}
    assert "o2" in by_order, "小写+尾空格的门店/商品被当成脏外键删掉了"
    assert (by_order["o2"]["store_id"], by_order["o2"]["product_id"]) == ("S02", "P02")
    assert by_order["o2"]["date"] == "2026-06-02"      # YYYY/M/D
    assert by_order["o2"]["amount_cents"] == 3800       # ¥38.00
    assert by_order["o3"]["date"] == "2026-06-03"       # DD-MM-YYYY，日在前
    assert by_order["o4"]["amount_cents"] == 3800       # 全角空格 + ¥
    assert by_order["o24"]["date"] == "2026-06-09"       # YYYY-M-D
    assert by_order["o25"]["date"] == "2026-06-06"       # D-M-YYYY


def test_multiline_order_and_refund_survive(cleaned):
    _, dst = cleaned
    rows = _rows(dst, "SELECT * FROM sales_clean")
    assert sum(1 for r in rows if r["order_id"] == "o20") == 2, "同单不同商品的两行必须都在"
    same_product = [r for r in rows if r["order_id"] == "o22"]
    assert len(same_product) == 2, "支付方式不同就不是七字段全同，两行都必须保留"
    assert {r["payment"] for r in same_product} == {"现金", "微信"}
    refunds = [r for r in rows if r["is_refund"] == 1]
    assert len(refunds) == 1
    assert refunds[0]["order_id"] == "o21"
    assert refunds[0]["amount_cents"] == -3800, "退款行必须保留，金额记负"


def test_duplicate_is_compared_after_normalisation(cleaned):
    """日期、门店、商品、金额写法不同，但规范化后七字段相同，只能留一行。"""
    _, dst = cleaned
    rows = _rows(dst, "SELECT * FROM sales_clean WHERE order_id = 'o23'")
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-06-08"
    assert rows[0]["store_id"] == "S01"
    assert rows[0]["amount_cents"] == 3800
