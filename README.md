# Squash Coach Hub

## Description

Squash Coach Hub is a Django-based web application designed to assist squash coaches, particularly those working with high school players (leveraging sport psychology principles), in planning training sessions, tracking player performance metrics, managing assessments, and visualizing progress. It aims to provide a centralized platform for effective coaching and player development, linking planning with performance tracking. This project currently links externally to the "Shot IQ" application.

## Features

* **Session Planning:** Create and manage training sessions (date, time, duration, school group, coaches).
* **Time Blocks:** Divide sessions into time blocks (duration, courts, rotation interval, focus).
* **Activity Management:** Define reusable drills (with player counts) or add custom activities, assigning them to courts within time blocks.
* **Attendance Tracking:** Mark player attendance per session via the Session Detail page.
* **School Group Attendance Link:** Store an external URL (e.g., Google Form) per School Group for attendance; display a direct link on the associated Session Detail page.
* **Live Session View:** Dynamic view showing current/next block, player court assignments (with automatic rotation), activities, time simulation, and rotation alerts.
* **Player Profiles:** Centralized view per player: details, attendance, session assessments, recorded metrics (sprints, volleys, drives), match results, performance charts, coach feedback history.
* **Coach Feedback:** Ability for coaches to add structured feedback (strengths, development areas, focus, notes) per player, viewable on the profile (optionally linked to a session).
* **Metric & Match Tracking:** Forms to log results for court sprints, consecutive volleys (FH/BH), consecutive backwall drives (FH/BH), and match outcomes (practice/competitive).
* **Session Assessments:** Record coach assessments on player attributes (effort, focus, resilience, composure, decision-making).
* **Player List & Filtering:** Dedicated page listing active players, allowing filtering by School Group and searching by player name (first or last).
* **Image Optimization:** Player profile photos are automatically resized (max 300x300, preserving aspect ratio) and corrected for orientation upon upload using Pillow.
* **Data Visualization:** Basic line charts on player profiles showing metric progress over time (using Chart.js).
* **Manual Court Assignment:** Visually drag-and-drop players between courts on Session Detail page; assignments persist and reflect in Live Session view. Option to clear manual assignments per block.
* **One-Page Session Plan:** Generate a simplified, mobile-friendly, shareable view of a session's schedule and activities (via Web Share API).
* **Homepage Dashboard:** Displays upcoming sessions, player management card, and links to other resources (including Shot IQ, Admin site).
* **Django Admin Customization:** Enhanced admin for managing drills, players (group filtering), sessions (inline blocks, attendees), School Groups (including Attendance Form URL).

## Technology Stack

* **Backend:** Python 3.13, Django 5.2
* **Database:**
    * Local Development: SQLite3 (`db.sqlite3`)
    * Production (PythonAnywhere): MySQL (Configured via Environment Variable)
* **Frontend:** HTML5, CSS3 (custom stylesheet + inline styles), JavaScript (ES6+)
* **Environment Variables:** `python-dotenv` (manages settings via `.env` files)
* **Database URL Parsing:** `dj-database-url` (parses `DATABASE_URL` env var)
* **Image Processing:** `Pillow` (for `ImageField` and upload optimization)
* **Database Driver (Production):** `mysqlclient` (or `mysql-connector-python`)
* **JavaScript Libraries:**
    * Chart.js (^4) for data visualization
    * Moment.js (^2.29.4) & chartjs-adapter-moment (^1.1.1) for Chart.js time scale (loaded locally from `static/vendor/`)
    * SortableJS (^1.15.2) for drag-and-drop functionality (loaded via CDN)
    * Bootstrap Icons (via CDN) for UI icons
* **Version Control:** Git / GitHub

## Project Structure

```
squash-coach-hub/
|-- .git/
|-- .gitignore             # Specifies ignored files (MUST include .env, venv, db.sqlite3, mediafiles)
|-- .env                   # Environment variables (local version OR production version - NOT IN GIT)
|-- coach_project/         # Django project config
|   |-- settings.py        # Reads settings from environment variables via dotenv
|   |-- urls.py            # Project-level URL routing (admin, planning app, homepage)
|   |-- wsgi.py            # WSGI entry point
|   |-- ...
|-- planning/              # Main Django app
|   |-- migrations/        # Database migration files (e.g., 0001_initial.py, ...)
|   |-- static/planning/   # App-specific static files (style.css, vendor libs, etc.)
|   |-- templates/planning/ # HTML templates (homepage, session_detail, player_profile, forms, etc.)
|   |-- __init__.py
|   |-- admin.py           # Django admin config (e.g., SchoolGroupAdmin)
|   |-- apps.py
|   |-- forms.py           # CoachFeedbackForm, etc.
|   |-- models.py          # Player, Session, SchoolGroup, CoachFeedback, etc.
|   |-- tests.py
|   |-- urls.py            # App-specific URLs (planning namespace)
|   |-- views.py           # View functions (player_profile, add_coach_feedback, etc.)
|
|-- mediafiles/            # User-uploaded files (e.g., player photos) - GITIGNORED
|-- staticfiles/           # Target for 'collectstatic' on PA (defined by STATIC_ROOT env var) - GITIGNORED
|-- venv/                  # Local virtual environment - GITIGNORED
|-- db.sqlite3             # Local SQLite database - GITIGNORED
|-- manage.py              # Django management script
|-- requirements.txt       # Python package dependencies
|-- README.md              # This file
```

## Key Files Overview

* **`coach_project/settings.py`**: Main project configuration. Reads sensitive/environment-specific settings from environment variables via `python-dotenv`.
* **`.env`**: File (in project root locally & on PA, **ignored by Git**) storing environment variables (DB URLs, SECRET_KEY, DEBUG status, HOSTS, STATIC_ROOT etc.).
* **`.gitignore`**: Specifies files/directories Git should ignore (e.g., `.env`, `venv/`, `db.sqlite3`, `mediafiles/`, `__pycache__/`, `staticfiles/`).
* **`planning/models.py`**: Defines database models (`Player`, `Session`, `SchoolGroup` [with `attendance_form_url`], `CoachFeedback`, etc.). Includes `Player.save()` override for image optimization.
* **`planning/views.py`**: Contains view functions handling requests, fetching data, processing forms (like `add_coach_feedback`), and rendering templates.
* **`planning/urls.py`**: Maps URL paths within the `/planning/` namespace to specific view functions. Includes patterns for feedback forms.
* **`planning/admin.py`**: Configures how models appear in the Django admin site (e.g., making `attendance_form_url` visible in `SchoolGroupAdmin`).
* **`planning/templates/planning/`**: Contains HTML templates. `session_detail.html` now includes logic to display the attendance link. `player_profile.html` displays feedback and has links to add more.
* **`requirements.txt`**: Lists required Python packages (`Django`, `python-dotenv`, `dj-database-url`, `Pillow`, `mysqlclient`).
* **WSGI File (on PA):** `/var/www/..._wsgi.py`. Standard configuration pointing to project and settings module. Does *not* need custom `.env` loading logic.

## Environment Configuration (`.env`)

This project relies on a `.env` file in the project root directory for environment-specific settings. **This file MUST be in `.gitignore`.**

* **Local `.env`:** Contains `DEBUG=True`, local `SECRET_KEY`, `DATABASE_URL='sqlite:///db.sqlite3'`, `ALLOWED_HOSTS='127.0.0.1,localhost'`, etc.
* **Production `.env` (on PA):** Contains `DEBUG=False`, production `SECRET_KEY`, `ALLOWED_HOSTS='YourUsername.pythonanywhere.com'`, `DATABASE_URL='mysql://...'`, `STATIC_ROOT='/home/YourUsername/projectname/staticfiles/'`, `CSRF_TRUSTED_ORIGINS='https://...'`, etc.

## Local Development Setup

1.  Clone repository.
2.  Navigate to project directory.
3.  Create & Activate virtual environment (`venv`).
4.  Install dependencies: `pip install -r requirements.txt`.
5.  Create `.env` file in root with local settings (see above).
6.  Apply migrations: `python manage.py migrate`.
7.  Create superuser: `python manage.py createsuperuser`.
8.  Run server: `python manage.py runserver`.
9.  Access at `http://127.0.0.1:8000/`.

## Deployment Workflow (PythonAnywhere)

1.  **Local:** Make changes, test, run `makemigrations` if models changed.
2.  **Git:** `git status`, `git add .`, `git commit -m "..."`, `git pull origin main` (optional check), `git push origin main`.
3.  **PythonAnywhere:**
    * Open Bash Console.
    * `cd ~/squash-coach-hub`
    * `workon squashapp_venv`
    * `git pull origin main`
    * `pip install -r requirements.txt` (To update dependencies)
    * `python manage.py migrate` (To apply schema changes)
    * `python manage.py collectstatic --noinput` (To update static files)
    * Go to **Web Tab** -> Click **Reload**.
    * Check live site & logs.

## PythonAnywhere Setup Notes

* **Database:** Use MySQL via the PA "Databases" tab. Configure `DATABASE_URL` in the PA `.env` file.
* **Environment Variables:** Create `.env` in the project root (`~/squash-coach-hub/.env`) on PA with production values. Ensure it's gitignored.
* **WSGI Configuration:** Use the standard WSGI file generated by PA, ensuring it points to your project and `coach_project.settings`.
* **Static/Media Files Mapping (Web Tab):**
    * `/static/` -> `/home/CharlSquash/squash-coach-hub/staticfiles/`
    * `/media/` -> `/home/CharlSquash/squash-coach-hub/mediafiles/`
* **Virtual Environment:** Set path on Web Tab. Install packages from `requirements.txt`.
* **Initial Setup:** Run `migrate` and `createsuperuser` after first deployment / setting up MySQL.
* **Data Entry:** Add School Group Attendance Form URLs via the Django Admin interface on the live site.

## Future Enhancements (Planned/Ideas)

* Add Edit/Delete functionality for Coach Feedback entries.
* Add Edit/Delete functionality for metric and match records on player profiles.
* Implement a user-clickable Dark Mode toggle button.
* Reliably fix/implement Chart.js time scale axis formatting.
* Add player court assignments display to `one_page_plan.html`.
* Add summary statistics/dashboards to player profiles or group views.
* Implement filtering/sorting options for data tables (e.g., session list).
* Add tracking for other relevant squash metrics or sport psychology assessments (Goal Setting, Well-being checks).
* Implement user authentication/authorization (e.g., coach logins).
* Create a `base.html` template for a consistent site layout and navigation.
* Optimize disk space usage (e.g., re-process existing media files).
* Enhance Drill Library (tags, videos).
* Add Session Templates.

```

---

There you go! This updated README covers the latest features and the refined setup/deployment process. Remember to commit this file to your Git repository.