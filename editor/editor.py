from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# Function to create a connection to the SQLite database
def get_db_connection():
    conn = sqlite3.connect('bookings.db')
    conn.row_factory = sqlite3.Row
    return conn

# Function to get all bookings from the 'bookings' table
def get_bookings():
    conn = get_db_connection()
    bookings = conn.execute('SELECT * FROM bookings').fetchall()
    conn.close()
    return bookings

# Function to get all taken bookings from the 'taken_bookings' table
def get_taken_bookings():
    conn = get_db_connection()
    taken_bookings = conn.execute('SELECT * FROM taken_bookings').fetchall()
    conn.close()
    return taken_bookings

# Route to display all bookings and taken bookings
@app.route('/')
def index():
    bookings = get_bookings()
    taken_bookings = get_taken_bookings()
    return render_template('index.html', bookings=bookings, taken_bookings=taken_bookings)

# Route to add a new booking
@app.route('/add_booking', methods=['POST'])
def add_booking():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        language = request.form['language']
        time_start = request.form['time_start']
        time_end = request.form['time_end']
        organization_number = request.form['organization_number']
        billing_address = request.form['billing_address']
        email_billing_address = request.form['email_billing_address']
        marking = request.form['marking']
        avtalskund_marking = request.form['avtalskund_marking']
        reference = request.form['reference']

        conn = get_db_connection()
        conn.execute('''INSERT INTO bookings 
                        (name, email, phone, language, time_start, time_end, organization_number,
                        billing_address, email_billing_address, marking, avtalskund_marking, reference)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (name, email, phone, language, time_start, time_end, organization_number,
                    billing_address, email_billing_address, marking, avtalskund_marking, reference))
        conn.commit()
        conn.close()

    return redirect(url_for('index'))

# Route to delete a booking
@app.route('/delete_taken_booking/<int:booking_id>')
def delete_taken_booking(booking_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM taken_bookings WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# Route to move a booking to 'taken_bookings' table
@app.route('/move_to_taken_bookings/<int:booking_id>')
def move_to_taken_bookings(booking_id):
    conn = get_db_connection()

    # Get the booking from 'bookings' table
    booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()

    # Insert the booking into 'taken_bookings' table
    conn.execute('''INSERT INTO taken_bookings 
                    (name, email, phone, language, time_start, time_end, organization_number,
                    billing_address, email_billing_address, marking, avtalskund_marking, reference)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (booking['name'], booking['email'], booking['phone'], booking['language'],
                  booking['time_start'], booking['time_end'], booking['organization_number'],
                  booking['billing_address'], booking['email_billing_address'], booking['marking'],
                  booking['avtalskund_marking'], booking['reference']))

    # Delete the booking from 'bookings' table
    conn.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))

    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
