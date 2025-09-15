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
import hashlib

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

ORDER_INBOX = "order@tolkar.se"
ACCEPTED_INBOX = "accepted@tolkar.se"
CANCELLED_INBOX = "cancelled@tolkar.se"


def send_email(subject, body, to_addresses, bcc=None):
    """Send an email and fail silently if configuration is missing."""

    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]
    if isinstance(bcc, str):
        bcc = [bcc]

    to_addresses = [addr for addr in (to_addresses or []) if addr]
    bcc = [addr for addr in (bcc or []) if addr]

    smtp_username = os.getenv("email")
    smtp_password = os.getenv('Email_password')
    smtp_server = os.getenv("smtp_server_address")
    smtp_port = os.getenv("smtp_port")

    if not to_addresses or not smtp_username or not smtp_password or not smtp_server or not smtp_port:
        return False

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = ", ".join(to_addresses)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    if bcc:
        msg['Bcc'] = ", ".join(bcc)

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_username, to_addresses + bcc, msg.as_string())
        return True
    except Exception as exc:  # pragma: no cover - avoid failing hard in prod
        print(f"Failed to send email: {exc}")
        return False


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
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, language, time_start, time_end, status, accepted_by_name, accepted_by_phone
            FROM bookings
            WHERE email = ?
            ORDER BY time_start DESC
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
    if 'authenticated' not in session:
        return render_template('login.html'), 401

    data = request.get_json(silent=True) or {}
    translator_name = data.get('translator_name', '').strip()
    translator_phone = data.get('translator_phone', '').strip()

    if not translator_name or not translator_phone:
        return {"error": "Translator name and phone are required."}, 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT name, email, phone, language, time_start, time_end, organization_number,
               billing_address, email_billing_address, marking, avtalskund_marking, reference, status
        FROM bookings WHERE id = ?
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Booking not found."}, 404

    (*customer_data, status) = row
    if status != 'pending':
        conn.close()
        return {"error": "Booking already processed."}, 400

    cursor.execute(
        """
        UPDATE bookings
        SET status='accepted', accepted_by_name=?, accepted_by_phone=?
        WHERE id=? AND status='pending'
        """,
        (translator_name, translator_phone, job_id),
    )
    conn.commit()
    conn.close()

    job_info = {
        "name": customer_data[0],
        "email": customer_data[1],
        "phone": customer_data[2],
        "language": customer_data[3],
        "time_start": customer_data[4],
        "time_end": customer_data[5],
        "organization_number": customer_data[6],
        "billing_address": customer_data[7],
        "email_billing_address": customer_data[8],
        "marking": customer_data[9],
        "avtalskund_marking": customer_data[10],
        "reference": customer_data[11],
    }

    translator_email = session.get('tolkar_email', '')
    subject = f"Bokning #{job_id} accepterad"

    translator_body = f"""
Hej,

Du har accepterat bokningen #{job_id}.

Kund: {job_info['name']} ({job_info['email']}, {job_info['phone']})
Språk: {job_info['language']}
Starttid: {job_info['time_start']}
Sluttid: {job_info['time_end']}

Tolk: {translator_name} – {translator_phone}

Kom ihåg att kontakta kunden vid eventuella ändringar.

Vänliga hälsningar,
Tolkar.se
"""
    user_body = f"""
Hej {job_info['name']},

Din bokning #{job_id} har accepterats av {translator_name} – {translator_phone}.

Du kan kontakta tolken direkt vid ändringar eller avbokning. Enligt villkoren behöver avbokning ske minst 24 timmar innan start.

Detaljer:
Språk: {job_info['language']}
Starttid: {job_info['time_start']}
Sluttid: {job_info['time_end']}

Tack för att du använder Tolkar.se!
"""
    admin_body = f"""
Bokning #{job_id} har accepterats.

Kund: {job_info['name']} ({job_info['email']}, {job_info['phone']})
Språk: {job_info['language']}
Starttid: {job_info['time_start']}
Sluttid: {job_info['time_end']}
Tolk: {translator_name} – {translator_phone}
"""

    send_email(subject, translator_body, translator_email)
    send_email(subject, user_body, job_info['email'])
    send_email(subject, admin_body, ACCEPTED_INBOX)

    return {"message": "Job accepted"}


@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if not session.get('user_id'):
        return redirect(url_for('user_login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    user_email = session.get('user_email')
    cursor.execute(
        "SELECT name, language, time_start, time_end, status, phone FROM bookings WHERE id=? AND email=?",
        (booking_id, user_email),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return redirect(url_for('home'))

    name, language, time_start, time_end, status, phone = row
    if status != 'pending':
        conn.close()
        return redirect(url_for('home'))

    cursor.execute(
        "UPDATE bookings SET status='cancelled' WHERE id=? AND email=? AND status='pending'",
        (booking_id, user_email),
    )
    conn.commit()
    conn.close()

    subject = f"Bokning #{booking_id} avbokad"
    body = f"""
Hej {name},

Din bokning #{booking_id} för {language} den {time_start} - {time_end} har avbokats.

Om detta skedde av misstag kan du göra en ny bokning via Tolkar.se.
"""
    admin_body = f"""
Bokning #{booking_id} har avbokats av kunden.

Kund: {name} ({user_email}, {phone})
Språk: {language}
Starttid: {time_start}
Sluttid: {time_end}
"""

    send_email(subject, body, user_email)
    send_email(subject, admin_body, CANCELLED_INBOX)
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
            cursor.execute(
                "INSERT INTO bookings (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, avtalskund_marking, reference, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                ),
            )
            booking_id = cursor.lastrowid
            conn.commit()

            # Close the database connection
            conn.close()

            subject = f"Bekräftelse bokning #{booking_id}"
            body = f"""
Hej {name},

Tack för din bokning hos Tolkar.se. Här är en sammanställning av uppdraget:

Språk: {language}
Starttid: {time_start}
Sluttid: {time_end}
Telefon: {phone}

Du kan avboka via ditt konto så länge ingen tolk har accepterat uppdraget. När en tolk är bokad kontaktar du tolken direkt.

Vi återkommer så snart någon accepterar uppdraget.
"""
            admin_body = f"""
Ny bokning #{booking_id} har skapats.

Kund: {name} ({email}, {phone})
Språk: {language}
Starttid: {time_start}
Sluttid: {time_end}
Referens: {reference or '-'}
"""

            send_email(subject, body, email)
            send_email(f"Ny bokning #{booking_id}", admin_body, ORDER_INBOX)
            time.sleep(1)
            session['submitted'] = False
            if session.get('user_id'):
                return redirect(url_for('home'))
            return redirect("https://www.tolkar.se/bekraftelse/")
        else:
            return "invalid request"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == PASSWORD:
            # Store the email in the session
            session['tolkar_email'] = request.form['email']
            session['authenticated'] = True
            return redirect(url_for('get_jobs'))
        else:
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email_input = request.form['email']
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, email, email_salt FROM logins')
        user_row = None
        for user_id, email_hash, email_salt in cursor.fetchall():
            if functions.verify_email(email_input, email_hash, email_salt):
                user_row = (user_id, email_input)
                break

        if user_row:
            user_id, plain_email = user_row
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expiry = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            cursor.execute(
                'UPDATE logins SET reset_token_hash=?, reset_token_expiry=? WHERE id=?',
                (token_hash, expiry, user_id),
            )
            conn.commit()
            reset_path = url_for('reset_password', token=token)
            reset_link = request.url_root.rstrip('/') + reset_path
            body = f"""
Hej,

Vi har tagit emot en begäran om att återställa ditt lösenord på Tolkar.se.

Använd länken nedan för att ange ett nytt lösenord. Länken är giltig i en timme.
{reset_link}

Om du inte har begärt återställning kan du ignorera detta meddelande.
"""
            send_email('Återställ ditt lösenord', body, plain_email)

        conn.close()
        return render_template('forgot_password.html', submitted=True)

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, reset_token_expiry FROM logins WHERE reset_token_hash = ?',
        (token_hash,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return render_template('reset_password.html', invalid=True), 404

    user_id, expiry = row
    try:
        expiry_dt = datetime.fromisoformat(expiry)
    except (TypeError, ValueError):
        expiry_dt = datetime.utcnow() - timedelta(seconds=1)

    if datetime.utcnow() > expiry_dt:
        cursor.execute(
            'UPDATE logins SET reset_token_hash=NULL, reset_token_expiry=NULL WHERE id=?',
            (user_id,),
        )
        conn.commit()
        conn.close()
        return render_template('reset_password.html', expired=True), 400

    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            conn.close()
            return render_template('reset_password.html', token=token, error='Lösenorden matchar inte.', token_valid=True)

        pwd_hash, pwd_salt = functions.hash_password(password)
        cursor.execute(
            'UPDATE logins SET password_hash=?, salt=?, reset_token_hash=NULL, reset_token_expiry=NULL WHERE id=?',
            (pwd_hash, pwd_salt, user_id),
        )
        conn.commit()
        conn.close()
        return render_template('reset_password.html', success=True)

    conn.close()
    return render_template('reset_password.html', token=token, token_valid=True)

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
                    accepted_by_name TEXT,
                    accepted_by_phone TEXT,
                    status TEXT NOT NULL DEFAULT "pending")''')

    # Ensure the status column exists for older databases
    cursor.execute("PRAGMA table_info(bookings)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
    for col in ('accepted_by_name', 'accepted_by_phone'):
        if col not in columns:
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col} TEXT")

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
                    totp_secret TEXT,
                    reset_token_hash TEXT,
                    reset_token_expiry TEXT)''')

    cursor.execute("PRAGMA table_info(logins)")
    login_columns = [info[1] for info in cursor.fetchall()]
    extra_cols = [
        'organization_number',
        'billing_address',
        'email_billing_address',
        'email_salt',
        'totp_secret',
        'reset_token_hash',
        'reset_token_expiry',
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
