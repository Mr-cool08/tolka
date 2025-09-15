from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import time
import functions
from itertools import combinations
import subprocess
import pyotp
import urllib.parse
import secrets

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


def ensure_booking_schema(conn):
    """Ensure new optional columns exist on the bookings table."""
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(bookings)")
        columns = [info[1] for info in cursor.fetchall()]
        statements = []
        if 'status' not in columns:
            statements.append("ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        if 'interpreter_name' not in columns:
            statements.append("ALTER TABLE bookings ADD COLUMN interpreter_name TEXT")
        if 'interpreter_phone' not in columns:
            statements.append("ALTER TABLE bookings ADD COLUMN interpreter_phone TEXT")
        for statement in statements:
            cursor.execute(statement)
        if statements:
            conn.commit()
    except sqlite3.OperationalError:
        # The table might not exist yet (e.g., during first-time setup in tests).
        pass


def send_email_message(recipients, subject, body, bcc=None):
    """Send an email using SMTP settings if available."""
    if not recipients or app.config.get('TESTING'):
        return
    if isinstance(recipients, str):
        recipients = [recipients]
    if bcc and isinstance(bcc, str):
        bcc = [bcc]

    smtp_username = os.getenv("email")
    smtp_password = os.getenv('Email_password')
    smtp_server = os.getenv("smtp_server_address")
    smtp_port = os.getenv("smtp_port")

    if not all([smtp_username, smtp_password, smtp_server, smtp_port]):
        return

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    all_recipients = list(recipients)
    if bcc:
        msg['Bcc'] = ", ".join(bcc)
        all_recipients.extend(bcc)

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_username, all_recipients, msg.as_string())
    except Exception as exc:
        print(f"Failed to send email: {exc}")


def format_booking_email(name, email, phone, language, time_start, time_end, reference, booking_id):
    return (
        f"Boknings-ID: {booking_id}\n"
        f"Namn: {name}\n"
        f"E-post: {email}\n"
        f"Telefon: {phone}\n"
        f"Språk: {language}\n"
        f"Starttid: {time_start}\n"
        f"Sluttid: {time_end}\n"
        f"Referens: {reference or '-'}"
    )


@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    session.pop('user_id', None)
    session.pop('user_email', None)
    return redirect(url_for('home'))


@app.route('/')
def home():
    if session.get('user_id'):
        user_email = session.get('user_email')
        conn = sqlite3.connect('database.db')
        ensure_booking_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, language, time_start, time_end, status, interpreter_name, interpreter_phone
            FROM bookings WHERE email = ? ORDER BY time_start DESC
            """,
            (user_email,),
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT email FROM logins WHERE id = ?", (session['user_id'],))
        row = cursor.fetchone()
        hashed_email = row[0] if row else ''
        conn.close()
        bookings = [
            {
                'id': booking[0],
                'language': booking[1],
                'time_start': booking[2],
                'time_end': booking[3],
                'status': booking[4] or 'pending',
                'interpreter_name': booking[5],
                'interpreter_phone': booking[6],
            }
            for booking in rows
        ]
        message = (
            "Hello,\n\n"
            "Please remove my account from Tolkar.se.\n"
            f"Email hash: {hashed_email}\n\n"
            "Regards,\n"
        )
        body = urllib.parse.quote(message)
        removal_link = (
            "mailto:placeholder@tolkar.se"
            f"?subject=Account%20Deletion%20Request&body={body}"
        )
        return render_template(
            'home.html', bookings=bookings, removal_link=removal_link
        )
    return render_template('home.html')


@app.route('/booking')
def index():
    user_name = user_email = user_phone = ''
    logged_in = False
    if session.get('user_id'):
        logged_in = True
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name, phone FROM logins WHERE id = ?', (session['user_id'],))
        row = cursor.fetchone()
        conn.close()
        if row:
            user_name, user_phone = row
            user_email = session.get('user_email', '')
    return render_template(
        'index.html',
        combo_list=languages,
        user_name=user_name,
        user_email=user_email,
        user_phone=user_phone,
        logged_in=logged_in,
    )


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        organization_number = request.form.get('organization_number', '')
        billing_address = request.form.get('billing_address', '')
        email_billing_address = request.form.get('email_billing_address', '')
        pwd_hash, salt = functions.hash_password(password)
        email_hash, email_salt = functions.hash_email(email)
        enable_2fa = bool(request.form.get('enable_2fa'))
        totp_secret = pyotp.random_base32() if enable_2fa else None
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT email, email_salt FROM logins")
        for existing_hash, existing_salt in cursor.fetchall():
            if functions.verify_email(email, existing_hash, existing_salt):
                conn.close()
                return render_template('signup.html', error='E-post används redan')
        cursor.execute(
            """
            INSERT INTO logins (
                name, email, email_salt, phone, password_hash, salt,
                organization_number, billing_address, email_billing_address, totp_secret
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                email_hash,
                email_salt,
                phone,
                pwd_hash,
                salt,
                organization_number,
                billing_address,
                email_billing_address,
                totp_secret,
            ),
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        if enable_2fa:
            session['pending_user_id'] = user_id
            session['pending_user_email'] = email
            session['new_totp_secret'] = totp_secret
            return redirect(url_for('two_factor'))
        session['user_id'] = user_id
        session['user_email'] = email
        return redirect(url_for('home'))
    return render_template('signup.html')


@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, email_salt, password_hash, salt, totp_secret FROM logins")
        for row in cursor.fetchall():
            user_id, email_hash, email_salt, pwd_hash, pwd_salt, totp_secret = row
            if functions.verify_email(email, email_hash, email_salt) and functions.verify_password(password, pwd_hash, pwd_salt):
                conn.close()
                if totp_secret:
                    session['pending_user_id'] = user_id
                    session['pending_user_email'] = email
                    return redirect(url_for('two_factor'))
                session['user_id'] = user_id
                session['user_email'] = email
                return redirect(url_for('home'))
        conn.close()
        return render_template('user_login.html', error='Invalid credentials')
    return render_template('user_login.html')

@app.route('/two_factor', methods=['GET', 'POST'])
def two_factor():
    if 'pending_user_id' not in session:
        return redirect(url_for('user_login'))
    secret = session.get('new_totp_secret')
    display_secret = secret
    if not secret:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT totp_secret FROM logins WHERE id = ?', (session['pending_user_id'],))
        row = cursor.fetchone()
        conn.close()
        if row:
            secret = row[0]
    if request.method == 'POST':
        token = request.form['token']
        totp = pyotp.TOTP(secret)
        if totp.verify(token):
            session['user_id'] = session.pop('pending_user_id')
            session['user_email'] = session.pop('pending_user_email')
            session.pop('new_totp_secret', None)
            return redirect(url_for('home'))
        return render_template('verify_2fa.html', error='Invalid code', secret=display_secret)
    return render_template('verify_2fa.html', secret=display_secret)

@app.route('/health')
def health():
    """Health check endpoint used by deployment platforms."""
    return "OK", 200
@app.route('/jobs') # The page to display the list of jobs
def get_jobs():
    if 'authenticated' not in session or session['authenticated'] == False:
        return render_template('login.html')

    # Connect to the database
    conn = sqlite3.connect('database.db')
    ensure_booking_schema(conn)
    cursor = conn.cursor()

    # Retrieve pending jobs from the database
    cursor.execute("SELECT * FROM bookings WHERE status='pending' ORDER BY id ASC")

    jobs = cursor.fetchall()

    # Close the database connection
    cursor.close()
    conn.close()

    # Render the bookings.html template with the job data
    return render_template('bookings.html', jobs=jobs)

@app.route('/jobs/<int:job_id>', methods=['POST']) # The action to accept the job
def accept_job(job_id):
    print(job_id)
    # Check if the user is authenticated
    if 'authenticated' not in session:
        return render_template('login.html')

    # Connect to the database
    conn = sqlite3.connect('database.db')
    ensure_booking_schema(conn)
    cursor = conn.cursor()

    # Retrieve job information from the database
    cursor.execute("SELECT name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, avtalskund_marking, reference FROM bookings WHERE id = ?", (job_id,))
    job_data = cursor.fetchone()

    if not job_data:
        conn.close()
        return 'Job not found', 404

    interpreter_name = session.get('tolkar_name')
    interpreter_phone = session.get('tolkar_phone')
    interpreter_email = session.get('tolkar_email', '')

    if not interpreter_name or not interpreter_phone:
        conn.close()
        return 'Interpreter contact details missing', 400

    # Mark the job as accepted instead of deleting
    cursor.execute(
        "UPDATE bookings SET status='accepted', interpreter_name=?, interpreter_phone=? WHERE id = ?",
        (interpreter_name, interpreter_phone, job_id),
    )
    conn.commit()

    # Close the database connection
    cursor.close()
    conn.close()
    booking_details = format_booking_email(
        job_data[0],
        job_data[1],
        job_data[2],
        job_data[3],
        job_data[4],
        job_data[5],
        job_data[11],
        job_id,
    )

    bcc_address = os.getenv("email")

    interpreter_subject = f"Bekräftelse – Bokning {job_id}"
    interpreter_body = (
        "Kära Herr/Fru,\n\n"
        "Du har accepterat följande uppdrag:\n\n"
        f"{booking_details}\n\n"
        "Kontakta beställaren direkt vid eventuella frågor eller ändringar.\n\n"
        "Med vänliga hälsningar,\nTolkar-teamet"
    )
    send_email_message(interpreter_email, interpreter_subject, interpreter_body, bcc=bcc_address)

    user_subject = f"Din bokning har accepterats – {job_id}"
    user_body = (
        "Kära Herr/Fru,\n\n"
        "Din bokning har accepterats.\n"
        f"Tolk: {interpreter_name} ({interpreter_phone})\n\n"
        f"{booking_details}\n\n"
        "Kontakta tolken minst 24 timmar i förväg vid ändringar eller avbokning.\n\n"
        "Med vänliga hälsningar,\nTolkar-teamet"
    )
    send_email_message(job_data[1], user_subject, user_body, bcc=bcc_address)

    accepted_subject = f"Bokning accepterad – {job_id}"
    accepted_body = (
        f"{booking_details}\n\n"
        f"Tolk: {interpreter_name} ({interpreter_phone})\n"
        f"Tolken e-post: {interpreter_email or '-'}"
    )
    send_email_message('accepted@tolkar.se', accepted_subject, accepted_body, bcc=bcc_address)

    return 'Job accepted and email sent'


@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if not session.get('user_id'):
        return redirect(url_for('user_login'))
    conn = sqlite3.connect('database.db')
    ensure_booking_schema(conn)
    cursor = conn.cursor()
    user_email = session.get('user_email')
    cursor.execute(
        """
        SELECT name, phone, language, time_start, time_end, reference
        FROM bookings WHERE id=? AND email=? AND status='pending'
        """,
        (booking_id, user_email),
    )
    booking = cursor.fetchone()
    if not booking:
        conn.close()
        return redirect(url_for('home'))
    cursor.execute(
        "UPDATE bookings SET status='cancelled' WHERE id=? AND email=? AND status='pending'",
        (booking_id, user_email),
    )
    conn.commit()
    conn.close()

    booking_details = format_booking_email(
        booking[0],
        user_email,
        booking[1],
        booking[2],
        booking[3],
        booking[4],
        booking[5],
        booking_id,
    )
    subject = f"Bokning avbruten – {booking_id}"
    body = (
        "Följande bokning har avbrutits av beställaren innan den accepterades:\n\n"
        f"{booking_details}"
    )
    send_email_message('cancelled@tolkar.se', subject, body, bcc=os.getenv('email'))
    return redirect(url_for('home'))

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'GET':
        if session.get('user_id'):
            return redirect(url_for('confirmation'))
        return redirect(url_for('billing'))
    if session.get("submitted"):
        return render_template("error.html", message="You have already submitted")


    language = request.form['language']
    time_start_str = request.form['starttime']
    time_end_minutes = int(request.form['endtime'])
    time_start = datetime.strptime(time_start_str, '%Y-%m-%dT%H:%M')
    time_end = time_start + timedelta(minutes=time_end_minutes)
    time_start_str_trimmed = time_start.strftime('%Y-%m-%d %H:%M')
    time_end_str_trimmed = time_end.strftime('%Y-%m-%d %H:%M')

    if session.get('user_id'):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT name, phone, organization_number, billing_address, email_billing_address FROM logins WHERE id = ?',
            (session['user_id'],),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return redirect(url_for('user_login'))
        name, phone, organization_number, billing_address, email_billing_address = row
        email = session.get('user_email')
        if functions.booking_exists(name, email, phone, language, time_start, time_end):
            return render_template('error.html', message='This booking already exists.', error_name='409')
        session.update(
            {
                'name': name,
                'email': email,
                'phone': phone,
                'language': language,
                'time_start': time_start_str_trimmed,
                'time_end': time_end_str_trimmed,
                'organization_number': organization_number,
                'billing_address': billing_address,
                'email_billing_address': email_billing_address,
                'submitted': True,
            }
        )
        return redirect(url_for('confirmation'))

    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    if functions.booking_exists(name, email, phone, language, time_start, time_end):
        return render_template('error.html', message='This booking already exists.', error_name='409')
    session.update(
        {
            'name': name,
            'email': email,
            'phone': phone,
            'language': language,
            'time_start': time_start_str_trimmed,
            'time_end': time_end_str_trimmed,
        }
    )
    return redirect(url_for('billing'))


@app.route('/billing', methods=['GET', 'POST'])
def billing():
    if session.get('user_id'):
        return redirect(url_for('confirmation'))
    if request.method == 'GET':
        if 'name' not in session:
            return redirect(url_for('index'))
        return render_template('billing.html')

    organization_number = request.form['organization_number']
    billing_address = request.form['billing_address']
    email_billing_address = request.form['email_billing_address']
    reference = request.form['reference']
    session.update(
        {
            'organization_number': organization_number,
            'billing_address': billing_address,
            'email_billing_address': email_billing_address,
            'reference': reference,
            'submitted': True,
        }
    )
    return redirect(url_for('confirmation'))

@app.route('/confirmation', methods=['GET', 'POST'])
def confirmation():
    if 'submitted' not in session or session['submitted'] == False:
        return redirect(url_for('index'))
    else:
        if request.method == 'GET':
            organization_number = session.get('organization_number')
            billing_address = session.get('billing_address')
            email_billing_address = session.get('email_billing_address')
            reference = session.get('reference')
            name = session.get('name')
            email = session.get('email')
            language = session.get('language')
            time_start = session.get('time_start')
            time_end = session.get('time_end')
            phone = session.get('phone')
            return render_template(
                'confirmation.html',
                name=name,
                email=email,
                phone=phone,
                language=language,
                time_start=time_start,
                time_end=time_end,
                organization_number=organization_number,
                billing_address=billing_address,
                email_billing_address=email_billing_address,
                reference=reference,
            )
        elif request.method == 'POST':
            organization_number = session.get('organization_number')
            billing_address = session.get('billing_address')
            email_billing_address = session.get('email_billing_address')
            reference = session.get('reference')
            name = session.get('name')
            email = session.get('email')
            language = session.get('language')
            time_start = session.get('time_start')
            time_end = session.get('time_end')
            phone = session.get('phone')
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            ensure_booking_schema(conn)
            cursor.execute(
                "INSERT INTO bookings (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, avtalskund_marking, reference, status, interpreter_name, interpreter_phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    email,
                    phone,
                    language,
                    time_start,
                    time_end,
                    organization_number,
                    billing_address,
                    email_billing_address,
                    '',
                    '',
                    reference,
                    'pending',
                    None,
                    None,
                ),
            )
            booking_id = cursor.lastrowid
            conn.commit()

            booking_details = format_booking_email(
                name,
                email,
                phone,
                language,
                time_start,
                time_end,
                reference,
                booking_id,
            )

            order_subject = f"Ny bokning – {booking_id}"
            order_body = (
                "En ny bokning har skapats:\n\n"
                f"{booking_details}"
            )
            user_subject = f"Bekräftelse av bokning – {booking_id}"
            user_body = (
                "Tack för din bokning! Här kommer en bekräftelse på mottagna uppgifter:\n\n"
                f"{booking_details}\n\n"
                "Du får en ny avisering när en tolk har accepterat uppdraget."
            )
            bcc_address = os.getenv('email')
            conn.close()
            send_email_message('order@tolkar.se', order_subject, order_body, bcc=bcc_address)
            send_email_message(email, user_subject, user_body, bcc=bcc_address)
            time.sleep(1)
            session['submitted'] = False
            if session.get('user_id'):
                return redirect(url_for('home'))
            return redirect("https://www.tolkar.se/bekraftelse/")
        else:
            return "invalid request"


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            return render_template('forgot_password.html', error='Ange e-postadress')
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, email, email_salt FROM logins")
        except sqlite3.OperationalError:
            conn.close()
            message = "Om e-postadressen finns registrerad har ett nytt lösenord skickats."
            return render_template('forgot_password.html', message=message)
        user_id = None
        for user_row in cursor.fetchall():
            user_id_candidate, email_hash, email_salt = user_row
            if functions.verify_email(email, email_hash, email_salt):
                user_id = user_id_candidate
                break
        if user_id:
            new_password = secrets.token_urlsafe(8)
            pwd_hash, pwd_salt = functions.hash_password(new_password)
            cursor.execute(
                "UPDATE logins SET password_hash = ?, salt = ? WHERE id = ?",
                (pwd_hash, pwd_salt, user_id),
            )
            conn.commit()
            conn.close()
            subject = "Återställning av lösenord"
            body = (
                "Hej,\n\n"
                "Ditt lösenord har återställts. Använd det temporära lösenordet nedan för att logga in och byt det därefter:\n\n"
                f"{new_password}\n\n"
                "Med vänliga hälsningar,\nTolkar-teamet"
            )
            send_email_message(email, subject, body, bcc=os.getenv('email'))
        else:
            conn.close()
        message = "Om e-postadressen finns registrerad har ett nytt lösenord skickats."
        return render_template('forgot_password.html', message=message)
    return render_template('forgot_password.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form['password']
        interpreter_name = request.form.get('name', '').strip()
        interpreter_phone = request.form.get('phone', '').strip()
        if not interpreter_name or not interpreter_phone:
            return render_template(
                'login.html',
                error='Name and phone number are required',
                email=email,
                name=interpreter_name,
                phone=interpreter_phone,
            )
        if password == PASSWORD:
            # Store interpreter contact details in the session
            session['tolkar_email'] = email
            session['tolkar_name'] = interpreter_name
            session['tolkar_phone'] = interpreter_phone
            session['authenticated'] = True
            return redirect(url_for('get_jobs'))
        else:
            return render_template(
                'login.html',
                error='Invalid password',
                email=email,
                name=interpreter_name,
                phone=interpreter_phone,
            )
    return render_template('login.html')

@app.errorhandler(404)
def page_not_found(e):
    return (
        render_template(
            'error.html',
            message='Detta var inte vad du letade efter.',
            error_name='404',
        ),
        404,
    )
if __name__ == '__main__':
    # Connect to the database and create the 'bookings' table if it doesn't exist
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Create the 'bookings' table if it doesn't exist
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
                    reference TEXT,
                    status TEXT NOT NULL DEFAULT "pending")''')

    ensure_booking_schema(conn)

    # Create the 'logins' table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS logins
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    email_salt TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    organization_number TEXT,
                    billing_address TEXT,
                    email_billing_address TEXT,
                    totp_secret TEXT)''')

    cursor.execute("PRAGMA table_info(logins)")
    login_columns = [info[1] for info in cursor.fetchall()]
    extra_cols = [
        'organization_number',
        'billing_address',
        'email_billing_address',
        'email_salt',
        'totp_secret',
    ]
    for col in extra_cols:
        if col not in login_columns:
            cursor.execute(f"ALTER TABLE logins ADD COLUMN {col} TEXT")

    conn.commit()
    conn.close()

    # Ensure a default test account exists for easier manual testing
    functions.ensure_test_user()

    port = int(os.environ.get("PORT", 80))
    app.run(port=port, host="0.0.0.0", debug=False)
