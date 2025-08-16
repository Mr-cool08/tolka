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


def hash_email(email, salt=None):
    """Hash an email with PBKDF2 and return hex digest and salt."""
    email = email.lower()
    if salt is None:
        salt = os.urandom(16)
    else:
        salt = bytes.fromhex(salt)
    email_hash = hashlib.pbkdf2_hmac('sha256', email.encode(), salt, 100000)
    return email_hash.hex(), salt.hex()


def verify_email(email, stored_hash, salt):
    """Verify an email against the stored hash and salt."""
    new_hash, _ = hash_email(email, salt)
    return new_hash == stored_hash

def ensure_test_user(email="test@example.com", password="Masbo124"):
    """Create a default test user if it does not already exist."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT email, email_salt FROM logins")
    for email_hash, email_salt in cursor.fetchall():
        if verify_email(email, email_hash, email_salt):
            conn.close()
            return
    pwd_hash, pwd_salt = hash_password(password)
    email_hash, email_salt = hash_email(email)
    cursor.execute(
        "INSERT INTO logins (name, email, email_salt, phone, password_hash, salt, organization_number, billing_address, email_billing_address, totp_secret) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("Test User", email_hash, email_salt, "0000000000", pwd_hash, pwd_salt, "", "", "", ""),
    )
    conn.commit()
    conn.close()
