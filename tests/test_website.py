# -*- coding: utf-8 -*-
import pytest
import sqlite3
import pyotp
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


def test_signup_login_logout_flow(tmp_path, monkeypatch):
    db_path = tmp_path / "database.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            email_salt TEXT NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            organization_number TEXT,
            billing_address TEXT,
            email_billing_address TEXT,
            totp_secret TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            language TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            status TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.chdir(tmp_path)
    website.app.config.update({"TESTING": True})
    with website.app.test_client() as client:
        signup_data = {
            "name": "Tester",
            "email": "tester@example.com",
            "phone": "123456",
            "password": "secret",
        }
        resp = client.post("/signup", data=signup_data)
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            token = pyotp.TOTP(sess["new_totp_secret"]).now()
        resp = client.post("/two_factor", data={"token": token})
        assert resp.status_code == 302
        resp = client.get("/logout")
        assert resp.status_code == 302
        home = client.get("/")
        assert home.status_code == 200
        assert "Skapa konto" in home.get_data(as_text=True)
