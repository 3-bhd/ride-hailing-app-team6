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

    cursor = conn.cursor()

    # --- Migration: ensure rides table has estimated_time_minutes + driver_id columns ---
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rides'")
        if cursor.fetchone() is not None:
            cursor.execute("PRAGMA table_info(rides)")
            columns = [row[1] for row in cursor.fetchall()]  # row[1] is column name

            if "estimated_time_minutes" not in columns:
                cursor.execute("ALTER TABLE rides ADD COLUMN estimated_time_minutes INTEGER")

            if "driver_id" not in columns:
                cursor.execute("ALTER TABLE rides ADD COLUMN driver_id INTEGER")
    except sqlite3.Error as e:
        # If something goes wrong, just print it; do not break the app
        print(f"[init_db] Migration for rides extra columns failed: {e}")

    # Check if admin user exists, if not create one
    cursor.execute("SELECT id FROM users WHERE email = 'admin@ridehail.com'")
    admin_exists = cursor.fetchone()

    if not admin_exists:
        admin_password = generate_password_hash("Admin123!")
        cursor.execute(
            "INSERT INTO users (name, email, phone, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("Admin User", "admin@ridehail.com", "0000000000", admin_password, "admin"),
        )
        print("Admin user created: admin@ridehail.com / Admin123!")

    conn.commit()
    conn.close()


def get_current_driver():
    """
    Return the driver row (joined with user + status) for the logged-in driver, or None.
    """
    if "user_id" not in session or session.get("role") != "driver":
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            u.name,
            d.id AS driver_id,
            d.license_number,
            d.vehicle_info,
            d.verification_status,
            COALESCE(ds.is_online, 0) AS is_online
        FROM drivers d
        JOIN users u ON d.user_id = u.id
        LEFT JOIN driver_status ds ON ds.driver_id = d.id
        WHERE u.id = ?
        """,
        (session["user_id"],),
    )
    driver = cursor.fetchone()
    conn.close()
    return driver



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

def get_current_driver():
    """
    Return the driver row (joined with user) for the logged-in driver, or None.
    """
    if "user_id" not in session or session.get("role") != "driver":
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            u.name,
            d.id AS driver_id,
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
    return driver

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

    conn = get_db()
    cursor = conn.cursor()

    # Get passenger info
    cursor.execute("SELECT name, email FROM users WHERE id = ?", (session["user_id"],))
    passenger = cursor.fetchone()

    # Check if passenger already has an active ride
    cursor.execute(
        """
        SELECT id
        FROM rides
        WHERE passenger_id = ?
          AND status IN ('waiting', 'accepted', 'picked_up')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session["user_id"],),
    )
    active_ride = cursor.fetchone()

    # Fetch recent completed / cancelled rides for history
    cursor.execute(
        """
        SELECT
            r.*,
            u2.name AS driver_name
        FROM rides r
        LEFT JOIN drivers d ON r.driver_id = d.id
        LEFT JOIN users u2 ON d.user_id = u2.id
        WHERE r.passenger_id = ?
          AND r.status IN ('completed', 'cancelled')
        ORDER BY r.created_at DESC
        LIMIT 5
        """,
        (session["user_id"],),
    )
    recent_rides = cursor.fetchall()

    conn.close()

    if active_ride:
        # Redirect to waiting / status page if they already have a ride
        return redirect(url_for("wait_driver", ride_id=active_ride["id"]))

    return render_template(
        "passenger_dashboard.html",
        passenger=passenger,
        recent_rides=recent_rides,
    )




# ============================================================
# SPRINT 2 - TASK 1: Passenger Ride Request Form
# ============================================================

@app.route("/passenger/request-ride", methods=["POST"])
def passenger_request_ride():
    # Must be logged in as a passenger
    if "user_id" not in session or session.get("role") != "passenger":
        flash("Please log in as a passenger to request a ride.")
        return redirect(url_for("passenger_login_page"))

    conn = get_db()
    cursor = conn.cursor()

    # Do not allow a new request if passenger already has an active ride
    cursor.execute(
        """
        SELECT id
        FROM rides
        WHERE passenger_id = ?
          AND status IN ('waiting', 'accepted', 'picked_up')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session["user_id"],),
    )
    existing = cursor.fetchone()
    if existing:
        conn.close()
        flash("You already have an active ride. You must finish or cancel it before requesting another.")
        return redirect(url_for("wait_driver", ride_id=existing["id"]))

    # Get form data
    pickup_address = request.form.get("pickup_address", "").strip()
    dropoff_address = request.form.get("dropoff_address", "").strip()
    notes = request.form.get("notes", "").strip()

    # Get lat/lng from form (set by Leaflet + Nominatim JS)
    def parse_float(value):
        try:
            if not value:
                return None
            return float(value)
        except ValueError:
            return None

    pickup_lat = parse_float(request.form.get("pickup_lat"))
    pickup_lng = parse_float(request.form.get("pickup_lng"))
    dropoff_lat = parse_float(request.form.get("dropoff_lat"))
    dropoff_lng = parse_float(request.form.get("dropoff_lng"))

    if not pickup_address or not dropoff_address:
        conn.close()
        flash("Please enter both pickup and dropoff addresses.")
        return redirect(url_for("passenger_dashboard"))

    try:
        cursor.execute(
            """
            INSERT INTO rides (
                passenger_id,
                pickup_address,
                dropoff_address,
                pickup_lat,
                pickup_lng,
                dropoff_lat,
                dropoff_lng,
                notes,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'requested')
            """,
            (
                session["user_id"],
                pickup_address,
                dropoff_address,
                pickup_lat,
                pickup_lng,
                dropoff_lat,
                dropoff_lng,
                notes,
            ),
        )
        conn.commit()
        ride_id = cursor.lastrowid

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
    # Calculate distance and duration
    import math

    # 1) Distance (km)
    if ride["pickup_lat"] and ride["dropoff_lat"]:
        # Haversine straight-line distance
        lat1, lon1 = float(ride["pickup_lat"]), float(ride["pickup_lng"])
        lat2, lon2 = float(ride["dropoff_lat"]), float(ride["dropoff_lng"])

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        straight_distance = 6371 * c  # km

        # Approximate road distance as ~1.3x straight line, and clamp
        distance_km = round(max(1.0, min(straight_distance * 1.3, 40.0)), 1)
    else:
        # Fallback when we have no coordinates: assume a medium city trip
        distance_km = 7.0

    # 2) Duration (minutes) – assume ~3 minutes per km + 5 minutes overhead
    duration_min = round(distance_km * 3 + 5)

    # Store estimated time in the database for use on the waiting screen
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE rides SET estimated_time_minutes = ? WHERE id = ?",
            (duration_min, ride_id)
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"[fare_estimate] Failed to update estimated_time_minutes: {e}")

    # 3) Fare breakdown – more moderate pricing
    base_fare = 15.0             # starting fee
    per_km = 5.0                 # per km
    per_min = 0.3                # per minute in traffic
    service_fee = 3.0            # fixed platform fee

    distance_charge = distance_km * per_km
    duration_charge = duration_min * per_min
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


@app.route("/confirm-ride/<int:ride_id>", methods=["POST"])
def confirm_ride(ride_id):
    # Ensure passenger is logged in
    if "user_id" not in session or session.get("role") != "passenger":
        flash("Please log in first.")
        return redirect(url_for("passenger_login_page"))

    conn = get_db()
    cursor = conn.cursor()

    # Update ride status → waiting for driver
    cursor.execute(
        "UPDATE rides SET status = 'waiting' WHERE id = ?",
        (ride_id,)
    )
    conn.commit()
    conn.close()

    # Redirect passenger to waiting screen
    return redirect(url_for("wait_driver", ride_id=ride_id))


@app.route("/wait-driver/<int:ride_id>")
def wait_driver(ride_id):
    # Passenger must be logged in to view their ride status
    if "user_id" not in session or session.get("role") != "passenger":
        flash("Please log in as a passenger to view your ride.")
        return redirect(url_for("passenger_login_page"))

    conn = get_db()
    cursor = conn.cursor()

    # Get the ride for this passenger
    cursor.execute(
        "SELECT * FROM rides WHERE id = ? AND passenger_id = ?",
        (ride_id, session["user_id"]),
    )
    ride = cursor.fetchone()

    if not ride:
        conn.close()
        flash("Ride not found.")
        return redirect(url_for("passenger_dashboard"))

    # Default: no driver info
    driver = None

    # If a driver is assigned to this ride, load their info
    if "driver_id" in ride.keys() and ride["driver_id"]:
        cursor.execute(
            """
            SELECT
                u.name AS driver_name,
                d.vehicle_info AS vehicle_info,
                d.license_number AS license_number
            FROM drivers d
            JOIN users u ON d.user_id = u.id
            WHERE d.id = ?
            """,
            (ride["driver_id"],),
        )
        driver = cursor.fetchone()

    conn.close()

    return render_template("wait_driver.html", ride=ride, driver=driver)

@app.route("/passenger/rides/<int:ride_id>/cancel", methods=["POST"])
def passenger_cancel_ride(ride_id):
    # Must be logged in as a passenger
    if "user_id" not in session or session.get("role") != "passenger":
        flash("Please log in as a passenger to cancel a ride.")
        return redirect(url_for("passenger_login_page"))

    conn = get_db()
    cursor = conn.cursor()

    # Make sure this ride belongs to this passenger
    cursor.execute(
        """
        SELECT status
        FROM rides
        WHERE id = ? AND passenger_id = ?
        """,
        (ride_id, session["user_id"]),
    )
    ride = cursor.fetchone()

    if not ride:
        conn.close()
        flash("Ride not found.")
        return redirect(url_for("passenger_dashboard"))

    # Only allow cancellation if the ride is still in an active pre-trip state
    if ride["status"] in ("completed", "cancelled"):
        conn.close()
        flash("This ride is already finished.")
        return redirect(url_for("passenger_dashboard"))

    if ride["status"] == "picked_up":
        conn.close()
        flash("You cannot cancel a ride after being picked up.")
        return redirect(url_for("passenger_dashboard"))

    cursor.execute(
        "UPDATE rides SET status = 'cancelled' WHERE id = ?",
        (ride_id,),
    )
    conn.commit()
    conn.close()

    flash("Your ride has been cancelled.")
    return redirect(url_for("passenger_dashboard"))

    
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

    driver = get_current_driver()
    if driver is None:
        flash("Driver profile not found. Please complete registration.")
        return redirect(url_for("driver_register_page"))

    conn = get_db()
    cursor = conn.cursor()

    # One active ride per driver: accepted or picked_up
    cursor.execute(
        """
        SELECT *
        FROM rides
        WHERE driver_id = ?
          AND status IN ('accepted', 'picked_up')
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (driver["driver_id"],),
    )
    active_ride = cursor.fetchone()

    # Only show waiting requests if no active ride
    ride_requests = []
    if not active_ride:
        cursor.execute(
            """
            SELECT
                id,
                pickup_address,
                dropoff_address,
                pickup_lat,
                pickup_lng,
                dropoff_lat,
                dropoff_lng,
                estimated_time_minutes,
                created_at
            FROM rides
            WHERE status = 'waiting'
            ORDER BY created_at ASC
            """
        )
        ride_requests = cursor.fetchall()

    # Fetch recent completed / cancelled rides for this driver
    cursor.execute(
        """
        SELECT
            r.*,
            u.name AS passenger_name
        FROM rides r
        JOIN users u ON r.passenger_id = u.id
        WHERE r.driver_id = ?
          AND r.status IN ('completed', 'cancelled')
        ORDER BY r.created_at DESC
        LIMIT 5
        """,
        (driver["driver_id"],),
    )
    ride_history = cursor.fetchall()

    conn.close()

    return render_template(
        "driver_dashboard.html",
        driver=driver,
        active_ride=active_ride,
        ride_requests=ride_requests,
        ride_history=ride_history,
    )


@app.route("/driver/rides/<int:ride_id>/accept", methods=["POST"])
def driver_accept_ride(ride_id):
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver.")
        return redirect(url_for("passenger_login_page"))

    driver = get_current_driver()
    if driver is None:
        flash("Driver profile not found.")
        return redirect(url_for("driver_dashboard"))

    conn = get_db()
    cursor = conn.cursor()

    # Ensure driver has no active ride already
    cursor.execute(
        """
        SELECT id
        FROM rides
        WHERE driver_id = ?
          AND status IN ('accepted', 'picked_up')
        LIMIT 1
        """,
        (driver["driver_id"],),
    )
    existing = cursor.fetchone()
    if existing:
        conn.close()
        flash("You already have an active ride. Finish it before accepting a new one.")
        return redirect(url_for("driver_dashboard"))

    # Check ride still exists & is waiting
    cursor.execute("SELECT status FROM rides WHERE id = ?", (ride_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        flash("Ride not found.")
        return redirect(url_for("driver_dashboard"))

    if row["status"] != "waiting":
        conn.close()
        flash("Ride has already been taken or is not available.")
        return redirect(url_for("driver_dashboard"))

    # Mark as accepted and assign this driver
    cursor.execute(
        "UPDATE rides SET status = 'accepted', driver_id = ? WHERE id = ?",
        (driver["driver_id"], ride_id),
    )
    conn.commit()
    conn.close()

    flash(f"Ride #{ride_id} accepted successfully.")
    return redirect(url_for("driver_dashboard"))




@app.route("/driver/rides/<int:ride_id>/reject", methods=["POST"])
def driver_reject_ride(ride_id):
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver.")
        return redirect(url_for("passenger_login_page"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM rides WHERE id = ?", (ride_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        flash("Ride not found.")
        return redirect(url_for("driver_dashboard"))

    if row["status"] != "waiting":
        conn.close()
        flash("Ride is no longer available.")
        return redirect(url_for("driver_dashboard"))

    cursor.execute("UPDATE rides SET status = 'cancelled' WHERE id = ?", (ride_id,))
    conn.commit()
    conn.close()

    flash(f"Ride #{ride_id} rejected.")
    return redirect(url_for("driver_dashboard"))


@app.route("/driver/rides/<int:ride_id>/cancel", methods=["POST"])
def driver_cancel_ride(ride_id):
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver.")
        return redirect(url_for("passenger_login_page"))

    driver = get_current_driver()
    if driver is None:
        flash("Driver profile not found.")
        return redirect(url_for("driver_dashboard"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT status
        FROM rides
        WHERE id = ? AND driver_id = ?
        """,
        (ride_id, driver["driver_id"]),
    )
    ride = cursor.fetchone()

    if not ride:
        conn.close()
        flash("Ride not found or not assigned to you.")
        return redirect(url_for("driver_dashboard"))

    if ride["status"] not in ("accepted", "picked_up"):
        conn.close()
        flash("Ride is no longer active.")
        return redirect(url_for("driver_dashboard"))

    cursor.execute("UPDATE rides SET status = 'cancelled' WHERE id = ?", (ride_id,))
    conn.commit()
    conn.close()

    flash(f"Ride #{ride_id} has been cancelled.")
    return redirect(url_for("driver_dashboard"))


@app.route("/driver/rides/<int:ride_id>/picked-up", methods=["POST"])
def driver_picked_up(ride_id):
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver.")
        return redirect(url_for("passenger_login_page"))

    driver = get_current_driver()
    if driver is None:
        flash("Driver profile not found.")
        return redirect(url_for("driver_dashboard"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT status
        FROM rides
        WHERE id = ? AND driver_id = ?
        """,
        (ride_id, driver["driver_id"]),
    )
    ride = cursor.fetchone()

    if not ride:
        conn.close()
        flash("Ride not found or not assigned to you.")
        return redirect(url_for("driver_dashboard"))

    if ride["status"] != "accepted":
        conn.close()
        flash("Ride is not in 'accepted' state.")
        return redirect(url_for("driver_dashboard"))

    cursor.execute("UPDATE rides SET status = 'picked_up' WHERE id = ?", (ride_id,))
    conn.commit()
    conn.close()

    flash(f"Ride #{ride_id} marked as picked up.")
    return redirect(url_for("driver_dashboard"))


@app.route("/driver/rides/<int:ride_id>/complete", methods=["POST"])
def driver_complete_ride(ride_id):
    if "user_id" not in session or session.get("role") != "driver":
        flash("Please log in as a driver.")
        return redirect(url_for("passenger_login_page"))

    driver = get_current_driver()
    if driver is None:
        flash("Driver profile not found.")
        return redirect(url_for("driver_dashboard"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT status
        FROM rides
        WHERE id = ? AND driver_id = ?
        """,
        (ride_id, driver["driver_id"]),
    )
    ride = cursor.fetchone()

    if not ride:
        conn.close()
        flash("Ride not found or not assigned to you.")
        return redirect(url_for("driver_dashboard"))

    if ride["status"] not in ("accepted", "picked_up"):
        conn.close()
        flash("Ride is not active.")
        return redirect(url_for("driver_dashboard"))

    cursor.execute("UPDATE rides SET status = 'completed' WHERE id = ?", (ride_id,))
    conn.commit()
    conn.close()

    flash(f"Ride #{ride_id} marked as completed.")
    return redirect(url_for("driver_dashboard"))


@app.route("/driver/requests", methods=["GET"])
def driver_requests():
    return redirect(url_for("driver_dashboard"))



# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
