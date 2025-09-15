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


def send_email(to_addresses, subject, body, bcc=None):
    """Send an email if SMTP settings are configured."""

    smtp_username = os.getenv("email")
    smtp_password = os.getenv("Email_password")
    smtp_server = os.getenv("smtp_server_address")
    smtp_port = os.getenv("smtp_port")

    if not all([smtp_username, smtp_password, smtp_server, smtp_port]):
        print("Email configuration missing; skipping email send.")
        return False

    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]
    to_addresses = [addr for addr in to_addresses if addr]
    if not to_addresses:
        return False

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = ", ".join(to_addresses)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    bcc_list = []
    if bcc:
        if isinstance(bcc, str):
            bcc_list = [bcc]
        else:
            bcc_list = [addr for addr in bcc if addr]
    if smtp_username not in to_addresses and smtp_username not in bcc_list:
        bcc_list.append(smtp_username)
    if bcc_list:
        msg['Bcc'] = ", ".join(bcc_list)

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            recipients = list(dict.fromkeys(to_addresses + bcc_list))
            server.sendmail(smtp_username, recipients, msg.as_string())
        return True
    except Exception as exc:
        print(f"Failed to send email: {exc}")
        return False


def format_booking_summary(booking):
    """Return a multiline summary string for a booking."""

    lines = [
        f"Boknings-ID: {booking.get('id', '')}",
        f"Namn: {booking['name']}",
        f"E-post: {booking['email']}",
        f"Telefon: {booking['phone']}",
        f"Språk: {booking['language']}",
        f"Starttid: {booking['time_start']}",
        f"Sluttid: {booking['time_end']}",
        f"Organisationsnummer: {booking.get('organization_number', '')}",
        f"Fakturaadress: {booking.get('billing_address', '')}",
        f"Faktura e-post: {booking.get('email_billing_address', '')}",
        f"Referens: {booking.get('reference', '')}",
    ]
    return "\n".join(lines)


@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('tolkar_email', None)
    session.pop('interpreter_name', None)
    session.pop('interpreter_phone', None)
    return redirect(url_for('home'))


@app.route('/')
def home():
    if session.get('user_id'):
        user_email = session.get('user_email')
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, language, time_start, time_end, status, interpreter_name, interpreter_phone
            FROM bookings WHERE email = ? ORDER BY time_start DESC
            """,
            (user_email,),
        )
        rows = cursor.fetchall()
        bookings = [
            {
                'id': row['id'],
                'language': row['language'],
                'time_start': row['time_start'],
                'time_end': row['time_end'],
                'status': row['status'],
                'interpreter_name': row['interpreter_name'] or '',
                'interpreter_phone': row['interpreter_phone'] or '',
            }
            for row in rows
        ]
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


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            return render_template('forgot_password.html', error='Ange en e-postadress.')

        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT id, email, email_salt FROM logins')
        user_row = None
        for row in cursor.fetchall():
            if functions.verify_email(email, row['email'], row['email_salt']):
                user_row = row
                break

        if user_row:
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            cursor.execute('DELETE FROM password_resets WHERE user_id = ?', (user_row['id'],))
            cursor.execute(
                'INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)',
                (user_row['id'], token, expires_at),
            )
            conn.commit()
            reset_link = url_for('reset_password', token=token, _external=True)
            body = (
                "Hej!\n\n"
                "Vi har fått en begäran om att återställa ditt lösenord på Tolkar.se.\n"
                "Använd länken nedan för att välja ett nytt lösenord. Länken är giltig i 1 timme.\n\n"
                f"{reset_link}\n\n"
                "Om du inte har begärt återställningen kan du ignorera detta mejl.\n\n"
                "Hälsningar,\nTolkar.se"
            )
            send_email([email], 'Återställ ditt lösenord', body)
        else:
            conn.commit()
        conn.close()
        message = 'Om adressen finns registrerad har ett mejl med återställningslänk skickats.'
        return render_template('forgot_password.html', message=message)
    return render_template('forgot_password.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    token = request.values.get('token', '').strip()
    if not token:
        return render_template('reset_password.html', error='Ogiltig eller förfallen länk.')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, expires_at FROM password_resets WHERE token = ?', (token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return render_template('reset_password.html', error='Ogiltig eller förfallen länk.')

    expires_at = None
    if row['expires_at']:
        try:
            expires_at = datetime.fromisoformat(row['expires_at'])
        except ValueError:
            expires_at = None
    if expires_at and expires_at < datetime.utcnow():
        cursor.execute('DELETE FROM password_resets WHERE token = ?', (token,))
        conn.commit()
        conn.close()
        return render_template('reset_password.html', error='Ogiltig eller förfallen länk.')

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not password:
            conn.close()
            return render_template('reset_password.html', token=token, error='Lösenordet får inte vara tomt.')
        if password != confirm_password:
            conn.close()
            return render_template('reset_password.html', token=token, error='Lösenorden matchar inte.')
        pwd_hash, salt = functions.hash_password(password)
        cursor.execute('UPDATE logins SET password_hash = ?, salt = ? WHERE id = ?', (pwd_hash, salt, row['user_id']))
        cursor.execute('DELETE FROM password_resets WHERE token = ?', (token,))
        conn.commit()
        conn.close()
        return render_template('reset_password_success.html')

    conn.close()
    return render_template('reset_password.html', token=token)

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
    # Check if the user is authenticated
    if not session.get('authenticated'):
        return render_template('login.html')

    interpreter_email = session.get('tolkar_email', '')
    interpreter_name = (session.get('interpreter_name') or '').strip()
    interpreter_phone = (session.get('interpreter_phone') or '').strip()
    if not interpreter_name or not interpreter_phone:
        return 'Tolkuppgifter saknas.', 400

    # Connect to the database
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Retrieve job information from the database
    cursor.execute("SELECT * FROM bookings WHERE id = ?", (job_id,))
    booking_row = cursor.fetchone()
    if booking_row is None:
        conn.close()
        return 'Bokningen kunde inte hittas.', 404
    if booking_row['status'] == 'accepted':
        conn.close()
        return 'Bokningen är redan accepterad.', 400

    cursor.execute(
        "UPDATE bookings SET status='accepted', interpreter_name=?, interpreter_phone=? WHERE id = ?",
        (interpreter_name, interpreter_phone, job_id),
    )
    conn.commit()
    conn.close()

    booking = {
        'id': booking_row['id'],
        'name': booking_row['name'],
        'email': booking_row['email'],
        'phone': booking_row['phone'],
        'language': booking_row['language'],
        'time_start': booking_row['time_start'],
        'time_end': booking_row['time_end'],
        'organization_number': booking_row['organization_number'] or '',
        'billing_address': booking_row['billing_address'] or '',
        'email_billing_address': booking_row['email_billing_address'] or '',
        'reference': booking_row['reference'] or '',
    }
    summary = format_booking_summary(booking)

    interpreter_subject = f"Bekräftelse på accepterat uppdrag #{job_id}"
    interpreter_body = (
        f"Hej {interpreter_name},\n\n"
        "Du har accepterat följande uppdrag:\n\n"
        f"{summary}\n\n"
        "Kontakta beställaren vid frågor eller ändringar.\n\n"
        "Hälsningar,\nTolkar.se"
    )
    send_email([interpreter_email], interpreter_subject, interpreter_body)

    user_subject = f"Din bokning har accepterats – ärende #{job_id}"
    user_body = (
        f"Hej {booking['name']},\n\n"
        f"Din bokning har accepterats av {interpreter_name} – {interpreter_phone}.\n"
        "Kontakta tolken direkt vid mindre ändringar eller avbokning (minst 24 timmar i förväg).\n\n"
        f"{summary}\n\n"
        "Tack för att du använder Tolkar.se!"
    )
    send_email([booking['email']], user_subject, user_body)

    accepted_subject = f"Bokning #{job_id} accepterad"
    accepted_body = (
        "Följande uppdrag har accepterats:\n\n"
        f"{summary}\n\n"
        f"Tolken: {interpreter_name} – {interpreter_phone} ({interpreter_email})"
    )
    send_email(['accepted@tolkar.se'], accepted_subject, accepted_body)

    return 'Job accepted and notifications sent'


@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if not session.get('user_id'):
        return redirect(url_for('user_login'))
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user_email = session.get('user_email')
    cursor.execute(
        "SELECT * FROM bookings WHERE id=? AND email=? AND status='pending'",
        (booking_id, user_email),
    )
    booking_row = cursor.fetchone()
    if not booking_row:
        conn.close()
        return redirect(url_for('home'))
    cursor.execute(
        "UPDATE bookings SET status='cancelled' WHERE id=? AND email=? AND status='pending'",
        (booking_id, user_email),
    )
    conn.commit()
    conn.close()

    booking = {
        'id': booking_row['id'],
        'name': booking_row['name'],
        'email': booking_row['email'],
        'phone': booking_row['phone'],
        'language': booking_row['language'],
        'time_start': booking_row['time_start'],
        'time_end': booking_row['time_end'],
        'organization_number': booking_row['organization_number'] or '',
        'billing_address': booking_row['billing_address'] or '',
        'email_billing_address': booking_row['email_billing_address'] or '',
        'reference': booking_row['reference'] or '',
    }
    summary = format_booking_summary(booking)
    cancel_subject = f"Bokning #{booking_id} avbruten"
    cancel_body = "Beställaren har avbrutit följande bokning:\n\n" + summary
    send_email(['cancelled@tolkar.se'], cancel_subject, cancel_body)
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
                """
                INSERT INTO bookings (
                    name, email, phone, language, time_start, time_end,
                    organization_number, billing_address, email_billing_address,
                    marking, avtalskund_marking, reference, status, interpreter_name, interpreter_phone
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

            booking = {
                'id': booking_id,
                'name': name,
                'email': email,
                'phone': phone,
                'language': language,
                'time_start': time_start,
                'time_end': time_end,
                'organization_number': organization_number or '',
                'billing_address': billing_address or '',
                'email_billing_address': email_billing_address or '',
                'reference': reference or '',
            }
            summary = format_booking_summary(booking)

            order_subject = f"Ny bokning #{booking_id}"
            order_body = "En ny bokning har skapats:\n\n" + summary
            send_email(['order@tolkar.se'], order_subject, order_body)

            user_subject = f"Tack för din bokning – ärende #{booking_id}"
            user_body = (
                f"Hej {name},\n\n"
                "Här är en kopia av din beställning på Tolkar.se.\n\n"
                f"{summary}\n\n"
                "Vi återkommer när en tolk har accepterat uppdraget.\n\n"
                "Hälsningar,\nTolkar.se"
            )
            send_email([email], user_subject, user_body)

            # Close the database connection
            conn.close()
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
            interpreter_name = request.form.get('name', '').strip()
            interpreter_phone = request.form.get('phone', '').strip()
            # Store the email in the session
            session['tolkar_email'] = request.form['email']
            if interpreter_name:
                session['interpreter_name'] = interpreter_name
            if interpreter_phone:
                session['interpreter_phone'] = interpreter_phone
            session.setdefault('interpreter_name', interpreter_name)
            session.setdefault('interpreter_phone', interpreter_phone)
            session['authenticated'] = True
            return redirect(url_for('get_jobs'))
        else:
            return render_template('login.html', error='Invalid password')
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
                    status TEXT NOT NULL DEFAULT "pending",
                    interpreter_name TEXT,
                    interpreter_phone TEXT)''')

    # Ensure the status column exists for older databases
    cursor.execute("PRAGMA table_info(bookings)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
    if 'interpreter_name' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN interpreter_name TEXT")
    if 'interpreter_phone' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN interpreter_phone TEXT")

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

    cursor.execute('''CREATE TABLE IF NOT EXISTS password_resets
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES logins(id) ON DELETE CASCADE)''')

    conn.commit()
    conn.close()

    # Ensure a default test account exists for easier manual testing
    functions.ensure_test_user()

    port = int(os.environ.get("PORT", 80))
    app.run(port=port, host="0.0.0.0", debug=False)
