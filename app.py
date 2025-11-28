import os
from io import BytesIO
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from sqlalchemy import or_, text, inspect

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def normalize_database_uri(raw_uri: str) -> str:
    if raw_uri.startswith("postgres://"):
        return raw_uri.replace("postgres://", "postgresql://", 1)
    return raw_uri


app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_uri(
    os.getenv('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'app.db'))
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {'pdf'}

USERS = {
    "admin": {"password": "#GladPippi28!", "role": "admin"},
    "approver": {"password": "#GladPingvin12!", "role": "reviewer"},
}

ADMIN_STATUSES = ["Pending", "Awaiting approval", "Disputed", "Accepted"]
REVIEWER_STATUSES = ["Pending", "Approved", "Rejected"]


def allowed_file(filename: str) -> bool:
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
    pdf_data = db.Column(db.LargeBinary, nullable=True)
    cost_estimate = db.Column(db.Integer, nullable=True)
    accepted_cost = db.Column(db.Integer, nullable=True)
    status_admin = db.Column(db.String(30), default="Pending")
    status_reviewer = db.Column(db.String(20), default="Pending")
    comment_admin = db.Column(db.Text, nullable=True)
    comment_reviewer = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def pdf_file_path(self) -> str:
        return os.path.join(app.config["UPLOAD_FOLDER"], self.pdf_filename)

    @property
    def has_pdf(self) -> bool:
        if self.pdf_data:
            return True
        return os.path.exists(self.pdf_file_path)


def ensure_inspection_columns():
    inspector = inspect(db.engine)
    if "inspections" not in inspector.get_table_names():
        db.create_all()
        return

    existing_columns = {column["name"] for column in inspector.get_columns("inspections")}
    ddl_statements = []

    def add_column(name: str, ddl: str):
        if name not in existing_columns:
            ddl_statements.append(f"ALTER TABLE inspections ADD COLUMN {name} {ddl}")

    dialect = db.engine.url.get_dialect().name
    binary_type = "BYTEA" if dialect == "postgresql" else "BLOB"

    add_column("cost_estimate", "INTEGER")
    add_column("accepted_cost", "INTEGER")
    add_column("status_admin", "VARCHAR(30) DEFAULT 'Pending'")
    add_column("status_reviewer", "VARCHAR(20) DEFAULT 'Pending'")
    add_column("comment_admin", "TEXT")
    add_column("comment_reviewer", "TEXT")
    add_column("pdf_data", binary_type)

    if ddl_statements:
        with db.engine.begin() as conn:
            for ddl in ddl_statements:
                conn.execute(text(ddl))


with app.app_context():
    db.create_all()
    ensure_inspection_columns()


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
    q = request.args.get("q", "").strip()
    query = Inspection.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Inspection.registration_number.ilike(like),
                Inspection.dealer_name.ilike(like),
                Inspection.status_admin.ilike(like),
                Inspection.status_reviewer.ilike(like),
            )
        )
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
        file_bytes = file.read()
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        inspection = Inspection(
            registration_number=registration_number,
            dealer_name=dealer_name or None,
            pdf_filename=filename,
            pdf_data=file_bytes,
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
def edit_inspection(inspection_id: int):
    inspection = Inspection.query.get_or_404(inspection_id)
    role = session.get("role")
    if request.method == "POST":
        if role == "admin":
            cost_str = request.form.get("cost_estimate", "").strip()
            inspection.cost_estimate = int(cost_str) if cost_str else None
            inspection.comment_admin = request.form.get("comment_admin", "").strip() or None
            new_status = request.form.get("status_admin", inspection.status_admin)
            if new_status in ADMIN_STATUSES:
                inspection.status_admin = new_status
        else:
            accepted_str = request.form.get("accepted_cost", "").strip()
            inspection.accepted_cost = int(accepted_str) if accepted_str else None
            inspection.comment_reviewer = request.form.get("comment_reviewer", "").strip() or None
            new_status = request.form.get("status_reviewer", inspection.status_reviewer)
            if new_status in REVIEWER_STATUSES:
                inspection.status_reviewer = new_status

        db.session.commit()
        flash("Inspection updated", "success")
        return redirect(url_for("list_inspections"))
    return render_template(
        "edit_inspection.html",
        inspection=inspection,
        role=role,
        admin_statuses=ADMIN_STATUSES,
        reviewer_statuses=REVIEWER_STATUSES,
    )


@app.route("/inspection/<int:inspection_id>/cost", methods=["POST"])
@login_required
def update_cost(inspection_id: int):
    inspection = Inspection.query.get_or_404(inspection_id)
    if session.get("role") != "admin":
        flash("Only admin can edit cost estimate", "error")
        return redirect(url_for("list_inspections"))
    cost_str = request.form.get("cost_estimate", "").strip()
    try:
        inspection.cost_estimate = int(cost_str) if cost_str else None
        db.session.commit()
        flash("Cost estimate updated", "success")
    except ValueError:
        flash("Invalid cost estimate", "error")
    return redirect(url_for("list_inspections"))


@app.route("/inspection/<int:inspection_id>/accepted_cost", methods=["POST"])
@login_required
def update_accepted_cost(inspection_id: int):
    inspection = Inspection.query.get_or_404(inspection_id)
    if session.get("role") != "reviewer":
        flash("Only approver can edit accepted cost", "error")
        return redirect(url_for("list_inspections"))
    cost_str = request.form.get("accepted_cost", "").strip()
    try:
        inspection.accepted_cost = int(cost_str) if cost_str else None
        db.session.commit()
        flash("Accepted cost updated", "success")
    except ValueError:
        flash("Invalid accepted cost", "error")
    return redirect(url_for("list_inspections"))


@app.route("/inspection/<int:inspection_id>/pdf")
@login_required
def view_pdf(inspection_id: int):
    inspection = Inspection.query.get_or_404(inspection_id)
    if inspection.pdf_data:
        return send_file(
            BytesIO(inspection.pdf_data),
            mimetype="application/pdf",
            download_name=inspection.pdf_filename,
            as_attachment=False,
        )

    if os.path.exists(inspection.pdf_file_path):
        with open(inspection.pdf_file_path, "rb") as f:
            data = f.read()
        inspection.pdf_data = data
        db.session.commit()
        return send_file(
            BytesIO(data),
            mimetype="application/pdf",
            download_name=inspection.pdf_filename,
            as_attachment=False,
        )

    flash("PDF file could not be found", "error")
    return redirect(url_for("list_inspections"))


@app.route("/inspection/<int:inspection_id>/delete_pdf", methods=["POST"])
@login_required
def delete_pdf(inspection_id: int):
    inspection = Inspection.query.get_or_404(inspection_id)
    if session.get("role") != "admin":
        flash("Only admin can delete PDFs", "error")
        return redirect(url_for("edit_inspection", inspection_id=inspection.id))

    if os.path.exists(inspection.pdf_file_path):
        os.remove(inspection.pdf_file_path)

    inspection.pdf_data = None
    db.session.commit()

    flash("PDF deleted", "success")
    return redirect(url_for("edit_inspection", inspection_id=inspection.id))


if __name__ == "__main__":
    app.run(debug=True)
