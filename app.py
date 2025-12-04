import os
from io import BytesIO
from datetime import datetime, date
from functools import wraps
from typing import Any, Dict, List, Optional

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
import calendar

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def normalize_database_uri(raw_uri: str) -> str:
    if raw_uri.startswith("postgres://"):
        raw_uri = raw_uri.replace("postgres://", "postgresql://", 1)

    if raw_uri.startswith("postgresql://") and "sslmode=" not in raw_uri:
        separator = "?" if "?" not in raw_uri else "&"
        raw_uri = f"{raw_uri}{separator}sslmode=require"

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


ASSET_OVERVIEW_COLUMNS = [
    "Bilnr",
    "Display",
    "Fabrikat/Modell",
    "Märke",
    "Årsmodell",
    "Första reg.datum",
    "Ägaredatum",
    "Köpsdatum",
    "Registreringsnummer",
    "Typ",
    "Biltyp",
    "Typ av finansiering",
    "Finansiär",
    "Köpeskilling",
    "Netto som begagnad",
    "Nybilspris",
    "Ev kreditgivarens kreditgräns",
    "Avtalets löptid",
    "Återköpspris",
    "Avdrag för hantering och adm",
    "Avskrivning",
    "Avskrivning per månad",
    "Registreringsavgift",
    "Ev rabatter",
]


def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%d-%m-%Y").date()


PLACEHOLDER_ASSETS = [
    {
        "Bilnr": "KP20P236784",
        "Display": 2,
        "Fabrikat/Modell": "FH16 HEAVY DUTY",
        "Märke": "VOLVO",
        "Årsmodell": 2020,
        "Första reg.datum": "25-11-2020",
        "Ägaredatum": "25-11-2020",
        "Köpsdatum": "06-03-2023",
        "Registreringsnummer": "HEM17R",
        "Typ": 3,
        "Biltyp": "Traktor",
        "Typ av finansiering": "Volvofinans",
        "Finansiär": "Volvofinans",
        "Köpeskilling": 1201783,
        "Netto som begagnad": 1201783,
        "Nybilspris": 2204002,
        "Ev kreditgivarens kreditgräns": 214090,
        "Avtalets löptid": 36,
        "Återköpspris": 547278,
        "Avdrag för hantering och adm": 0,
        "Avskrivning": 701814,
        "Avskrivning per månad": 19494,
        "Registreringsavgift": 0,
        "Ev rabatter": 0,
    },
    {
        "Bilnr": "KP20P237804",
        "Display": 2,
        "Fabrikat/Modell": "SCANIA 500 S",
        "Märke": "SCANIA",
        "Årsmodell": 2019,
        "Första reg.datum": "27-08-2019",
        "Ägaredatum": "07-11-2022",
        "Köpsdatum": "07-11-2022",
        "Registreringsnummer": "PPM24L",
        "Typ": 4,
        "Biltyp": "Lastbil",
        "Typ av finansiering": "Volvofinans",
        "Finansiär": "Volvofinans",
        "Köpeskilling": 1197834,
        "Netto som begagnad": 1197834,
        "Nybilspris": 1714768,
        "Ev kreditgivarens kreditgräns": 91061,
        "Avtalets löptid": 36,
        "Återköpspris": 342954,
        "Avdrag för hantering och adm": 0,
        "Avskrivning": 508820,
        "Avskrivning per månad": 14134,
        "Registreringsavgift": 0,
        "Ev rabatter": 0,
    },
    {
        "Bilnr": "KP15H114979",
        "Display": 1,
        "Fabrikat/Modell": "SCANIA R580",
        "Märke": "SCANIA",
        "Årsmodell": 2015,
        "Första reg.datum": "29-01-2015",
        "Ägaredatum": "23-05-2023",
        "Köpsdatum": "23-05-2023",
        "Registreringsnummer": "XDG99Z",
        "Typ": 4,
        "Biltyp": "Lastbil",
        "Typ av finansiering": "Volvofinans",
        "Finansiär": "Volvofinans",
        "Köpeskilling": 489920,
        "Netto som begagnad": 489920,
        "Nybilspris": 2289000,
        "Ev kreditgivarens kreditgräns": 129063,
        "Avtalets löptid": 36,
        "Återköpspris": 960445,
        "Avdrag för hantering och adm": 0,
        "Avskrivning": 809035,
        "Avskrivning per månad": 22473,
        "Registreringsavgift": 0,
        "Ev rabatter": 0,
    },
    {
        "Bilnr": "KP20P267104",
        "Display": 2,
        "Fabrikat/Modell": "SCANIA R580",
        "Märke": "SCANIA",
        "Årsmodell": 2015,
        "Första reg.datum": "17-02-2015",
        "Ägaredatum": "23-05-2023",
        "Köpsdatum": "23-05-2023",
        "Registreringsnummer": "SOT11Z",
        "Typ": 4,
        "Biltyp": "Lastbil",
        "Typ av finansiering": "Volvofinans",
        "Finansiär": "Volvofinans",
        "Köpeskilling": 514749,
        "Netto som begagnad": 514749,
        "Nybilspris": 2289000,
        "Ev kreditgivarens kreditgräns": 98451,
        "Avtalets löptid": 36,
        "Återköpspris": 891384,
        "Avdrag för hantering och adm": 0,
        "Avskrivning": 882030,
        "Avskrivning per månad": 24390,
        "Registreringsavgift": 0,
        "Ev rabatter": 0,
    },
    {
        "Bilnr": "KP16H114995",
        "Display": 1,
        "Fabrikat/Modell": "SCANIA R580",
        "Märke": "SCANIA",
        "Årsmodell": 2015,
        "Första reg.datum": "20-02-2015",
        "Ägaredatum": "23-05-2023",
        "Köpsdatum": "23-05-2023",
        "Registreringsnummer": "XOG51W",
        "Typ": 4,
        "Biltyp": "Lastbil",
        "Typ av finansiering": "Volvofinans",
        "Finansiär": "Volvofinans",
        "Köpeskilling": 511996,
        "Netto som begagnad": 511996,
        "Nybilspris": 2289000,
        "Ev kreditgivarens kreditgräns": 99888,
        "Avtalets löptid": 36,
        "Återköpspris": 869729,
        "Avdrag för hantering och adm": 0,
        "Avskrivning": 907285,
        "Avskrivning per månad": 25202,
        "Registreringsavgift": 0,
        "Ev rabatter": 0,
    },
    {
        "Bilnr": "KP20P236184",
        "Display": 1,
        "Fabrikat/Modell": "SCANIA R580",
        "Märke": "SCANIA",
        "Årsmodell": 2015,
        "Första reg.datum": "03-03-2015",
        "Ägaredatum": "23-05-2023",
        "Köpsdatum": "23-05-2023",
        "Registreringsnummer": "XOG51W",
        "Typ": 4,
        "Biltyp": "Lastbil",
        "Typ av finansiering": "Volvofinans",
        "Finansiär": "Volvofinans",
        "Köpeskilling": 521578,
        "Netto som begagnad": 521578,
        "Nybilspris": 2289000,
        "Ev kreditgivarens kreditgräns": 107615,
        "Avtalets löptid": 36,
        "Återköpspris": 748551,
        "Avdrag för hantering och adm": 0,
        "Avskrivning": 1018835,
        "Avskrivning per månad": 28301,
        "Registreringsavgift": 0,
        "Ev rabatter": 0,
    },
]


def format_currency(value: Optional[int]) -> str:
    if value is None:
        return "-"
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return "-"
    return f"{numeric_value:,.0f} kr".replace(",", " ")


def first_of_month(dt: date) -> date:
    return date(dt.year, dt.month, 1)


def add_months(base_date: date, months: int) -> date:
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def build_forecast(rows: List[Dict[str, Any]], current_date: date, horizon_months: int = 12):
    months = [add_months(first_of_month(current_date), offset) for offset in range(horizon_months)]
    month_labels = [month.strftime("%Y-%m") for month in months]

    forecast_rows = []
    depreciation_totals = [0 for _ in months]

    for row in rows:
        try:
            registration_date = parse_date(str(row["Första reg.datum"]))
            months_in_term = int(row["Avtalets löptid"])
            monthly_depreciation = int(row["Avskrivning per månad"])
            net_price_new = int(row["Nybilspris"])
        except (KeyError, ValueError, TypeError):
            # Skip malformed rows to avoid breaking the admin dashboard
            continue

        values = []
        for idx, month in enumerate(months):
            months_since_registration = months_between(registration_date, month)
            if months_since_registration < 0 or months_since_registration > months_in_term:
                values.append(None)
                continue
            depreciated_value = max(net_price_new - monthly_depreciation * months_since_registration, 0)
            values.append(depreciated_value)
            depreciation_totals[idx] += monthly_depreciation

        forecast_rows.append({
            "asset": f"{row['Registreringsnummer']} ({row['Fabrikat/Modell']})",
            "monthly_values": values,
        })

    summary_row = [total if total else None for total in depreciation_totals]

    return {
        "months": month_labels,
        "rows": forecast_rows,
        "depreciation_totals": summary_row,
    }


app.jinja_env.filters["currency"] = format_currency


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
    admin_assets = PLACEHOLDER_ASSETS if session.get("role") == "admin" else []
    forecast = build_forecast(admin_assets, datetime.utcnow().date()) if admin_assets else None
    return render_template(
        "dashboard.html",
        inspections=inspections,
        search_query=q,
        asset_columns=ASSET_OVERVIEW_COLUMNS,
        admin_assets=admin_assets,
        forecast=forecast,
    )


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

    file_path = inspection.pdf_file_path
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
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


@app.route("/referral")
def referral_preview():
    """Static preview that mirrors the provided referral reward design."""
    return render_template("referral.html")

if __name__ == "__main__":
    app.run(debug=True)
