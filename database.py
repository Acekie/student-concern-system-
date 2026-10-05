"""
Database initialization and data layer for the Student Concern Routing and Resolution Tracking System (ResolvEd).
Matches the Crow's Foot ERD and relational schema specifications.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "student_concerns.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(force_reseed=False):
    """Initializes tables and seeds initial realistic production-ready data."""
    if os.path.exists(DB_PATH):
        if not force_reseed:
            return
        try:
            os.remove(DB_PATH)
        except Exception:
            pass

    conn = get_db_connection()
    cursor = conn.cursor()

    if force_reseed:
        cursor.executescript("""
            DROP TABLE IF EXISTS concern_feedback;
            DROP TABLE IF EXISTS concern_audit_logs;
            DROP TABLE IF EXISTS concerns;
            DROP TABLE IF EXISTS concern_categories;
            DROP TABLE IF EXISTS users;
            DROP TABLE IF EXISTS departments;
        """)

    # Create tables
    cursor.executescript("""
    -- 1. Departments Table
    CREATE TABLE IF NOT EXISTS departments (
        department_id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_code TEXT UNIQUE NOT NULL,
        department_name TEXT NOT NULL,
        contact_email TEXT NOT NULL,
        head_officer TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1
    );

    -- 2. Users Table
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id_number TEXT UNIQUE,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'staff', 'admin')),
        department_id INTEGER,
        contact_number TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE SET NULL
    );

    -- 3. Concern Categories Table
    CREATE TABLE IF NOT EXISTS concern_categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        category_name TEXT NOT NULL,
        default_priority TEXT NOT NULL DEFAULT 'MEDIUM' CHECK(default_priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
        sla_hours INTEGER NOT NULL DEFAULT 72,
        description TEXT,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
    );

    -- 4. Concerns Table
    CREATE TABLE IF NOT EXISTS concerns (
        concern_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        department_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        assigned_staff_id INTEGER,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'MEDIUM' CHECK(priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
        status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK(status IN ('SUBMITTED', 'ROUTED', 'IN_PROGRESS', 'RESOLVED', 'REJECTED', 'CLOSED')),
        sla_target_date TIMESTAMP NOT NULL,
        resolved_at TIMESTAMP,
        attachment_path TEXT,
        resolution_summary TEXT,
        rejection_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT,
        FOREIGN KEY (category_id) REFERENCES concern_categories(category_id) ON DELETE RESTRICT,
        FOREIGN KEY (assigned_staff_id) REFERENCES users(user_id) ON DELETE SET NULL
    );

    -- 5. Concern Audit Logs Table
    CREATE TABLE IF NOT EXISTS concern_audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        concern_id INTEGER NOT NULL,
        actor_id INTEGER NOT NULL,
        previous_status TEXT,
        new_status TEXT,
        action_type TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (concern_id) REFERENCES concerns(concern_id) ON DELETE CASCADE,
        FOREIGN KEY (actor_id) REFERENCES users(user_id) ON DELETE RESTRICT
    );

    -- 6. Concern Feedback Table
    CREATE TABLE IF NOT EXISTS concern_feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        concern_id INTEGER UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
        feedback_comments TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (concern_id) REFERENCES concerns(concern_id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # Seed Departments
    departments_data = [
        ("REG", "Office of the University Registrar", "registrar@university.edu", "Dr. Erlinda Santos"),
        ("FIN", "Student Accounting & Finance Office", "finance@university.edu", "Prof. Roberto Mendoza"),
        ("ACAD", "Academic Affairs & Department Chairs", "academics@university.edu", "Dean Patricia Morales"),
        ("OSA", "Office of Student Affairs & Services", "studentaffairs@university.edu", "Atty. Fernando Cruz"),
        ("ICTO", "Information & Communication Technology Office", "ithelpdesk@university.edu", "Engr. Jonathan Reyes")
    ]
    cursor.executemany("""
        INSERT INTO departments (department_code, department_name, contact_email, head_officer)
        VALUES (?, ?, ?, ?);
    """, departments_data)

    # Seed Concern Categories
    categories_data = [
        # REG (id 1)
        (1, "Transcript of Records (TOR) & Certifications", "HIGH", 48, "Requests, errors, or delays regarding official transcript or certificates of enrollment."),
        (1, "Enrollment & Subject Adding/Dropping", "URGENT", 24, "Course load adjustment, prerequisite validation, and enrollment confirmation."),
        # FIN (id 2)
        (2, "Tuition Assessment & Payment Discrepancy", "HIGH", 48, "Portal payment clearance, online banking posting delays, and ledger balance queries."),
        (2, "Scholarship Grants & Refunds", "MEDIUM", 72, "Discounts, government scholarship vouchers, and overpayment refund requests."),
        # ACAD (id 3)
        (3, "Grade Incomplete / Clarification Consultation", "MEDIUM", 72, "Grade verification, INC completion processing, and syllabus requirements."),
        (3, "Faculty Advising & Curriculum Concerns", "LOW", 120, "Academic consultation, prerequisite overload appeals, and graduation standing."),
        # OSA (id 4)
        (4, "Student Organization & Activity Permits", "MEDIUM", 72, "Club accreditation, campus facility usage requests, and activity permits."),
        (4, "Guidance & Mental Health Support", "URGENT", 24, "Confidential psychological counseling appointments and student wellness assistance."),
        # ICTO (id 5)
        (5, "Campus Portal, Wi-Fi & LMS Access", "URGENT", 24, "Student portal password resets, LMS course enrollment errors, campus Wi-Fi credentials.")
    ]
    cursor.executemany("""
        INSERT INTO concern_categories (department_id, category_name, default_priority, sla_hours, description)
        VALUES (?, ?, ?, ?, ?);
    """, categories_data)

    # Seed Users (Hashed passwords)
    # Passwords:
    # Admin: 'Admin@123' / 'Admin@12345'
    # Staff: 'Staff@123' / 'Staff@12345'
    # Student: 'Student@123' / 'Student@12345'
    users_data = [
        # Admins
        (None, "Engr. Victor Tan", "admin@univ.edu", generate_password_hash("Admin@123"), "admin", None, "+63 917 111 2233"),
        (None, "System Administrator (Demo)", "demo.admin@email.com", generate_password_hash("Admin@12345"), "admin", None, "+63 917 000 0001"),

        # Department Staff
        (None, "Maria Elena Ramos", "staff.registrar@univ.edu", generate_password_hash("Staff@123"), "staff", 1, "+63 918 222 3344"),
        (None, "Carlos Miguel Gomez", "staff.finance@univ.edu", generate_password_hash("Staff@123"), "staff", 2, "+63 918 333 4455"),
        (None, "Prof. Teresa Diaz", "staff.academic@univ.edu", generate_password_hash("Staff@123"), "staff", 3, "+63 918 444 5566"),
        (None, "Atty. Fernando Cruz", "staff.osa@univ.edu", generate_password_hash("Staff@123"), "staff", 4, "+63 918 555 6677"),
        (None, "Department Resolver (Demo)", "demo.staff@email.com", generate_password_hash("Staff@12345"), "staff", 1, "+63 918 000 0002"),

        # Students
        ("2023-01042", "Maria Clarisse Santos", "student.santos@univ.edu", generate_password_hash("Student@123"), "student", None, "+63 920 123 4567"),
        ("2022-04891", "Juan Carlo Dela Cruz", "student.delacruz@univ.edu", generate_password_hash("Student@123"), "student", None, "+63 920 765 4321"),
        ("2024-00129", "Bea Angela Reyes", "student.reyes@univ.edu", generate_password_hash("Student@123"), "student", None, "+63 920 999 8888"),
        ("2023-99999", "Student User (Demo)", "demo.user@email.com", generate_password_hash("Student@12345"), "student", None, "+63 920 000 0003")
    ]
    cursor.executemany("""
        INSERT INTO users (student_id_number, full_name, email, password_hash, role, department_id, contact_number)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, users_data)

    # Seed Sample Concerns with realistic dates and diverse statuses
    now = datetime.now()
    
    concerns_data = [
        # 1. Closed/Resolved with rating: Grade Clarification (ACAD)
        (
            "CRN-2026-0001", 8, 3, 5, 5,
            "Discrepancy in CS301 Final Grade Computation",
            "My posted midterm exam grade was 92, but my portal reflects 75. Kindly request verification with the professor.",
            "MEDIUM", "CLOSED",
            (now - timedelta(days=5) + timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            "Re-checked grade sheet with Prof. Diaz. Transposition typo corrected from 75 to 95. Updated in University Portal.",
            None,
            (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 2. In Progress: Tuition Payment Not Credited (FIN)
        (
            "CRN-2026-0002", 8, 2, 3, 4,
            "Online Bank Transfer for 2nd Sem Tuition Not Reflected",
            "Transferred PHP 15,500 via GCash to university bank account last Monday. Reference #GC-901827. Assessment remains unpaid.",
            "HIGH", "IN_PROGRESS",
            (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            "receipt_gcash_901827.pdf",
            None,
            None,
            (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 3. OVERDUE Ticket: Transcript for Board Exam (REG)
        (
            "CRN-2026-0003", 9, 1, 1, 3,
            "Urgent Transcript of Records (TOR) for PRC Licensure Board Exam",
            "Deadline for PRC submission is approaching next week. Submitted clearance 3 weeks ago but document is still in queue.",
            "URGENT", "ROUTED",
            (now - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S"), # Overdue!
            None,
            "clearance_form_signed.pdf",
            None,
            None,
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 4. Resolved: LMS & Wi-Fi login credentials (ICTO)
        (
            "CRN-2026-0004", 10, 5, 9, 1, # Admin resolved
            "Cannot connect to Student Wi-Fi 'UnivNet-Secure'",
            "My university active directory account cannot authenticate to campus Wi-Fi after password reset.",
            "URGENT", "RESOLVED",
            (now - timedelta(days=3) + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            "Active Directory sync re-triggered for student user account. Tested authentication successfully.",
            None,
            (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 5. Submitted: Student Org Activity Approval (OSA)
        (
            "CRN-2026-0005", 11, 4, 7, None,
            "Junior CS Society Hackathon 2026 Hall Reservation",
            "Submitting proposal for 24-hour coding competition on March 25, 2026. Attached endorsement letters from faculty advisor.",
            "MEDIUM", "SUBMITTED",
            (now + timedelta(hours=60)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            "hackathon_proposal_2026.pdf",
            None,
            None,
            (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 6. Rejected: Duplicate Subject Enrollment
        (
            "CRN-2026-0006", 9, 1, 2, 3,
            "Request to waive prerequisite for Advanced Database Systems",
            "Would like to take CS402 concurrently with prerequisite CS301 without prior passing mark.",
            "HIGH", "REJECTED",
            (now - timedelta(days=4) + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            None,
            "University Academic Policy Section 4.2 strictly prohibits concurrent enrollment of failed/uncompleted prerequisites.",
            (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 7. In Progress: Scholarship Billing Deduction
        (
            "CRN-2026-0007", 11, 2, 4, 4,
            "CHED TDP Scholarship Discount Not Applied to Remaining Balance",
            "Received official Masterlist from CHED Region Office. Accounting assessment has not credited the PHP 7,500 grant subsidy.",
            "MEDIUM", "IN_PROGRESS",
            (now + timedelta(hours=40)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            "ched_masterlist_proof.pdf",
            None,
            None,
            (now - timedelta(hours=32)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 8. Submitted: Enrollment Add/Drop Subject
        (
            "CRN-2026-0008", 8, 1, 2, None,
            "Overload request for 1 additional 3-unit elective (Graduating status)",
            "I am in my final graduating term and require 1 additional elective unit (IT405 Mobile Computing).",
            "URGENT", "SUBMITTED",
            (now + timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            None,
            None,
            None,
            (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
        )
    ]

    cursor.executemany("""
        INSERT INTO concerns (
            ticket_number, student_id, department_id, category_id, assigned_staff_id,
            subject, description, priority, status, sla_target_date, resolved_at,
            attachment_path, resolution_summary, rejection_reason, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, concerns_data)

    # Seed Audit Logs
    audit_data = [
        # CRN-2026-0001 trail
        (1, 8, None, "SUBMITTED", "SUBMITTED", "Concern filed by student via online portal.", (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 1, "SUBMITTED", "ROUTED", "ROUTED", "Auto-routed to Academic Affairs based on category.", (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 5, "ROUTED", "IN_PROGRESS", "CLAIMED", "Ticket assigned to Prof. Teresa Diaz for departmental verification.", (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 5, "IN_PROGRESS", "RESOLVED", "RESOLVED", "Resolution note posted and grade update submitted to registrar.", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 8, "RESOLVED", "CLOSED", "CLOSED", "Student confirmed resolution and closed ticket.", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),

        # CRN-2026-0002 trail
        (2, 8, None, "SUBMITTED", "SUBMITTED", "Payment discrepancy reported with GCash reference.", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
        (2, 1, "SUBMITTED", "ROUTED", "ROUTED", "Auto-routed to Student Accounting & Finance.", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
        (2, 4, "ROUTED", "IN_PROGRESS", "CLAIMED", "Ticket claimed by Carlos Gomez (Finance Officer). Checking bank reconciliation file.", (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")),

        # CRN-2026-0003 trail
        (3, 9, None, "SUBMITTED", "SUBMITTED", "Urgent TOR concern filed for board exam.", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
        (3, 1, "SUBMITTED", "ROUTED", "ROUTED", "Auto-routed to Registrar queue.", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),

        # CRN-2026-0006 trail (Rejection)
        (6, 9, None, "SUBMITTED", "SUBMITTED", "Prerequisite waiver appeal filed.", (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")),
        (6, 3, "SUBMITTED", "REJECTED", "REJECTED", "Registrar verified prerequisite curriculum chart. Appeal rejected in compliance with university policy.", (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"))
    ]
    cursor.executemany("""
        INSERT INTO concern_audit_logs (concern_id, actor_id, previous_status, new_status, action_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, audit_data)

    # Seed Feedback
    cursor.execute("""
        INSERT INTO concern_feedback (concern_id, student_id, rating, feedback_comments, submitted_at)
        VALUES (1, 8, 5, 'Thank you so much! My grade was promptly corrected within 2 days before graduation evaluation.', ?);
    """, ((now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),))

    conn.commit()
    conn.close()
    print("Database initialized and successfully seeded with realistic production records.")

if __name__ == "__main__":
    init_db(force_reseed=True)
