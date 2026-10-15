"""Shared fixtures. External services (yfinance, RSS, Gemini) are always mocked."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def mock_market(monkeypatch):
    """Default fake market data; tests can override attributes on the returned object."""

    class Market:
        prices = {}
        info = {}
        default_price = Decimal("100.00")

        def last_price(self, symbol):
            return self.prices.get(symbol, self.default_price)

        def fetch_info(self, symbol):
            return self.info.get(symbol, {})

        def history(self, symbol, period):
            return [{"date": "2026-01-01", "close": 100.0}, {"date": "2026-01-02", "close": 101.5}]

    market = Market()
    monkeypatch.setattr("portfolio.services._fetch_last_price", market.last_price)
    monkeypatch.setattr("portfolio.services._fetch_info", market.fetch_info)
    monkeypatch.setattr("portfolio.services._fetch_history", market.history)
    return market


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("alice", "alice@example.com", "password-123")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user("bob", "bob@example.com", "password-123")


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def make_holding():
    from portfolio.models import Holding

    def _make(user, symbol="INFY.NS", quantity="10", avg="1000", last=None, sector="Technology", name=""):
        return Holding.objects.create(
            user=user,
            symbol=symbol,
            name=name or symbol.split(".")[0].title(),
            sector=sector,
            quantity=Decimal(quantity),
            avg_buy_price=Decimal(avg),
            last_price=Decimal(last) if last is not None else None,
        )

    return _make
