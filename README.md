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
| Code execution | Judge0 (off until `JUDGE0_URL` is set) |

## Core feature: Learning tracks

Instructors organize practice into learning tracks of coding activities, each with its own test
cases, and students enroll to work through them. This follows SDD features F-02 (tracks),
F-03 (activities), F-04 (test cases), F-05 (enrollment), F-06 and F-07 (code editor, Run,
Submit and automatic checking), F-08 (search and filtering), F-09 (peer reviews), F-10
(reflections), F-11 and F-12 (progress report and pass-rate summary) and F-13 (CSV export).

| Role | What they can do |
|---|---|
| Instructor | Create, view, edit and delete their own tracks, the coding activities inside them, and each activity's test cases (visible samples or hidden). Publish tracks and activities. See who is enrolled. See every submission on their activities, with full test results, and filter by student and verdict. Search their tracks and filter by status; filter a track's activities. Open each track's student progress report and activity pass-rate summary and download both as CSV. |
| Student | Search and filter published tracks, enroll, drop and rejoin. Open a track's published activities while enrolled and see the sample test cases (never the hidden ones). Write code, Run it with their own input, and Submit it to be checked against every test case. See the verdict, score and results (hidden tests show only pass or fail). Review classmates' accepted solutions, write a reflection on each attempt, and follow their progress under My progress. Enrolled tracks and recent attempts show on the dashboard. |
| Administrator | Manage user accounts and roles. |

Tables (from the SDD data dictionary): `learning_tracks`, `activities`, `test_cases`, `enrollments`,
`submissions`, `test_results`, `peer_reviews`, `reflections`.
The database enforces a unique track title per instructor, a unique activity title per track,
a unique test case number per activity with at least 1 point, one enrollment per student per
track, and the allowed difficulty, language, time limit (500 to 10,000 ms) and attempt limit
(1 to 50). An activity can only be published once it has a test case. Instructors can only reach
their own tracks; other instructors get 404 and students get 403.

Submissions follow the SDD rules: an active enrollment, the attempt limit, the due date, 1 to
65,535 characters of code, a verdict of Accepted only when every test passes, and a score weighted
by test case points. Tracks, activities and test cases that have submissions can't be deleted.

### Code checking (Judge0)

Code runs on [Judge0](https://judge0.com), never on the Codemm server. It is off by default:
with `JUDGE0_URL` empty in `.env`, Run and Submit are closed and no code leaves the server.
Student code is only sent over HTTPS (plain `http://` is refused except for a Judge0 on this
computer), and Judge0 replies larger than 1 MB are rejected.
To turn it on, set `JUDGE0_URL` to a Judge0 server, for example the public
`https://ce.judge0.com` for demos (rate-limited and run by a third party, so don't put private
data in test cases) or your own Judge0 on a Linux server. The automated tests replace Judge0
with a stand-in and never call the network.

Peer reviews follow BR-17 to BR-19 (accepted solutions only, classmates in the same track, never
your own, one review each, ratings 1 to 5, a comment of at least 20 characters). Reflections follow
BR-20 (one per submission, by its author, at least 50 characters).

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

The tests create and then delete a temporary database. Supabase's connection pooler doesn't
allow that, so the tests use a separate local PostgreSQL server while the app keeps using Supabase.

1. Start a throwaway PostgreSQL server (needs Docker):

   ```bash
   docker run -d --name codemm-test-db -e POSTGRES_USER=codemm -e POSTGRES_PASSWORD=codemm \
     -e POSTGRES_DB=codemm -p 127.0.0.1:5433:5432 postgres:17-alpine
   ```

2. Copy the `TEST_DB_*` lines from `.env.example` into your `.env`.
3. Run the tests:

   ```bash
   python manage.py test
   ```

   Expected result: `Ran 124 tests ... OK`. Judge0 is replaced with a stand-in, so the tests never
   call the network.

4. Remove the test server when you're done: `docker rm -f codemm-test-db`.

Test files: `accounts/tests.py`, `tracks/tests.py`, `reviews/tests.py`, `reports/tests.py`.

## Project structure

```
codemm/      settings (reads .env), root URLs
accounts/    custom user model, sign-up and profile views, tests
dashboard/   role dashboards, RoleRequiredMixin, user role editing
tracks/      learning tracks, activities, test cases, enrollments, search, submissions and Judge0 checking, tests
reviews/     peer reviews and reflections, tests
reports/     progress report, pass-rate summary and CSV export, tests
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
- After 5 failed logins for one username from one address, login is locked for 15 minutes.
- Each student can Run or Submit at most 10 times a minute, so nobody can flood Judge0.
