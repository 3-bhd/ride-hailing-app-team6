# U-Ride — Ride-Hailing Management System

Full-stack ride-hailing platform built with Python Flask, SQLite, and Jinja2 using Agile/Scrum methodology.

---

## Overview

U-Ride is a multi-role ride-hailing management system that handles the full lifecycle of ride requests — from passenger and driver registration through to ride matching, booking, and trip management. The system was built across two Agile sprints, delivering a working prototype with role-based access control, driver verification, and a complete admin dashboard.

> A live demo was previously deployed on Railway. The full system can be run locally using the instructions below.

---

## Features

- Passenger registration, login, and ride request dashboard
- Driver registration with document upload and verification workflow
- Admin dashboard for approving/rejecting driver applications
- Driver online/offline availability toggle
- Ride matching and trip lifecycle management
- Role-based access control across all user types
- Full session management and secure password hashing

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Flask |
| Database | SQLite |
| Frontend | HTML, CSS, Jinja2 |
| Auth | Session-based, Werkzeug password hashing |
| Project Management | Jira (Scrum), GitHub |

---

## Sprints

### Sprint 1
- User Story 1: Passenger registration and login
- User Story 4: Driver registration and document upload
- User Story 5: Driver online/offline status toggle

### Sprint 2
- User Story 2: Ride request and matching
- User Story 3: Trip lifecycle management
- User Story 6: Additional platform features

All 16 story points delivered on time with zero spillover in Sprint 1.

---

## Installation
```bash
pip install -r requirements.txt
python -c "from app import init_db; init_db()"
python app.py
```

Then open `http://127.0.0.1:5000/` in your browser.

---

## System Roles

| Role | Capabilities |
|------|-------------|
| Passenger | Register, login, request rides, view trip status |
| Driver | Register, upload documents, toggle availability, manage trips |
| Admin | View and approve/reject driver applications |

---

## Repository

[github.com/3-bhd/ride-hailing-app-team6](https://github.com/3-bhd/ride-hailing-app-team6)

---

## Authors

- **Omar Abdelhady** — [@3-bhd](https://github.com/3-bhd) — Backend architecture, authentication, database design, Scrum Master & Product Owner
- **Janna Osama** — [@Jannaosama](https://github.com/Jannaosama)
- **George Christo** — [@georgechristo-ctrl](https://github.com/georgechristo-ctrl)
- **Farida Elanany** — [@faridaelanany](https://github.com/faridaelanany)
- **Abdelrahman Eid** — [@Abdelrahman-233](https://github.com/Abdelrahman-233)

The American University in Cairo — Software Engineering Course
