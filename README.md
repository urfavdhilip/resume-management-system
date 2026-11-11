# Resume Management System - Final 2

A Flask + MySQL resume management application with admin authentication, candidate records, education history, candidate-specific skills, and resume/photo uploads.

## Included features

- Admin login and logout (passwords stored as Werkzeug hashes)
- Dashboard statistics and recently added candidates
- Candidate create, view, edit, delete, and search
- Education history create, edit, and delete per candidate
- Skills create, edit, and delete per candidate
- Skill categories: Technical, Soft, Tools, Language, Other
- Proficiency levels: Beginner, Intermediate, Advanced, Expert
- Resume upload/download (PDF, DOC, DOCX)
- Profile photo upload (PNG, JPG, JPEG, WEBP)
- MySQL tables and foreign keys created automatically without dropping existing data
- Responsive UI with native Apple-style system font stack and UTF-8 templates

## Windows setup

1. Install MySQL Server and create a database, for example `resume_management`.
2. Open PowerShell in this folder.
3. Create and activate a virtual environment:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

4. Edit `.env`: set `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `SECRET_KEY`, `ADMIN_USERNAME`, and a private `ADMIN_PASSWORD`.
5. Create the schema and the first admin, then launch:

```powershell
python -c "from database import initialize_database; initialize_database(); print('Database ready')"
flask --app app create-admin
python app.py
```

6. Open `http://127.0.0.1:5000` and sign in using the admin credentials configured in `.env`.

## Existing project migration

This package creates its own tables (`admins`, `candidates`, `education`, `skills`) and does not delete or alter tables with other names. If your old database uses a different candidate schema/table naming convention, export/backup it and migrate its records deliberately before using this package. Do not run destructive SQL against your old database.

## Routes

- `/login`, `/logout`, `/dashboard`
- `/candidates` and `/resumes`
- `/candidate/add`, `/candidate/<id>`, `/candidate/<id>/edit`
- `/candidate/<id>/education/add` and edit/delete routes
- `/candidate/<id>/skills/add` and edit/delete routes

## Notes

- Use a strong `SECRET_KEY` and admin password.
- This is a local development starter. Before public deployment, add CSRF protection, HTTPS, rate limiting, and production server configuration.
- `debug=False` by default. Errors are logged in the terminal; database exceptions should be diagnosed from those logs.
