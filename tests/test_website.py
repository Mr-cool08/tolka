# -*- coding: utf-8 -*-
import pytest
import sqlite3
import pyotp
import functions
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


def test_user_login_without_2fa_redirects_home(client):
    conn = sqlite3.connect("database.db")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            email_salt TEXT NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            organization_number TEXT,
            billing_address TEXT,
            email_billing_address TEXT,
            totp_secret TEXT
        )"""
    )
    conn.commit()

    email = "user-no2fa@example.com"
    password = "secret"
    pwd_hash, pwd_salt = functions.hash_password(password)
    email_hash, email_salt = functions.hash_email(email)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logins (name, email, email_salt, phone, password_hash, salt, organization_number, billing_address, email_billing_address, totp_secret) VALUES (?, ?, ?, ?, ?, ?, '', '', '', '')",
        ("Test", email_hash, email_salt, "000", pwd_hash, pwd_salt),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    response = client.post("/user_login", data={"email": email, "password": password})
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM logins WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def test_user_login_with_2fa_redirects_two_factor(client):
    conn = sqlite3.connect("database.db")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            email_salt TEXT NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            organization_number TEXT,
            billing_address TEXT,
            email_billing_address TEXT,
            totp_secret TEXT
        )"""
    )
    conn.commit()

    email = "user-2fa@example.com"
    password = "secret"
    pwd_hash, pwd_salt = functions.hash_password(password)
    email_hash, email_salt = functions.hash_email(email)
    totp_secret = pyotp.random_base32()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logins (name, email, email_salt, phone, password_hash, salt, organization_number, billing_address, email_billing_address, totp_secret) VALUES (?, ?, ?, ?, ?, ?, '', '', '', ?)",
        ("Test", email_hash, email_salt, "000", pwd_hash, pwd_salt, totp_secret),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    response = client.post("/user_login", data={"email": email, "password": password})
    assert response.status_code == 302
    assert response.headers["Location"] == "/two_factor"

    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM logins WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def test_two_factor_secret_not_shown_on_login(client):
    conn = sqlite3.connect("database.db")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            email_salt TEXT NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            organization_number TEXT,
            billing_address TEXT,
            email_billing_address TEXT,
            totp_secret TEXT
        )"""
    )
    conn.commit()

    email = "user-secret@example.com"
    password = "secret"
    pwd_hash, pwd_salt = functions.hash_password(password)
    email_hash, email_salt = functions.hash_email(email)
    totp_secret = pyotp.random_base32()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logins (name, email, email_salt, phone, password_hash, salt, organization_number, billing_address, email_billing_address, totp_secret) VALUES (?, ?, ?, ?, ?, ?, '', '', '', ?)",
        ("Test", email_hash, email_salt, "000", pwd_hash, pwd_salt, totp_secret),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    response = client.post("/user_login", data={"email": email, "password": password})
    assert response.status_code == 302
    assert response.headers["Location"] == "/two_factor"

    response = client.get("/two_factor")
    assert response.status_code == 200
    assert totp_secret not in response.get_data(as_text=True)

    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM logins WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def test_login_respects_application_root(monkeypatch):
    import os
    import website

    monkeypatch.setenv("password", "secret")
    website.PASSWORD = "secret"

    app = website.app
    app.config.update({
        "TESTING": True,
        "APPLICATION_ROOT": "/prefix",
        "SERVER_NAME": "example.com",
    })

    with app.test_client() as client:
        response = client.post(
            "/login",
            base_url="http://example.com/prefix",
            data={"email": "e", "password": "secret"},
        )

        assert response.status_code == 302
        assert response.headers["Location"] == "/prefix/jobs"
