# Tolkar.se - Translation Service Web Application

Tolkar.se is a Flask-based web application for managing translation bookings.
Visitors can submit translation jobs and registered users can review and accept
pending jobs.  The project uses SQLite for storage and includes optional
two-factor authentication for user logins.

## Features
- Submit translation job requests with billing details
- User registration and login with PBKDF2-hashed passwords and emails
- Optional TOTP-based two-factor authentication
- View and accept pending jobs after authentication
- `/health` endpoint for deployment health checks

## Installation
1. Clone the repository and create a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set required environment variables:
   - `password` – shared secret to access job management routes

## Usage
Run the application locally:
```bash
export password=<your-password>
python website.py
```
The site will be available at <http://localhost:5000/>.

## Testing
Execute the test suite with:
```bash
pytest
```

## Database
SQLite database `database.db` contains:
- `bookings`: translation job details and billing information
- `logins`: user accounts and optional TOTP secrets

## Routes
- `/` – home page and user bookings
- `/booking` – submit a translation request
- `/signup` – create a user account
- `/user_login` – user login
- `/two_factor` – verify 2FA token
- `/jobs` – list pending jobs (requires `password`)
- `/jobs/<id>` – accept a job
- `/health` – health check endpoint

## License
This project is licensed under the MIT License.
