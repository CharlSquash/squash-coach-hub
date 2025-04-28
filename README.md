Markdown

# Squash Coach Hub (Displays as "SquashSync" on Frontend)

## Description

Squash Coach Hub (displayed as **SquashSync** on the frontend) is a Django-based web application designed to assist squash coaches, particularly those working with high school players (leveraging sport psychology principles), in planning training sessions, tracking player performance metrics, managing assessments and feedback, and visualizing progress. It aims to provide a centralized platform for effective coaching and player development. This project currently links externally to the "Shot IQ" application.

## Features

* **Session Planning:** Create and manage training sessions (date, time, duration, school group, coaches).
* **Time Blocks:** Divide sessions into time blocks (duration, courts, rotation interval, focus).
* **Activity Management:** Define reusable drills (with player counts) or add custom activities, assigning them to courts within time blocks.
* **Attendance Tracking:** Mark player attendance per session via the Session Detail page.
* **School Group Attendance Link:** Store an external URL (e.g., Google Form) per School Group; display a direct link on the associated Session Detail page for easy access.
* **Live Session View:** Dynamic view showing current/next block, player court assignments (with automatic rotation), activities, time simulation, and rotation alerts. Includes a link back to the Session Plan.
* **Player Profiles:** Centralized view per player: details, attendance, session assessments, recorded metrics (sprints, volleys, drives), match results, performance charts, coach feedback history. Includes a "Back to Players List" link.
* **Coach Feedback:** Ability for coaches to add structured feedback (strengths, development areas, focus, notes) per player directly from the player's profile, viewable chronologically on the profile (optionally linked to a session).
* **Metric & Match Tracking:** Forms to log results for court sprints, consecutive volleys (FH/BH), consecutive backwall drives (FH/BH), and match outcomes (practice/competitive).
* **Session Assessments:** Record coach assessments on player attributes (effort, focus, resilience, composure, decision-making).
* **Player List & Filtering:** Dedicated page listing active players, allowing filtering by School Group and searching by player name (first or last). Includes a "Back to Home" link.
* **Image Optimization:** Player profile photos are automatically resized (max 300x300, preserving aspect ratio) and corrected for orientation upon upload using Pillow via the `Player.save()` method.
* **Data Visualization:** Basic line charts on player profiles showing metric progress over time (using Chart.js).
* **Manual Court Assignment:** Visually drag-and-drop players between courts on Session Detail page; assignments persist and reflect in Live Session view. Option to clear manual assignments per block.
* **One-Page Session Plan:** Generate a simplified, mobile-friendly, shareable view of a session's schedule and activities (via Web Share API). Includes a link back to the full Session Plan.
* **Homepage Dashboard:** Displays the site name "SquashSync" with a custom banner image. Shows cards for Upcoming Sessions, recently completed Sessions (as Feedback Reminders), Player Management, and Tools & Resources (Shot IQ, Admin site). Includes a link back to Home.
* **Django Admin Customization:** Enhanced admin for managing drills, players (group filtering), sessions (inline blocks, attendees, auto-populating attendees from group on save), School Groups (including Attendance Form URL).

## Technology Stack

* **Backend:** Python 3.13, Django 5.2
* **Database:**
    * Local Development: SQLite3 (`db.sqlite3`)
    * Production (PythonAnywhere): MySQL (Configured via Environment Variable)
* **Frontend:** HTML5, CSS3 (custom `style.css` + inline styles), JavaScript (ES6+)
* **Environment Variables:** `python-dotenv` (manages settings via `.env` files)
* **Database URL Parsing:** `dj-database-url` (parses `DATABASE_URL` env var)
* **Image Processing:** `Pillow` (for `ImageField` and upload optimization)
* **Database Driver (Production):** `mysqlclient` (or `mysql-connector-python`)
* **JavaScript Libraries:**
    * Chart.js (^4)
    * Moment.js (^2.29.4) & chartjs-adapter-moment (^1.1.1) (local vendor)
    * SortableJS (^1.15.2) (CDN)
    * Bootstrap Icons (CDN)
* **Version Control:** Git / GitHub

## Project Structure

squash-coach-hub/
|-- .git/
|-- .gitignore             # Specifies ignored files (MUST include .env, venv, db.sqlite3, mediafiles, staticfiles)
|-- .env                   # Environment variables (local OR production version - NOT IN GIT)
|-- coach_project/         # Django project config
|   |-- settings.py        # Reads settings from environment variables via dotenv
|   |-- urls.py            # Project-level URL routing
|   |-- wsgi.py            # WSGI entry point
|   |-- ...
|-- planning/              # Main Django app
|   |-- migrations/        # Database migration files
|   |-- static/planning/   # App-specific static files (style.css, images/, vendor/)
|   |-- templates/planning/ # HTML templates (homepage, session_detail, player_profile, forms, etc.)
|   |-- init.py
|   |-- admin.py           # Custom ModelAdmin classes (SessionAdmin, SchoolGroupAdmin)
|   |-- apps.py
|   |-- forms.py           # CoachFeedbackForm, etc.
|   |-- models.py          # Player, Session, SchoolGroup, CoachFeedback, etc. (with relevant methods)
|   |-- tests.py
|   |-- urls.py            # App-specific URLs (planning namespace)
|   |-- views.py           # View functions (homepage_view, player_profile, add_coach_feedback, etc.)
|
|-- mediafiles/            # User-uploaded files (e.g., player photos) - GITIGNORED
|-- staticfiles/           # Target for 'collectstatic' on PA (defined by STATIC_ROOT env var) - GITIGNORED
|-- venv/                  # Local virtual environment - GITIGNORED
|-- db.sqlite3             # Local SQLite database - GITIGNORED
|-- manage.py              # Django management script
|-- requirements.txt       # Python package dependencies
|-- README.md              # This file


## Key Files Overview

* **`coach_project/settings.py`**: Reads configuration from environment variables (`.env`). Defines base settings.
* **`.env`**: Stores environment-specific variables (DB, SECRET_KEY, DEBUG, HOSTS, STATIC_ROOT etc.). **Crucially ignored by Git.** One version exists locally, a different one (with production values) exists in the project root on PythonAnywhere.
* **`.gitignore`**: Ensures sensitive files (`.env`), local artifacts (`db.sqlite3`, `venv`, `__pycache__`), user uploads (`mediafiles`), and collected static files (`staticfiles`) are not committed to Git.
* **`planning/models.py`**: Defines database models. `Player.save` includes image optimization. `Session` includes `@property` for start/end datetimes. `SchoolGroup` includes `attendance_form_url`. `CoachFeedback` model added.
* **`planning/views.py`**: Handles request logic. `homepage_view` queries upcoming and recently finished sessions. `add_coach_feedback` handles the feedback form. `player_profile` displays player data including feedback.
* **`planning/urls.py`**: Defines URL patterns for the `planning` app, including player profiles, session views, feedback forms. Uses `app_name = 'planning'`.
* **`planning/admin.py`**: Customizes admin interface. `SessionAdmin.save_model` auto-populates attendees from group. `SchoolGroupAdmin` displays `attendance_form_url`.
* **`planning/templates/planning/`**: HTML templates. `homepage.html` includes custom banner and feedback reminder card. `session_detail.html` includes attendance link. `player_profile.html` displays feedback and includes "Add Feedback" and "Back to Players List" buttons. `live_session.html` and `one_page_plan.html` include "Back to Session Plan" links. `add_coach_feedback_form.html` created.
* **`planning/static/planning/style.css`**: Main stylesheet, including styles for `.homepage-header` using the background image.
* **WSGI File (on PA):** Standard configuration pointing to project and settings; does *not* need custom `.env` loading logic.
* **`requirements.txt`**: Lists `Django`, `python-dotenv`, `dj-database-url`, `Pillow`, `mysqlclient` (or connector).

## Environment Configuration (`.env`)

Uses `python-dotenv` loading `.env` from the project root (`BASE_DIR`). **File must be in `.gitignore`.**
* **Local `.env`:** `DEBUG=True`, local `SECRET_KEY`, `DATABASE_URL='sqlite:///db.sqlite3'`, `ALLOWED_HOSTS='127.0.0.1,localhost'`, `STATIC_ROOT=''`.
* **Production `.env` (on PA):** `DEBUG=False`, production `SECRET_KEY`, `ALLOWED_HOSTS='YourUsername.pythonanywhere.com'`, `DATABASE_URL='mysql://...'`, `STATIC_ROOT='/home/YourUsername/projectname/staticfiles/'`, `CSRF_TRUSTED_ORIGINS='https://...'`.

## Local Development Setup

1.  Clone repository.
2.  Navigate to project directory.
3.  Create & Activate virtual environment (`venv`).
4.  Install dependencies: `pip install -r requirements.txt`.
5.  Create `.env` file in root with local settings.
6.  Apply migrations: `python manage.py migrate`.
7.  Create superuser: `python manage.py createsuperuser`.
8.  Run server: `python manage.py runserver`.
9.  Access at `http://127.0.0.1:8000/`.

## Deployment Workflow (PythonAnywhere)

(Assumes initial PA setup is complete)
1.  **Local:** Make changes, test, `makemigrations` if needed.
2.  **Git:** `git add .`, `git commit -m "..."`, `git push origin main`.
3.  **PythonAnywhere:**
    * Open Bash Console.
    * `cd ~/squash-coach-hub`
    * `workon squashapp_venv` (Activate virtualenv)
    * `git pull origin main`
    * `pip install -r requirements.txt` (Update dependencies)
    * `python manage.py migrate` (Apply schema changes)
    * `python manage.py collectstatic --noinput` (Collect static files)
    * Go to **Web Tab** -> Click **Reload**.
    * Check live site & logs.

## PythonAnywhere Setup Notes

* **Database:** Use MySQL via PA "Databases" tab. Configure `DATABASE_URL` in PA `.env`.
* **Environment Variables:** Create `.env` in project root (`~/squash-coach-hub/.env`) on PA with production values. Ensure it's gitignored.
* **WSGI Configuration:** Standard file pointing to project/settings. Found via Web Tab.
* **Static/Media Files Mapping (Web Tab -> Static files):**
    * URL `/static/` -> Directory `/home/CharlSquash/squash-coach-hub/staticfiles/`
    * URL `/media/` -> Directory `/home/CharlSquash/squash-coach-hub/mediafiles/`
* **Virtual Environment:** Set path on Web Tab. Install `requirements.txt`.
* **Initial Setup:** Run `migrate` and `createsuperuser` after first deployment / setting up MySQL.
* **Data Entry:** Add School Group Attendance Form URLs via the Django Admin on the live site.

## Future Enhancements (Planned/Ideas)

* Add Edit/Delete functionality for Coach Feedback entries.
* Add Edit/Delete functionality for metric and match records.
* Implement Dark Mode toggle button.
* Refine Chart.js time scale axis formatting.
* Add player court assignments display to `one_page_plan.html`.
* Add summary statistics/dashboards.
* Implement filtering/sorting options for data tables.
* Add Goal Setting module.
* Add Mental Skills / Well-being tracking options.
* Implement user authentication/authorization (coach logins).
* Create a `base.html` template for consistent layout.
* Optimize disk space usage (re-process existing media files).
* Enhance Drill Library (tags, videos).
* Add Session Templates.