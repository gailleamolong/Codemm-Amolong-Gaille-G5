# Codemm

**Codemm: A Programming Practice, Auto-Checking, and Peer Review System for CIT-U IT and CS Students**

CSIT327 Information Management 2, section G5. Prepared by Gaille Arrofo Amolong.

Codemm organizes programming practice into learning tracks and coding activities. Students write
code in the browser and submit it, the system checks it against the activity's test cases, and
classmates review accepted solutions. This repository is the full-stack Django implementation
described in the Software Design Document (SDD).

| Part | Technology |
|---|---|
| Back end and front end | Django 5.2 with Django templates, HTML and CSS |
| Database | PostgreSQL hosted on Supabase (SQLite is not used) |
| Code execution (later phase) | Judge0 |

## Project Development 1: Account Feature

| Requirement | Where it lives |
|---|---|
| Registration with validation (required fields, email format, unique username, email and ID number, matching passwords) | `accounts/forms.py` `RegistrationForm`, `/register/` |
| Hashed passwords through Django's built-in authentication | `accounts/models.py` `User` (custom user model, `password_hash` column) |
| Login, logout and error messages | `/login/`, `/logout/` (POST only) |
| Protected pages redirect logged-out users to the login page | `@login_required` and `@role_required` in `accounts/decorators.py` |
| Role-based dashboards for Administrator, Instructor and Student | `/administrator/`, `/instructor/`, `/student/` |
| Users cannot open another role's dashboard by typing its URL | `role_required` returns 403 Forbidden |
| View and edit your own profile (name, email, ID number) | `/profile/`, `/profile/edit/` |
| Administrator assigns roles and deactivates accounts (SDD F-01) | User accounts table on `/administrator/` |

New sign-ups are students. The administrator promotes users to instructor or administrator.
The first administrator is created with `python manage.py createsuperuser`.

### `users` table (SDD data dictionary)

`user_id` PK, `username` UNIQUE, `email` UNIQUE, `password_hash`, `first_name`, `last_name`,
`id_number` UNIQUE NULL, `role` CHECK IN (`ADMIN`, `INSTRUCTOR`, `STUDENT`) DEFAULT `STUDENT`,
`is_active`, `created_at`. Django adds `is_staff`, `is_superuser` and `last_login` for its admin site.

## Setup

Requires Python 3.12 and a Supabase project (or any PostgreSQL 15+ database).

```bash
git clone https://github.com/gailleamolong/Codemm-Amolong-Gaille-G5.git
cd Codemm-Amolong-Gaille-G5
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

1. `DJANGO_SECRET_KEY`: any long random string, for example the output of
   `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
2. Database: in Supabase, open your project, click **Connect**, and copy the **Session pooler**
   values into `DB_HOST`, `DB_PORT`, `DB_USER` (looks like `postgres.<project-ref>`), `DB_NAME`
   (`postgres`) and `DB_PASSWORD` (your database password). Keep `DB_SSLMODE=require`.

Then create the tables and the first administrator, and start the server:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Tests

```bash
python manage.py test
```

The tests create a temporary test database, so run them against a local PostgreSQL database
rather than Supabase.

## Project structure

```
codemm/      settings (reads .env), root URLs
accounts/    custom user model, forms, views, role decorator, tests
templates/   base layout, account pages, role dashboards, 403 page
static/css/  stylesheet
```

## Security notes

- `.env`, `venv/` and `__pycache__/` are in `.gitignore`. Never commit database passwords or Supabase keys.
- Logout uses POST with a CSRF token. Every form is CSRF-protected.
- Deactivated accounts cannot log in.
