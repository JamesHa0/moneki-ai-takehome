"""中文 BM25 分词回归测试。"""

from __future__ import annotations

from kbqa.tokenizer import content_tokens, tokenize


def test_chinese_text_uses_overlapping_bigrams():
    assert tokenize("外卖订单") == ["外卖", "卖订", "订单"]
    assert tokenize("外卖订单多久内可以申请退款") == [
        "外卖",
        "卖订",
        "订单",
        "单多",
        "多久",
        "久内",
        "内可",
        "可以",
        "以申",
        "申请",
        "请退",
        "退款",
    ]


def test_english_digits_and_punctuation_are_split_as_words():
    assert tokenize("Beef Poke P06 2026") == ["beef", "poke", "p06", "2026"]
    assert tokenize("退款，换货") == ["退款", "换货"]
    assert tokenize("ＡＢＣ１２３") == ["abc123"]
    assert tokenize("店") == ["店"]


def test_content_tokens_removes_stop_only_bigrams_and_words():
    assert content_tokens("的了是在") == []
    assert content_tokens("What is the refund") == ["refund"]
    assert "一下" not in content_tokens("请问一下退款")
