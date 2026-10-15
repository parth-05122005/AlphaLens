"""Create the demo account with holdings, prices, news and a daily agent. Safe to run repeatedly.

Calls the service functions directly (not Celery) so it works without a worker running.
"""

import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from agents.models import Agent
from portfolio import services
from portfolio.models import Holding
from research.ingest import refresh_news_for_holding

logger = logging.getLogger(__name__)

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo12345"

# (symbol, name, sector, quantity, avg-price factor vs. the current price, fallback avg price).
# Factors < 1 show a gain and > 1 a loss, so the demo has a mixed P&L.
CANDIDATES = [
    ("INFY.NS", "Infosys Limited", "Technology", 25, Decimal("0.88"), Decimal("1450")),
    ("TCS.NS", "Tata Consultancy Services Limited", "Technology", 8, Decimal("1.12"), Decimal("3400")),
    ("HDFCBANK.NS", "HDFC Bank Limited", "Financial Services", 30, Decimal("0.94"), Decimal("1600")),
    ("RELIANCE.NS", "Reliance Industries Limited", "Energy", 15, Decimal("0.90"), Decimal("2500")),
    # Tata Motors demerged in 2025; TATAMOTORS.NS no longer resolves, TMPV.NS is the passenger-vehicle business.
    ("TATAMOTORS.NS", "Tata Motors Limited", "Consumer Cyclical", 40, Decimal("1.08"), Decimal("700")),
    ("TMPV.NS", "Tata Motors Passenger Vehicles Limited", "Consumer Cyclical", 40, Decimal("1.08"), Decimal("300")),
    ("ITC.NS", "ITC Limited", "Consumer Defensive", 60, Decimal("0.95"), Decimal("420")),
]
TARGET_HOLDINGS = 5

AGENT_NAME = "Morning brief"
AGENT_INSTRUCTION = (
    "Give me a morning brief: the 3 most important developments across my holdings, why they matter, "
    "and flag anything about layoffs, guidance cuts or regulatory action."
)


class Command(BaseCommand):
    help = "Create or refresh the demo/demo12345 account with sample holdings, news and a daily agent."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=DEMO_USERNAME, defaults={"email": "demo@alphalens.app"})
        user.set_password(DEMO_PASSWORD)
        user.save()
        self.stdout.write(f"{'Created' if created else 'Found'} user '{DEMO_USERNAME}'")

        holdings = self._seed_holdings(user)

        updated = services.refresh_prices(holdings)
        self.stdout.write(f"Refreshed prices for {updated}/{len(holdings)} holdings")

        for holding in holdings:
            try:
                result = refresh_news_for_holding(holding)
                self.stdout.write(f"  news {holding.symbol}: {result}")
            except Exception as exc:  # e.g. no GEMINI_API_KEY yet: keep going, news can be refreshed later
                self.stdout.write(self.style.WARNING(f"  news {holding.symbol} failed: {exc}"))

        agent, agent_created = Agent.objects.get_or_create(
            user=user,
            name=AGENT_NAME,
            defaults={"instruction": AGENT_INSTRUCTION, "schedule": Agent.Schedule.DAILY},
        )
        self.stdout.write(f"{'Created' if agent_created else 'Found'} agent '{agent.name}' (daily)")
        services.invalidate_summary(user.id)
        self.stdout.write(self.style.SUCCESS(f"Demo ready: log in as {DEMO_USERNAME} / {DEMO_PASSWORD}"))

    def _seed_holdings(self, user) -> list[Holding]:
        existing = {h.symbol: h for h in Holding.objects.filter(user=user)}
        holdings = []
        for symbol, name, sector, qty, factor, fallback in CANDIDATES:
            if len(holdings) >= TARGET_HOLDINGS:
                break
            if symbol in existing:  # second run: keep what's there
                holdings.append(existing[symbol])
                continue
            try:
                price = services._fetch_last_price(symbol)
            except Exception:
                price = None
            if price is None:
                self.stdout.write(self.style.WARNING(f"  skipping {symbol}: no price data on yfinance"))
                continue
            holding = Holding(
                user=user,
                symbol=symbol,
                name=name,
                sector=sector,
                quantity=Decimal(qty),
                avg_buy_price=(price * factor).quantize(Decimal("0.01")),
            )
            services.enrich_holding(holding)
            holding.save()
            holdings.append(holding)
            self.stdout.write(f"  added {symbol}")

        if not holdings:  # yfinance unreachable: seed fixed prices so the demo still works offline
            self.stdout.write(self.style.WARNING("  yfinance unavailable; using fallback prices"))
            for symbol, name, sector, qty, _factor, fallback in CANDIDATES:
                if symbol == "TATAMOTORS.NS" or len(holdings) >= TARGET_HOLDINGS:
                    continue
                holdings.append(
                    Holding.objects.create(
                        user=user, symbol=symbol, name=name, sector=sector, quantity=Decimal(qty), avg_buy_price=fallback
                    )
                )
        return holdings
