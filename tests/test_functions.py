import sqlite3
import os
import functions


def setup_db(tmp_path):
    db_path = tmp_path / 'database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            language TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        "INSERT INTO bookings (name, email, phone, language, time_start, time_end) VALUES (?, ?, ?, ?, ?, ?)",
        ("Alice", "alice@example.com", "123", "English", "10", "11"),
    )
    conn.commit()
    conn.close()
    return db_path


def setup_logins_db(tmp_path):
    db_path = tmp_path / 'database.db'
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
        """,
    )
    conn.commit()
    conn.close()
    return db_path


def test_generate_secret_key_length_and_uniqueness():
    key1 = functions.generate_secret_key()
    key2 = functions.generate_secret_key()
    assert len(key1) == 64
    assert len(key2) == 64
    assert key1 != key2


def test_booking_exists_true(tmp_path, monkeypatch):
    setup_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert functions.booking_exists(
        "Alice", "alice@example.com", "123", "English", "10", "11"
    )


def test_booking_exists_false(tmp_path, monkeypatch):
    setup_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert not functions.booking_exists(
        "Bob", "bob@example.com", "456", "Swedish", "10", "11"
    )


def test_hash_password_and_verify():
    password = "secret"
    pwd_hash, salt = functions.hash_password(password)
    assert isinstance(pwd_hash, str) and isinstance(salt, str)
    assert len(pwd_hash) == 64
    assert len(salt) == 32
    assert functions.verify_password(password, pwd_hash, salt)
    assert not functions.verify_password("wrong", pwd_hash, salt)


def test_hash_email_and_verify():
    email = "user@example.com"
    email_hash, salt = functions.hash_email(email)
    assert isinstance(email_hash, str) and isinstance(salt, str)
    assert len(email_hash) == 64
    assert len(salt) == 32
    assert functions.verify_email(email, email_hash, salt)
    assert not functions.verify_email("other@example.com", email_hash, salt)


def test_ensure_test_user_creates_single_entry(tmp_path, monkeypatch):
    setup_logins_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    functions.ensure_test_user()
    # Second call should not create a duplicate
    functions.ensure_test_user()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT email, email_salt, totp_secret FROM logins')
    rows = cursor.fetchall()
    conn.close()
    count = sum(
        1 for e_hash, e_salt, _ in rows if functions.verify_email('test@example.com', e_hash, e_salt)
    )
    assert count == 1
    assert all(totp == '' for _, _, totp in rows)
