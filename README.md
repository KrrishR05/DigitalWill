# Digital Will Platform

A secure Django web application that acts as a **digital will** — allowing users to store encrypted sensitive assets (passwords, documents, personal notes) and automatically release them to designated nominees after a period of inactivity.

### Live Deployment :
http://digitalwill.onrender.com/

---

## Features

- **Encrypted Asset Vault** — Passwords, documents, and notes stored with Fernet symmetric encryption
- **Nominee Management** — Assign trusted nominees to individual assets
- **Inactivity Detection** — Configurable inactivity threshold triggers the release workflow
- **OTP Verification** — Nominees receive a unique 6-digit OTP via email to verify identity before accessing assets
- **Final Message** — Leave a personal farewell message delivered to nominees on release
- **Activity Log** — Full audit trail of all important actions
- **Multi-section Settings** — Inactivity threshold, account info, password change, danger zone

---

## Tech Stack

- **Backend**: Django 4.2+
- **Encryption**: `cryptography` (Fernet symmetric encryption)
- **Email**: Gmail SMTP with App Password
- **Database**: SQLite (development) — swap to PostgreSQL for production
- **Environment**: `python-dotenv`

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-username/digital-will.git
cd digital-will
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux
```

Open `.env` and fill in **all** values:

```env
SECRET_KEY=your-random-secret-key-here
DEBUG=True
FERNET_KEY=your-fernet-key-here
EMAIL_HOST_USER=your_gmail@gmail.com
EMAIL_HOST_PASSWORD=your_16_char_app_password
```

**Generate a SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Generate a FERNET_KEY:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Get a Gmail App Password:**
Google Account > Security > 2-Step Verification > App Passwords

> **Important:** Each new deployment needs its **own** `FERNET_KEY`. If you share the key, encrypted data can be decrypted by others. If you change the key, existing encrypted data will become unreadable.

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Create a superuser (optional)

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000

---

## Environment Variables Reference

| Variable | Description | Required |
|---|---|---|
| `SECRET_KEY` | Django secret key (keep this private!) | Yes |
| `DEBUG` | `True` for development, `False` for production | Yes |
| `FERNET_KEY` | Fernet encryption key for asset data | Yes |
| `EMAIL_HOST_USER` | Gmail address for sending OTP emails | Yes |
| `EMAIL_HOST_PASSWORD` | Gmail App Password (16 chars, no spaces) | Yes |

---

## Project Structure

```
digital-will/
├── digital_will/        # Django project settings
│   ├── settings.py
│   └── urls.py
├── vault/               # Main app
│   ├── models.py        # UserProfile, DigitalAsset, Nominee, ReleaseRequest...
│   ├── views.py         # All main views
│   ├── otp_views.py     # OTP generation and nominee verification
│   ├── forms.py
│   ├── utils.py         # Encryption, decryption, activity logging
│   └── migrations/
├── templates/           # HTML templates
│   └── vault/
├── static/              # CSS, JS, images
├── .env.example         # Template for environment variables
├── requirements.txt
└── manage.py
```

---

## Security Notes

- `.env` is excluded from git via `.gitignore` — never commit it
- All asset content is encrypted at rest using Fernet symmetric encryption
- Nominee access is double-gated: OTP + server session token
- CSRF protection is enabled on all forms
- For **production**, set `DEBUG=False` and update `ALLOWED_HOSTS` in `settings.py`

---

## License

MIT License — feel free to use and modify.
