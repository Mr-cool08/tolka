from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
from datetime import datetime
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import time
import stuff

load_dotenv()
app = Flask(__name__)
app.secret_key = stuff.generate_secret_key()

# Define the password for accessing the /jobs route
PASSWORD = os.getenv('password')
@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))
    
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/jobs') # The page to display the list of jobs
def get_jobs():
    if 'authenticated' not in session or session['authenticated'] == False:
        return render_template('login.html')

    # Connect to the database
    conn = sqlite3.connect('bookings.db')
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
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()

    # Retrieve job information from the database
    cursor.execute("SELECT name, email, phone, language, time_start, time_end FROM bookings WHERE id = ?", (job_id,))
    job_data = cursor.fetchone()

    # Insert the accepted job into the 'taken_bookings' table
    cursor.execute("INSERT INTO taken_bookings (name, email, phone, language, time_start, time_end) VALUES (?, ?, ?, ?, ?, ?)", (job_data[0], job_data[1], job_data[2], job_data[3], job_data[4], job_data[5]))
    conn.commit()

    # Delete the accepted job from the 'bookings' table
    cursor.execute("DELETE FROM bookings WHERE id = ?", (job_id,))
    conn.commit()

    # Close the database connection
    cursor.close()
    conn.close()
    def send_tolkar_email():
        # Making the email body and subject
        email_subject = f"Translation Application - Job ID: {job_id}"
        email_body = f"""
        Dear Sir/Madam,

        Here is the application for the job ID: {job_id}.

        Name: {job_data[0]}
        Email: {job_data[1]}
        Phone number: {job_data[2]}
        Preferred Language: {job_data[3]}
        Available Start Time: {job_data[4]}
        Available End Time: {job_data[5]}


        Please review the applicant's qualifications and credentials. If you require any further information or have any questions, please reach out to the applicant directly using the provided email address or phone number.
        
        
        Thank you for choosing our service. We appreciate your support.
        
        
        Best regards,
        The Tolkar Team"""   
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
        Dear Sir/Madam,

        Your application for the job ID: {job_id} has been accepted.
        
        If you haven't used our service, please contact us.
        Here is your information:   
        Name: {job_data[0]}
        Preferred Language: {job_data[3]}
        Available Start Time: {job_data[4]}
        Available End Time: {job_data[5]}
        
        
        Thank you for choosing our service. We appreciate your support.
        
        
        Best regards,
        The Tolkar Team"""
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
        time_end_str = request.form['endtime'] 
        phone = request.form['phone']
        time_start = datetime.strptime(time_start_str, '%Y-%m-%dT%H:%M')
        time_end = datetime.strptime(time_end_str, '%Y-%m-%dT%H:%M')
        time_start_str_trimmed = time_start.strftime('%Y-%m-%d %H:%M')# Extract date, hours, and minutes
        time_end_str_trimmed = time_end.strftime('%Y-%m-%d %H:%M')# Extract date, hours, and minutes

        
        



        # Check if the booking already exists in the database
        if stuff.booking_exists(name, email, phone, language, time_start, time_end):
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
    reference = request.form['reference']
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
            name = session.get('name')
            email = session.get('email')
            language = session.get('language')
            time_start = session.get('time_start')
            time_end = session.get('time_end')
            phone = session.get('phone')
            return render_template('confirmation.html', name=name, email=email, phone=phone, language=language, time_start=time_start, time_end=time_end, organization_number=organization_number, billing_address=billing_address, email_billing_address=email_billing_address, marking=marking, reference=reference)
        elif request.method == 'POST':
            organization_number = session.get('organization_number')
            billing_address = session.get('billing_address')
            email_billing_address = session.get('email_billing_address')
            marking = session.get('marking')
            reference = session.get('reference')
            name = session.get('name')
            email = session.get('email')
            language = session.get('language')
            time_start = session.get('time_start')
            time_end = session.get('time_end')
            phone = session.get('phone')
            conn = sqlite3.connect('bookings.db')
            cursor = conn.cursor()
            time.sleep(1)
            session['submitted'] = False
            return "Booking saved"
        else:
            return "invalid request"

        # Insert the booking details into the database, including the billing information
        cursor.execute(
            "INSERT INTO bookings (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, reference) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, email, phone, language, time_start, time_end, organization_number, billing_address, email_billing_address, marking, reference))
        conn.commit()

        # Close the database connection
        conn.close()

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
    return render_template('error.html', message='This was not what you were looking for.', error_name='404')
if __name__ == '__main__':
    # Connect to the database and create the 'bookings' table if it doesn't exist
    conn = sqlite3.connect('bookings.db')
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
                    billing_address TEXT NOT NULL,
                    email_billing_address TEXT NOT NULL,
                    marking TEXT,
                    reference TEXT)''')

    # Create the 'taken_bookings' table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS taken_bookings
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    language TEXT NOT NULL,
                    time_start TEXT NOT NULL,
                    time_end TEXT NOT NULL,
                    organization_number TEXT,
                    billing_address TEXT NOT NULL,
                    email_billing_address TEXT NOT NULL,
                    marking TEXT,
                    reference TEXT)''')

    conn.close()
    app.run(port=8080, host="0.0.0.0", debug=True)
