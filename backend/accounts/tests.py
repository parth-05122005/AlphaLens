import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_login_and_me():
    client = APIClient()
    resp = client.post(
        reverse("register"),
        {"username": "alice", "email": "alice@example.com", "password": "s3cret-pass"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["user"]["username"] == "alice"
    assert resp.data["access"] and resp.data["refresh"]

    resp = client.post(reverse("login"), {"username": "alice", "password": "s3cret-pass"}, format="json")
    assert resp.status_code == 200
    access = resp.data["access"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    resp = client.get(reverse("me"))
    assert resp.status_code == 200
    assert resp.data == {"id": resp.data["id"], "username": "alice", "email": "alice@example.com"}


@pytest.mark.django_db
def test_register_rejects_short_password_and_duplicate_username():
    client = APIClient()
    resp = client.post(reverse("register"), {"username": "bob", "password": "short"}, format="json")
    assert resp.status_code == 400
    assert "password" in resp.data

    client.post(reverse("register"), {"username": "bob", "password": "long-enough-1"}, format="json")
    resp = client.post(reverse("register"), {"username": "bob", "password": "long-enough-1"}, format="json")
    assert resp.status_code == 400
    assert "username" in resp.data


@pytest.mark.django_db
def test_me_requires_auth():
    assert APIClient().get(reverse("me")).status_code == 401
