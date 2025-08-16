import sqlite3
import secrets


def generate_secret_key():
    """Generate a random 32-byte hexadecimal secret key."""
    return secrets.token_hex(32)


def booking_exists(name, email, phone, language, time_start, time_end):
    """Check if a booking with the same details already exists."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM bookings WHERE name = ? AND email = ? AND phone = ? AND language = ? AND time_start = ? AND time_end = ?",
        (name, email, phone, language, time_start, time_end),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

