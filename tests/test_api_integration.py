from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app.api as api
import app.data.catalog as catalog


def _client(tmp_path, monkeypatch):
    database_path = tmp_path / "integration.db"
    monkeypatch.setattr(api, "AUTH_DB", database_path)
    monkeypatch.setattr(catalog, "AUTH_DB", database_path)
    return TestClient(api.app), database_path


def _csrf(client):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _register_and_login(client, email="owner@example.com"):
    token = _csrf(client)
    assert client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
        headers={"X-CSRF-Token": token},
    ).status_code == 200
    token = _csrf(client)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    return _csrf(client)


def test_http_auth_csrf_logout_and_trip_ownership(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.get("/trips").status_code == 401
    assert client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    ).status_code == 403

    csrf = _register_and_login(client)
    assert client.post(
        "/plan",
        json={
            "destination": "Jaipur",
            "duration": 0,
            "travelers": 2,
            "budget": 10000,
            "interests": ["History"],
        },
        headers={"X-CSRF-Token": csrf},
    ).status_code == 422
    assert client.post(
        "/trips",
        json={"request": {"destination": "Jaipur"}, "result": {}},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 200
    assert len(client.get("/trips").json()) == 1
    assert client.post("/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/trips").status_code == 401


def test_http_csrf_origin_and_token_validation(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"Origin": "https://evil.example"},
    ).status_code == 403
    csrf = _csrf(client)
    assert client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"X-CSRF-Token": "wrong"},
    ).status_code == 403
    assert client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 200


def test_http_login_rate_limit_expires_and_success_resets(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(api, "RATE_LIMIT_MAX_FAILURES", 2)
    monkeypatch.setattr(api, "RATE_LIMIT_WINDOW", timedelta(minutes=5))
    csrf = _csrf(client)
    assert client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 200

    for _ in range(2):
        csrf = _csrf(client)
        assert client.post(
            "/auth/login",
            json={"email": "OWNER@example.com", "password": "wrong"},
            headers={"X-CSRF-Token": csrf},
        ).status_code == 401
    csrf = _csrf(client)
    assert client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "wrong"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 429

    old = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    import sqlite3
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE login_attempts SET window_started_at = ?", (old,))
    csrf = _csrf(client)
    assert client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 200
    csrf = _csrf(client)
    assert client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "wrong"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 401
    csrf = _csrf(client)
    assert client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 200
    csrf = _csrf(client)
    assert client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "wrong"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 401


def test_http_cors_rejects_untrusted_origin(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.options(
        "/auth/csrf",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400


def test_http_live_hotel_offers_are_private_and_price_checked(tmp_path, monkeypatch):
    client, database_path = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("WANDERWISE_HOTEL_MODE", "live")
    _register_and_login(client)

    class FakeRapidClient:
        async def search(self, **_kwargs):
            return {
                "provider": "expedia_rapid",
                "status": "available",
                "offers": [{
                    "hotel_name": "Provider Hotel",
                    "availability": "available",
                    "total_price": 2500,
                    "currency": "INR",
                    "occupancy": {"adults": 2, "children_ages": [], "rooms": 1},
                    "source": "Expedia Rapid live availability",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "_price_check_path": "/v3/properties/p/rooms/r/rates/r?token=private",
                    "offer_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                }],
            }

        async def price_check(self, path, **_kwargs):
            assert path.endswith("token=private")
            return {"status": "available", "occupancy_pricing": {"2": {"total": 2500}}}

    monkeypatch.setattr(api, "ExpediaRapidClient", FakeRapidClient)
    check_in = (datetime.now(timezone.utc) + timedelta(days=30)).date()
    check_out = check_in + timedelta(days=2)
    csrf = _csrf(client)
    response = client.post(
        "/hotels/search",
        headers={"X-CSRF-Token": csrf},
        json={
            "destination": "Jaipur",
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "adults": 2,
            "rooms": 1,
        },
    )
    assert response.status_code == 200
    offer = response.json()["offers"][0]
    assert offer["hotel_name"] == "Provider Hotel"
    assert "_price_check_path" not in offer

    price_check = client.post(
        f"/hotel-offers/{offer['offer_id']}/price-check",
        headers={"X-CSRF-Token": csrf},
        json={},
    )
    assert price_check.status_code == 200
    assert price_check.json()["status"] == "available"

    client2, _ = _client(tmp_path, monkeypatch)
    _register_and_login(client2, "other@example.com")
    other_csrf = _csrf(client2)
    unauthorized = client2.post(
        f"/hotel-offers/{offer['offer_id']}/price-check",
        headers={"X-CSRF-Token": other_csrf},
        json={},
    )
    assert unauthorized.status_code == 404


def test_http_demo_mode_does_not_claim_live_hotel_search(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    _register_and_login(client)
    monkeypatch.setenv("WANDERWISE_HOTEL_MODE", "demo")
    csrf = _csrf(client)
    response = client.post(
        "/hotels/search",
        headers={"X-CSRF-Token": csrf},
        json={
            "destination": "Jaipur",
            "check_in": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
            "check_out": (datetime.now(timezone.utc) + timedelta(days=32)).date().isoformat(),
            "adults": 2,
        },
    )
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()
