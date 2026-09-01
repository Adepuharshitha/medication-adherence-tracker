import sqlite3
import hashlib
import os
from datetime import datetime, date
import pytz

DB_PATH = "med_adherence.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('patient', 'caregiver', 'doctor')),
            full_name TEXT NOT NULL,
            email TEXT,
            timezone TEXT DEFAULT 'UTC',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Caregiver-Patient relationships
    c.execute("""
        CREATE TABLE IF NOT EXISTS caregiver_patient (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caregiver_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            FOREIGN KEY(caregiver_id) REFERENCES users(id),
            FOREIGN KEY(patient_id) REFERENCES users(id),
            UNIQUE(caregiver_id, patient_id)
        )
    """)

    # Medications table
    c.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            frequency TEXT NOT NULL,
            times_per_day INTEGER DEFAULT 1,
            instructions TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            prescribed_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(patient_id) REFERENCES users(id)
        )
    """)

    # Medication logs table
    c.execute("""
        CREATE TABLE IF NOT EXISTS medication_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            scheduled_date TEXT NOT NULL,
            scheduled_time TEXT,
            taken_at TEXT,
            status TEXT NOT NULL CHECK(status IN ('taken', 'missed', 'skipped')),
            dose_number INTEGER DEFAULT 1,
            notes TEXT,
            logged_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(medication_id) REFERENCES medications(id),
            FOREIGN KEY(patient_id) REFERENCES users(id)
        )
    """)

    # Reminders table
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            medication_id INTEGER NOT NULL,
            reminder_time TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            message TEXT,
            FOREIGN KEY(patient_id) REFERENCES users(id),
            FOREIGN KEY(medication_id) REFERENCES medications(id)
        )
    """)

    # AI chat history
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()

    # Seed demo users
    _seed_demo_data(conn)
    conn.close()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _seed_demo_data(conn):
    c = conn.cursor()

    demo_users = [
        ("patient1", "pass123", "patient", "Alice Johnson", "alice@example.com"),
        ("patient2", "pass123", "patient", "Bob Smith", "bob@example.com"),
        ("caregiver1", "pass123", "caregiver", "Carol White", "carol@example.com"),
        ("doctor1", "pass123", "doctor", "Dr. David Brown", "david@example.com"),
    ]

    user_ids = {}
    for username, password, role, full_name, email in demo_users:
        existing = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not existing:
            c.execute(
                "INSERT INTO users (username, password_hash, role, full_name, email) VALUES (?,?,?,?,?)",
                (username, _hash_password(password), role, full_name, email),
            )
            user_ids[username] = c.lastrowid
        else:
            user_ids[username] = existing["id"]

    conn.commit()

    # Assign patients to caregiver and doctor
    for patient_key in ["patient1", "patient2"]:
        for caregiver_key in ["caregiver1", "doctor1"]:
            try:
                c.execute(
                    "INSERT INTO caregiver_patient (caregiver_id, patient_id) VALUES (?,?)",
                    (user_ids[caregiver_key], user_ids[patient_key]),
                )
            except Exception:
                pass

    conn.commit()

    # Seed medications for patient1
    p1_id = user_ids["patient1"]
    meds = [
        (p1_id, "Metformin", "500mg", "Twice daily", 2, "Take with meals", "2024-01-01", None, "Dr. David Brown"),
        (p1_id, "Lisinopril", "10mg", "Once daily", 1, "Take in the morning", "2024-01-01", None, "Dr. David Brown"),
        (p1_id, "Atorvastatin", "20mg", "Once daily", 1, "Take at bedtime", "2024-01-15", None, "Dr. David Brown"),
    ]
    med_ids = []
    for med in meds:
        existing = c.execute(
            "SELECT id FROM medications WHERE patient_id=? AND name=?", (med[0], med[1])
        ).fetchone()
        if not existing:
            c.execute(
                """INSERT INTO medications
                   (patient_id, name, dosage, frequency, times_per_day, instructions, start_date, end_date, prescribed_by)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                med,
            )
            med_ids.append(c.lastrowid)
        else:
            med_ids.append(existing["id"])

    conn.commit()

    # Seed 30 days of logs for patient1
    import random
    today = date.today()
    for day_offset in range(29, -1, -1):
        from datetime import timedelta
        log_date = today - timedelta(days=day_offset)
        log_date_str = log_date.isoformat()
        for med_id in med_ids:
            med = c.execute("SELECT times_per_day FROM medications WHERE id=?", (med_id,)).fetchone()
            if not med:
                continue
            for dose_num in range(1, med["times_per_day"] + 1):
                existing = c.execute(
                    "SELECT id FROM medication_logs WHERE medication_id=? AND scheduled_date=? AND dose_number=?",
                    (med_id, log_date_str, dose_num),
                ).fetchone()
                if not existing:
                    # 85% adherence rate for demo
                    status = random.choices(["taken", "missed", "skipped"], weights=[85, 10, 5])[0]
                    c.execute(
                        """INSERT INTO medication_logs
                           (medication_id, patient_id, scheduled_date, status, dose_number)
                           VALUES (?,?,?,?,?)""",
                        (med_id, p1_id, log_date_str, status, dose_num),
                    )
    conn.commit()


# ── Auth ─────────────────────────────────────────────────────────────────────

def authenticate_user(username: str, password: str):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username, _hash_password(password)),
    ).fetchone()
    conn.close()
    return dict(user) if user else None


def register_user(username, password, role, full_name, email=""):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, email) VALUES (?,?,?,?,?)",
            (username, _hash_password(password), role, full_name, email),
        )
        conn.commit()
        return True, "Registration successful!"
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


# ── Medications ───────────────────────────────────────────────────────────────

def get_medications(patient_id, active_only=True):
    conn = get_connection()
    query = "SELECT * FROM medications WHERE patient_id=?"
    params = [patient_id]
    if active_only:
        query += " AND is_active=1"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_medication(patient_id, name, dosage, frequency, times_per_day, instructions, start_date, end_date, prescribed_by):
    conn = get_connection()
    conn.execute(
        """INSERT INTO medications
           (patient_id, name, dosage, frequency, times_per_day, instructions, start_date, end_date, prescribed_by)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (patient_id, name, dosage, frequency, times_per_day, instructions, start_date, end_date, prescribed_by),
    )
    conn.commit()
    conn.close()


def deactivate_medication(med_id):
    conn = get_connection()
    conn.execute("UPDATE medications SET is_active=0 WHERE id=?", (med_id,))
    conn.commit()
    conn.close()


# ── Logs ──────────────────────────────────────────────────────────────────────

def log_medication(medication_id, patient_id, scheduled_date, status, dose_number=1, notes="", scheduled_time=""):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM medication_logs WHERE medication_id=? AND scheduled_date=? AND dose_number=?",
        (medication_id, scheduled_date, dose_number),
    ).fetchone()
    taken_at = datetime.now().isoformat() if status == "taken" else None
    if existing:
        conn.execute(
            "UPDATE medication_logs SET status=?, taken_at=?, notes=?, logged_at=datetime('now') WHERE id=?",
            (status, taken_at, notes, existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO medication_logs
               (medication_id, patient_id, scheduled_date, scheduled_time, taken_at, status, dose_number, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (medication_id, patient_id, scheduled_date, scheduled_time, taken_at, status, dose_number, notes),
        )
    conn.commit()
    conn.close()


def get_logs(patient_id, days=30):
    conn = get_connection()
    rows = conn.execute(
        """SELECT ml.*, m.name as med_name, m.dosage
           FROM medication_logs ml
           JOIN medications m ON ml.medication_id = m.id
           WHERE ml.patient_id=?
           AND ml.scheduled_date >= date('now', ?)
           ORDER BY ml.scheduled_date DESC, ml.dose_number""",
        (patient_id, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_adherence_stats(patient_id, days=30):
    conn = get_connection()
    rows = conn.execute(
        """SELECT status, COUNT(*) as cnt
           FROM medication_logs
           WHERE patient_id=? AND scheduled_date >= date('now', ?)
           GROUP BY status""",
        (patient_id, f"-{days} days"),
    ).fetchall()
    conn.close()
    stats = {"taken": 0, "missed": 0, "skipped": 0}
    for r in rows:
        stats[r["status"]] = r["cnt"]
    total = sum(stats.values())
    stats["total"] = total
    stats["rate"] = round((stats["taken"] / total * 100), 1) if total > 0 else 0
    return stats


def get_daily_adherence(patient_id, days=30):
    conn = get_connection()
    rows = conn.execute(
        """SELECT scheduled_date,
                  SUM(CASE WHEN status='taken' THEN 1 ELSE 0 END) as taken,
                  COUNT(*) as total
           FROM medication_logs
           WHERE patient_id=? AND scheduled_date >= date('now', ?)
           GROUP BY scheduled_date
           ORDER BY scheduled_date""",
        (patient_id, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_patients_for_caregiver(caregiver_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT u.* FROM users u
           JOIN caregiver_patient cp ON cp.patient_id = u.id
           WHERE cp.caregiver_id=?""",
        (caregiver_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def link_patient(caregiver_id, patient_username):
    conn = get_connection()
    patient = conn.execute("SELECT id FROM users WHERE username=? AND role='patient'", (patient_username,)).fetchone()
    if not patient:
        conn.close()
        return False, "Patient not found."
    try:
        conn.execute(
            "INSERT INTO caregiver_patient (caregiver_id, patient_id) VALUES (?,?)",
            (caregiver_id, patient["id"]),
        )
        conn.commit()
        conn.close()
        return True, "Patient linked successfully."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Already linked to this patient."


# ── AI Chat History ───────────────────────────────────────────────────────────

def save_chat_message(user_id, role, content):
    conn = get_connection()
    conn.execute(
        "INSERT INTO ai_chat_history (user_id, role, content) VALUES (?,?,?)",
        (user_id, role, content),
    )
    conn.commit()
    conn.close()


def get_chat_history(user_id, limit=20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM ai_chat_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))


# ── Reminders ─────────────────────────────────────────────────────────────────

def get_reminders(patient_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT r.*, m.name as med_name FROM reminders r
           JOIN medications m ON r.medication_id = m.id
           WHERE r.patient_id=? AND r.is_active=1""",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_reminder(patient_id, medication_id, reminder_time, message=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO reminders (patient_id, medication_id, reminder_time, message) VALUES (?,?,?,?)",
        (patient_id, medication_id, reminder_time, message),
    )
    conn.commit()
    conn.close()


def delete_reminder(reminder_id):
    conn = get_connection()
    conn.execute("UPDATE reminders SET is_active=0 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()
