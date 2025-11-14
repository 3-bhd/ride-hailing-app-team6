from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "CHANGE_ME"

DB_PATH = "database.db"


# ===============================
# DATABASE
# ===============================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with open("schema.sql", "r") as f:
        sql = f.read()
    conn = get_db()
    conn.executescript(sql)
    conn.commit()
    conn.close()


if not os.path.exists(DB_PATH):
    init_db()
else:
    init_db()


# ===============================
# HELPERS
# ===============================
def password_strong(pw):
    if len(pw) < 8:
        return False
    has_digit = any(c.isdigit() for c in pw)
    symbols = "!@#$%^&*()_+-=,."
    has_symbol = any(c in symbols for c in pw)
    return has_digit and has_symbol


def email_or_phone_exists(email, phone):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM users WHERE email = ? OR phone = ?", (email, phone)
    )
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


# ===============================
# BASIC ROUTE
# ===============================
@app.route("/")
def home():
    return render_template("base.html")


# ============================================================
# STORY 1 — PASSENGER REGISTRATION & LOGIN (YOUR PART)
# ============================================================

@app.route("/passenger/register", methods=["GET"])
def passenger_register_page():
    return render_template("passenger_register.html")


@app.route("/passenger/register", methods=["POST"])
def passenger_register_submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")

    if not name or not email or not phone or not password:
        return "Missing fields.", 400

    if not password_strong(password):
        return "Weak password. Must be >=8 chars, digit + symbol.", 400

    if email_or_phone_exists(email, phone):
        return "Email or phone already registered.", 400

    pw_hash = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO users (name, email, phone, password_hash, role)
           VALUES (?, ?, ?, ?, 'passenger')""",
        (name, email, phone, pw_hash)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    session["user_id"] = user_id
    session["role"] = "passenger"

    return redirect(url_for("home"))


@app.route("/passenger/login", methods=["GET"])
def passenger_login_page():
    return render_template("passenger_login.html")


@app.route("/passenger/login", methods=["POST"])
def passenger_login_submit():
    email = request.form.get("email").strip().lower()
    password = request.form.get("password")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password_hash, role FROM users WHERE email = ?", (email,)
    )
    user = cursor.fetchone()
    conn.close()

    if user is None:
        return "Invalid credentials.", 400

    if not check_password_hash(user["password_hash"], password):
        return "Invalid credentials.", 400

    session["user_id"] = user["id"]
    session["role"] = user["role"]

    if user["role"] == "driver":
        return redirect("/driver/dashboard")
    if user["role"] == "admin":
        return redirect("/admin/drivers")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ============================================================
# STORY 4 — DRIVER REGISTRATION (PLACEHOLDER FOR TEAM)
# ============================================================

@app.route("/driver/register", methods=["GET"])
def driver_register_page():
    return render_template("driver_register.html")


@app.route("/driver/register", methods=["POST"])
def driver_register_submit():
    # --------------------
    # Get Form Data
    # --------------------
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")
    license_number = request.form.get("license_number", "").strip()
    vehicle_info = request.form.get("vehicle_info", "").strip()

    # --------------------
    # Validation
    # --------------------
    if not all([name, email, phone, password, license_number, vehicle_info]):
        return "Missing fields.", 400

    if not password_strong(password):
        return "Weak password. Must be ≥8 chars, digit + symbol.", 400

    if email_or_phone_exists(email, phone):
        return "Email or phone already registered.", 400

    pw_hash = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor()

    # --------------------
    # Insert into users table
    # --------------------
    cursor.execute("""
        INSERT INTO users (name, email, phone, password_hash, role)
        VALUES (?, ?, ?, ?, 'driver')
    """, (name, email, phone, pw_hash))

    conn.commit()
    user_id = cursor.lastrowid

    # --------------------
    # Insert into drivers table
    # --------------------
    cursor.execute("""
        INSERT INTO drivers (user_id, license_number, vehicle_info, verification_status)
        VALUES (?, ?, ?, 'pending')
    """, (user_id, license_number, vehicle_info))

    conn.commit()
    conn.close()

    # --------------------
    # Log in driver immediately (no admin flow)
    # --------------------
    session["user_id"] = user_id
    session["role"] = "driver"

    return redirect("/driver/dashboard")




# ============================================================
# STORY 4 — ADMIN APPROVAL (PLACEHOLDER FOR TEAM)
# ============================================================

@app.route("/admin/drivers", methods=["GET"])
def admin_drivers_list():
    return "TODO: admin driver list (TEAM PART)", 501


@app.route("/admin/drivers/<int:driver_id>/approve", methods=["POST"])
def admin_approve(driver_id):
    return "TODO: admin approve (TEAM PART)", 501


@app.route("/admin/drivers/<int:driver_id>/reject", methods=["POST"])
def admin_reject(driver_id):
    return "TODO: admin reject (TEAM PART)", 501


# ============================================================
# STORY 5 — DRIVER DASHBOARD + TOGGLE (PARTLY YOURS LATER)
# ============================================================

@app.route("/driver/dashboard")
def driver_dashboard():
    return "TODO: dashboard (TEAM PART)", 501


@app.route("/driver/toggle", methods=["POST"])
def driver_toggle():
    return "TODO: toggle (OMAR LATER)", 501


# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
