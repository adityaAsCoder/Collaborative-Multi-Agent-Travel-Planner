import pytest

import app.api as api
import app.data.catalog as catalog


def test_sessions_authenticate_and_logout_without_trusting_email(tmp_path, monkeypatch):
    database_path = tmp_path / "auth.db"
    monkeypatch.setattr(api, "AUTH_DB", database_path)
    monkeypatch.setattr(catalog, "AUTH_DB", database_path)

    assert api.register(api.RegisterRequest(
        email="Owner@Example.com",
        password="password123",
    ))["message"]
    response = api.login(api.LoginRequest(
        email="owner@example.com",
        password="password123",
    ))
    token = response.headers["set-cookie"].split("=", 1)[1].split(";", 1)[0]

    assert api.current_email(token) == "owner@example.com"
    with pytest.raises(api.HTTPException) as error:
        api.current_email(None)
    assert error.value.status_code == 401

    api.save_trip("owner@example.com", {"destination": "Jaipur"}, {"itinerary": []})
    assert len(api.get_trips(api.current_email(token))) == 1

    logout_response = api.Response()
    assert api.logout(logout_response, token)["message"] == "Logged out."
    with pytest.raises(api.HTTPException) as error:
        api.current_email(token)
    assert error.value.status_code == 401


def test_trip_lookup_requires_matching_authenticated_owner(tmp_path, monkeypatch):
    database_path = tmp_path / "auth.db"
    monkeypatch.setattr(api, "AUTH_DB", database_path)
    monkeypatch.setattr(catalog, "AUTH_DB", database_path)

    catalog.create_user("owner@example.com", "password123")
    trip_id = api.save_trip("owner@example.com", {}, {})

    assert api.get_trip_by_id(trip_id, "owner@example.com") is not None
    assert api.get_trip_by_id(trip_id, "attacker@example.com") is None
