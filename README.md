Tolkar.se - Translation Service Web Application
==============================================

This repository contains the source code for Tolkar.se, a web application that provides translation services. The application is built using Flask and uses SQLite for data storage. Users can submit translation job requests, and authenticated users can view and accept those requests. The application also sends confirmation emails to users and the translation company.

Table of Contents
-----------------
1. Installation
2. Features
3. Usage
4. Database
5. Routes
6. Authentication
7. Error Handling
8. License

# 1. Installation

Since this is a web application, you do not need to install it locally. You can access the live version of the application at https://www.tolkar.se/.

# 2. Features

- Users can create accounts or log in to reuse their contact information.
- Passwords are stored securely using salted hashes.
- Translation job requests can also be submitted as a one-time guest booking.
- Administrators can view the list of job requests.

# 3. Usage

Home page: Users can sign up, log in, or continue as guests from the landing page.

Submit Translation Job:

1. Fill out the required information in the form, including name, email, preferred language, start time, end time, and phone number.
2. Click "Submit" to proceed to the billing information form.

Billing Information Form:

1. Enter the billing information, including organization number, billing address, email billing address, marking, and reference.
2. Click "Submit" to complete the submission.

Viewing Job Requests (For Administrators):

1. Navigate to https://www.tolkar.se/login.
2. Enter the correct password to access the list of job requests.

# 4. Database

The application uses a SQLite database called `database.db` to store information. Two primary tables are used:

- **bookings**: Stores translation job details and billing information submitted by users.
- **logins**: Stores user account information with salted password hashes.

# 5. Routes

The application defines several routes for different functionalities:

- `/` : Home page with options to sign up, log in, or book as a guest.
- `/book` : Form for submitting translation job information.
- `/signup` : Create a new user account.
- `/user_login` : Log in to an existing account.
- `/user_logout` : Log out of the current account.
- `/submit` : Route for submitting translation job requests.
- `/billing` : Route for submitting billing information.
- `/login` : Admin authentication to access job requests.
- `/jobs` : View translation job requests (admin access).

# 6. Authentication

The application uses a simple password-based authentication mechanism to protect the /jobs route. The password is stored as an environment variable and is required to access the job request list.

# 7. Error Handling

The application handles various types of errors gracefully and provides appropriate error messages to users. Some common error handling routes are:

- /error: Route to display custom error messages with error codes.
- /error/404: Route to handle page-not-found errors (HTTP 404).

# 8. License

This project is licensed under the MIT License.

Note: This README file is meant for informational purposes only and should not be used for direct execution.
