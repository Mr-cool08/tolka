# -*- coding: utf-8 -*-
import pytest
import website


@pytest.fixture
def client():
    website.app.config.update({"TESTING": True})
    with website.app.test_client() as client:
        yield client


def test_home_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Välkommen" in response.get_data(as_text=True)


def test_booking_route(client):
    response = client.get("/booking")
    assert response.status_code == 200
    assert "Bokning av översättare" in response.get_data(as_text=True)


def test_login_route(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Login" in response.get_data(as_text=True)


def test_health_route(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "OK" in response.get_data(as_text=True)


def test_404_route(client):
    response = client.get("/not-found")
    assert response.status_code == 404
    assert "Detta var inte vad du letade efter." in response.get_data(as_text=True)


def test_two_factor_requires_pending_user(client):
    response = client.get("/two_factor")
    assert response.status_code == 302
    assert "/user_login" in response.headers["Location"]
