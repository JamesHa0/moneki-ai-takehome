"""把原始 sales 导进 var/clean.db，指标都查这张表。"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional

#: 金额里的 `¥` 去掉再按数字解析。
_CURRENCY = str.maketrans("", "", "¥￥ \t　")

REMOVAL_REASONS = (
    "1_unparseable_date",
    "2_empty_amount",
    "3_qty_le_zero",
    "4_store_not_in_stores",
    "5_product_not_in_products",
    "6_duplicate_row",
)

_ISO_DATE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_SLASH_DATE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
_DAY_FIRST_DATE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")


def parse_amount(value: Optional[str]) -> tuple[Optional[int], str]:
    """返回 (分, 状态)。状态取值：`ok`、`empty`、`bad`。

    KB-001 §2.3 与 §3.2：`¥38.00` 与 `38.00` 是同一个金额；空金额直接剔除，**不回填**。
    """
    text = (value or "").translate(_CURRENCY)
    if not text:
        return None, "empty"
    try:
        cents = int((Decimal(text) * 100).to_integral_value())
    except (InvalidOperation, ValueError):
        return None, "bad"
    return cents, "ok"


def parse_date(value: Optional[str]) -> Optional[str]:
    """按 KB-001 §2.2 解析三种日期并做真实日期校验。"""
    text = (value or "").strip()

    match = _ISO_DATE.match(text) or _SLASH_DATE.match(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
    else:
        match = _DAY_FIRST_DATE.match(text)
        if not match:
            return None
        day, month, year = (int(part) for part in match.groups())

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_qty(value: Optional[str]) -> Optional[int]:
    """KB-001 §2.4：按整数解析。解析不了的按 0 处理，会被 §3.3 剔除。"""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


@dataclass
class CleaningReport:
    raw_rows: int = 0
    kept_rows: int = 0
    kept_sales_rows: int = 0
    kept_refund_rows: int = 0
    removed: dict[str, int] = field(default_factory=lambda: {k: 0 for k in REMOVAL_REASONS})
    note_unparseable_amount: int = 0

    def as_dict(self) -> dict:
        return {
            "raw_rows": self.raw_rows,
            "removed": dict(self.removed, note_unparseable_amount=self.note_unparseable_amount),
            "kept_rows": self.kept_rows,
            "kept_sales_rows": self.kept_sales_rows,
            "kept_refund_rows": self.kept_refund_rows,
        }


def open_readonly(path: Path) -> sqlite3.Connection:
    """按 SQLite 只读 URI 打开数据库。"""
    conn = sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro",
        uri=True,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    return conn


class _SalesRows:
    """给销售游标附上外键白名单，避免改动 clean_rows() 的函数签名。"""

    def __init__(
        self,
        rows: Iterable[sqlite3.Row],
        stores: Iterable[tuple],
        products: Iterable[tuple],
    ) -> None:
        self._rows = rows
        self.store_ids = {str(row[0]).strip().upper() for row in stores}
        self.product_ids = {str(row[0]).strip().upper() for row in products}

    def __iter__(self):
        return iter(self._rows)


def clean_rows(rows: Iterable[sqlite3.Row]) -> tuple[list[tuple], CleaningReport]:
    """按 KB-001 v3 完成规范化、六步剔除和七字段去重。"""
    report = CleaningReport()
    kept: list[tuple] = []
    seen: set[tuple] = set()
    store_ids = getattr(rows, "store_ids", None)
    product_ids = getattr(rows, "product_ids", None)
    if store_ids is None or product_ids is None:
        raise ValueError(
            "clean_rows() 需要外键白名单才能执行规则 4/5；"
            "请传入 build_clean_db 用的 _SalesRows，不要直接传普通可迭代对象。"
        )

    for row in rows:
        report.raw_rows += 1

        # 规则 1：日期必须能按三种口径解析，并经过真实日期校验。
        iso_date = parse_date(row["date"])
        if iso_date is None:
            report.removed["1_unparseable_date"] += 1
            continue

        # 规则 2：空金额不回填，直接剔除；无法解析的非空金额保留原有留痕行为。
        cents, status = parse_amount(row["amount"])
        if status == "empty":
            report.removed["2_empty_amount"] += 1
            continue
        if status == "bad":
            report.note_unparseable_amount += 1
            cents = 0

        # 规则 3：解析不了的 qty 按 None 处理，与 qty <= 0 一起剔除。
        qty = parse_qty(row["qty"])
        if qty is None or qty <= 0:
            report.removed["3_qty_le_zero"] += 1
            continue

        # 先规范化，再判断外键。顺序反过来会误删 s01 / "S01 " 这类合法写法。
        store_id = (row["store_id"] or "").strip().upper()
        product_id = (row["product_id"] or "").strip().upper()
        if store_ids is not None and store_id not in store_ids:
            report.removed["4_store_not_in_stores"] += 1
            continue
        if product_ids is not None and product_id not in product_ids:
            report.removed["5_product_not_in_products"] += 1
            continue

        # 规则 6：只有七个字段规范化后完全一致才算重复。
        order_id = (row["order_id"] or "").strip()
        payment = (row["payment"] or "").strip()
        key = (order_id, iso_date, store_id, product_id, qty, cents, payment)
        if key in seen:
            report.removed["6_duplicate_row"] += 1
            continue
        seen.add(key)
        kept.append(
            (
                order_id,
                iso_date,
                store_id,
                product_id,
                qty,
                cents,
                payment,
                1 if cents < 0 else 0,
            )
        )

    report.kept_rows = len(kept)
    report.kept_refund_rows = sum(1 for row in kept if row[5] < 0)
    report.kept_sales_rows = sum(1 for row in kept if row[5] > 0)
    return kept, report


_SCHEMA = """
CREATE TABLE stores (store_id TEXT PRIMARY KEY, store_name TEXT, category TEXT, district TEXT);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_name TEXT,
                       product_category TEXT, unit_price REAL);
CREATE TABLE sales_clean (
    order_id TEXT, date TEXT, store_id TEXT, product_id TEXT,
    qty INTEGER, amount_cents INTEGER, payment TEXT, is_refund INTEGER
);
CREATE INDEX idx_clean_date ON sales_clean(date);
CREATE INDEX idx_clean_store ON sales_clean(store_id);
CREATE INDEX idx_clean_product ON sales_clean(product_id);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def build_clean_db(source: Path, target: Path) -> CleaningReport:
    """从只读的源库重建清洗表。返回清洗台账，供 `/api/health` 与数据质量面板使用。"""
    if not source.exists():
        raise FileNotFoundError("找不到源数据库：%s" % source)
    src = open_readonly(source)
    try:
        stores = [tuple(r) for r in src.execute("SELECT store_id, store_name, category, district FROM stores")]
        products = [
            tuple(r)
            for r in src.execute(
                "SELECT product_id, product_name, product_category, unit_price FROM products"
            )
        ]
        rows, report = clean_rows(
            _SalesRows(
                src.execute(
                    "SELECT order_id, date, store_id, product_id, qty, amount, payment FROM sales"
                ),
                stores,
                products,
            )
        )
    finally:
        src.close()

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    out = sqlite3.connect(target)
    try:
        out.executescript(_SCHEMA)
        out.executemany("INSERT INTO stores VALUES (?,?,?,?)", stores)
        out.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
        out.executemany("INSERT INTO sales_clean VALUES (?,?,?,?,?,?,?,?)", rows)
        out.execute(
            "INSERT INTO meta VALUES ('cleaning_report', ?)",
            (json.dumps(report.as_dict(), ensure_ascii=False),),
        )
        out.execute("INSERT INTO meta VALUES ('source_db', ?)", (source.name,))
        out.commit()
    finally:
        out.close()
    return report
