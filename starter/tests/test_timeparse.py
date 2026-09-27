"""Colloquial date parsing must distinguish a day from a whole month."""

from __future__ import annotations

from datetime import date

from kbqa.timeparse import parse_time


TODAY = date(2026, 9, 1)


def test_month_day_without_suffix_is_a_single_day():
    spec = parse_time("为什么8月19营业额低了", TODAY)

    assert spec.window == ("2026-08-19", "2026-08-19")
    assert spec.explicit is True


def test_month_without_day_remains_the_whole_month():
    spec = parse_time("8月的营业额是多少", TODAY)

    assert spec.window == ("2026-08-01", "2026-08-31")


def test_invalid_bare_day_is_not_treated_as_a_date():
    spec = parse_time("8月32营业额", TODAY)

    assert spec.window == ("2026-08-01", "2026-08-31")
