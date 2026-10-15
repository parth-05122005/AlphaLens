from datetime import timedelta

import pytest
from django.utils import timezone

from research.models import Document

pytestmark = pytest.mark.django_db


def headline(user, holding, title, score, label, days_ago=1):
    return Document.objects.create(
        user=user,
        holding=holding,
        source_type="news",
        title=title,
        url=f"https://news.example.com/{title.replace(' ', '-')}",
        content=title,
        status="ready",
        published_at=timezone.now() - timedelta(days=days_ago),
        sentiment_score=score,
        sentiment_label=label,
    )


def test_negative_headlines_trigger_alert(api, user, make_holding):
    tata = make_holding(user, "TATAMOTORS.NS")
    infy = make_holding(user, "INFY.NS")
    headline(user, tata, "Tata Motors recalls vehicles", -0.7, "negative")
    headline(user, tata, "Tata Motors sales slump", -0.5, "negative")
    headline(user, tata, "Tata Motors opens new plant", 0.4, "positive")
    headline(user, infy, "Infosys wins deal", 0.6, "positive")

    alerts = api.get("/api/alerts/").data

    assert [a["symbol"] for a in alerts] == ["TATAMOTORS.NS"]
    alert = alerts[0]
    assert "2 negative headlines" in alert["reason"]
    assert [h["title"] for h in alert["headlines"]] == ["Tata Motors recalls vehicles", "Tata Motors sales slump"]


def test_low_average_alone_triggers_alert(api, user, make_holding):
    h = make_holding(user, "RELIANCE.NS")
    headline(user, h, "Reliance faces probe", -0.6, "negative")
    alerts = api.get("/api/alerts/").data
    assert len(alerts) == 1 and "average news sentiment" in alerts[0]["reason"].lower()


def test_old_or_mild_news_does_not_alert(api, user, other_user, make_holding):
    h = make_holding(user, "HDFCBANK.NS")
    headline(user, h, "Old bad news one", -0.9, "negative", days_ago=10)
    headline(user, h, "Old bad news two", -0.9, "negative", days_ago=12)
    headline(user, h, "Slightly soft quarter", -0.1, "neutral")
    theirs = make_holding(other_user, "TCS.NS")
    headline(other_user, theirs, "TCS layoffs", -0.8, "negative")
    headline(other_user, theirs, "TCS guidance cut", -0.8, "negative")

    assert api.get("/api/alerts/").data == []
