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


def fake_vector(text: str) -> list[float]:
    """Deterministic bag-of-words embedding: similar wording -> similar vector."""
    import hashlib
    import math
    import re

    from django.conf import settings

    vec = [0.0] * settings.EMBEDDING_DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % len(vec)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Tests never call Gemini. Override `generate_reply` / `json_reply` or the call lists as needed."""

    class FakeLLM:
        def __init__(self):
            self.generate_calls = []
            self.json_calls = []
            self.embed_calls = 0
            self.generate_reply = "Here is what the sources say [1]."
            self.json_reply = None  # None -> neutral score for every id in the prompt

        def embed(self, text, task_type="RETRIEVAL_QUERY"):
            self.embed_calls += 1
            return fake_vector(text)

        def embed_many(self, texts, task_type="RETRIEVAL_DOCUMENT"):
            self.embed_calls += 1
            return [fake_vector(t) for t in texts]

        def generate(self, system_prompt, user_prompt):
            self.generate_calls.append((system_prompt, user_prompt))
            if isinstance(self.generate_reply, Exception):
                raise self.generate_reply
            return self.generate_reply

        def generate_json(self, system_prompt, user_prompt):
            import re

            self.json_calls.append((system_prompt, user_prompt))
            if self.json_reply is not None:
                return self.json_reply(user_prompt) if callable(self.json_reply) else self.json_reply
            ids = re.findall(r"^(\d+):", user_prompt, flags=re.M)
            return {"results": [{"id": int(i), "score": 0.0, "label": "neutral"} for i in ids]}

    fake = FakeLLM()
    for name in ("embed", "embed_many", "generate", "generate_json"):
        monkeypatch.setattr(f"core.llm.{name}", getattr(fake, name))
    return fake


@pytest.fixture(autouse=True)
def mock_feed(monkeypatch):
    """Fake Google News RSS. Set `.entries` to control what fetch_news sees."""
    import feedparser

    class Feed:
        def __init__(self):
            self.entries = []
            self.urls = []

        def __call__(self, url):
            self.urls.append(url)
            return feedparser.FeedParserDict(entries=[feedparser.FeedParserDict(e) for e in self.entries])

    feed = Feed()
    monkeypatch.setattr("research.ingest._fetch_feed", feed)
    return feed


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
