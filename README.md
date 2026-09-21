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
- **Archive export** — download every document as a single zip for personal backup (previous file versions included)
- **Version history** — renewing or replacing a file keeps the old file and its expiry date; download or restore any earlier file from the document page
- **Trash** — deleting moves a document to the trash for 30 days (restore or delete permanently); shared links are revoked on delete
- **Custom reminders & snooze** — per-document reminder days (90/60/30/15/7/3/1) instead of the global schedule, and "remind me in 1/3/7 days" from the document or renew page
- **Auto-read on upload** *(optional)* — Claude reads the chosen file and pre-fills title, category, issue and expiry dates; only empty fields are filled and every suggestion is highlighted for review
- **Account page** — edit profile, change password, see 2FA status, sign out other devices
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

### Auto-read on upload (optional)

Add your key to `secrets.json` to turn it on (it is off when the key is missing):

```json
"ANTHROPIC_API_KEY": "sk-ant-...",
"ANTHROPIC_MODEL": "claude-opus-5",
"AI_EXTRACTION_HOURLY_LIMIT": 30
```

`ANTHROPIC_MODEL` and `AI_EXTRACTION_HOURLY_LIMIT` are optional (defaults shown). Uploaded PDFs/images (max 10 MB) are sent to the Claude API to be read, which the upload form tells the user. Available in the API as `POST /api/documents/extract/`.

### Sending expiry reminders

```bash
python manage.py send_expiry_reminders
```

Run this daily via cron (or any scheduler). It's idempotent — each (document, threshold) pair notifies once per cycle; renewing a document resets its reminder history. A document's own reminder days override the global `EXPIRY_REMINDER_DAYS`, and snoozed reminders fire from the same command.

### Emptying the trash

```bash
python manage.py purge_trash
```

Permanently deletes documents (and their files) trashed more than `TRASH_RETENTION_DAYS` (30) ago. Run it daily next to `send_expiry_reminders`.

---

## Project Structure

```
mybox/
├── PROJECT/          # Django settings
├── apps/
│   ├── core/          # Home page
│   ├── accounts/      # User model, login/register, profile, password change
│   ├── documents/     # Document, DocumentVersion, Category, Entity + services.py (renew, versions, trash, archive), extraction.py (Claude), purge_trash command
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
