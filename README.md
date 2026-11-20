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

## Core feature: Learning tracks (Project Development 2)

Instructors organize practice into learning tracks, and students enroll to work through them.
This follows SDD features F-02 (tracks), F-03 (activities) and F-05 (enrollment).

| Role | What they can do |
|---|---|
| Instructor | Create, view, edit and delete their own tracks and the coding activities inside them. Publish a track to open it to students. See who is enrolled. |
| Student | Browse published tracks, enroll, drop and rejoin. Open a track's published activities while enrolled. Enrolled tracks show on the dashboard. |
| Administrator | Manage user accounts and roles. |

Tables (from the SDD data dictionary): `learning_tracks`, `activities`, `enrollments`.
The database enforces a unique track title per instructor, a unique activity title per track,
one enrollment per student per track, and the allowed difficulty, language, time limit
(500 to 10,000 ms) and attempt limit (1 to 50). Instructors can only reach their own tracks;
other instructors get 404 and students get 403.

## Account Feature (Project Development 1)

| Requirement | Where it lives |
|---|---|
| Registration with validation and hashed passwords | `accounts/forms.py` `SignUpForm`, `/accounts/signup/` |
| Login and logout | Django's built-in `/accounts/login/` and `/accounts/logout/` |
| Role dashboards that block other roles | `dashboard/views.py` `RoleRequiredMixin`: `/student/`, `/instructor/`, `/administrator/` |
| View and edit your own profile | `/accounts/profile/`, `/accounts/profile/edit/` |
| Administrator assigns roles and deactivates accounts | `/administrator/` |

New sign-ups are students. The first administrator is created with `python manage.py createsuperuser`.

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
accounts/    custom user model, sign-up and profile views, tests
dashboard/   role dashboards, RoleRequiredMixin, user role editing
tracks/      learning tracks, activities and enrollments (core feature), tests
templates/   pages for each app
static/      stylesheet, Codemm logo and fonts
```

## Branches

`main` holds stable releases, `develop` integrates features, and each feature has its own
`feature/<name>` branch merged into `develop` through a pull request.

## Security notes

- `.env`, `venv/` and `__pycache__/` are in `.gitignore`. Never commit database passwords or Supabase keys.
- Logout uses POST with a CSRF token. Every form is CSRF-protected.
- Deactivated accounts cannot log in.
