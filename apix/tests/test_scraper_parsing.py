"""Offline parser checks for fare-specific selectors and debug capture."""

from __future__ import annotations

import logging

from scraper.scraper_utils import extract_lowest_quote


class _Element:
    def __init__(self, text: str | None):
        self.text = text

    @property
    def first(self):
        return self

    def count(self) -> int:
        return int(self.text is not None)

    def inner_text(self) -> str:
        assert self.text is not None
        return self.text


class _Card:
    def __init__(self, raw_text: str, total_text: str | None):
        self.raw_text = raw_text
        self.total_text = total_text

    def locator(self, selector):
        return _Element(self.total_text if selector == "[data-testid*='total-fare']" else None)

    def inner_text(self) -> str:
        return self.raw_text

    def inner_html(self) -> str:
        return f"<article><span data-testid='total-fare'>{self.total_text}</span></article>"


class _Cards:
    def __init__(self, cards):
        self.cards = cards

    def count(self) -> int:
        return len(self.cards)

    def nth(self, index: int):
        return self.cards[index]


class _Page:
    def __init__(self, cards):
        self.cards = cards

    def locator(self, selector):
        assert selector == ("article.flight",)
        return _Cards(self.cards)


SELECTORS = {
    "card": ("article.flight",),
    "total": ("[data-testid*='total-fare']",),
    "carrier": (),
    "fare_class": (),
    "base": (),
    "taxes": (),
    "flight_number": (),
    "departure": (),
}


def test_parser_uses_the_currency_marked_total_and_logs_capture(caplog):
    page = _Page([_Card("6E 110 | 08:00 | 2h 10m | ₹5,890", "₹5,890")])

    with caplog.at_level(logging.INFO, logger="apix.scraper"):
        quote = extract_lowest_quote(page, SELECTORS, debug_fares=True)

    assert quote is not None
    assert quote["total_fare"] == 5890.0
    assert "total_text='₹5,890'" in caplog.text
    assert "6E 110 | 08:00 | 2h 10m | ₹5,890" in caplog.text


def test_parser_rejects_a_currency_marked_non_fare_amount(caplog):
    page = _Page([_Card("6E 110 | 08:00 | 2h 10m | ₹5,890", "₹110")])

    with caplog.at_level(logging.WARNING, logger="apix.scraper"):
        quote = extract_lowest_quote(page, SELECTORS)

    assert quote is None
    assert "Rejected implausible fare 110.00" in caplog.text
