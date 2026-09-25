"""文档题不能被“多少/多久/几”兜底改写；现在问的是现行文档。"""

from __future__ import annotations

from datetime import date

import pytest

from kbqa.entities import Catalog
from kbqa.planner import Planner


def _planner() -> Planner:
    return Planner(
        Catalog(
            stores=[{"store_id": "S02", "store_name": "Makai Poke"}],
            products=[
                {
                    "product_id": "P06",
                    "product_name": "牛肉poke",
                    "product_category": "轻食",
                    "unit_price": 45.0,
                }
            ],
        ),
        date(2026, 9, 1),
        {"start": "2026-05-01", "end": "2026-08-31"},
    )


@pytest.mark.parametrize(
    "question",
    [
        "外卖订单多久内可以申请退款？",
        "三文鱼那次断供，供应商最后赔了我们多少钱？",
        "员工迟到多久算一次？",
        "7 月顾客投诉最集中的是什么问题？有多少条？",
    ],
)
def test_numeric_words_do_not_override_document_route(question):
    plan = _planner().plan(question)

    assert plan.intent == "doc"


@pytest.mark.parametrize(
    "question",
    [
        "Super Souper 现在周五晚上营业到几点？",
        "会员现在单笔充值满 500 送多少？",
        "牛肉poke 现在卖多少钱一份？商品表里那个价能直接拿来用吗？",
    ],
)
def test_relative_now_document_questions_use_full_data_period(question):
    plan = _planner().plan(question)

    assert plan.intent in ("doc", "hybrid")
    assert plan.window == ("2026-05-01", "2026-08-31")


def test_out_of_period_data_question_still_refuses():
    plan = _planner().plan("9 月的营业额是多少？")

    assert plan.intent == "refusal"
    assert plan.kind == "out_of_period"
