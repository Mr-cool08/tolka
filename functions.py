import sqlite3
import secrets
import os
import hashlib


def generate_secret_key():
    """Generate a random 32-byte key using secrets module."""
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


def hash_password(password, salt=None):
    """Hash a password with PBKDF2 and return hex digest and salt."""
    if salt is None:
        salt = os.urandom(16)
    else:
        salt = bytes.fromhex(salt)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return pwd_hash.hex(), salt.hex()


def verify_password(password, stored_hash, salt):
    """Verify a password against the stored hash and salt."""
    new_hash, _ = hash_password(password, salt)
    return new_hash == stored_hash
