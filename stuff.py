import sqlite3
import os
import secrets
def generate_secret_key():
    # Generate a random 32-byte key using secrets module
    return secrets.token_hex(32)
def booking_exists(name, email, phone, language, time_start, time_end):
    # Connect to the database
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()

    # Check if the booking already exists in the database
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE name = ? AND email = ? AND phone = ? AND language = ? AND time_start = ? AND time_end = ?",
                   (name, email, phone, language, time_start, time_end))
    count = cursor.fetchone()[0]

    # Close the database connection
    conn.close()

    return count > 0