# Codemm PD2 Report

Gaille Arrofo Amolong · CSIT327 Information Management 2 · Section G5

## First increment

Codemm is a programming practice, auto-checking, and peer review system for CIT-U IT and CS students. The first increment establishes the Django project and builds the Account Feature that later increments will use.

Django 5.2 handles the server and renders the pages with Django templates. The application uses PostgreSQL hosted on Supabase. Database credentials are supplied through a local `.env` file.

## Account Feature

- **Registration.** The form validates required fields, email format, unique usernames and email addresses, and matching passwords. Django hashes passwords through its built-in authentication system. Successful registration displays a confirmation, and invalid input shows field errors. New users start as students.
- **Login and logout.** Users sign in with a username or email and password. The login page reports invalid credentials, logout ends the session, and protected pages redirect signed-out visitors to login.
- **Role dashboards.** Administrators land on the user management dashboard and can assign roles or deactivate accounts. Instructors see their teaching workspace, and students see their learning workspace. A signed-in user who opens a dashboard for another role receives a 403 response.
- **Profile.** Users can view and update their own name, email, and ID number. Profile access uses the signed-in account, and profile editing cannot change the account's role.

## Verification and delivery

The delivered revision includes 27 automated test cases covering registration and password hashing, login and logout, access to protected pages, dashboard permissions, administrator actions, and profile updates.

The public repository is named `Codemm-Amolong-Gaille-G5`. It includes `requirements.txt` and ignores `.env`, `venv/`, and `__pycache__/`. The first increment spans 11 commits for project setup, account implementation, tests, documentation, and interface changes. [Delivered source](https://github.com/gailleamolong/Codemm-Amolong-Gaille-G5/tree/ff177cc0dd5b6b8709051ce270b26c0c50c27648)

GitHub records the first increment's final push to `main` on November 13, 2026 at 9:04 a.m. Philippine time. This report was prepared on November 20, 2026 and documents that delivered revision. [Repository activity](https://github.com/gailleamolong/Codemm-Amolong-Gaille-G5/activity)
