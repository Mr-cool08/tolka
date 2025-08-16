import sqlite3
import os
import secrets
import hashlib
import binascii

def generate_secret_key():
    # Generate a random 32-byte key using secrets module
    return secrets.token_hex(32)

def booking_exists(name, email, phone, language, time_start, time_end):
    # Connect to the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Check if the booking already exists in the database
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE name = ? AND email = ? AND phone = ? AND language = ? AND time_start = ? AND time_end = ?", (name, email, phone, language, time_start, time_end))
    count = cursor.fetchone()[0]

    # Close the database connection
    conn.close()

    return count > 0

def hash_password(password):
    salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return binascii.hexlify(salt).decode('utf-8'), binascii.hexlify(hashed).decode('utf-8')

def verify_password(password, salt, hashed):
    salt_bytes = binascii.unhexlify(salt.encode('utf-8'))
    check_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000)
    return binascii.hexlify(check_hash).decode('utf-8') == hashed
