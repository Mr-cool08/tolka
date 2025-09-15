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

ORDER_EMAIL = "order@tolkar.se"
CANCELLED_EMAIL = "cancelled@tolkar.se"
ACCEPTED_EMAIL = "accepted@tolkar.se"


def ensure_bookings_schema(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            status TEXT NOT NULL DEFAULT 'pending',
            accepted_by_name TEXT,
            accepted_by_phone TEXT
        )
        """
    )
    cursor.execute("PRAGMA table_info(bookings)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'accepted_by_name' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN accepted_by_name TEXT")
    if 'accepted_by_phone' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN accepted_by_phone TEXT")
    conn.commit()


def ensure_password_reset_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def send_email(recipients, subject, body):
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r for r in recipients if r]
    if not recipients:
        return False

    smtp_username = os.getenv("email")
    smtp_password = os.getenv('Email_password')
    smtp_server = os.getenv("smtp_server_address")
    smtp_port = os.getenv("smtp_port")

    if (
        not smtp_username
        or not smtp_password
        or not smtp_server
        or not smtp_port
    ):
        app.logger.warning("Email configuration missing. Skipping email send to %s", recipients)
        return False

    if app.config.get("TESTING"):
        app.logger.debug("Testing mode – not sending email to %s", recipients)
        return True

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    bcc = smtp_username

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(
                smtp_username,
                recipients + [bcc],
                msg.as_string(),
            )
        return True
    except Exception as exc:
        app.logger.error("Failed to send email to %s: %s", recipients, exc)
        return False


@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('tolkar_email', None)
    session.pop('tolkar_name', None)
    session.pop('tolkar_phone', None)
    return redirect(url_for('home'))


@app.route('/')
def home():
    if session.get('user_id'):
        user_email = session.get('user_email')
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        ensure_bookings_schema(conn)
        cursor.execute(
            """
            SELECT id, language, time_start, time_end, status, accepted_by_name, accepted_by_phone
            FROM bookings WHERE email = ?
            """,
            (user_email,),
        )
        bookings = cursor.fetchall()
        cursor.execute("SELECT email FROM logins WHERE id = ?", (session['user_id'],))
        row = cursor.fetchone()
        hashed_email = row[0] if row else ''
        conn.close()
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
    cursor = conn.cursor()
    ensure_bookings_schema(conn)

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
    cursor = conn.cursor()
    ensure_bookings_schema(conn)

    # Retrieve job information from the database
    cursor.execute(
        """
        SELECT name, email, phone, language, time_start, time_end,
               organization_number, billing_address, email_billing_address,
               marking, avtalskund_marking, reference
        FROM bookings WHERE id = ?
        """,
        (job_id,),
    )
    job_data = cursor.fetchone()

    tolkar_name = session.get('tolkar_name', '').strip()
    tolkar_phone = session.get('tolkar_phone', '').strip()
    tolkar_email = session.get('tolkar_email', '').strip()

    if not job_data:
        conn.close()
        return "Jobb hittades inte", 404

    if not tolkar_name or not tolkar_phone:
        conn.close()
        return "Tolkinformation saknas", 400

    # Mark the job as accepted instead of deleting
    cursor.execute(
        "UPDATE bookings SET status='accepted', accepted_by_name=?, accepted_by_phone=? WHERE id = ?",
        (tolkar_name, tolkar_phone, job_id),
    )
    conn.commit()

    # Close the database connection
    cursor.close()
    conn.close()
    booking_summary = (
        f"Kund: {job_data[0]}\n"
        f"E-post: {job_data[1]}\n"
        f"Telefon: {job_data[2]}\n"
        f"Språk: {job_data[3]}\n"
        f"Starttid: {job_data[4]}\n"
        f"Sluttid: {job_data[5]}\n"
    )

    translator_summary = f"Tolken: {tolkar_name} – {tolkar_phone}"

    send_email(
        tolkar_email,
        f"Bekräftelse – uppdrag {job_id}",
        (
            "Hej!\n\n"
            "Du har accepterat följande uppdrag:\n\n"
            f"{booking_summary}\n"
            "Vänligen kontakta beställaren vid behov.\n\n"
            "Hälsningar,\nTolkar.se"
        ),
    )

    send_email(
        job_data[1],
        f"Din bokning har accepterats (ID {job_id})",
        (
            "Hej!\n\n"
            "Din bokning har accepterats av en tolk. Här är detaljerna:\n\n"
            f"{booking_summary}"
            f"{translator_summary}\n\n"
            "Kontakta tolken direkt för eventuella ändringar eller avbokningar minst 24 timmar i förväg.\n\n"
            "Hälsningar,\nTolkar.se"
        ),
    )

    send_email(
        ACCEPTED_EMAIL,
        f"Bokning accepterad – ID {job_id}",
        (
            "En bokning har accepterats.\n\n"
            f"{booking_summary}"
            f"{translator_summary}\n"
            f"Tolkens e-post: {tolkar_email}\n"
        ),
    )

    return 'Job accepted and email sent'


@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if not session.get('user_id'):
        return redirect(url_for('user_login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    ensure_bookings_schema(conn)
    user_email = session.get('user_email')
    cursor.execute(
        """
        SELECT id, name, email, phone, language, time_start, time_end
        FROM bookings
        WHERE id=? AND email=? AND status='pending'
        """,
        (booking_id, user_email),
    )
    booking = cursor.fetchone()
    cursor.execute(
        "UPDATE bookings SET status='cancelled' WHERE id=? AND email=? AND status='pending'",
        (booking_id, user_email),
    )
    conn.commit()
    conn.close()
    if booking:
        details = (
            f"Kund: {booking[1]}\n"
            f"E-post: {booking[2]}\n"
            f"Telefon: {booking[3]}\n"
            f"Språk: {booking[4]}\n"
            f"Starttid: {booking[5]}\n"
            f"Sluttid: {booking[6]}\n"
        )
        send_email(
            CANCELLED_EMAIL,
            f"Bokning avbruten – ID {booking[0]}",
            "En bokning har avbrutits innan den accepterades.\n\n" + details,
        )
        send_email(
            booking[2],
            f"Bekräftelse på avbokning (ID {booking[0]})",
            (
                "Hej!\n\n"
                "Din bokning har avbokats. Ingen tolk hade accepterat uppdraget.\n\n"
                f"{details}"
                "Hälsningar,\nTolkar.se"
            ),
        )
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

    ensure_conn = sqlite3.connect('database.db')
    ensure_bookings_schema(ensure_conn)
    ensure_conn.close()

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
            ensure_bookings_schema(conn)
            cursor.execute(
                """
                INSERT INTO bookings (
                    name, email, phone, language, time_start, time_end,
                    organization_number, billing_address, email_billing_address,
                    marking, avtalskund_marking, reference, status,
                    accepted_by_name, accepted_by_phone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
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
                    '',
                    '',
                ),
            )
            booking_id = cursor.lastrowid
            conn.commit()

            # Close the database connection
            conn.close()
            time.sleep(1)
            session['submitted'] = False
            booking_details = (
                f"Boknings-ID: {booking_id}\n"
                f"Namn: {name}\n"
                f"E-post: {email}\n"
                f"Telefon: {phone}\n"
                f"Språk: {language}\n"
                f"Starttid: {time_start}\n"
                f"Sluttid: {time_end}\n"
                f"Organisationsnummer: {organization_number}\n"
                f"Fakturaadress: {billing_address}\n"
                f"Faktura via e-post: {email_billing_address}\n"
                f"Referens: {reference}\n"
            )
            send_email(
                email,
                "Din bokningsbekräftelse",
                (
                    "Hej!\n\n"
                    "Tack för din bokning hos Tolkar.se. Här är en sammanfattning:\n\n"
                    f"{booking_details}"
                    "Vi kontaktar dig när en tolk har accepterat uppdraget.\n\n"
                    "Hälsningar,\nTolkar.se"
                ),
            )
            send_email(
                ORDER_EMAIL,
                f"Ny bokning mottagen – ID {booking_id}",
                "En ny bokning har lagts.\n\n" + booking_details,
            )
            if session.get('user_id'):
                return redirect(url_for('home'))
            return redirect("https://www.tolkar.se/bekraftelse/")
        else:
            return "invalid request"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        tolkar_name = request.form.get('name', '').strip()
        tolkar_phone = request.form.get('phone', '').strip()
        tolkar_email = request.form.get('email', '').strip()
        if not tolkar_name or not tolkar_phone:
            return render_template('login.html', error='Namn och telefonnummer krävs.', prefill_email=tolkar_email, prefill_name=tolkar_name, prefill_phone=tolkar_phone)
        if password == PASSWORD:
            # Store the email in the session
            session['tolkar_email'] = tolkar_email
            session['tolkar_name'] = tolkar_name
            session['tolkar_phone'] = tolkar_phone
            session['authenticated'] = True
            return redirect(url_for('get_jobs'))
        else:
            return render_template('login.html', error='Felaktigt lösenord.', prefill_email=tolkar_email, prefill_name=tolkar_name, prefill_phone=tolkar_phone)
    return render_template('login.html', prefill_email='', prefill_name='', prefill_phone='')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            message = 'Ange en giltig e-postadress.'
        else:
            conn = sqlite3.connect('database.db')
            ensure_password_reset_table(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, email_salt FROM logins")
            user_id = None
            for row in cursor.fetchall():
                candidate_id, email_hash, email_salt = row
                if functions.verify_email(email, email_hash, email_salt):
                    user_id = candidate_id
                    break
            if user_id is not None:
                token = secrets.token_urlsafe(32)
                expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
                cursor.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
                cursor.execute(
                    "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
                    (user_id, token, expires_at),
                )
                conn.commit()
                reset_link = url_for('reset_password', token=token, _external=True)
                send_email(
                    email,
                    'Återställning av lösenord',
                    (
                        "Hej!\n\n"
                        "Vi har mottagit en begäran om att återställa ditt lösenord hos Tolkar.se."
                        " Klicka på länken nedan för att välja ett nytt lösenord. Länken är giltig i en timme.\n\n"
                        f"{reset_link}\n\n"
                        "Om du inte har begärt detta kan du ignorera meddelandet.\n\n"
                        "Hälsningar,\nTolkar.se"
                    ),
                )
            conn.commit()
            conn.close()
            message = 'Om ett konto finns registrerat skickas instruktioner till e-postadressen.'
        return render_template('forgot_password.html', message=message)
    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = sqlite3.connect('database.db')
    ensure_password_reset_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, expires_at FROM password_resets WHERE token = ?", (token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return render_template('reset_password.html', error='Ogiltig eller utgången länk.', token=None)
    user_id, expires_at_str = row
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
    except ValueError:
        cursor.execute("DELETE FROM password_resets WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return render_template('reset_password.html', error='Ogiltig eller utgången länk.', token=None)
    if datetime.utcnow() > expires_at:
        cursor.execute("DELETE FROM password_resets WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return render_template('reset_password.html', error='Ogiltig eller utgången länk.', token=None)
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        errors = []
        if password != confirm_password:
            errors.append('Lösenorden matchar inte.')
        if len(password) < 8:
            errors.append('Lösenordet måste vara minst 8 tecken.')
        if errors:
            conn.close()
            return render_template('reset_password.html', error=' '.join(errors), token=token)
        pwd_hash, salt = functions.hash_password(password)
        cursor.execute(
            "UPDATE logins SET password_hash = ?, salt = ? WHERE id = ?",
            (pwd_hash, salt, user_id),
        )
        cursor.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return render_template('reset_password.html', success=True)
    conn.close()
    return render_template('reset_password.html', token=token)

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
                    status TEXT NOT NULL DEFAULT "pending",
                    accepted_by_name TEXT,
                    accepted_by_phone TEXT)''')

    # Ensure the status column exists for older databases
    cursor.execute("PRAGMA table_info(bookings)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
    if 'accepted_by_name' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN accepted_by_name TEXT")
    if 'accepted_by_phone' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN accepted_by_phone TEXT")

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

    ensure_password_reset_table(conn)
    conn.commit()
    conn.close()

    # Ensure a default test account exists for easier manual testing
    functions.ensure_test_user()

    port = int(os.environ.get("PORT", 80))
    app.run(port=port, host="0.0.0.0", debug=False)
