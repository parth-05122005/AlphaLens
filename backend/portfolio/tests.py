from decimal import Decimal

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from portfolio.models import Holding
from portfolio.services import get_price_history, refresh_prices, summary_key

pytestmark = pytest.mark.django_db


def test_create_holding_normalizes_symbol_and_enriches(api, mock_market):
    mock_market.info = {"INFY.NS": {"longName": "Infosys Limited", "sector": "Technology", "currentPrice": 1500}}
    resp = api.post("/api/holdings/", {"symbol": "infy", "quantity": "10", "avg_buy_price": "1400"}, format="json")
    assert resp.status_code == 201, resp.data
    assert resp.data["symbol"] == "INFY.NS"
    assert resp.data["name"] == "Infosys Limited"
    assert resp.data["sector"] == "Technology"
    assert Decimal(resp.data["last_price"]) == Decimal("1500")
    assert resp.data["pnl"] == 1000.0


def test_create_holding_keeps_user_input_when_lookup_fails(api, monkeypatch):
    def boom(symbol):
        raise ConnectionError("yahoo down")

    monkeypatch.setattr("portfolio.services._fetch_info", boom)
    resp = api.post(
        "/api/holdings/",
        {"symbol": "TCS.NS", "name": "TCS", "sector": "IT", "quantity": "1", "avg_buy_price": "3000"},
        format="json",
    )
    assert resp.status_code == 201
    assert (resp.data["name"], resp.data["sector"]) == ("TCS", "IT")


@pytest.mark.parametrize("field,value", [("quantity", "0"), ("avg_buy_price", "-5")])
def test_create_holding_rejects_non_positive_values(api, field, value):
    data = {"symbol": "INFY", "quantity": "1", "avg_buy_price": "100", field: value}
    resp = api.post("/api/holdings/", data, format="json")
    assert resp.status_code == 400
    assert field in resp.data


def test_duplicate_symbol_rejected(api, user, make_holding):
    make_holding(user, "INFY.NS")
    resp = api.post("/api/holdings/", {"symbol": "INFY", "quantity": "1", "avg_buy_price": "100"}, format="json")
    assert resp.status_code == 400


def test_user_isolation(api, other_user, make_holding):
    theirs = make_holding(other_user, "TCS.NS")
    assert api.get("/api/holdings/").data["count"] == 0
    assert api.get(f"/api/holdings/{theirs.id}/").status_code == 404
    assert api.delete(f"/api/holdings/{theirs.id}/").status_code == 404
    assert Holding.objects.filter(pk=theirs.pk).exists()


def test_summary_math(api, user, make_holding):
    make_holding(user, "INFY.NS", quantity="10", avg="100", last="120", sector="Technology")
    make_holding(user, "HDFCBANK.NS", quantity="5", avg="200", last="180", sector="Financial Services")
    make_holding(user, "XYZ.NS", quantity="2", avg="50", last=None, sector=None)

    data = api.get("/api/portfolio/summary/").data
    # invested: 1000 + 1000 + 100 = 2100; value: 1200 + 900 + 100 (falls back to avg) = 2200
    assert data["total_invested"] == 2100.0
    assert data["current_value"] == 2200.0
    assert data["pnl"] == 100.0
    assert data["pnl_pct"] == round(100 / 2100 * 100, 2)
    assert data["allocation_by_sector"] == [
        {"sector": "Technology", "value": 1200.0},
        {"sector": "Financial Services", "value": 900.0},
        {"sector": "Other", "value": 100.0},
    ]
    assert len(data["holdings"]) == 3


def test_summary_is_cached_and_invalidated_on_edit(api, user, make_holding):
    h = make_holding(user, "INFY.NS", quantity="10", avg="100", last="100")
    assert api.get("/api/portfolio/summary/").data["current_value"] == 1000.0
    assert cache.get(summary_key(user.id)) is not None

    # A direct DB change is hidden by the cache...
    Holding.objects.filter(pk=h.pk).update(quantity=Decimal("20"))
    assert api.get("/api/portfolio/summary/").data["current_value"] == 1000.0

    # ...but editing through the API invalidates it.
    resp = api.patch(f"/api/holdings/{h.id}/", {"quantity": "30"}, format="json")
    assert resp.status_code == 200
    assert cache.get(summary_key(user.id)) is None
    assert api.get("/api/portfolio/summary/").data["current_value"] == 3000.0


def test_refresh_prices_endpoint_returns_202_and_updates_prices(api, user, make_holding, mock_market):
    h = make_holding(user, "INFY.NS", last="100")
    mock_market.prices = {"INFY.NS": Decimal("1555.55")}
    resp = api.post("/api/holdings/refresh-prices/")
    assert resp.status_code == 202
    assert resp.data["task_id"]
    h.refresh_from_db()
    assert h.last_price == Decimal("1555.55")
    assert h.last_price_at is not None

    status = api.get(f"/api/tasks/{resp.data['task_id']}/").data
    assert status["state"] == "SUCCESS" and status["ready"] is True


def test_refresh_prices_survives_bad_ticker(user, make_holding, monkeypatch):
    good = make_holding(user, "INFY.NS", last="100")
    bad = make_holding(user, "BAD.NS", last="50")

    def fetch(symbol):
        if symbol == "BAD.NS":
            raise ValueError("no data")
        return Decimal("200")

    monkeypatch.setattr("portfolio.services._fetch_last_price", fetch)
    assert refresh_prices(Holding.objects.filter(user=user)) == 1
    good.refresh_from_db()
    bad.refresh_from_db()
    assert good.last_price == Decimal("200")
    assert bad.last_price == Decimal("50")


def test_price_history_is_cached(api, user, make_holding, monkeypatch):
    calls = []

    def history(symbol, period):
        calls.append((symbol, period))
        return [{"date": "2026-01-01", "close": 10.0}]

    monkeypatch.setattr("portfolio.services._fetch_history", history)
    h = make_holding(user, "INFY.NS")
    for _ in range(2):
        resp = api.get(f"/api/holdings/{h.id}/history/?period=6mo")
        assert resp.status_code == 200
        assert resp.data["points"] == [{"date": "2026-01-01", "close": 10.0}]
    assert calls == [("INFY.NS", "6mo")]
    assert get_price_history("INFY.NS", "6mo") == [{"date": "2026-01-01", "close": 10.0}]
    assert api.get(f"/api/holdings/{h.id}/history/?period=5y").status_code == 400


def test_requires_auth():
    assert APIClient().get("/api/holdings/").status_code == 401


def test_seed_demo_is_idempotent(mock_market, mock_feed):
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    from agents.models import Agent

    mock_market.prices = {"TATAMOTORS.NS": None}  # delisted after the demerger
    mock_feed.entries = [
        {"title": "Markets rally", "link": "https://news.example.com/rally", "summary": "Stocks rose."}
    ]

    call_command("seed_demo")
    call_command("seed_demo")

    demo = get_user_model().objects.get(username="demo")
    assert demo.check_password("demo12345")
    symbols = list(Holding.objects.filter(user=demo).values_list("symbol", flat=True))
    assert sorted(symbols) == sorted(["INFY.NS", "TCS.NS", "HDFCBANK.NS", "RELIANCE.NS", "TMPV.NS"])
    assert Agent.objects.filter(user=demo, schedule="daily").count() == 1
    assert all(h.last_price is not None for h in Holding.objects.filter(user=demo))
