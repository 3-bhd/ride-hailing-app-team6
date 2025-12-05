# Task 3 — Waiting for Driver: Files & code snippets
# --------------------------------------------------
# This single file contains the code snippets you should add to your Flask project
# to implement Task 3: add estimated_time_minutes to `rides` table (migration)
# and add route /wait-driver/<ride_id> + template.
#
# Instructions:
# 1. Add `db.py` helpers (or merge with your existing db helper) to run migrations at startup.
# 2. Add the migration code that will ALTER TABLE if needed.
# 3. Add the Flask route `/wait-driver/<int:ride_id>` into your app (or blueprint).
# 4. Add the Jinja template `templates/wait_driver.html` to your templates folder.
# 5. Restart the app. The migration runs once at startup and will add the column if missing.

# ---------- db.py (or integrate into your existing db helper) ----------
# Place this as e.g. app/db.py or merge into your current database utilities.

import sqlite3
import os
from flask import g

DB_PATH = os.environ.get('SQLITE_DB', 'database.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def close_db(e=None):
    db = g.pop('_database', None)
    if db is not None:
        db.close()

def run_migrations():
    """Run simple migrations to ensure `estimated_time_minutes` column exists.
    This migration is safe to call multiple times.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # check if rides table exists first
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='rides'
    """)
    if cur.fetchone() is None:
        # If rides table doesn't exist at all, create a basic table (you may already have this elsewhere).
        cur.execute('''
            CREATE TABLE rides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger_id INTEGER,
                pickup_address TEXT,
                dropoff_address TEXT,
                pickup_lat REAL,
                pickup_lng REAL,
                dropoff_lat REAL,
                dropoff_lng REAL,
                estimated_fare REAL,
                status TEXT,
                created_at TEXT,
                estimated_time_minutes INTEGER
            )
        ''')
        conn.commit()
        conn.close()
        return

    # Check if column estimated_time_minutes exists
    cur.execute("PRAGMA table_info(rides)")
    columns = [r[1] for r in cur.fetchall()]  # second field is name
    if 'estimated_time_minutes' not in columns:
        # ALTER TABLE to add the column (SQLite supports ADD COLUMN)
        cur.execute("ALTER TABLE rides ADD COLUMN estimated_time_minutes INTEGER")
        conn.commit()

    conn.close()

# ---------- app.py additions (or your main Flask app) ----------
# Import and call run_migrations() early in your app startup (before serving requests)

# from flask import Flask, render_template, g, abort
# from db import get_db, close_db, run_migrations
#
# app = Flask(__name__)
#
# app.teardown_appcontext(close_db)
#
# # Run migrations at startup
# run_migrations()
#
# @app.route('/wait-driver/<int:ride_id>')
# def wait_driver(ride_id):
#     db = get_db()
#     cur = db.execute('SELECT * FROM rides WHERE id = ?', (ride_id,))
#     ride = cur.fetchone()
#     if ride is None:
#         abort(404)
#     # ride is a sqlite3.Row, accessible as ride['pickup_address'] etc.
#     return render_template('wait_driver.html', ride=ride)
#
# # Example: If you want to show how rides are created elsewhere in your app, ensure
# # that when you insert a new ride you can insert estimated_time_minutes (or leave NULL).
#
# # Example insert (used elsewhere when passenger submits ride):
# # db = get_db()
# # db.execute('''INSERT INTO rides (passenger_id, pickup_address, dropoff_address, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, estimated_fare, status, created_at, estimated_time_minutes)
# #               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)''',
# #            (passenger_id, pickup_address, dropoff_address, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, estimated_fare, 'requested', estimated_time_minutes))
# # db.commit()

# ---------- templates/wait_driver.html ----------
# Save this as templates/wait_driver.html in your Flask templates folder.

"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Waiting for Driver</title>
    <style>
      body { font-family: Arial, Helvetica, sans-serif; background:#f7f7f9; color:#222; }
      .card { max-width:700px; margin:60px auto; background:white; padding:24px; border-radius:12px; box-shadow:0 6px 18px rgba(0,0,0,0.06); }
      h1 { margin-top:0 }
      .addresses { display:flex; gap:12px; flex-direction:column; }
      .addr { padding:12px; border-radius:8px; background:#fbfbfd; border:1px solid #eee }
      .meta { margin-top:14px; color:#555 }
      .loader { margin:28px auto; width:80px; height:80px; position:relative }

      /* Simple spinning dots loader */
      .dot { width:16px; height:16px; border-radius:50%; background:#007bff; position:absolute; animation:spin 1s linear infinite }
      .dot:nth-child(2) { transform: rotate(120deg) translate(28px); animation-delay: -0.16s }
      .dot:nth-child(3) { transform: rotate(240deg) translate(28px); animation-delay: -0.32s }
      @keyframes spin { 0% { transform: rotate(0deg) translate(28px) } 100% { transform: rotate(360deg) translate(28px) } }

      .small { font-size:0.9rem; color:#666 }
      .center { text-align:center }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Waiting for Driver…</h1>
      <p class="small">Ride ID: {{ ride['id'] }}</p>

      <div class="addresses">
        <div class="addr">
          <strong>Pickup</strong>
          <div>{{ ride['pickup_address'] }}</div>
        </div>
        <div class="addr">
          <strong>Dropoff</strong>
          <div>{{ ride['dropoff_address'] }}</div>
        </div>
      </div>

      <div class="center">
        <div class="loader" aria-hidden="true">
          <div class="dot"></div>
          <div class="dot"></div>
          <div class="dot"></div>
        </div>
      </div>

      <div class="meta center">
        {% if ride['estimated_time_minutes'] %}
          <p>Estimated time for driver arrival: <strong>{{ ride['estimated_time_minutes'] }} minutes</strong></p>
        {% else %}
          <p>Estimated time for driver arrival: <strong>Pending</strong></p>
        {% endif %}

        <p class="small">Status: <strong>{{ ride['status'] or 'requested' }}</strong></p>
      </div>

    </div>
  </body>
</html>
"""

# ---------- Migration SQL (migration script) ----------
# Save as migrations/001_add_estimated_time_minutes.sql if you have a migration folder.

"""
-- 001_add_estimated_time_minutes.sql
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
-- Note: SQLite supports ADD COLUMN; this file is informative. The Python migration above is safer.
ALTER TABLE rides ADD COLUMN estimated_time_minutes INTEGER;
COMMIT;
PRAGMA foreign_keys=ON;
"""

# ---------- Notes & Integration checklist ----------
# - If your app already has a get_db / close_db / migrations mechanism, integrate run_migrations() into it.
# - The run_migrations() function is idempotent: it creates the rides table if missing, or adds the column if absent.
# - Ensure you call run_migrations() before the first request. For example:
#     if __name__ == '__main__':
#         run_migrations()
#         app.run(debug=True)
#   or call it at import-time in your application factory.
# - The route /wait-driver/<int:ride_id> loads the ride row and passes it to wait_driver.html template.
# - The template uses simple CSS loader and displays pickup/dropoff and estimated_time_minutes.

# ---------- Example: small integration snippet to drop into your existing app file ----------
"""
# in app.py (or wherever you register routes)
from flask import Flask, render_template, abort
from db import run_migrations, get_db, close_db

app = Flask(__name__)
app.teardown_appcontext(close_db)

# run migrations at startup
run_migrations()

@app.route('/wait-driver/<int:ride_id>')
def wait_driver(ride_id):
    db = get_db()
    cur = db.execute('SELECT * FROM rides WHERE id = ?', (ride_id,))
    ride = cur.fetchone()
    if ride is None:
        abort(404)
    return render_template('wait_driver.html', ride=ride)

# Example: start server
# if __name__ == '__main__':
#     app.run(debug=True)
"""

# ---------- End of file ----------
# If you want, I can now produce the minimal patch/diff for your repo, or paste the exact
# files in separate messages. Which would you prefer? (If you'd like the patch, say so.)
