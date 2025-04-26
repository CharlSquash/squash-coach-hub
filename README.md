# Squash Coach Hub

## Description

Squash Coach Hub is a Django-based web application designed to assist squash coaches, particularly those working with high school players (leveraging sport psychology principles), in planning training sessions, tracking player performance metrics, managing assessments, and visualizing progress. It aims to provide a centralized platform for effective coaching and player development, linking planning with performance tracking. This project currently links externally to the "Shot IQ" application.

## Features

* **Session Planning:** Create and manage training sessions (date, time, duration, school group, coaches).
* **Time Blocks:** Divide sessions into time blocks (duration, courts, rotation interval, focus).
* **Activity Management:** Define reusable drills (with player counts) or add custom activities, assigning them to courts within time blocks.
* **Attendance Tracking:** Mark player attendance per session via the Session Detail page.
* **Live Session View:** Dynamic view showing current/next block, player court assignments (with automatic rotation), activities, time simulation, and rotation alerts.
* **Player Profiles:** Centralized view per player: details, attendance, session assessments, recorded metrics (sprints, volleys, drives), match results, performance charts.
* **Metric & Match Tracking:** Forms to log results for court sprints, consecutive volleys (FH/BH), consecutive backwall drives (FH/BH), and match outcomes (practice/competitive).
* **Session Assessments:** Record coach assessments on player attributes (effort, focus, resilience, composure, decision-making).
* **Player List & Filtering:** Dedicated page listing active players, allowing filtering by School Group and searching by player name (first or last).
* **Image Optimization:** Player profile photos are automatically resized (max 300x300, preserving aspect ratio) and corrected for orientation upon upload using Pillow.
* **Data Visualization:** Basic line charts on player profiles showing metric progress over time (using Chart.js).
* **Manual Court Assignment:** Visually drag-and-drop players between courts on Session Detail page; assignments persist and reflect in Live Session view. Option to clear manual assignments per block.
* **One-Page Session Plan:** Generate a simplified, mobile-friendly, shareable view of a session's schedule and activities (via Web Share API).
* **Homepage Dashboard:** Displays upcoming sessions, player management card, and links to other resources (including Shot IQ, Admin site).
* **Django Admin Customization:** Enhanced admin for managing drills, players (group filtering), sessions (inline blocks, attendees).

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
|   |-- urls.py            # Project URLs
|   |-- wsgi.py            # WSGI entry point
|   |-- ...
|-- planning/              # Main Django app
|   |-- migrations/
|   |-- static/planning/
|   |-- templates/planning/
|   |-- admin.py
|   |-- models.py          # Includes Player.save() override for image optimization
|   |-- views.py           # Includes players_list_view with filtering/search
|   |-- urls.py
|   |-- ...
|-- mediafiles/            # User-uploaded files (e.g., player photos) - GITIGNORED
|-- staticfiles/           # Target for 'collectstatic' on PA (defined by STATIC_ROOT env var) - GITIGNORED
|-- venv/                  # Local virtual environment - GITIGNORED
|-- db.sqlite3             # Local SQLite database - GITIGNORED
|-- manage.py              # Django management script
|-- requirements.txt       # Python package dependencies
|-- README.md              # This file
```

## Environment Configuration (`.env`)

This project uses a `.env` file to manage environment-specific settings, keeping `settings.py` consistent across environments (and safe for Git).

* **Mechanism:** The `python-dotenv` package loads variables from a `.env` file located in the project root (`BASE_DIR`). `settings.py` then reads these variables using `os.environ.get()`.
* **Local `.env`:**
    * Create this file in your local project root (`C:\...\squash-coach-hub\.env`).
    * **MUST be listed in `.gitignore`.**
    * Contains settings for development: `DEBUG=True`, a local `SECRET_KEY`, `ALLOWED_HOSTS='127.0.0.1,localhost'`, `DATABASE_URL='sqlite:///db.sqlite3'`, `STATIC_ROOT=''`, etc.
* **Production `.env` (PythonAnywhere):**
    * Create this file in your **project root on PythonAnywhere** (`/home/CharlSquash/squash-coach-hub/.env`).
    * **MUST be listed in `.gitignore`.**
    * Contains settings for production: `DEBUG=False`, a unique production `SECRET_KEY`, `ALLOWED_HOSTS='YourUsername.pythonanywhere.com'`, `DATABASE_URL='mysql://...'` (with PA MySQL credentials), `STATIC_ROOT='/home/YourUsername/projectname/staticfiles/'`, `CSRF_TRUSTED_ORIGINS='https://...'`.
* **WSGI File (PA):** The WSGI file on PythonAnywhere should *not* load `.env` itself; it relies on `settings.py` loading the `.env` file from the project root.

## Local Development Setup

1.  **Clone Repository:** `git clone <your_repo_url>`
2.  **Navigate to Project:** `cd squash-coach-hub`
3.  **Create & Activate Virtual Environment:**
    ```bash
    python -m venv venv
    venv\Scripts\activate  # Windows
    # source venv/bin/activate # macOS/Linux
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt 
    # Ensure Pillow, dj-database-url are included
    ```
5.  **Create Local `.env` File:** Create `.env` in the root directory. Add local settings (DEBUG=True, local SECRET_KEY, SQLite DATABASE_URL, ALLOWED_HOSTS='127.0.0.1,localhost', etc.). See "Environment Configuration" section.
6.  **Apply Migrations (Creates local SQLite DB):**
    ```bash
    python manage.py migrate
    ```
7.  **Create Superuser (for Local Admin):**
    ```bash
    python manage.py createsuperuser 
    ```
8.  **Run Development Server:**
    ```bash
    python manage.py runserver
    ```
9.  Access the site at `http://127.0.0.1:8000/`.

## Deployment Workflow (PythonAnywhere)

1.  **Local Development:** Make changes locally. Test thoroughly. Run `makemigrations` locally if models change.
2.  **Version Control (Git):**
    * `git status`
    * `git add <changed_files>` (including new migration files, `requirements.txt`, `settings.py`, `.gitignore` if changed)
    * `git commit -m "Descriptive commit message"`
    * `git pull origin main` (Recommended: Check for remote changes first)
    * `git push origin main` (Push local commits to GitHub)
3.  **PythonAnywhere Deployment:**
    * Open a **Bash Console**.
    * Navigate to project directory: `cd ~/squash-coach-hub`
    * Activate virtualenv: `workon squashapp_venv` (or `source ...`)
    * Pull latest code: `git pull origin main`
    * Install/update dependencies: `pip install -r requirements.txt`
    * Apply database migrations: `python manage.py migrate`
    * Collect static files: `python manage.py collectstatic --noinput`
    * Go to the **Web Tab**.
    * Click the **Reload** button.
    * Check live site and error/server logs.

## PythonAnywhere Setup Notes

* **Database:** Create a MySQL database via the PA "Databases" tab. Note the username, password (set one!), hostname, and database name.
* **Environment Variables (`.env`):** Create `.env` file inside the project root (`~/squash-coach-hub/.env`). Add production settings (see "Environment Configuration"), using the MySQL `DATABASE_URL` format and the absolute path for `STATIC_ROOT`. **Ensure `.env` is in `.gitignore`**.
* **WSGI Configuration:** Ensure the WSGI file on the Web tab correctly points to your project path and sets `DJANGO_SETTINGS_MODULE`. It does *not* need custom code to load `.env`.
* **Static Files Mapping:** On the "Web" tab -> "Static files":
    * URL: `/static/` -> Directory: `/home/CharlSquash/squash-coach-hub/staticfiles/`
* **Media Files Mapping:** On the "Web" tab -> "Static files":
    * URL: `/media/` -> Directory: `/home/CharlSquash/squash-coach-hub/mediafiles/`
* **Virtual Environment:** Ensure the correct virtualenv path is set on the "Web" tab. Install all packages from `requirements.txt` into it.
* **Initial Setup:** After first deployment or switching to MySQL, run `python manage.py migrate` to create tables and `python manage.py createsuperuser` to create the production admin account.

## Future Enhancements (Planned/Ideas)

* Add Edit/Delete functionality for metric and match records on player profiles.
* Implement a user-clickable Dark Mode toggle button.
* Reliably fix/implement Chart.js time scale axis formatting.
* Add player court assignments display to `one_page_plan.html`.
* Add summary statistics/dashboards to player profiles or group views.
* Implement filtering/sorting options for data tables (e.g., session list).
* Add tracking for other relevant squash metrics or sport psychology assessments.
* Implement user authentication/authorization (e.g., coach logins).
* Create a `base.html` template for a consistent site layout and navigation.
* Explore advanced image optimization (e.g., `django-imagekit`, different formats like WebP).

```

---

This updated README should provide a much more complete picture of the project's current state and configuration. Remember to commit this updated `README.md` file to your Git repository!