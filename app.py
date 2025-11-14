from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "CHANGE_ME"

DB_PATH = "database.db"

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'jfif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


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

    # Check if admin user exists, if not create one
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = 'admin@ridehail.com'")
    admin_exists = cursor.fetchone()

    if not admin_exists:
        admin_password = generate_password_hash("Admin123!")
        cursor.execute(
            "INSERT INTO users (name, email, phone, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("Admin User", "admin@ridehail.com", "0000000000", admin_password, "admin")
        )
        print("Admin user created: admin@ridehail.com / Admin123!")

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


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, folder):
    if file and allowed_file(file.filename):
        # Generate unique filename to prevent conflicts
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        filename = secure_filename(unique_filename)
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder)

        # Create subdirectory if it doesn't exist
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder, filename)
        full_path = os.path.join(folder_path, filename)
        file.save(full_path)
        return file_path
    return None


# ===============================
# BASIC ROUTE
# ===============================
@app.route("/")
def home():
    return render_template("base.html")


# Route to serve uploaded files
@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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

    if user["role"] == "admin":
        return redirect("/admin/drivers")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ============================================================
# STORY 4 — DRIVER REGISTRATION (TASK A - COMPLETE WITH FILE UPLOADS)
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
        flash("All fields are required.")
        return redirect("/driver/register")

    if not password_strong(password):
        flash("Weak password. Must be at least 8 characters with at least one digit and one symbol.")
        return redirect("/driver/register")

    if email_or_phone_exists(email, phone):
        flash("Email or phone number already registered.")
        return redirect("/driver/register")

    # Check if files were uploaded
    if 'id_document' not in request.files or 'license_document' not in request.files or 'vehicle_document' not in request.files:
        flash("Please upload all required documents.")
        return redirect("/driver/register")

    id_document = request.files['id_document']
    license_document = request.files['license_document']
    vehicle_document = request.files['vehicle_document']

    if id_document.filename == '' or license_document.filename == '' or vehicle_document.filename == '':
        flash("Please select all required documents.")
        return redirect("/driver/register")

    # --------------------
    # Save uploaded files
    # --------------------
    id_doc_path = save_uploaded_file(id_document, 'id_documents')
    license_doc_path = save_uploaded_file(license_document, 'license_documents')
    vehicle_doc_path = save_uploaded_file(vehicle_document, 'vehicle_documents')

    if not all([id_doc_path, license_doc_path, vehicle_doc_path]):
        flash("Invalid file type. Allowed formats: PDF, PNG, JPG, JPEG")
        return redirect("/driver/register")

    pw_hash = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor()

    try:
        # --------------------
        # Insert into users table
        # --------------------
        cursor.execute("""
            INSERT INTO users (name, email, phone, password_hash, role)
            VALUES (?, ?, ?, ?, 'driver')
        """, (name, email, phone, pw_hash))

        user_id = cursor.lastrowid

        # --------------------
        # Insert into drivers table WITH FILE PATHS
        # --------------------
        cursor.execute("""
            INSERT INTO drivers (user_id, license_number, vehicle_info, 
                               id_doc_path, license_doc_path, vehicle_doc_path, 
                               verification_status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (user_id, license_number, vehicle_info,
              id_doc_path, license_doc_path, vehicle_doc_path))

        conn.commit()

        flash("Driver registration submitted successfully! Waiting for admin approval.")
        return redirect("/")

    except Exception as e:
        conn.rollback()
        # Clean up uploaded files if database operation fails
        for file_path in [id_doc_path, license_doc_path, vehicle_doc_path]:
            if file_path and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], file_path)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file_path))
        flash(f"Registration failed: {str(e)}")
        return redirect("/driver/register")

    finally:
        conn.close()


# ============================================================
# STORY 4 — ADMIN APPROVAL (TASK B - COMPLETE IMPLEMENTATION)
# ============================================================

@app.route("/admin/drivers", methods=["GET"])
def admin_drivers_list():
    # Check if user is admin
    if session.get("role") != "admin":
        return "Access denied. Admin privileges required.", 403

    conn = get_db()
    cursor = conn.cursor()

    # Get pending drivers
    cursor.execute("""
        SELECT d.id as driver_id, u.name, u.email, u.phone, d.license_number, 
               d.vehicle_info, d.id_doc_path, d.license_doc_path, d.vehicle_doc_path,
               d.verification_status
        FROM drivers d
        JOIN users u ON d.user_id = u.id
        WHERE d.verification_status = 'pending'
    """)
    pending_drivers = cursor.fetchall()

    # Get approved drivers
    cursor.execute("""
        SELECT d.id as driver_id, u.name, u.email, u.phone, d.license_number, 
               d.vehicle_info, d.verification_status
        FROM drivers d
        JOIN users u ON d.user_id = u.id
        WHERE d.verification_status = 'approved'
    """)
    approved_drivers = cursor.fetchall()

    # Get rejected drivers
    cursor.execute("""
        SELECT d.id as driver_id, u.name, u.email, u.phone, d.license_number, 
               d.vehicle_info, d.verification_status
        FROM drivers d
        JOIN users u ON d.user_id = u.id
        WHERE d.verification_status = 'rejected'
    """)
    rejected_drivers = cursor.fetchall()

    conn.close()

    return render_template("admin_drivers.html",
                           pending_drivers=pending_drivers,
                           approved_drivers=approved_drivers,
                           rejected_drivers=rejected_drivers)


@app.route("/admin/drivers/<int:driver_id>/approve", methods=["POST"])
def admin_approve(driver_id):
    if session.get("role") != "admin":
        return "Access denied.", 403

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE drivers 
            SET verification_status = 'approved' 
            WHERE id = ?
        """, (driver_id,))

        conn.commit()
        flash(f"Driver #{driver_id} has been approved successfully!")

    except Exception as e:
        conn.rollback()
        flash(f"Error approving driver: {str(e)}")

    finally:
        conn.close()

    return redirect("/admin/drivers")


@app.route("/admin/drivers/<int:driver_id>/reject", methods=["POST"])
def admin_reject(driver_id):
    if session.get("role") != "admin":
        return "Access denied.", 403

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE drivers 
            SET verification_status = 'rejected' 
            WHERE id = ?
        """, (driver_id,))

        conn.commit()
        flash(f"Driver #{driver_id} has been rejected.")

    except Exception as e:
        conn.rollback()
        flash(f"Error rejecting driver: {str(e)}")

    finally:
        conn.close()

    return redirect("/admin/drivers")


# ============================================================
# STORY 5 — DRIVER DASHBOARD + TOGGLE (PLACEHOLDER FOR TEAM)
# ============================================================

@app.route("/driver/dashboard", methods=["GET"])
def driver_dashboard():
    # Must be logged in as a driver
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver to access your dashboard.")
        return redirect(url_for("passenger_login_submit"))  # or your login page route

    conn = get_db()
    cursor = conn.cursor()

    # Get the driver linked to this logged-in user
    cursor.execute("""
        SELECT 
            u.name,
            d.id              AS driver_id,
            d.license_number,
            d.vehicle_info,
            d.verification_status,
            COALESCE(d.is_online, 0) AS is_online
        FROM drivers d
        JOIN users u ON d.user_id = u.id
        WHERE u.id = ?
    """, (session["user_id"],))
    driver = cursor.fetchone()
    conn.close()

    if driver is None:
        flash("Driver profile not found. Please complete your registration first.")
        return redirect(url_for("driver_register_page"))

    return render_template("driver_dashboard.html", driver=driver)


@app.route("/driver/toggle", methods=["POST"])
def driver_toggle():
    # This is just a safe placeholder; Omar will add the real logic.
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver first.")
        return redirect(url_for("passenger_login_submit"))

    # TODO (Omar): flip is_online, store timestamps, etc.
    flash("Online/Offline toggle backend will be implemented soon.")
    return redirect(url_for("driver_dashboard"))

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
