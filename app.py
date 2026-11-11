"""Resume Management System - Flask application."""
import os
import uuid
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
from mysql.connector import IntegrityError, Error
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import get_db_connection, initialize_database

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "development-only-change-this-secret"),
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
    UPLOAD_FOLDER=str(UPLOAD_DIR),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

RESUME_EXTENSIONS = {"pdf", "doc", "docx"}
PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
SKILL_CATEGORIES = ["Technical", "Soft", "Tools", "Language", "Other"]
PROFICIENCIES = ["Beginner", "Intermediate", "Advanced", "Expert"]


def db_execute(sql, params=(), fetch=None):
    """Execute a query with a fresh connection and guaranteed cleanup."""
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        if fetch == "one":
            result = cur.fetchone()
        elif fetch == "all":
            result = cur.fetchall()
        else:
            result = cur.lastrowid
        if fetch is None:
            conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename, extensions):
    return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in extensions)


def store_upload(file_storage, extensions):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename, extensions):
        raise ValueError("Unsupported file type.")
    original = secure_filename(file_storage.filename)
    suffix = Path(original).suffix.lower()
    filename = f"{uuid.uuid4().hex}{suffix}"
    file_storage.save(UPLOAD_DIR / filename)
    return filename


def remove_upload(filename):
    if filename:
        path = UPLOAD_DIR / Path(filename).name
        if path.is_file():
            path.unlink(missing_ok=True)


def get_candidate(candidate_id):
    candidate = db_execute("SELECT * FROM candidates WHERE candidate_id=%s", (candidate_id,), "one")
    if not candidate:
        abort(404)
    return candidate


@app.context_processor
def inject_globals():
    return {"current_admin": session.get("username"),
            "skill_categories": SKILL_CATEGORIES,
            "proficiencies": PROFICIENCIES}


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("admin_id") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = db_execute("SELECT * FROM admins WHERE username=%s", (username,), "one")
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["admin_id"]
            session["username"] = admin["username"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    stats = db_execute("""SELECT COUNT(*) AS candidates,
        SUM(CASE WHEN resume_file IS NOT NULL AND resume_file<>'' THEN 1 ELSE 0 END) AS resumes
        FROM candidates""", fetch="one")
    recent = db_execute("SELECT * FROM candidates ORDER BY created_at DESC LIMIT 6", fetch="all")
    return render_template("dashboard.html", stats=stats, recent=recent)


@app.route("/candidates")
@app.route("/resumes")
@login_required
def candidates():
    q = request.args.get("q", "").strip()
    rows = db_execute("""SELECT * FROM candidates
        WHERE full_name LIKE %s OR email LIKE %s OR phone LIKE %s
        ORDER BY candidate_id DESC""", (f"%{q}%", f"%{q}%", f"%{q}%"), "all")
    return render_template("candidates.html", candidates=rows, q=q)


@app.route("/candidate/add", methods=["GET", "POST"])
@app.route("/add", methods=["GET", "POST"])
@login_required
def candidate_add():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        if not name or not email:
            flash("Candidate name and email are required.", "error")
            return render_template("candidate_form.html", candidate=None)
        photo = resume = None
        try:
            photo = store_upload(request.files.get("photo_file"), PHOTO_EXTENSIONS)
            resume = store_upload(request.files.get("resume_file"), RESUME_EXTENSIONS)
            new_id = db_execute("""INSERT INTO candidates
                (full_name,email,phone,address,summary,photo_file,resume_file)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (name, email, request.form.get("phone", "").strip(),
                 request.form.get("address", "").strip(), request.form.get("summary", "").strip(),
                 photo, resume))
            flash("Candidate created successfully.", "success")
            return redirect(url_for("candidate_detail", candidate_id=new_id))
        except (Error, ValueError) as exc:
            remove_upload(photo); remove_upload(resume)
            app.logger.exception("Unable to create candidate")
            flash(str(exc), "error")
    return render_template("candidate_form.html", candidate=None)


@app.route("/candidate/<int:candidate_id>")
@app.route("/candidate/<int:candidate_id>/view")
@app.route("/view_candidate/<int:candidate_id>")
@login_required
def candidate_detail(candidate_id):
    candidate = get_candidate(candidate_id)
    education = db_execute("SELECT * FROM education WHERE candidate_id=%s ORDER BY COALESCE(end_year,0) DESC, education_id DESC", (candidate_id,), "all")
    skills = db_execute("SELECT * FROM skills WHERE candidate_id=%s ORDER BY category, skill_name", (candidate_id,), "all")
    return render_template("candidate_detail.html", candidate=candidate, education=education, skills=skills)


@app.route("/candidate/<int:candidate_id>/edit", methods=["GET", "POST"])
@login_required
def candidate_edit(candidate_id):
    candidate = get_candidate(candidate_id)
    if request.method == "POST":
        photo = candidate.get("photo_file")
        resume = candidate.get("resume_file")
        new_photo = new_resume = None
        try:
            if request.files.get("photo_file") and request.files["photo_file"].filename:
                new_photo = store_upload(request.files["photo_file"], PHOTO_EXTENSIONS); photo = new_photo
            if request.files.get("resume_file") and request.files["resume_file"].filename:
                new_resume = store_upload(request.files["resume_file"], RESUME_EXTENSIONS); resume = new_resume
            db_execute("""UPDATE candidates SET full_name=%s,email=%s,phone=%s,address=%s,
                summary=%s,photo_file=%s,resume_file=%s WHERE candidate_id=%s""",
                (request.form.get("full_name", "").strip(), request.form.get("email", "").strip(),
                 request.form.get("phone", "").strip(), request.form.get("address", "").strip(),
                 request.form.get("summary", "").strip(), photo, resume, candidate_id))
            if new_photo: remove_upload(candidate.get("photo_file"))
            if new_resume: remove_upload(candidate.get("resume_file"))
            flash("Candidate updated.", "success")
            return redirect(url_for("candidate_detail", candidate_id=candidate_id))
        except (Error, ValueError) as exc:
            remove_upload(new_photo); remove_upload(new_resume)
            app.logger.exception("Unable to update candidate"); flash(str(exc), "error")
    return render_template("candidate_form.html", candidate=candidate)


@app.route("/candidate/<int:candidate_id>/delete", methods=["POST"])
@login_required
def candidate_delete(candidate_id):
    candidate = get_candidate(candidate_id)
    db_execute("DELETE FROM candidates WHERE candidate_id=%s", (candidate_id,))
    remove_upload(candidate.get("photo_file")); remove_upload(candidate.get("resume_file"))
    flash("Candidate and related education/skills deleted.", "success")
    return redirect(url_for("candidates"))


@app.route("/candidate/<int:candidate_id>/education/add", methods=["GET", "POST"])
@login_required
def education_add(candidate_id):
    candidate = get_candidate(candidate_id)
    if request.method == "POST":
        try:
            db_execute("""INSERT INTO education
                (candidate_id,degree,institution,field_of_study,start_year,end_year,grade,details)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (candidate_id, request.form.get("degree", "").strip(),
                 request.form.get("institution", "").strip(), request.form.get("field_of_study", "").strip(),
                 request.form.get("start_year") or None, request.form.get("end_year") or None,
                 request.form.get("grade", "").strip(), request.form.get("details", "").strip()))
            flash("Education added.", "success")
            return redirect(url_for("candidate_detail", candidate_id=candidate_id))
        except Error as exc:
            app.logger.exception("Education insert failed"); flash(str(exc), "error")
    return render_template("education_form.html", candidate=candidate, record=None)


@app.route("/candidate/<int:candidate_id>/education/<int:education_id>/edit", methods=["GET", "POST"])
@login_required
def education_edit(candidate_id, education_id):
    candidate = get_candidate(candidate_id)
    record = db_execute("SELECT * FROM education WHERE education_id=%s AND candidate_id=%s", (education_id, candidate_id), "one")
    if not record: abort(404)
    if request.method == "POST":
        db_execute("""UPDATE education SET degree=%s,institution=%s,field_of_study=%s,
            start_year=%s,end_year=%s,grade=%s,details=%s WHERE education_id=%s AND candidate_id=%s""",
            (request.form.get("degree", "").strip(), request.form.get("institution", "").strip(),
             request.form.get("field_of_study", "").strip(), request.form.get("start_year") or None,
             request.form.get("end_year") or None, request.form.get("grade", "").strip(),
             request.form.get("details", "").strip(), education_id, candidate_id))
        flash("Education updated.", "success")
        return redirect(url_for("candidate_detail", candidate_id=candidate_id))
    return render_template("education_form.html", candidate=candidate, record=record)


@app.route("/candidate/<int:candidate_id>/education/<int:education_id>/delete", methods=["POST"])
@login_required
def education_delete(candidate_id, education_id):
    get_candidate(candidate_id)
    db_execute("DELETE FROM education WHERE education_id=%s AND candidate_id=%s", (education_id, candidate_id))
    flash("Education record deleted.", "success")
    return redirect(url_for("candidate_detail", candidate_id=candidate_id))


@app.route("/candidate/<int:candidate_id>/skills/add", methods=["GET", "POST"])
@login_required
def skill_add(candidate_id):
    candidate = get_candidate(candidate_id)
    if request.method == "POST":
        name = request.form.get("skill_name", "").strip()
        category = request.form.get("category", "Technical").strip()
        proficiency = request.form.get("proficiency", "Intermediate").strip()

        if not name or len(name) > 120:
            flash("Skill name is required and must be 120 characters or fewer.", "error")
        elif category not in SKILL_CATEGORIES or proficiency not in PROFICIENCIES:
            flash("Choose a valid skill category and proficiency.", "error")
        else:
            try:
                db_execute(
                    """INSERT INTO skills
                       (candidate_id, skill_name, category, proficiency)
                       VALUES (%s, %s, %s, %s)""",
                    (candidate_id, name, category, proficiency)
                )
                flash("Skill added successfully.", "success")
                return redirect(url_for("candidate_detail", candidate_id=candidate_id))
            except IntegrityError:
                flash("This skill already exists for this candidate.", "error")
            except Error:
                app.logger.exception("Database error while adding a skill")
                flash("The skill could not be saved. Check the Skills table in MySQL and the terminal error.", "error")

    return render_template(
        "skill_form.html", candidate=candidate, record=None,
        skill_categories=SKILL_CATEGORIES, proficiencies=PROFICIENCIES
    )


@app.route("/candidate/<int:candidate_id>/skills/<int:skill_id>/edit", methods=["GET", "POST"])
@login_required
def skill_edit(candidate_id, skill_id):
    candidate = get_candidate(candidate_id)
    record = db_execute(
        "SELECT * FROM skills WHERE skill_id=%s AND candidate_id=%s",
        (skill_id, candidate_id), "one"
    )
    if not record:
        abort(404)

    if request.method == "POST":
        name = request.form.get("skill_name", "").strip()
        category = request.form.get("category", "Technical").strip()
        proficiency = request.form.get("proficiency", "Intermediate").strip()

        if not name or len(name) > 120:
            flash("Skill name is required and must be 120 characters or fewer.", "error")
        elif category not in SKILL_CATEGORIES or proficiency not in PROFICIENCIES:
            flash("Choose a valid skill category and proficiency.", "error")
        else:
            try:
                db_execute(
                    """UPDATE skills
                       SET skill_name=%s, category=%s, proficiency=%s
                       WHERE skill_id=%s AND candidate_id=%s""",
                    (name, category, proficiency, skill_id, candidate_id)
                )
                flash("Skill updated successfully.", "success")
                return redirect(url_for("candidate_detail", candidate_id=candidate_id))
            except IntegrityError:
                flash("Another skill with this name already exists for this candidate.", "error")
            except Error:
                app.logger.exception("Database error while updating a skill")
                flash("The skill could not be updated. Check the Skills table in MySQL and the terminal error.", "error")

    return render_template(
        "skill_form.html", candidate=candidate, record=record,
        skill_categories=SKILL_CATEGORIES, proficiencies=PROFICIENCIES
    )


@app.route("/candidate/<int:candidate_id>/skills/<int:skill_id>/delete", methods=["POST"])
@login_required
def skill_delete(candidate_id, skill_id):
    get_candidate(candidate_id)
    try:
        db_execute(
            "DELETE FROM skills WHERE skill_id=%s AND candidate_id=%s",
            (skill_id, candidate_id)
        )
        flash("Skill deleted successfully.", "success")
    except Error:
        app.logger.exception("Database error while deleting a skill")
        flash("The skill could not be deleted. Check the terminal error.", "error")
    return redirect(url_for("candidate_detail", candidate_id=candidate_id))


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, Path(filename).name, as_attachment=False)


@app.route("/candidate/<int:candidate_id>/resume")
@login_required
def download_resume(candidate_id):
    candidate = get_candidate(candidate_id)
    if not candidate.get("resume_file"):
        flash("No resume uploaded for this candidate.", "error")
        return redirect(url_for("candidate_detail", candidate_id=candidate_id))
    return send_from_directory(UPLOAD_DIR, candidate["resume_file"], as_attachment=True)


@app.errorhandler(413)
def too_large(_error):
    flash("File is too large. Maximum upload size is 12 MB.", "error")
    return redirect(request.referrer or url_for("candidates"))


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("Unhandled server error: %s", error)
    return render_template("error.html", code=500, message="An unexpected error occurred. Check the terminal log."), 500


@app.cli.command("create-admin")
def create_admin_command():
    """Create or update the initial admin from .env credentials."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD")
    if not password or password == "ChangeMe_123!":
        raise SystemExit("Set a private ADMIN_PASSWORD in .env before creating admin.")
    existing = db_execute("SELECT admin_id FROM admins WHERE username=%s", (username,), "one")
    hashed = generate_password_hash(password)
    if existing:
        db_execute("UPDATE admins SET password_hash=%s WHERE username=%s", (hashed, username))
        print(f"Admin password updated for {username}")
    else:
        db_execute("INSERT INTO admins (username,password_hash) VALUES (%s,%s)", (username, hashed))
        print(f"Admin created: {username}")


if __name__ == "__main__":
    try:
        initialize_database()
        print("Database schema is ready.")
        print("If this is a new installation, create admin with: flask --app app create-admin")
        app.run(host=os.getenv("FLASK_HOST", "127.0.0.1"),
                port=int(os.getenv("FLASK_PORT", "5000")), debug=False)
    except Exception:
        app.logger.exception("Application startup failed")
        raise
