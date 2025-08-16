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
