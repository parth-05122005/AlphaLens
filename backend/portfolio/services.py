"""Price and portfolio logic. All yfinance access goes through the small _fetch_* helpers."""

import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

import yfinance as yf
from django.apps import apps
from django.core.cache import cache
from django.db.models import Avg
from django.utils import timezone

from .models import Holding

logger = logging.getLogger(__name__)

HISTORY_PERIODS = ("1mo", "6mo", "1y")
HISTORY_TTL = 15 * 60
SUMMARY_TTL = 60


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    return symbol if "." in symbol else f"{symbol}.NS"


# --- yfinance access (patched in tests) ---


def _fetch_last_price(symbol: str) -> Decimal | None:
    closes = yf.Ticker(symbol).history(period="5d")["Close"].dropna()
    if closes.empty:
        return None
    return Decimal(str(round(float(closes.iloc[-1]), 2)))


def _fetch_info(symbol: str) -> dict:
    return yf.Ticker(symbol).info or {}


def _fetch_history(symbol: str, period: str) -> list[dict]:
    df = yf.Ticker(symbol).history(period=period, interval="1d")
    return [
        {"date": idx.date().isoformat(), "close": round(float(row["Close"]), 2)}
        for idx, row in df.iterrows()
        if row["Close"] == row["Close"]  # skip NaN
    ]


# --- cache keys ---


def summary_key(user_id: int) -> str:
    return f"summary:{user_id}"


def invalidate_summary(user_id: int) -> None:
    cache.delete(summary_key(user_id))


# --- services ---


def enrich_holding(holding: Holding) -> None:
    """Best-effort fill of name/sector (and a first price) from yfinance; keeps user input on failure."""
    try:
        info = _fetch_info(holding.symbol)
    except Exception:
        logger.warning("Could not fetch info for %s", holding.symbol, exc_info=True)
        return
    holding.name = info.get("longName") or info.get("shortName") or holding.name
    holding.sector = info.get("sector") or holding.sector
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price:
        holding.last_price = Decimal(str(round(float(price), 2)))
        holding.last_price_at = timezone.now()


def refresh_prices(holdings) -> int:
    """Update last_price for each holding. One bad ticker doesn't stop the batch. Returns count updated."""
    updated = 0
    user_ids = set()
    for holding in holdings:
        try:
            price = _fetch_last_price(holding.symbol)
        except Exception:
            logger.warning("Price fetch failed for %s", holding.symbol, exc_info=True)
            continue
        if price is None:
            logger.warning("No price data for %s", holding.symbol)
            continue
        holding.last_price = price
        holding.last_price_at = timezone.now()
        holding.save(update_fields=["last_price", "last_price_at"])
        user_ids.add(holding.user_id)
        updated += 1
    for user_id in user_ids:
        invalidate_summary(user_id)
    return updated


def get_price_history(symbol: str, period: str) -> list[dict]:
    if period not in HISTORY_PERIODS:
        raise ValueError(f"period must be one of {HISTORY_PERIODS}")
    key = f"price_history:{symbol}:{period}"
    data = cache.get(key)
    if data is None:
        data = _fetch_history(symbol, period)
        cache.set(key, data, HISTORY_TTL)
    return data


def holding_metrics(h: Holding) -> dict:
    invested = h.quantity * h.avg_buy_price
    price = h.last_price if h.last_price is not None else h.avg_buy_price
    value = h.quantity * price
    pnl = value - invested
    return {
        "invested": float(round(invested, 2)),
        "value": float(round(value, 2)),
        "pnl": float(round(pnl, 2)),
        "pnl_pct": float(round(pnl / invested * 100, 2)) if invested else 0.0,
    }


def sentiment_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.2:
        return "positive"
    if score <= -0.2:
        return "negative"
    return "neutral"


def recent_sentiment(user, days: int = 7) -> dict[int, dict]:
    """Average news sentiment per holding over the last `days` days."""
    Document = apps.get_model("research", "Document")
    since = timezone.now() - timedelta(days=days)
    rows = (
        Document.objects.filter(
            user=user, source_type="news", holding__isnull=False, sentiment_score__isnull=False, created_at__gte=since
        )
        .values("holding_id")
        .annotate(avg=Avg("sentiment_score"))
    )
    return {
        r["holding_id"]: {"sentiment": round(r["avg"], 2), "sentiment_label": sentiment_label(r["avg"])} for r in rows
    }


def get_portfolio_summary(user) -> dict:
    key = summary_key(user.id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    holdings = list(Holding.objects.filter(user=user))
    sentiment = recent_sentiment(user)
    total_invested = Decimal("0")
    current_value = Decimal("0")
    by_sector: dict[str, Decimal] = defaultdict(Decimal)
    rows = []
    for h in holdings:
        m = holding_metrics(h)
        total_invested += Decimal(str(m["invested"]))
        current_value += Decimal(str(m["value"]))
        by_sector[h.sector or "Other"] += Decimal(str(m["value"]))
        rows.append(
            {
                "id": h.id,
                "symbol": h.symbol,
                "name": h.name,
                "sector": h.sector,
                "quantity": float(h.quantity),
                "avg_buy_price": float(h.avg_buy_price),
                "last_price": float(h.last_price) if h.last_price is not None else None,
                "last_price_at": h.last_price_at.isoformat() if h.last_price_at else None,
                **sentiment.get(h.id, {"sentiment": None, "sentiment_label": None}),
                **m,
            }
        )

    pnl = current_value - total_invested
    updated = [h.last_price_at for h in holdings if h.last_price_at]
    summary = {
        "total_invested": float(round(total_invested, 2)),
        "current_value": float(round(current_value, 2)),
        "pnl": float(round(pnl, 2)),
        "pnl_pct": float(round(pnl / total_invested * 100, 2)) if total_invested else 0.0,
        "allocation_by_sector": sorted(
            ({"sector": s, "value": float(round(v, 2))} for s, v in by_sector.items()),
            key=lambda x: -x["value"],
        ),
        "holdings": rows,
        "prices_updated_at": max(updated).isoformat() if updated else None,
    }
    cache.set(key, summary, SUMMARY_TTL)
    return summary
