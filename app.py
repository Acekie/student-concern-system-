"""
CARD-MRI Development Institute, Inc. (CMDI)
Student Concern Routing and Resolution Tracking System (CARD MRI SCRRTS)
Enterprise Backend Application & Routing Controller
"""

import os
import csv
import io
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash,
    jsonify, Response, send_from_directory, abort
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import get_db_connection, init_db, DB_PATH
from mailer import send_registration_email, send_concern_status_email

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "card-mri-cmdi-secure-production-key-2026")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx', 'txt', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ensure CARD MRI database exists
if not os.path.exists(DB_PATH):
    init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/favicon.ico')
def favicon():
    return ('', 204)

# -------------------------------------------------------------
# Role-Based Security Decorators
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Authentication required. Please sign in with your CARD MRI institutional credentials.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please sign in to proceed.", "warning")
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash("Access Restricted: Your institutional role lacks permissions for this module.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# -------------------------------------------------------------
# Business Rules & Helper Utilities
# -------------------------------------------------------------
def generate_ticket_number(cursor):
    """Generates CARD MRI institutional tracking code: CMDI-CRN-YYYY-XXXX."""
    year = datetime.now().year
    cursor.execute("SELECT COUNT(*) AS total FROM concerns")
    count = cursor.fetchone()['total'] + 1
    return f"CMDI-CRN-{year}-{count:04d}"

def calculate_sla_target(cursor, category_id, priority):
    """Dynamic SLA Target Date Calculation based on CARD MRI department baseline."""
    cursor.execute("SELECT sla_hours FROM concern_categories WHERE category_id = ?", (category_id,))
    row = cursor.fetchone()
    base_hours = row['sla_hours'] if row else 72

    priority_multiplier = {
        'URGENT': 0.33,  # Urgent SLA (e.g. 24h)
        'HIGH': 0.66,    # High priority (e.g. 48h)
        'MEDIUM': 1.0,   # Standard SLA (e.g. 72h)
        'LOW': 1.66      # Extended inquiry
    }
    adjusted_hours = max(12, int(base_hours * priority_multiplier.get(priority, 1.0)))
    target_dt = datetime.now() + timedelta(hours=adjusted_hours)
    return target_dt.strftime("%Y-%m-%d %H:%M:%S")

def log_audit_event(cursor, concern_id, actor_id, prev_status, new_status, action_type, notes):
    """Enforces immutable transaction audit history."""
    cursor.execute("""
        INSERT INTO concern_audit_logs (concern_id, actor_id, previous_status, new_status, action_type, notes)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (concern_id, actor_id, prev_status, new_status, action_type, notes))

def check_is_overdue(sla_target_str, status):
    """Real-time overdue calculation."""
    if status in ('Resolved', 'Closed', 'Rejected'):
        return False
    try:
        sla_dt = datetime.strptime(sla_target_str, "%Y-%m-%d %H:%M:%S")
        return datetime.now() > sla_dt
    except Exception:
        return False

app.jinja_env.globals.update(check_is_overdue=check_is_overdue)

# -------------------------------------------------------------
# Module 1: User Registration (CARD MRI Institutional Intake)
# -------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Core Requirement 1: User Registration Module
    Accepts Students and Staff with CARD MRI institutional verification.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    departments = conn.execute("SELECT * FROM departments WHERE is_active = 1").fetchall()

    if request.method == 'POST':
        account_role = request.form.get('account_role', 'student')
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        campus_branch = request.form.get('campus_branch', 'Bay, Laguna (Main Campus)')
        contact_number = request.form.get('contact_number', '').strip()

        # Validation
        if not full_name or not email or not password:
            flash("All mandatory registration fields must be completed.", "danger")
            conn.close()
            return render_template('register.html', departments=departments)

        if password != confirm_password:
            flash("Password confirmation mismatch. Please verify passwords match.", "danger")
            conn.close()
            return render_template('register.html', departments=departments)

        if len(password) < 6:
            flash("Password must be at least 6 characters in length.", "danger")
            conn.close()
            return render_template('register.html', departments=departments)

        # Check duplicate email
        existing_user = conn.execute("SELECT user_id FROM users WHERE email = ?", (email,)).fetchone()
        if existing_user:
            flash("This institutional email is already registered. Please sign in.", "warning")
            conn.close()
            return redirect(url_for('login'))

        cursor = conn.cursor()

        if account_role == 'student':
            student_id = request.form.get('student_id_number', '').strip()
            course_program = request.form.get('course_program', '').strip()

            if not student_id or not course_program:
                flash("CARD MRI Student ID and Academic Program/Course are required for student registration.", "danger")
                conn.close()
                return render_template('register.html', departments=departments)

            # Check duplicate student ID
            dup_id = conn.execute("SELECT user_id FROM users WHERE student_id_number = ?", (student_id,)).fetchone()
            if dup_id:
                flash("This Student ID number is already registered.", "warning")
                conn.close()
                return render_template('register.html', departments=departments)

            hashed_pw = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (
                    student_id_number, full_name, email, password_hash, role,
                    course_program, campus_branch, contact_number
                ) VALUES (?, ?, ?, ?, 'student', ?, ?, ?);
            """, (student_id, full_name, email, hashed_pw, course_program, campus_branch, contact_number))

        elif account_role == 'staff':
            department_id = request.form.get('department_id')
            if not department_id:
                flash("Department staff registration requires selecting a designated CARD MRI department.", "danger")
                conn.close()
                return render_template('register.html', departments=departments)

            hashed_pw = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (
                    full_name, email, password_hash, role,
                    department_id, campus_branch, contact_number
                ) VALUES (?, ?, ?, 'staff', ?, ?, ?);
            """, (full_name, email, hashed_pw, department_id, campus_branch, contact_number))
        else:
            flash("Invalid registration role.", "danger")
            conn.close()
            return render_template('register.html', departments=departments)

        conn.commit()

        # Retrieve department name for staff email if applicable
        dept_name = None
        if account_role == 'staff' and department_id:
            dept_row = conn.execute("SELECT department_name FROM departments WHERE department_id = ?", (department_id,)).fetchone()
            if dept_row:
                dept_name = dept_row['department_name']

        conn.close()

        # Dispatch automated asynchronous email notification
        try:
            send_registration_email(
                to_email=email,
                full_name=full_name,
                role=account_role,
                student_id=student_id if account_role == 'student' else None,
                course_program=course_program if account_role == 'student' else None,
                department_name=dept_name,
                campus_branch=campus_branch
            )
        except Exception as mail_err:
            print(f"[MAILER EXCEPTION] {mail_err}")

        flash("CARD MRI Institutional Account successfully registered! An email confirmation has been dispatched. Please sign in with your credentials.", "success")
        return redirect(url_for('login'))

    conn.close()
    return render_template('register.html', departments=departments)

# -------------------------------------------------------------
# Module 2: Authentication (Standard Credential Only)
# -------------------------------------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Core Requirement 2: Authentication
    Strict credential-based authentication (Email/Password with Bcrypt verification).
    Explicitly excludes 1-click demo logins, social logins, or magic links.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please enter both your institutional email and password.", "danger")
            return render_template('login.html')

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['email'] = user['email']
            session['role'] = user['role']
            session['department_id'] = user['department_id']
            session['student_id_number'] = user['student_id_number']
            session['campus_branch'] = user['campus_branch']
            session['course_program'] = user['course_program']

            flash(f"Welcome to CARD MRI Portal, {user['full_name']}.", "success")
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard'))
        else:
            flash("Invalid institutional email or password. Please verify your credentials.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out from CARD MRI SCRRTS.", "info")
    return redirect(url_for('login'))

# -------------------------------------------------------------
# Module 3: Resolution Tracking & Dashboards
# -------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    """
    Core Requirement 4: Student Timeline Dashboard & Staff Resolution Dashboard
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session['user_id']
    role = session['role']
    dept_id = session.get('department_id')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if role == 'student':
        # Student Dashboard
        total = cursor.execute("SELECT COUNT(*) FROM concerns WHERE student_id = ?", (user_id,)).fetchone()[0]
        in_progress = cursor.execute("SELECT COUNT(*) FROM concerns WHERE student_id = ? AND status IN ('Submitted', 'Routed', 'In Progress')", (user_id,)).fetchone()[0]
        escalated = cursor.execute("SELECT COUNT(*) FROM concerns WHERE student_id = ? AND status = 'Escalated'", (user_id,)).fetchone()[0]
        resolved = cursor.execute("SELECT COUNT(*) FROM concerns WHERE student_id = ? AND status IN ('Resolved', 'Closed')", (user_id,)).fetchone()[0]

        concerns = cursor.execute("""
            SELECT c.*, d.department_name, d.department_code, cat.category_name
            FROM concerns c
            JOIN departments d ON c.department_id = d.department_id
            JOIN concern_categories cat ON c.category_id = cat.category_id
            WHERE c.student_id = ?
            ORDER BY c.created_at DESC
        """, (user_id,)).fetchall()

        conn.close()
        return render_template(
            'dashboard.html',
            role=role,
            total=total,
            in_progress=in_progress,
            escalated=escalated,
            resolved=resolved,
            concerns=concerns
        )

    elif role == 'staff':
        # Staff Resolution Dashboard (Scoped to CARD MRI Department)
        total_dept = cursor.execute("SELECT COUNT(*) FROM concerns WHERE department_id = ?", (dept_id,)).fetchone()[0]
        unassigned = cursor.execute("SELECT COUNT(*) FROM concerns WHERE department_id = ? AND assigned_staff_id IS NULL AND status IN ('Submitted', 'Routed')", (dept_id,)).fetchone()[0]
        my_assigned = cursor.execute("SELECT COUNT(*) FROM concerns WHERE assigned_staff_id = ? AND status IN ('In Progress', 'Escalated')", (user_id,)).fetchone()[0]
        escalated_dept = cursor.execute("SELECT COUNT(*) FROM concerns WHERE department_id = ? AND status = 'Escalated'", (dept_id,)).fetchone()[0]
        resolved_dept = cursor.execute("SELECT COUNT(*) FROM concerns WHERE department_id = ? AND status IN ('Resolved', 'Closed')", (dept_id,)).fetchone()[0]

        dept_concerns = cursor.execute("""
            SELECT c.*, u.full_name as student_name, u.student_id_number, u.course_program, cat.category_name, staff.full_name as staff_name
            FROM concerns c
            JOIN users u ON c.student_id = u.user_id
            JOIN concern_categories cat ON c.category_id = cat.category_id
            LEFT JOIN users staff ON c.assigned_staff_id = staff.user_id
            WHERE c.department_id = ?
            ORDER BY 
                CASE c.status WHEN 'Escalated' THEN 1 WHEN 'In Progress' THEN 2 WHEN 'Submitted' THEN 3 ELSE 4 END,
                c.created_at DESC
        """, (dept_id,)).fetchall()

        conn.close()
        return render_template(
            'dashboard.html',
            role=role,
            total=total_dept,
            unassigned=unassigned,
            my_assigned=my_assigned,
            escalated=escalated_dept,
            resolved=resolved_dept,
            concerns=dept_concerns
        )

    else:
        # Administrator Global Oversight Dashboard
        total = cursor.execute("SELECT COUNT(*) FROM concerns").fetchone()[0]
        pending = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status IN ('Submitted', 'Routed', 'In Progress')").fetchone()[0]
        escalated = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status = 'Escalated'").fetchone()[0]
        resolved = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status IN ('Resolved', 'Closed')").fetchone()[0]

        dept_breakdown = cursor.execute("""
            SELECT d.department_name, d.department_code,
                   COUNT(c.concern_id) as total_received,
                   SUM(CASE WHEN c.status = 'Escalated' THEN 1 ELSE 0 END) as escalated_count,
                   SUM(CASE WHEN c.status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) as resolved_count
            FROM departments d
            LEFT JOIN concerns c ON d.department_id = c.department_id
            GROUP BY d.department_id
        """).fetchall()

        recent_audits = cursor.execute("""
            SELECT l.*, c.ticket_number, u.full_name as actor_name, u.role as actor_role
            FROM concern_audit_logs l
            JOIN concerns c ON l.concern_id = c.concern_id
            JOIN users u ON l.actor_id = u.user_id
            ORDER BY l.created_at DESC LIMIT 8
        """).fetchall()

        conn.close()
        return render_template(
            'dashboard.html',
            role=role,
            total=total,
            pending=pending,
            escalated=escalated,
            resolved=resolved,
            dept_breakdown=dept_breakdown,
            recent_audits=recent_audits
        )

# -------------------------------------------------------------
# Module 4: Concern Submission & Intelligent Auto-Routing
# -------------------------------------------------------------
@app.route('/concerns/new', methods=['GET', 'POST'])
@login_required
@role_required('student')
def submit_concern():
    """
    Core Requirement: Concern Submission
    Strictly restricted to Student accounts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'MEDIUM').upper()

        if not category_id or not subject or not description:
            flash("All mandatory concern intake fields must be supplied.", "danger")
            departments = conn.execute("SELECT * FROM departments WHERE is_active = 1").fetchall()
            categories = conn.execute("SELECT * FROM concern_categories").fetchall()
            conn.close()
            return render_template('submit_concern.html', departments=departments, categories=categories)

        if priority not in ('LOW', 'MEDIUM', 'HIGH', 'URGENT'):
            priority = 'MEDIUM'

        # Auto-Routing Logic: Retrieve department mapped to category
        cat_info = cursor.execute("""
            SELECT c.*, d.department_id, d.department_name, d.department_code 
            FROM concern_categories c
            JOIN departments d ON c.department_id = d.department_id
            WHERE c.category_id = ?
        """, (category_id,)).fetchone()

        if not cat_info:
            flash("Selected inquiry category is invalid.", "danger")
            conn.close()
            return redirect(url_for('submit_concern'))

        department_id = cat_info['department_id']
        ticket_number = generate_ticket_number(cursor)
        sla_target = calculate_sla_target(cursor, category_id, priority)

        # Attachment file handling
        attachment_filename = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(f"{ticket_number}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    attachment_filename = filename
                else:
                    flash("Attachment rejected: Allowed file types are PDF, DOCX, PNG, JPG, ZIP.", "warning")

        # Insert Ticket
        cursor.execute("""
            INSERT INTO concerns (
                ticket_number, student_id, department_id, category_id,
                subject, description, priority, status, sla_target_date, attachment_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?);
        """, (ticket_number, session['user_id'], department_id, category_id, subject, description, priority, sla_target, attachment_filename))

        concern_id = cursor.lastrowid

        # Insert Initial Audit Log Event
        log_audit_event(
            cursor, concern_id, session['user_id'],
            None, 'Submitted', 'Submitted',
            f"Concern submitted by student. Auto-routed to CARD MRI {cat_info['department_name']} ({cat_info['department_code']}) with {priority} priority."
        )

        conn.commit()
        conn.close()

        flash(f"Inquiry logged successfully: Tracking Code [{ticket_number}]. Dispatched to {cat_info['department_name']}.", "success")
        return redirect(url_for('view_concern', concern_id=concern_id))

    departments = conn.execute("SELECT * FROM departments WHERE is_active = 1").fetchall()
    categories = conn.execute("""
        SELECT cat.*, d.department_name, d.department_code 
        FROM concern_categories cat
        JOIN departments d ON cat.department_id = d.department_id
        ORDER BY d.department_name, cat.category_name
    """).fetchall()
    conn.close()
    return render_template('submit_concern.html', departments=departments, categories=categories)

# -------------------------------------------------------------
# Module 5: Resolution Tracking, Timeline & Status Actions
# -------------------------------------------------------------
@app.route('/concerns/<int:concern_id>')
@login_required
def view_concern(concern_id):
    """Detailed concern view with student timeline and staff resolution controls."""
    conn = get_db_connection()
    cursor = conn.cursor()

    concern = cursor.execute("""
        SELECT c.*, d.department_name, d.department_code, d.contact_email as dept_email,
               cat.category_name, cat.sla_hours,
               u.full_name as student_name, u.email as student_email, u.student_id_number,
               u.course_program, u.campus_branch, u.contact_number as student_contact,
               staff.full_name as staff_name, staff.email as staff_email
        FROM concerns c
        JOIN departments d ON c.department_id = d.department_id
        JOIN concern_categories cat ON c.category_id = cat.category_id
        JOIN users u ON c.student_id = u.user_id
        LEFT JOIN users staff ON c.assigned_staff_id = staff.user_id
        WHERE c.concern_id = ?
    """, (concern_id,)).fetchone()

    if not concern:
        flash("Record not found.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    # Access control: Students view only their own records
    if session['role'] == 'student' and concern['student_id'] != session['user_id']:
        flash("Access violation: You can only view your own filed concerns.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    # Audit timeline
    audit_logs = cursor.execute("""
        SELECT l.*, u.full_name as actor_name, u.role as actor_role
        FROM concern_audit_logs l
        JOIN users u ON l.actor_id = u.user_id
        WHERE l.concern_id = ?
        ORDER BY l.created_at ASC
    """, (concern_id,)).fetchall()

    feedback = cursor.execute("SELECT * FROM concern_feedback WHERE concern_id = ?", (concern_id,)).fetchone()

    conn.close()
    return render_template('concern_detail.html', concern=concern, audit_logs=audit_logs, feedback=feedback)

@app.route('/concerns/<int:concern_id>/claim', methods=['POST'])
@login_required
@role_required('staff', 'admin')
def claim_concern(concern_id):
    """Department staff claims ticket into In Progress status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()

    if not concern:
        flash("Record not found.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    if session['role'] == 'staff' and concern['department_id'] != session.get('department_id'):
        flash("You cannot claim concerns outside your assigned department.", "danger")
        conn.close()
        return redirect(url_for('view_concern', concern_id=concern_id))

    prev_status = concern['status']
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE concerns
        SET assigned_staff_id = ?, status = 'In Progress', updated_at = ?
        WHERE concern_id = ?
    """, (session['user_id'], now_str, concern_id))

    log_audit_event(
        cursor, concern_id, session['user_id'],
        prev_status, 'In Progress', 'Claimed',
        f"Claimed by {session['full_name']} for investigation and resolution."
    )

    conn.commit()
    conn.close()
    flash("Ticket claimed successfully. Status updated to In Progress.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns/<int:concern_id>/escalate', methods=['POST'])
@login_required
@role_required('staff', 'admin')
def escalate_concern(concern_id):
    """Escalates concern to supervisory / administrative review."""
    escalation_reason = request.form.get('escalation_reason', '').strip()

    if not escalation_reason:
        flash("An explicit escalation justification is required.", "danger")
        return redirect(url_for('view_concern', concern_id=concern_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()

    prev_status = concern['status']
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE concerns
        SET status = 'Escalated', is_escalated = 1, escalation_reason = ?, updated_at = ?
        WHERE concern_id = ?
    """, (escalation_reason, now_str, concern_id))

    log_audit_event(
        cursor, concern_id, session['user_id'],
        prev_status, 'Escalated', 'Escalated',
        f"ESCALATION ALERT: {escalation_reason}"
    )

    conn.commit()
    conn.close()
    flash("Concern has been escalated to departmental supervisory queue.", "warning")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns/<int:concern_id>/update-status', methods=['POST'])
@login_required
@role_required('staff', 'admin')
def update_status(concern_id):
    """Updates status with internal staff notes and resolution summaries."""
    new_status = request.form.get('new_status')
    action_note = request.form.get('action_note', '').strip()
    internal_notes = request.form.get('internal_notes', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()

    if not concern:
        flash("Record not found.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    prev_status = concern['status']
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if new_status == 'Resolved':
        if not action_note:
            flash("Policy Mandate: A formal Resolution Summary is required when marking as Resolved.", "danger")
            conn.close()
            return redirect(url_for('view_concern', concern_id=concern_id))

        cursor.execute("""
            UPDATE concerns
            SET status = 'Resolved', resolution_summary = ?, internal_staff_notes = ?, resolved_at = ?, updated_at = ?
            WHERE concern_id = ?
        """, (action_note, internal_notes or concern['internal_staff_notes'], now_str, now_str, concern_id))

        log_audit_event(cursor, concern_id, session['user_id'], prev_status, 'Resolved', 'Resolved', f"Resolution Note: {action_note}")

    elif new_status == 'Rejected':
        if not action_note:
            flash("Policy Mandate: An academic/institutional policy justification is required to reject an inquiry.", "danger")
            conn.close()
            return redirect(url_for('view_concern', concern_id=concern_id))

        cursor.execute("""
            UPDATE concerns
            SET status = 'Rejected', rejection_reason = ?, internal_staff_notes = ?, updated_at = ?
            WHERE concern_id = ?
        """, (action_note, internal_notes or concern['internal_staff_notes'], now_str, concern_id))

        log_audit_event(cursor, concern_id, session['user_id'], prev_status, 'Rejected', 'Rejected', f"Rejection Justification: {action_note}")

    else:
        cursor.execute("""
            UPDATE concerns
            SET status = ?, internal_staff_notes = ?, updated_at = ?
            WHERE concern_id = ?
        """, (new_status, internal_notes or concern['internal_staff_notes'], now_str, concern_id))

    # Fetch student and department info for email dispatch
    student_info = cursor.execute("""
        SELECT u.email as student_email, u.full_name as student_name, c.ticket_number, c.subject, d.department_name
        FROM concerns c
        JOIN users u ON c.student_id = u.user_id
        JOIN departments d ON c.department_id = d.department_id
        WHERE c.concern_id = ?
    """, (concern_id,)).fetchone()

    conn.commit()
    conn.close()

    if student_info:
        try:
            send_concern_status_email(
                to_email=student_info['student_email'],
                student_name=student_info['student_name'],
                ticket_number=student_info['ticket_number'],
                subject_text=student_info['subject'],
                new_status=new_status,
                department_name=student_info['department_name'],
                action_notes=action_note
            )
        except Exception as mail_err:
            print(f"[MAILER EXCEPTION] {mail_err}")

    flash(f"Inquiry status successfully transitioned to {new_status}.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns/<int:concern_id>/close', methods=['POST'])
@login_required
def close_concern(concern_id):
    """Student confirms resolution and closes concern ticket."""
    conn = get_db_connection()
    cursor = conn.cursor()
    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()

    if not concern:
        flash("Record not found.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    if session['role'] == 'student' and concern['student_id'] != session['user_id']:
        flash("Access violation.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE concerns SET status = 'Closed', updated_at = ? WHERE concern_id = ?", (now_str, concern_id))
    log_audit_event(cursor, concern_id, session['user_id'], concern['status'], 'Closed', 'Closed', "Student confirmed resolution satisfaction and officially closed ticket.")

    conn.commit()
    conn.close()
    flash("Concern officially closed. Thank you for using CARD MRI SCRRTS.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns/<int:concern_id>/feedback', methods=['POST'])
@login_required
@role_required('student')
def submit_feedback(concern_id):
    """Captures student evaluation score (1-5 stars) and comments."""
    rating = int(request.form.get('rating', 5))
    comments = request.form.get('comments', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO concern_feedback (concern_id, student_id, rating, feedback_comments)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(concern_id) DO UPDATE SET rating = excluded.rating, feedback_comments = excluded.feedback_comments
    """, (concern_id, session['user_id'], rating, comments))

    conn.commit()
    conn.close()
    flash("Feedback received. Thank you for helping CARD MRI improve student service delivery.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns')
@login_required
def list_concerns():
    """All concerns query with search, status filters, priority filters, and department constraints."""
    conn = get_db_connection()
    cursor = conn.cursor()

    role = session['role']
    user_id = session['user_id']
    dept_id = session.get('department_id')

    status_filter = request.args.get('status', 'ALL')
    dept_filter = request.args.get('department', 'ALL')
    priority_filter = request.args.get('priority', 'ALL')
    search_query = request.args.get('q', '').strip()

    sql = """
        SELECT c.*, d.department_name, d.department_code, cat.category_name,
               u.full_name as student_name, u.student_id_number, u.course_program,
               staff.full_name as staff_name
        FROM concerns c
        JOIN departments d ON c.department_id = d.department_id
        JOIN concern_categories cat ON c.category_id = cat.category_id
        JOIN users u ON c.student_id = u.user_id
        LEFT JOIN users staff ON c.assigned_staff_id = staff.user_id
        WHERE 1=1
    """
    params = []

    if role == 'student':
        sql += " AND c.student_id = ?"
        params.append(user_id)
    elif role == 'staff':
        sql += " AND c.department_id = ?"
        params.append(dept_id)

    if status_filter != 'ALL':
        sql += " AND c.status = ?"
        params.append(status_filter)

    if dept_filter != 'ALL' and role == 'admin':
        sql += " AND c.department_id = ?"
        params.append(dept_filter)

    if priority_filter != 'ALL':
        sql += " AND c.priority = ?"
        params.append(priority_filter)

    if search_query:
        sql += " AND (c.ticket_number LIKE ? OR c.subject LIKE ? OR c.description LIKE ? OR u.full_name LIKE ?)"
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    sql += " ORDER BY c.created_at DESC"
    concerns = cursor.execute(sql, params).fetchall()
    departments = cursor.execute("SELECT * FROM departments WHERE is_active = 1").fetchall()
    conn.close()

    return render_template('concerns_list.html', concerns=concerns, departments=departments, status_filter=status_filter, dept_filter=dept_filter, priority_filter=priority_filter, search_query=search_query)

@app.route('/concerns/export/csv')
@login_required
@role_required('staff', 'admin')
def export_csv():
    """CSV Export Masterfile."""
    conn = get_db_connection()
    cursor = conn.cursor()
    concerns = cursor.execute("""
        SELECT c.ticket_number, u.full_name as student_name, u.student_id_number,
               u.course_program, u.campus_branch, d.department_name, cat.category_name,
               c.priority, c.status, c.sla_target_date, c.created_at, c.resolved_at,
               c.resolution_summary, staff.full_name as assigned_staff
        FROM concerns c
        JOIN departments d ON c.department_id = d.department_id
        JOIN concern_categories cat ON c.category_id = cat.category_id
        JOIN users u ON c.student_id = u.user_id
        LEFT JOIN users staff ON c.assigned_staff_id = staff.user_id
        ORDER BY c.created_at DESC
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ticket Number", "Student Name", "Student ID", "Program", "Campus",
        "Department", "Category", "Priority", "Status", "SLA Target Date",
        "Date Filed", "Date Resolved", "Resolution Summary", "Resolver Officer"
    ])
    for r in concerns:
        writer.writerow([
            r['ticket_number'], r['student_name'], r['student_id_number'], r['course_program'], r['campus_branch'],
            r['department_name'], r['category_name'], r['priority'], r['status'], r['sla_target_date'],
            r['created_at'], r['resolved_at'] or 'N/A', r['resolution_summary'] or 'N/A', r['assigned_staff'] or 'Unassigned'
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=CARD_MRI_Student_Concerns_Masterfile_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

@app.route('/users')
@login_required
@role_required('admin')
def list_users():
    """Module: User & Account Management - Displays all registered users."""
    conn = get_db_connection()
    cursor = conn.cursor()

    role_filter = request.args.get('role', 'ALL')
    search_query = request.args.get('q', '').strip()

    sql = """
        SELECT u.*, d.department_name, d.department_code
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE 1=1
    """
    params = []

    if role_filter != 'ALL':
        sql += " AND u.role = ?"
        params.append(role_filter)

    if search_query:
        sql += " AND (u.full_name LIKE ? OR u.email LIKE ? OR u.student_id_number LIKE ?)"
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard, wildcard])

    sql += " ORDER BY u.created_at DESC"
    users = cursor.execute(sql, params).fetchall()

    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_students = cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    total_staff = cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'staff'").fetchone()[0]
    total_admins = cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    conn.close()
    return render_template(
        'users.html',
        users=users,
        total_users=total_users,
        total_students=total_students,
        total_staff=total_staff,
        total_admins=total_admins,
        role_filter=role_filter,
        search_query=search_query
    )

@app.route('/reports')
@login_required
@role_required('admin')
def reports():
    """Module: Reports & SLA Analytics Hub."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total = cursor.execute("SELECT COUNT(*) FROM concerns").fetchone()[0]
    resolved = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status IN ('Resolved', 'Closed')").fetchone()[0]
    escalated = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status = 'Escalated'").fetchone()[0]
    resolution_rate = round((resolved / total * 100), 1) if total > 0 else 100.0

    avg_rating_row = cursor.execute("SELECT AVG(rating) FROM concern_feedback").fetchone()
    avg_rating = round(avg_rating_row[0], 2) if avg_rating_row and avg_rating_row[0] else 0.0

    dept_performance = cursor.execute("""
        SELECT d.department_name, d.department_code,
               COUNT(c.concern_id) as total_received,
               SUM(CASE WHEN c.status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) as total_resolved,
               SUM(CASE WHEN c.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN c.status = 'Escalated' THEN 1 ELSE 0 END) as escalated_count,
               AVG(f.rating) as avg_rating
        FROM departments d
        LEFT JOIN concerns c ON d.department_id = c.department_id
        LEFT JOIN concern_feedback f ON c.concern_id = f.concern_id
        GROUP BY d.department_id
    """).fetchall()

    status_counts = cursor.execute("""
        SELECT status, COUNT(*) as count FROM concerns GROUP BY status
    """).fetchall()

    priority_counts = cursor.execute("""
        SELECT priority, COUNT(*) as count FROM concerns GROUP BY priority
    """).fetchall()

    conn.close()
    return render_template(
        'reports.html',
        total=total,
        resolved=resolved,
        escalated=escalated,
        resolution_rate=resolution_rate,
        avg_rating=avg_rating,
        dept_performance=dept_performance,
        status_counts=status_counts,
        priority_counts=priority_counts
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting CARD MRI SCRRTS production server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
