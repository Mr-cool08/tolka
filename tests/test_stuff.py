import sqlite3
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stuff import generate_secret_key, booking_exists


def test_generate_secret_key_produces_random_hex():
    key1 = generate_secret_key()
    key2 = generate_secret_key()
    assert len(key1) == 64
    assert len(key2) == 64
    assert key1 != key2


def test_booking_exists(tmp_path, monkeypatch):
    db_path = tmp_path / "bookings.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE bookings (
            name TEXT,
            email TEXT,
            phone TEXT,
            language TEXT,
            time_start TEXT,
            time_end TEXT
        )
    """)
    cursor.execute(
        "INSERT INTO bookings VALUES (?,?,?,?,?,?)",
        ("John Doe", "john@example.com", "123", "English", "10", "11")
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)

    assert booking_exists("John Doe", "john@example.com", "123", "English", "10", "11")
    assert not booking_exists("Jane", "jane@example.com", "456", "French", "11", "12")

