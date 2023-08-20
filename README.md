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

- Users can submit translation job requests through the web interface.
- Authenticated users can view the list of job requests and accept them.
- Confirmation emails are sent to users and the translation company upon job acceptance.

# 3. Usage

Home page: The home page displays general information about the translation service. 
This part is not a part of the application.

Submit Translation Job:

1. Click on the "Submit Job" button on the home page.
2. Fill out the required information in the form, including name, email, preferred language, start time, end time, and phone number.
3. Click "Submit" to proceed to the billing information form.

Billing Information Form:

1. Enter the billing information, including organization number, billing address, email billing address, marking, and reference.
2. Click "Submit" to complete the submission.

Viewing and Accepting Job Requests (For Authenticated Users):

1. Navigate to https://www.tolkar.se/login.
2. Enter the correct password to access the list of job requests.
3. Review the job requests and click the "Accept" button to accept a job.
4. Confirmation emails will be sent to the user and the translation company upon accepting the job.

# 4. Database

The application uses a SQLite database to store translation job and billing information. Two tables are used:

- bookings: This table stores the translation job details and billing information submitted by users.
- taken_bookings: This table stores the accepted translation jobs.

# 5. Routes

The application defines several routes for different functionalities:

- /: Home page route that displays general information about the translation service.
- /submit: Route for submitting translation job requests.
- /billing: Route for submitting billing information.
- /login: Route for authentication to access and accept translation job requests.
- /jobs: Route to view and accept translation job requests.
- /jobs/<int:job_id>: Route to accept a specific translation job request.

 6. Authentication

The application uses a simple password-based authentication mechanism to protect the /jobs route. The password is stored as an environment variable and is required to access the job request list.

# 7. Error Handling

The application handles various types of errors gracefully and provides appropriate error messages to users. Some common error handling routes are:

- /error: Route to display custom error messages with error codes.
- /error/404: Route to handle page-not-found errors (HTTP 404).

8. License

This project is licensed under the MIT License.

Note: This README file is meant for informational purposes only and should not be used for direct execution.
