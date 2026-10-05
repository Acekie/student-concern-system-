"""
CARD-MRI Development Institute, Inc. (CMDI)
Student Concern Routing and Resolution Tracking System (CARD MRI SCRRTS)
Core Relational Database Schema and Data Access Layer
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
    """Initializes tables and seeds CARD MRI institutional departments and admin accounts."""
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

    # 1. CARD MRI Departments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        department_id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_code TEXT UNIQUE NOT NULL,
        department_name TEXT NOT NULL,
        head_officer TEXT NOT NULL,
        contact_email TEXT NOT NULL,
        campus_branch TEXT NOT NULL DEFAULT 'All Campuses',
        is_active INTEGER NOT NULL DEFAULT 1
    );
    """)

    # 2. CARD MRI Users Table (Students, Staff, Admins)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id_number TEXT UNIQUE,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'staff', 'admin')),
        course_program TEXT,
        campus_branch TEXT NOT NULL DEFAULT 'Bay, Laguna (Main Campus)',
        department_id INTEGER,
        contact_number TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE SET NULL
    );
    """)

    # 3. Concern Categories Table with Auto-Routing Rules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS concern_categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        category_name TEXT NOT NULL,
        default_priority TEXT NOT NULL DEFAULT 'MEDIUM' CHECK(default_priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
        sla_hours INTEGER NOT NULL DEFAULT 72,
        description TEXT,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
    );
    """)

    # 4. CARD MRI Concerns (Tickets) Table with Escalation Support
    cursor.execute("""
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
        status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Routed', 'In Progress', 'Escalated', 'Resolved', 'Closed', 'Rejected')),
        sla_target_date TIMESTAMP NOT NULL,
        is_escalated INTEGER NOT NULL DEFAULT 0,
        escalation_reason TEXT,
        resolved_at TIMESTAMP,
        attachment_path TEXT,
        internal_staff_notes TEXT,
        resolution_summary TEXT,
        rejection_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT,
        FOREIGN KEY (category_id) REFERENCES concern_categories(category_id) ON DELETE RESTRICT,
        FOREIGN KEY (assigned_staff_id) REFERENCES users(user_id) ON DELETE SET NULL
    );
    """)

    # 5. Concern Audit Logs Table
    cursor.execute("""
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
    """)

    # 6. Concern Feedback Table
    cursor.execute("""
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

    # Seed CARD MRI Internal Departments
    departments_data = [
        ("REG", "Office of the Registrar", "Dr. Carmelita S. Bayas", "registrar@cmdi.edu.ph", "Bay & Tagum Campuses"),
        ("FIN", "Student Accounting & Microfinance Finance", "Prof. Edzel A. Ramos", "accounting@cmdi.edu.ph", "Bay & Tagum Campuses"),
        ("SCHOL", "Scholarships & CARD Community Assistance", "Ms. Maria Luisa P. Gomez", "scholarships@cmdi.edu.ph", "All Campuses"),
        ("ACAD", "Academic Affairs & Dean's Office", "Dean Rosanna M. Mercado", "academics@cmdi.edu.ph", "Bay, Laguna"),
        ("ICTO", "ICT & Campus Infrastructure Support", "Engr. Kenneth M. Dalisay", "ict.support@cmdi.edu.ph", "All Campuses")
    ]
    cursor.executemany("""
        INSERT INTO departments (department_code, department_name, head_officer, contact_email, campus_branch)
        VALUES (?, ?, ?, ?, ?);
    """, departments_data)

    # Seed CARD MRI Concern Categories with Auto-Routing rules
    categories_data = [
        # REG (id 1)
        (1, "Official Transcript of Records (TOR) & Certifications", "HIGH", 48, "Requests for official records, diploma releases, and enrollment certifications."),
        (1, "Enrollment, Course Adding/Dropping & Subject Overload", "URGENT", 24, "Course schedule adjustment, prerequisite validation, and study load approvals."),
        # FIN (id 2)
        (2, "Tuition Assessment & Payment Discrepancy", "HIGH", 48, "Ledger balance clarification, bank transfer verification, and examination permit clearance."),
        (2, "Microfinance Education Loan & Installment Plan", "MEDIUM", 72, "CARD MBA tuition installment payment scheduling and financial counseling."),
        # SCHOL (id 3)
        (3, "CARD MRI Educational Grant / Member Scholarship", "MEDIUM", 72, "CARD Mutually Reinforcing Institutions scholarship grants, subsidies, and clearance."),
        (3, "CHED TDP / UNIFAST Government Subsidy Clearance", "HIGH", 48, "Validation of government tertiary education subsidies and masterlist claims."),
        # ACAD (id 4)
        (4, "Grade Clarification & INC Completion Verification", "MEDIUM", 72, "Incomplete mark completion processing and faculty grading consultation."),
        (4, "Curriculum Advising & Practicum / OJT Endorsement", "LOW", 120, "Academic tracking, microfinance internship placements, and graduation audit."),
        # ICTO (id 5)
        (5, "Campus LMS, Student Portal & Wi-Fi Network Access", "URGENT", 24, "Student portal credential retrieval, campus fiber Wi-Fi login, and LMS course errors.")
    ]
    cursor.executemany("""
        INSERT INTO concern_categories (department_id, category_name, default_priority, sla_hours, description)
        VALUES (?, ?, ?, ?, ?);
    """, categories_data)

    # Seed Initial CARD MRI Staff & Admin Accounts (Bcrypt Hashed Passwords)
    # Default passwords strictly follow corporate policy (No 1-click magic links)
    users_data = [
        # Administrators
        (None, "CARD MRI System Administrator", "admin@cmdi.edu.ph", generate_password_hash("CardMriAdmin@2026"), "admin", None, "Bay, Laguna (Main Campus)", None, "+63 917 800 1122"),
        
        # Department Staff (Mapped to CARD MRI Internal Departments)
        (None, "Regina C. Morales (Registrar Officer)", "staff.registrar@cmdi.edu.ph", generate_password_hash("Registrar@Card2026"), "staff", None, "Bay, Laguna (Main Campus)", 1, "+63 918 200 3344"),
        (None, "Anthony G. Pineda (Accounting Officer)", "staff.accounting@cmdi.edu.ph", generate_password_hash("Accounting@Card2026"), "staff", None, "Bay, Laguna (Main Campus)", 2, "+63 918 300 4455"),
        (None, "Theresa V. Alcantara (Scholarship Officer)", "staff.scholarship@cmdi.edu.ph", generate_password_hash("Scholarship@Card2026"), "staff", None, "Bay, Laguna (Main Campus)", 3, "+63 918 400 5566"),
        (None, "Prof. Bernardo L. Santos (Academic Chair)", "staff.academic@cmdi.edu.ph", generate_password_hash("Academics@Card2026"), "staff", None, "Bay, Laguna (Main Campus)", 4, "+63 918 500 6677"),
        (None, "Engr. Jonathan D. Reyes (ICT Admin)", "staff.ict@cmdi.edu.ph", generate_password_hash("IctSupport@Card2026"), "staff", None, "Bay, Laguna (Main Campus)", 5, "+63 918 600 7788"),

        # Sample Registered Students
        ("CMDI-2023-01042", "Clarisse Marie S. Bautista", "cbautista@student.cmdi.edu.ph", generate_password_hash("Student@Card2026"), "student", "BS Information Technology (BSIT)", "Bay, Laguna (Main Campus)", None, "+63 920 111 2233"),
        ("CMDI-2024-00891", "Jerome K. Delos Santos", "jdelossantos@student.cmdi.edu.ph", generate_password_hash("Student@Card2026"), "student", "BS Entrepreneurship (BSEntrep)", "Tagum City Campus", None, "+63 920 222 3344")
    ]
    cursor.executemany("""
        INSERT INTO users (
            student_id_number, full_name, email, password_hash, role,
            course_program, campus_branch, department_id, contact_number
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, users_data)

    # Seed Sample Concerns across explicit states (Submitted, Routed, In Progress, Escalated, Resolved, Closed)
    now = datetime.now()
    concerns_data = [
        # 1. Closed: Grade Clarification in Microfinance Accounting (ACAD)
        (
            "CMDI-CRN-2026-0001", 7, 4, 7, 5,
            "Clarification of Incomplete Grade mark in ENT302 Microfinance Field Practicum",
            "Submitted complete field portfolio and host evaluation to department coordinator last January. Portal still reflects INC status.",
            "MEDIUM", "Closed",
            (now - timedelta(days=6) + timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S"),
            0, None,
            (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
            None,
            "Internal staff verified receipt of hardcopy portfolio. INC grade updated to 1.75.",
            "Professor Bernardo Santos cross-checked documentation. Official completion slip forwarded to Registrar.",
            None,
            (now - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 2. Escalated Ticket: Tuition Payment Delay Exceeding SLA (FIN)
        (
            "CMDI-CRN-2026-0002", 7, 2, 3, 3,
            "CARD Bank Account Payment for Midterm Exam Clearance Not Credited",
            "Deposited PHP 8,500.00 via CARD Bank Bay Branch counter last Tuesday. Receipt #CB-882910. Portal displays remaining unpaid balance preventing exam permit generation.",
            "URGENT", "Escalated",
            (now - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S"), # Overdue target
            1, "SLA turnaround exceeded 24 hours. Critical exam permit deadline pending for midterms.",
            None,
            "deposit_receipt_cb882910.pdf",
            "Accounting desk flagged bank reconciliation statement. Batch confirmation delayed from local branch.",
            None,
            None,
            (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 3. In Progress: TOR Request for Licensure (REG)
        (
            "CMDI-CRN-2026-0003", 8, 1, 1, 2,
            "Urgent Transcript of Records (TOR) for Microfinance Professional Certification",
            "Applying for external national certification. Clearance already approved by Student Affairs and Accounting.",
            "HIGH", "In Progress",
            (now + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S"),
            0, None,
            None,
            "clearance_signed_complete.pdf",
            "Document print batch scheduled today. Awaiting registrar dry seal.",
            None,
            None,
            (now - timedelta(hours=28)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # 4. Submitted: CARD MBA Scholarship Subsidy (SCHOL)
        (
            "CMDI-CRN-2026-0004", 8, 3, 5, None,
            "CARD Mutually Reinforcing Institutions Scholarship Discount 2nd Semester Posting",
            "Parent is a 10-year CARD Bank member under Laguna Unit. Certificate of Good Standing submitted to scholarship office.",
            "MEDIUM", "Submitted",
            (now + timedelta(hours=56)).strftime("%Y-%m-%d %H:%M:%S"),
            0, None,
            None,
            "card_mba_membership_proof.pdf",
            None,
            None,
            None,
            (now - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S")
        )
    ]

    cursor.executemany("""
        INSERT INTO concerns (
            ticket_number, student_id, department_id, category_id, assigned_staff_id,
            subject, description, priority, status, sla_target_date, is_escalated,
            escalation_reason, resolved_at, attachment_path, internal_staff_notes,
            resolution_summary, rejection_reason, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, concerns_data)

    # Seed Audit Logs
    audit_data = [
        (1, 7, None, "Submitted", "Submitted", "Concern filed by student via online CMDI portal.", (now - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 1, "Submitted", "Routed", "Routed", "Auto-routed to Academic Affairs & Dean's Office queue.", (now - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 5, "Routed", "In Progress", "Claimed", "Claimed by Prof. Bernardo Santos for grade sheet inspection.", (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 5, "In Progress", "Resolved", "Resolved", "INC mark rectified in registrar database. Resolution notes recorded.", (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")),
        (1, 7, "Resolved", "Closed", "Closed", "Student confirmed grade update in portal and closed ticket.", (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")),

        (2, 7, None, "Submitted", "Submitted", "Urgent tuition clearance issue filed with bank deposit proof.", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
        (2, 1, "Submitted", "Routed", "Routed", "Auto-routed to Student Accounting & Microfinance Finance queue.", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
        (2, 3, "Routed", "In Progress", "Claimed", "Claimed by Anthony Pineda (Accounting).", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
        (2, 1, "In Progress", "Escalated", "Escalated", "Auto-escalated: SLA turnaround exceeded without bank clearance confirmation.", (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"))
    ]
    cursor.executemany("""
        INSERT INTO concern_audit_logs (concern_id, actor_id, previous_status, new_status, action_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, audit_data)

    # Seed Feedback
    cursor.execute("""
        INSERT INTO concern_feedback (concern_id, student_id, rating, feedback_comments, submitted_at)
        VALUES (1, 7, 5, 'Prompt resolution by Academic Affairs. My grade completion slip was processed accurately.', ?);
    """, ((now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),))

    conn.commit()
    conn.close()
    print("[*] CARD MRI CMDI Database successfully initialized and seeded.")

if __name__ == "__main__":
    init_db(force_reseed=True)
