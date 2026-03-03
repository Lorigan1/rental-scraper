"""Unit tests for BaseScraper utility methods.

Tests price extraction, relative date parsing, and text cleaning.
These are pure functions - no network access needed.
"""

import pytest
from datetime import datetime, timedelta

from rental_scraper.scrapers.base import BaseScraper


class TestExtractPrice:
    """Tests for BaseScraper.extract_price()."""

    def test_dollar_sign_with_comma(self):
        assert BaseScraper.extract_price("$1,200/month") == 1200

    def test_dollar_sign_no_comma(self):
        assert BaseScraper.extract_price("$850") == 850

    def test_dollar_with_space(self):
        assert BaseScraper.extract_price("$ 1,200") == 1200

    def test_per_month_no_dollar(self):
        assert BaseScraper.extract_price("1200/mo") == 1200

    def test_per_month_long(self):
        assert BaseScraper.extract_price("1200/month") == 1200

    def test_per_a_month(self):
        assert BaseScraper.extract_price("1200 a month") == 1200

    def test_per_month_text(self):
        assert BaseScraper.extract_price("1200 per month") == 1200

    def test_embedded_in_text(self):
        assert BaseScraper.extract_price("Room for rent $900/mo near UBC") == 900

    def test_too_low(self):
        """Prices below $100 are likely not monthly rent."""
        assert BaseScraper.extract_price("$50") is None

    def test_too_high(self):
        """Prices above $10,000 are likely not room rent."""
        assert BaseScraper.extract_price("$15,000") is None

    def test_empty_string(self):
        assert BaseScraper.extract_price("") is None

    def test_none_input(self):
        assert BaseScraper.extract_price(None) is None

    def test_no_price(self):
        assert BaseScraper.extract_price("Please contact for details") is None

    def test_edge_100(self):
        assert BaseScraper.extract_price("$100") == 100

    def test_edge_10000(self):
        assert BaseScraper.extract_price("$10,000") == 10000

    def test_multiple_prices_takes_first(self):
        """Should extract the first valid price."""
        assert BaseScraper.extract_price("$900/mo deposit $500") == 900


class TestParseRelativeDate:
    """Tests for BaseScraper.parse_relative_date()."""

    def test_just_now(self):
        result = BaseScraper.parse_relative_date("just now")
        assert result is not None
        assert (datetime.now() - result).total_seconds() < 5

    def test_moments_ago(self):
        result = BaseScraper.parse_relative_date("moments ago")
        assert result is not None

    def test_minutes_ago(self):
        result = BaseScraper.parse_relative_date("5 minutes ago")
        assert result is not None
        delta = datetime.now() - result
        assert 4 * 60 <= delta.total_seconds() <= 6 * 60

    def test_hours_ago(self):
        result = BaseScraper.parse_relative_date("2 hours ago")
        assert result is not None
        delta = datetime.now() - result
        assert 1.9 * 3600 <= delta.total_seconds() <= 2.1 * 3600

    def test_days_ago(self):
        result = BaseScraper.parse_relative_date("3 days ago")
        assert result is not None
        delta = datetime.now() - result
        assert 2.9 * 86400 <= delta.total_seconds() <= 3.1 * 86400

    def test_an_hour_ago(self):
        result = BaseScraper.parse_relative_date("an hour ago")
        assert result is not None
        delta = datetime.now() - result
        assert 0.9 * 3600 <= delta.total_seconds() <= 1.1 * 3600

    def test_a_minute_ago(self):
        result = BaseScraper.parse_relative_date("a minute ago")
        assert result is not None
        delta = datetime.now() - result
        assert 50 <= delta.total_seconds() <= 70

    def test_today(self):
        result = BaseScraper.parse_relative_date("today")
        assert result is not None
        assert result.date() == datetime.now().date()

    def test_yesterday(self):
        result = BaseScraper.parse_relative_date("yesterday")
        assert result is not None
        expected = (datetime.now() - timedelta(days=1)).date()
        assert result.date() == expected

    def test_weeks_ago(self):
        result = BaseScraper.parse_relative_date("2 weeks ago")
        assert result is not None
        delta = datetime.now() - result
        assert 13 * 86400 <= delta.total_seconds() <= 15 * 86400

    def test_empty_string(self):
        assert BaseScraper.parse_relative_date("") is None

    def test_none_input(self):
        assert BaseScraper.parse_relative_date(None) is None

    def test_nonsense(self):
        # dateutil may or may not parse this - just shouldn't crash
        result = BaseScraper.parse_relative_date("not a date at all xyz")
        # Result may be None or a parsed attempt - just don't crash
        assert result is None or isinstance(result, datetime)


class TestCleanText:
    """Tests for BaseScraper.clean_text()."""

    def test_extra_spaces(self):
        assert BaseScraper.clean_text("hello   world") == "hello world"

    def test_newlines(self):
        assert BaseScraper.clean_text("hello\n\n\nworld") == "hello world"

    def test_tabs(self):
        assert BaseScraper.clean_text("hello\t\tworld") == "hello world"

    def test_mixed_whitespace(self):
        assert BaseScraper.clean_text("  hello \n\t world  ") == "hello world"

    def test_nbsp(self):
        assert BaseScraper.clean_text("hello\xa0world") == "hello world"

    def test_empty_string(self):
        assert BaseScraper.clean_text("") == ""

    def test_none_input(self):
        assert BaseScraper.clean_text(None) == ""

    def test_already_clean(self):
        assert BaseScraper.clean_text("hello world") == "hello world"

    def test_preserves_content(self):
        text = "Room for rent $800/mo in Kitsilano - 2 roommates"
        assert BaseScraper.clean_text(text) == text
