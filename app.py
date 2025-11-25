import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Use SQLite by default; can be overridden with DATABASE_URL env var (e.g. Azure DB)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {'pdf'}

# Simple demo users (hard-coded for prototype).
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "approver": {"password": "approver123", "role": "reviewer"},
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


class Inspection(db.Model):
    __tablename__ = "inspections"

    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(50), nullable=False)
    dealer_name = db.Column(db.String(120), nullable=True)
    pdf_filename = db.Column(db.String(255), nullable=False)
    cost_estimate = db.Column(db.Float, nullable=True)
    status_admin = db.Column(db.String(20), default="Pending")
    status_reviewer = db.Column(db.String(20), default="Pending")
    comment_admin = db.Column(db.Text, nullable=True)
    comment_reviewer = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = USERS.get(username)
        if user and password == user["password"]:
            session["username"] = username
            session["role"] = user["role"]
            flash(f"Logged in as {username}", "success")
            return redirect(url_for("list_inspections"))
        flash("Invalid username or password", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return redirect(url_for("list_inspections"))


@app.route("/inspections")
@login_required
def list_inspections():
    # Search by registration number
    q = request.args.get("q", "").strip()
    query = Inspection.query
    if q:
        like = f"%{q}%"
        query = query.filter(Inspection.registration_number.ilike(like))
    inspections = query.order_by(Inspection.created_at.desc()).all()
    return render_template("dashboard.html", inspections=inspections, search_query=q)


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_inspection():
    if request.method == "POST":
        registration_number = request.form.get("registration_number", "").strip()
        dealer_name = request.form.get("dealer_name", "").strip()
        file = request.files.get("pdf_file")

        if not registration_number:
            flash("Registration number is required", "error")
            return redirect(request.url)

        if not file or file.filename == "":
            flash("Please select a PDF file", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Only PDF files are allowed", "error")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        inspection = Inspection(
            registration_number=registration_number,
            dealer_name=dealer_name or None,
            pdf_filename=filename,
            status_admin="Pending",
            status_reviewer="Pending",
        )
        db.session.add(inspection)
        db.session.commit()

        flash("Inspection uploaded", "success")
        return redirect(url_for("list_inspections"))

    return render_template("upload.html")


@app.route("/inspection/<int:inspection_id>/edit", methods=["GET", "POST"])
@login_required
def edit_inspection(inspection_id):
    inspection = Inspection.query.get_or_404(inspection_id)
    role = session.get("role")

    if request.method == "POST":
        # Cost estimate editable here too
        cost_str = request.form.get("cost_estimate", "").strip()
        inspection.cost_estimate = float(cost_str) if cost_str else None

        if role == "admin":
            inspection.comment_admin = request.form.get("comment_admin", "").strip() or None
            inspection.status_admin = request.form.get("status_admin", inspection.status_admin)
        else:
            inspection.comment_reviewer = request.form.get("comment_reviewer", "").strip() or None
            inspection.status_reviewer = request.form.get("status_reviewer", inspection.status_reviewer)

        db.session.commit()
        flash("Inspection updated", "success")
        return redirect(url_for("list_inspections"))

    return render_template("edit_inspection.html", inspection=inspection, role=role)


@app.route("/inspection/<int:inspection_id>/cost", methods=["POST"])
@login_required
def update_cost(inspection_id):
    # Inline editable column for cost estimate in the table
    inspection = Inspection.query.get_or_404(inspection_id)
    cost_str = request.form.get("cost_estimate", "").strip()
    try:
        inspection.cost_estimate = float(cost_str) if cost_str else None
        db.session.commit()
        flash("Cost estimate updated", "success")
    except ValueError:
        flash("Invalid cost estimate", "error")
    return redirect(url_for("list_inspections"))


@app.route("/inspection/<int:inspection_id>/pdf")
@login_required
def view_pdf(inspection_id):
    inspection = Inspection.query.get_or_404(inspection_id)
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], inspection.pdf_filename, as_attachment=False
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
