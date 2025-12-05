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
    return render_template("home.html")


# Route to serve uploaded files
@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))

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

    # Validate required fields
    if not all([name, email, phone, password]):
        flash("All fields are required.")
        return redirect(url_for("passenger_register_page"))

    # Password strength
    if not password_strong(password):
        flash("Weak password. Password must be at least 8 characters and include a digit and a symbol.")
        return redirect(url_for("passenger_register_page"))

    # Unique email / phone
    if email_or_phone_exists(email, phone):
        flash("Email or phone number already registered.")
        return redirect(url_for("passenger_register_page"))

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
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password_hash, role FROM users WHERE email = ?", (email,)
    )
    user = cursor.fetchone()
    conn.close()

    # Invalid email or password
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.")
        return redirect(url_for("passenger_login_page"))

        # Save session
    session["user_id"] = user["id"]
    session["role"] = user["role"]

    # Redirect by role
    if user["role"] == "admin":
        return redirect(url_for("admin_drivers_list"))
    elif user["role"] == "driver":
        return redirect(url_for("driver_dashboard"))
    else:  # passenger
        return redirect(url_for("passenger_dashboard"))


@app.route("/passenger/dashboard", methods=["GET", "POST"])
def passenger_dashboard():
    # Must be logged in as a passenger
    if "user_id" not in session or session.get("role") != "passenger":
        flash("Please log in as a passenger to access your dashboard.")
        return redirect(url_for("passenger_login_page"))

    # Get passenger info
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM users WHERE id = ?", (session["user_id"],))
    passenger = cursor.fetchone()
    conn.close()

    return render_template("passenger_dashboard.html", passenger=passenger)


# ============================================================
# SPRINT 2 - TASK 1: Passenger Ride Request Form
# ============================================================

@app.route("/passenger/request-ride", methods=["POST"])
def passenger_request_ride():
    # Must be logged in as a passenger
    if "user_id" not in session or session.get("role") != "passenger":
        flash("Please log in as a passenger to request a ride.")
        return redirect(url_for("passenger_login_page"))

    # Get form data
    pickup_address = request.form.get("pickup_address", "").strip()
    dropoff_address = request.form.get("dropoff_address", "").strip()
    notes = request.form.get("notes", "").strip()

    # Get lat/lng (currently empty, will be filled by Google Places later)
    pickup_lat = request.form.get("pickup_lat", "").strip() or "29.9759"  # Default: AUC coordinates
    pickup_lng = request.form.get("pickup_lng", "").strip() or "31.2839"
    dropoff_lat = request.form.get("dropoff_lat", "").strip() or "30.0596"  # Default: Zamalek
    dropoff_lng = request.form.get("dropoff_lng", "").strip() or "31.2237"

    # Validate required fields
    if not pickup_address or not dropoff_address:
        flash("Please enter both pickup and dropoff addresses.")
        return redirect(url_for("passenger_dashboard"))

    # Save to database
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
                       INSERT INTO rides (passenger_id, pickup_address, dropoff_address,
                                          pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
                                          notes, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'requested')
                       """, (session["user_id"], pickup_address, dropoff_address,
                             pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, notes))

        ride_id = cursor.lastrowid
        conn.commit()

        flash("Ride request submitted successfully!")
        return redirect(url_for("fare_estimate", ride_id=ride_id))

    except Exception as e:
        conn.rollback()
        flash(f"Error submitting ride request: {str(e)}")
        return redirect(url_for("passenger_dashboard"))

    finally:
        conn.close()


@app.route("/fare-estimate/<int:ride_id>")
def fare_estimate(ride_id):
    # Must be logged in as a passenger
    if "user_id" not in session or session.get("role") != "passenger":
        flash("Please log in as a passenger.")
        return redirect(url_for("passenger_login_page"))

    # Get ride from database
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, u.name as passenger_name
        FROM rides r
        JOIN users u ON r.passenger_id = u.id
        WHERE r.id = ? AND r.passenger_id = ?
    """, (ride_id, session["user_id"]))
    
    ride = cursor.fetchone()
    conn.close()

    if not ride:
        flash("Ride not found.")
        return redirect(url_for("passenger_dashboard"))

    # Calculate fake distance and duration
    import random
    import math
    
    # Generate realistic distance based on lat/lng if available
    if ride["pickup_lat"] and ride["dropoff_lat"]:
        # Simple haversine formula approximation
        lat1, lon1 = float(ride["pickup_lat"]), float(ride["pickup_lng"])
        lat2, lon2 = float(ride["dropoff_lat"]), float(ride["dropoff_lng"])
        
        # Approximate distance in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_km = round(6371 * c, 1)  # Earth radius in km
    else:
        # Fallback to random distance
        distance_km = round(random.uniform(3.0, 15.0), 1)
    
    # Calculate duration based on distance (approx 4 minutes per km + traffic)
    duration_min = round(distance_km * 4 + random.uniform(5, 15))
    
    # Calculate fare breakdown
    base_fare = 25.0
    distance_charge = distance_km * 8.0
    duration_charge = duration_min * 0.5
    service_fee = 5.0
    total_fare = round(base_fare + distance_charge + duration_charge + service_fee, 2)
    
    fare_estimate = {
        'distance_km': distance_km,
        'duration_min': duration_min,
        'base_fare': base_fare,
        'distance_charge': round(distance_charge, 2),
        'duration_charge': round(duration_charge, 2),
        'service_fee': service_fee,
        'total_fare': total_fare
    }
    
    return render_template("fare_estimate.html", 
                         ride=ride, 
                         fare_estimate=fare_estimate)

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
    # Only admins can access this page
    if session.get("role") != "admin":
        return render_template("access_denied.html"), 403

    conn = get_db()
    cursor = conn.cursor()

    # Pending drivers
    cursor.execute("""
                   SELECT d.id as driver_id,
                          u.name,
                          u.email,
                          u.phone,
                          d.license_number,
                          d.vehicle_info,
                          d.id_doc_path,
                          d.license_doc_path,
                          d.vehicle_doc_path,
                          d.verification_status
                   FROM drivers d
                            JOIN users u ON d.user_id = u.id
                   WHERE d.verification_status = 'pending'
                   """)
    pending_drivers = cursor.fetchall()

    # Approved drivers
    cursor.execute("""
                   SELECT d.id as driver_id,
                          u.name,
                          u.email,
                          u.phone,
                          d.license_number,
                          d.vehicle_info,
                          d.verification_status
                   FROM drivers d
                            JOIN users u ON d.user_id = u.id
                   WHERE d.verification_status = 'approved'
                   """)
    approved_drivers = cursor.fetchall()

    # Rejected drivers
    cursor.execute("""
                   SELECT d.id as driver_id,
                          u.name,
                          u.email,
                          u.phone,
                          d.license_number,
                          d.vehicle_info,
                          d.verification_status
                   FROM drivers d
                            JOIN users u ON d.user_id = u.id
                   WHERE d.verification_status = 'rejected'
                   """)
    rejected_drivers = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_drivers.html",
        pending_drivers=pending_drivers,
        approved_drivers=approved_drivers,
        rejected_drivers=rejected_drivers,
    )


@app.route("/admin/drivers/<int:driver_id>/approve", methods=["POST"])
def admin_approve(driver_id):
    if session.get("role") != "admin":
        return render_template("access_denied.html"), 403

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
                       UPDATE drivers
                       SET verification_status = 'approved'
                       WHERE id = ?
                       """, (driver_id,))
        conn.commit()
        flash(f"Driver #{driver_id} has been approved.")
    except Exception as e:
        conn.rollback()
        flash(f"Error approving driver: {str(e)}")
    finally:
        conn.close()

    return redirect(url_for("admin_drivers_list"))


@app.route("/admin/drivers/<int:driver_id>/reject", methods=["POST"])
def admin_reject(driver_id):
    if session.get("role") != "admin":
        return render_template("access_denied.html"), 403

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

    return redirect(url_for("admin_drivers_list"))


# ============================================================
# STORY 5 — DRIVER DASHBOARD + TOGGLE (PLACEHOLDER FOR TEAM)
# ============================================================

@app.route("/driver/dashboard", methods=["GET"])
def driver_dashboard():
    # Must be logged in as a driver
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver to access your dashboard.")
        return redirect(url_for("passenger_login_page"))

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
                       COALESCE(ds.is_online, 0) AS is_online
                   FROM drivers d
                            JOIN users u ON d.user_id = u.id
                            LEFT JOIN driver_status ds ON ds.driver_id = d.id
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
    # Must be logged in as a driver
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver to change your status.")
        return redirect(url_for("passenger_login_page"))

    conn = get_db()
    cursor = conn.cursor()

    # Get driver row + current status
    cursor.execute("""
                   SELECT
                       d.id AS driver_id,
                       d.verification_status,
                       COALESCE(ds.is_online, 0) AS is_online
                   FROM drivers d
                            JOIN users u ON d.user_id = u.id
                            LEFT JOIN driver_status ds ON ds.driver_id = d.id
                   WHERE u.id = ?
                   """, (session["user_id"],))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Driver profile not found. Please complete your registration first.")
        return redirect(url_for("driver_register_page"))

    # Must be approved before toggling
    if row["verification_status"] != "approved":
        conn.close()
        flash("You must be approved by an admin before going online.")
        return redirect(url_for("driver_dashboard"))

    driver_id = row["driver_id"]
    current_online = row["is_online"] or 0
    new_online = 0 if current_online else 1

    # Ensure a driver_status row exists, then update or insert
    cursor.execute("SELECT id FROM driver_status WHERE driver_id = ?", (driver_id,))
    status_row = cursor.fetchone()

    if status_row is None:
        cursor.execute("""
                       INSERT INTO driver_status (driver_id, is_online, last_change)
                       VALUES (?, ?, CURRENT_TIMESTAMP)
                       """, (driver_id, new_online))
    else:
        cursor.execute("""
                       UPDATE driver_status
                       SET is_online = ?,
                           last_change = CURRENT_TIMESTAMP
                       WHERE driver_id = ?
                       """, (new_online, driver_id))

    conn.commit()
    conn.close()

    flash(f"You are now {'Online' if new_online else 'Offline'}.")
    return redirect(url_for("driver_dashboard"))

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(debug=True)