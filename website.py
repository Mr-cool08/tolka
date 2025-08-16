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
    session.pop('user_id', None)
    return redirect(url_for('home'))
    
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/booking')
def index():
    user_name = user_email = user_phone = ''
    if session.get('user_id'):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name, email, phone FROM logins WHERE id = ?', (session['user_id'],))
        row = cursor.fetchone()
        conn.close()
        if row:
            user_name, user_email, user_phone = row
    return render_template('index.html', combo_list=languages, user_name=user_name, user_email=user_email, user_phone=user_phone)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        pwd_hash, salt = functions.hash_password(password)
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logins (name, email, phone, password_hash, salt) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, pwd_hash, salt),
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        session['user_id'] = user_id
        return redirect(url_for('index'))
    return render_template('signup.html')


@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash, salt FROM logins WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        if row and functions.verify_password(password, row[1], row[2]):
            session['user_id'] = row[0]
            return redirect(url_for('index'))
        return render_template('user_login.html', error='Invalid credentials')
    return render_template('user_login.html')

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

@app.route('/jobs/<int:job_id>', methods=['POST']) # The action to accept the job
def accept_job(job_id):
    print(job_id)
    # Check if the user is authenticated
    if 'authenticated' not in session:
        return render_template('login.html')

    # Connect to the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Retrieve job information from the database
    cursor.execute("SELECT name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, avtalskund_marking, reference FROM bookings WHERE id = ?", (job_id,))
    job_data = cursor.fetchone()

    # Remove the accepted job from the 'bookings' table
    cursor.execute("DELETE FROM bookings WHERE id = ?", (job_id,))
    conn.commit()

    # Close the database connection
    cursor.close()
    conn.close()
    def send_tolkar_email():
        # Making the email body and subject
        email_subject = f"Translation Application - Job ID: {job_id}"
        email_body = f"""
        Kära Herr/Fru,

        Här är bekräftelsen för jobb-ID: {job_id}.

        Namn: {job_data[0]}
        E-post: {job_data[1]}
        Telefonnummer: {job_data[2]}
        Önskat språk: {job_data[3]}
        Starttid: {job_data[4]}
        Sluttid: {job_data[5]}

        Vänligen granska sökandens kvalifikationer och referenser. Om du behöver ytterligare information eller har några frågor, vänligen kontakta sökanden direkt via det angivna e-postadressen eller telefonnumret.

        Tack för att du valde vår tjänst. Vi uppskattar ditt stöd.

        Med vänliga hälsningar,
        Tolkar-teamet"""   
        # Prepare email message
        msg = MIMEMultipart()
        msg['From'] = os.getenv("email") # Retrieving the email from the session
        msg['To'] = session.get('tolkar_email', '')  # Retrieve the email from the session
        msg['Subject'] = email_subject # Getting the subject
        msg.attach(MIMEText(email_body, 'plain'))
        smtp_username = os.getenv("email")# Getting the email for the sender
        smtp_password = os.getenv('Email_password') # Getting the password for the sender
        msg['Bcc'] = smtp_username # Adding the secret email to send to self.
        smtp_server = os.getenv("smpt_server_address")# Connect to the SMTP server
        smtp_port = os.getenv("smtp_port")# Connect to the SMTP server
        recipient_email = session.get('tolkar_email', '')  # Retrieve the recipient email from the session

        with smtplib.SMTP(smtp_server, smtp_port) as server: # Sending the email
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_username, [recipient_email, msg['Bcc']], msg.as_string())
            
            
            
    def send_user_email():
        # Making the email body and subject
        email_subject = f"Translation Application - Job ID: {job_id}"
        email_body = f"""
                Kära Herr/Fru,

        Din ansökan för jobb-ID: {job_id} har blivit accepterad.
        
        Om du inte har använt vår tjänst, vänligen kontakta oss.
        Här är din information:   
        Namn: {job_data[0]}
        Önskat språk: {job_data[3]}
        Starttid: {job_data[4]}
        Sluttid: {job_data[5]}
        
        
        Tack för att du valde vår tjänst. Vi uppskattar ditt stöd.
        
        
        Med vänliga hälsningar,
        Tolkar-teamet"""
        msg = MIMEMultipart()
        msg['From'] = os.getenv("email") # Retrieving the email from the .env file
        msg['To'] = job_data[1] # Retrieving the email from the database
        msg['Subject'] = email_subject # Getting the subject
        msg.attach(MIMEText(email_body, 'plain')) 
        smtp_username = os.getenv("email")# Getting the email for the sender
        smtp_password = os.getenv('Email_password')# Getting the password for the sender
        msg['Bcc'] = smtp_username # Adding the secret email to send to self.
        smtp_server = os.getenv("smpt_server_address")# Connect to the SMTP server
        smtp_port = os.getenv("smtp_port")# Connect to the SMTP server
        recipient_email = job_data[1] # Retrieve the recipient email from the database
        with smtplib.SMTP(smtp_server, smtp_port) as server: # Sending the email
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_username, [recipient_email, msg['Bcc']], msg.as_string()) #Sending the mail
    send_tolkar_email() # Running the function to send to the translation company
    send_user_email() # Running the function to send to the user
    return 'Job accepted and email sent'

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
            return redirect(url_for('index')) 
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
        return redirect(url_for('index'))
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
                    reference TEXT)''')

    # Create the 'logins' table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS logins
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    phone TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL)''')

    conn.close()
    app.run(port=8080, host="0.0.0.0", debug=True)
