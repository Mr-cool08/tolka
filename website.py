from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import time
import functions
from itertools import combinations
import subprocess
from werkzeug.security import generate_password_hash, check_password_hash

languages = [
    "Franska", "Engelska", "Tyska", "Spanska",
    "Portugisiska", "Italienska", "Ryska", "Kinesiska", "Arabiska",
    "Japanska", "Koreanska", "Nederländska", "Grekiska", "Turkiska",
    "Hebreiska", "Finska", "Danska", "Norska", "Isländska",
    "Polska", "Ungerska", "Tjeckiska", "Slovakiska", "Kroatiska",
    "Serbiska", "Rumänska", "Bulgarska", "Ukrainska", "Georgiska",
    "Persiska", "Hindi", "Bengali", "Tamil", "Urdu",
    "Malayalam", "Thai", "Vietnamesiska", "Malaysiska", "Indonesiska",
    "Filippinska", "Sinhala", "Svahili", "Amhariska", "Swahili",
    "Somaliska", "Fula", "Yoruba", "Zulu"
]



load_dotenv()
app = Flask(__name__)
app.secret_key = functions.generate_secret_key()

# Define the password for accessing the /jobs route
PASSWORD = os.getenv('password')
@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))
    
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/book')
def book():
    user = None
    if 'user_id' in session:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, email, phone FROM logins WHERE id = ?", (session['user_id'],))
        row = cursor.fetchone()
        conn.close()
        if row:
            user = {'name': row[0], 'email': row[1], 'phone': row[2]}
    return render_template('index.html', combo_list=languages, user=user)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO logins (name, email, phone, password_hash) VALUES (?, ?, ?, ?)",
                (name, email, phone, password_hash),
            )
            conn.commit()
            user_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('signup.html', error='Email already registered')
        conn.close()
        session['user_id'] = user_id
        return redirect(url_for('book'))
    return render_template('signup.html')


@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash, name, phone FROM logins WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        if row and check_password_hash(row[1], password):
            session['user_id'] = row[0]
            return redirect(url_for('book'))
        return render_template('user_login.html', error='Invalid email or password')
    return render_template('user_login.html')


@app.route('/user_logout')
def user_logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/jobs') # The page to display the list of jobs
def get_jobs():
    if 'authenticated' not in session or session['authenticated'] == False:
        return render_template('login.html')

    # Connect to the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Retrieve jobs from the database
    cursor.execute("SELECT * FROM bookings ORDER BY id ASC")

    jobs = cursor.fetchall()

    # Close the database connection
    cursor.close()
    conn.close()

    # Render the bookings.html template with the job data
    return render_template('bookings.html', jobs=jobs)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    
    if request.method == 'GET':
        return redirect('/billing')  # Redirect to the billing information form
    if "submitted" in session and session["submitted"] == True:
        return render_template("error.html", message="You have already submitted")
    else:
        # Retrieve the form data
        name = request.form['name']
        email = request.form['email']
        language = request.form['language']
        time_start_str = request.form['starttime']
        time_end_minutes = int(request.form['endtime'])  # Retrieve the selected end time in minutes
        phone = request.form['phone']
        time_start = datetime.strptime(time_start_str, '%Y-%m-%dT%H:%M')
        
        # Calculate the end time based on the selected minutes
        time_end = time_start + timedelta(minutes=time_end_minutes)
        
        time_start_str_trimmed = time_start.strftime('%Y-%m-%d %H:%M')  # Extract date, hours, and minutes
        time_end_str_trimmed = time_end.strftime('%Y-%m-%d %H:%M')  # Extract date, hours, and minutes
        
        # Check if the booking already exists in the database
        if functions.booking_exists(name, email, phone, language, time_start, time_end):
            return render_template('error.html', message='This booking already exists.', error_name='409')

        # Store the form data in the session
        session['name'] = name
        session['email'] = email
        session['phone'] = phone
        session['language'] = language
        session['time_start'] = time_start_str_trimmed
        session['time_end'] = time_end_str_trimmed

        return redirect('/billing')

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    if request.method == 'GET':
        if 'name' not in session:
            return redirect(url_for('book'))
        else:
            return render_template('billing.html')  # Render the billing information form

    # Retrieve the billing information from the form
    organization_number = request.form['organization_number']
    billing_address = request.form['billing_address']
    email_billing_address = request.form['email_billing_address']
    marking = request.form['marking']
    avtalskund_marking = request.form['avtalskund_marking']
    reference = request.form['reference']
    session["avtalskund_marking"] = avtalskund_marking
    session['organization_number'] = organization_number
    session['billing_address'] = billing_address
    session['email_billing_address'] = email_billing_address
    session['marking'] = marking
    session['reference'] = reference
    

    # Mark the form as submitted in the session
    session['submitted'] = True
    return redirect(url_for('confirmation'))

@app.route('/confirmation', methods=['GET', 'POST'])
def confirmation():
    if 'submitted' not in session or session['submitted'] == False:
        return redirect(url_for('book'))
    else:
        if request.method == 'GET':
            organization_number = session.get('organization_number')
            billing_address = session.get('billing_address')
            email_billing_address = session.get('email_billing_address')
            marking = session.get('marking')
            reference = session.get('reference')
            avtalskund_marking = session.get('avtalskund_marking')
            name = session.get('name')
            email = session.get('email')
            language = session.get('language')
            time_start = session.get('time_start')
            time_end = session.get('time_end')
            phone = session.get('phone')
            return render_template('confirmation.html', name=name, email=email, phone=phone, language=language, time_start=time_start, time_end=time_end, organization_number=organization_number, billing_address=billing_address, email_billing_address=email_billing_address, marking=marking, reference=reference, avtalskund_marking=avtalskund_marking)
        elif request.method == 'POST':
            organization_number = session.get('organization_number')
            billing_address = session.get('billing_address')
            email_billing_address = session.get('email_billing_address')
            marking = session.get('marking')
            reference = session.get('reference')
            avtalskund_marking = session.get('avtalskund_marking')
            name = session.get('name')
            email = session.get('email')
            language = session.get('language')
            time_start = session.get('time_start')
            time_end = session.get('time_end')
            phone = session.get('phone')
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute(
            "INSERT INTO bookings (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, avtalskund_marking, reference) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, avtalskund_marking, reference))
            conn.commit()

        # Close the database connection
            conn.close()
            time.sleep(1)
            session['submitted'] = False
            return redirect("https://www.tolkar.se/bekraftelse/")
        else:
            return "invalid request"
        """""
        # Insert the booking details into the database, including the billing information
        cursor.execute(
            "INSERT INTO bookings (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, reference) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, reference))
        conn.commit()

        # Close the database connection
        conn.close()
        """""

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == PASSWORD:
            # Store the email in the session
            session['tolkar_email'] = request.form['email']
            session['authenticated'] = True
            return redirect('/jobs')
        else:
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message='Detta var inte vad du letade efter.', error_name='404')

if __name__ == '__main__':
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS bookings
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    reference TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS logins
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT NOT NULL,
                    password_hash TEXT NOT NULL)''')

    conn.close()
    app.run(port=8080, host="0.0.0.0", debug=True)
