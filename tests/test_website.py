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
    old_password = website.PASSWORD
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

    website.PASSWORD = old_password
    app.config["APPLICATION_ROOT"] = "/"
    app.config["SERVER_NAME"] = None


def test_signup_creates_user_and_redirects_home(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect("database.db")
    conn.execute(
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
    conn.commit()
    conn.close()

    email = "signup@example.com"
    password = "secret"
    response = client.post(
        "/signup",
        data={
            "name": "User",
            "email": email,
            "phone": "000",
            "password": password,
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT id, email, email_salt, password_hash, salt FROM logins")
    row = cur.fetchone()
    conn.close()
    assert row is not None
    _id, e_hash, e_salt, p_hash, p_salt = row
    assert functions.verify_email(email, e_hash, e_salt)
    assert functions.verify_password(password, p_hash, p_salt)


def test_signup_duplicate_email_shows_error(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect("database.db")
    conn.execute(
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
    email = "dup@example.com"
    pwd_hash, pwd_salt = functions.hash_password("pw")
    email_hash, email_salt = functions.hash_email(email)
    conn.execute(
        "INSERT INTO logins (name, email, email_salt, phone, password_hash, salt, organization_number, billing_address, email_billing_address, totp_secret) VALUES (?, ?, ?, ?, ?, ?, '', '', '', '')",
        ("U", email_hash, email_salt, "0", pwd_hash, pwd_salt),
    )
    conn.commit()
    conn.close()

    response = client.post(
        "/signup",
        data={
            "name": "U",
            "email": email,
            "phone": "1",
            "password": "pw",
        },
    )
    assert response.status_code == 200
    assert "E-post används redan" in response.get_data(as_text=True)


def test_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_email"] = "user@example.com"
        sess["authenticated"] = True

    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "user_email" not in sess
        assert "authenticated" not in sess


def test_cancel_booking_updates_status(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect("database.db")
    conn.execute(
        """
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            language TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            organization_number TEXT,
            billing_address TEXT,
            email_billing_address TEXT,
            marking TEXT,
            avtalskund_marking TEXT,
            reference TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
        )
        """
    )
    conn.commit()
    conn.execute(
        "INSERT INTO bookings (name, email, phone, language, time_start, time_end, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
        ("N", "cancel@example.com", "1", "English", "s", "e"),
    )
    booking_id = conn.execute("SELECT id FROM bookings").fetchone()[0]
    conn.commit()
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_email"] = "cancel@example.com"

    response = client.post(f"/cancel_booking/{booking_id}")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    conn = sqlite3.connect("database.db")
    status = conn.execute("SELECT status FROM bookings WHERE id = ?", (booking_id,)).fetchone()[0]
    conn.close()
    assert status == "cancelled"


def test_confirmation_post_creates_booking(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect("database.db")
    conn.execute(
        """
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            language TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            organization_number TEXT,
            billing_address TEXT,
            email_billing_address TEXT,
            marking TEXT,
            avtalskund_marking TEXT,
            reference TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
        )
        """
    )
    conn.commit()
    conn.close()

    with client.session_transaction() as sess:
        sess.update(
            {
                "organization_number": "1",
                "billing_address": "A",
                "email_billing_address": "b@example.com",
                "reference": "R",
                "name": "Name",
                "email": "c@example.com",
                "language": "English",
                "time_start": "s",
                "time_end": "e",
                "phone": "0",
                "submitted": True,
            }
        )

    response = client.post("/confirmation")
    assert response.status_code == 302
    conn = sqlite3.connect("database.db")
    row = conn.execute("SELECT name, status FROM bookings").fetchone()
    conn.close()
    assert row == ("Name", "pending")
