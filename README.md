# MyBox

A personal digital vault for storing your important documents (ID, contracts, insurance, certificates...) and automatically tracking their expiry dates before they catch you off guard.

---

## Tech Stack

| | |
|---|---|
| **Backend** | Django 5.2, Python 3.12, MySQL |
| **Frontend** | Bootstrap 5 RTL, Bootstrap Icons, installable PWA |
| **Font** | Cairo (Google Fonts) |

---

## Key Features

- **Document storage** — upload, categorize (fixed bilingual categories), link to an entity (self/family/vehicle/property/work), tag, and search
- **Expiry tracking** — automatic reminders 30/15/7/1 days before expiry (email + in-app notification), driven by the daily `send_expiry_reminders` management command
- **Renew** — update the expiry date and replace the file in one action, resetting the reminder schedule for the new cycle
- **Dashboard** — opens straight on "closest to expiry", not a random list
- **Archive export** — download every document as a single zip for personal backup
- **Installable as an app** — manifest + service worker (offline-capable app shell) with an install prompt on desktop, Android, and iOS

---

## Quick Start

```bash
# Activate the virtual environment
source .env/bin/activate

# Install requirements
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Create the superuser
python manage.py createsuperuser

# Run the server
python manage.py runserver
```

`secrets.json` (gitignored) holds `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, the MySQL `DATABASE` config, `EMAIL`, and `SITE_URL`. For local development, add your dev host/IP to `ALLOWED_HOSTS`; for production, set `DEBUG: false` and point `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` at the real domain.

### Sending expiry reminders

```bash
python manage.py send_expiry_reminders
```

Run this daily via cron (or any scheduler). It's idempotent — each (document, threshold) pair notifies once per cycle; renewing a document resets its reminder history.

---

## Project Structure

```
mybox/
├── PROJECT/          # Django settings
├── apps/
│   ├── core/          # Home page
│   ├── accounts/      # User model, login/register
│   ├── documents/     # Document, Category, Entity + services.py (renew, archive export)
│   └── notifications/ # In-app notifications, ReminderLog, send_expiry_reminders command
├── static/
│   ├── css/mybox.css
│   └── js/mybox.js
├── media/
├── secrets.json
└── manage.py
```

---

**Version:** 0.1 — **Status:** MVP scaffold
