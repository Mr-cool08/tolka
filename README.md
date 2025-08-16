# Tolkar.se – Online Translation Booking

Use the production service at [tolkar.se](https://tolkar.se) or try the
development build at [tolka.onrender.com](https://tolka.onrender.com).

Tolkar.se is a web service that helps you book professional interpreters.  This
guide explains how to use the site as a visitor or registered user.

## How it works

1. **Create an account**  \
   Visit `/signup` and register with your name, email and phone number.  You can
   also add billing details for faster checkout and enable optional two‑factor
   authentication (2FA) for extra security.
2. **Sign in**  \
   Log in at `/user_login`.  If you enabled 2FA, you'll be asked for a one‑time
   code from your authenticator app.
3. **Book a translator**  \
   Go to `/booking` to choose languages, date, time and additional notes.  After
   submitting the form you will be guided through billing and receive a
   confirmation page.
4. **Track your bookings**  \
   The home page lists all your pending and accepted jobs.  You can cancel a
   pending booking before it is accepted.

When a translation company accepts your job request, a confirmation email is
sent to the address you provided during sign‑up.

## Frequently asked questions

**Do I need an account?**  \
Yes. Accounts let us contact you about your bookings and keep your information
secure.

**How do I delete my account?**  \
Use the “Remove my account” link on the home page. It will open an email draft
requesting account deletion.

**Is my data secure?**  \
Passwords are stored with PBKDF2 hashing and 2FA is available for extra
protection.

## For developers

If you want to run the site locally or contribute to development:

```bash
pip install -r requirements.txt
export password=<admin-password>
python website.py
```

Run tests with:

```bash
pytest
```

## License
This project is licensed under the MIT License.
