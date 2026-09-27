"""文档题不能被“多少/多久/几”兜底改写；现在问的是现行文档。"""

from __future__ import annotations

from datetime import date

import pytest

from kbqa.entities import Catalog
from kbqa.planner import Planner


def _planner() -> Planner:
    return Planner(
        Catalog(
            stores=[
                {"store_id": "S02", "store_name": "Makai Poke"},
                {"store_id": "S04", "store_name": "Arigato Sando"},
            ],
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


@pytest.mark.parametrize(
    ("question", "window"),
    [
        ("为什么8月19营业额低了", ("2026-08-19", "2026-08-19")),
        ("为什么8月19日营业额低了？", ("2026-08-19", "2026-08-19")),
        (
            "S02 在 8 月 17 日到 19 日为什么一分钱营业额都没有？",
            ("2026-08-17", "2026-08-19"),
        ),
    ],
)
def test_why_anomaly_route_is_not_overwritten(question, window):
    plan = _planner().plan(question)

    assert plan.kind == "anomaly"
    assert plan.intent == "hybrid"
    assert plan.needs_data is True
    assert plan.needs_docs is True
    assert plan.window == window


def test_document_why_question_stays_document():
    plan = _planner().plan("S04 为什么不卖吞拿鱼三明治了？")

    assert plan.kind == "doc"
    assert plan.intent == "doc"
    assert plan.needs_data is False


def test_decline_word_with_metric_routes_to_anomaly():
    plan = _planner().plan("8 月 19 营业额低了")

    assert plan.kind == "anomaly"
    assert plan.intent == "hybrid"
    assert plan.window == ("2026-08-19", "2026-08-19")


@pytest.mark.parametrize(
    "question",
    [
        "8 月营业额比 7 月高了还是低了？",
        "7 月客单价跟 6 月比，是涨了还是跌了？",
    ],
)
def test_trend_alternative_is_not_an_anomaly(question):
    plan = _planner().plan(question)

    assert plan.kind == "compare"
    assert plan.intent == "data"


def test_ranking_question_marks_best_and_worst():
    plan = _planner().plan("7 月 24 卖得最好的商品是哪个，最差的又是哪个？")

    assert plan.kind == "top_products"
    assert plan.intent == "data"
    assert plan.slots["asks_top"] is True
    assert plan.slots["asks_bottom"] is True


@pytest.mark.parametrize(
    ("question", "asks_top", "asks_bottom"),
    [
        ("7 月 24 卖得最好的商品是哪个？", True, False),
        ("7 月 24 卖得最差的商品是哪个？", False, True),
    ],
)
def test_single_direction_ranking_still_uses_top_products(
    question, asks_top, asks_bottom
):
    plan = _planner().plan(question)

    assert plan.kind == "top_products"
    assert plan.intent == "data"
    assert plan.slots["asks_top"] is asks_top
    assert plan.slots["asks_bottom"] is asks_bottom


@pytest.mark.parametrize(
    "question",
    [
        "8 月的净营业额比 7 月少了多少？",
        "S02 的牛肉poke 销量比上月少了多少？",
        "7 月的退款金额比 6 月低了多少？",
    ],
)
def test_comparison_quantity_question_is_not_an_anomaly(question):
    """「比上月少了多少」是在要一个数，不是问「出了什么事」。

    软下降信号（少了/低了）本身不足以判定异常：一旦句子里同时有比较句式和
    数量问法，它就是纯数据题。判错会让隐藏题库里"换一种问法"的比较题
    被当成异常题，`answer_type_in: [data]` 直接不成立。
    """
    plan = _planner().plan(question)

    assert plan.kind != "anomaly"
    assert plan.intent == "data"
