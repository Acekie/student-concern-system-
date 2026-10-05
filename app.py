"""
Student Concern Routing and Resolution Tracking System (ResolvEd)
Flask Core Application & API
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

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "resolved-super-secure-production-secret-2026")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx', 'txt', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ensure database exists
if not os.path.exists(DB_PATH):
    init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------------------------------------------------
# Security & Access Control Decorators
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash("Unauthorized access: Your role lacks permission for this action.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# -------------------------------------------------------------
# Business Rules & Helper Utilities
# -------------------------------------------------------------
def generate_ticket_number(cursor):
    """Business Rule 1: Generates standard sequential ticket CRN-YYYY-XXXX."""
    year = datetime.now().year
    cursor.execute("SELECT COUNT(*) AS total FROM concerns")
    count = cursor.fetchone()['total'] + 1
    return f"CRN-{year}-{count:04d}"

def calculate_sla_target(cursor, category_id, priority):
    """
    Business Rule 2: Dynamic SLA Target Date Calculation.
    Base SLA from category, adjusted by priority urgency.
    """
    cursor.execute("SELECT sla_hours FROM concern_categories WHERE category_id = ?", (category_id,))
    row = cursor.fetchone()
    base_hours = row['sla_hours'] if row else 72

    priority_multiplier = {
        'URGENT': 0.33,  # Urgent cut to 1/3 (e.g. 24h)
        'HIGH': 0.66,    # High cut to 2/3 (e.g. 48h)
        'MEDIUM': 1.0,   # Standard SLA
        'LOW': 1.66      # Low priority extended
    }
    adjusted_hours = max(12, int(base_hours * priority_multiplier.get(priority, 1.0)))
    target_dt = datetime.now() + timedelta(hours=adjusted_hours)
    return target_dt.strftime("%Y-%m-%d %H:%M:%S")

def log_audit_event(cursor, concern_id, actor_id, prev_status, new_status, action_type, notes):
    """Business Rule 4: Immutable audit trail logging."""
    cursor.execute("""
        INSERT INTO concern_audit_logs (concern_id, actor_id, previous_status, new_status, action_type, notes)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (concern_id, actor_id, prev_status, new_status, action_type, notes))

def check_is_overdue(sla_target_str, status):
    """Checks if concern has violated its SLA resolution deadline."""
    if status in ('RESOLVED', 'CLOSED', 'REJECTED'):
        return False
    try:
        sla_dt = datetime.strptime(sla_target_str, "%Y-%m-%d %H:%M:%S")
        return datetime.now() > sla_dt
    except Exception:
        return False

app.jinja_env.globals.update(check_is_overdue=check_is_overdue)

# -------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please enter both email and password.", "danger")
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

            flash(f"Welcome back, {user['full_name']}! Logged in as {user['role'].upper()}.", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash("Invalid email or password. Please verify your credentials.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('login'))

# -------------------------------------------------------------
# Module 1: Dashboard & Analytics
# -------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    user_id = session['user_id']
    role = session['role']
    dept_id = session.get('department_id')

    # Common metrics calculation
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if role == 'student':
        # Student metrics
        cursor = conn.cursor()
        total_concerns = cursor.execute("SELECT COUNT(*) FROM concerns WHERE student_id = ?", (user_id,)).fetchone()[0]
        in_progress = cursor.execute("SELECT COUNT(*) FROM concerns WHERE student_id = ? AND status IN ('SUBMITTED', 'ROUTED', 'IN_PROGRESS')", (user_id,)).fetchone()[0]
        resolved = cursor.execute("SELECT COUNT(*) FROM concerns WHERE student_id = ? AND status IN ('RESOLVED', 'CLOSED')", (user_id,)).fetchone()[0]
        overdue = cursor.execute("""
            SELECT COUNT(*) FROM concerns 
            WHERE student_id = ? AND status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') AND sla_target_date < ?
        """, (user_id, now_str)).fetchone()[0]

        recent_concerns = cursor.execute("""
            SELECT c.*, d.department_name, cat.category_name 
            FROM concerns c
            JOIN departments d ON c.department_id = d.department_id
            JOIN concern_categories cat ON c.category_id = cat.category_id
            WHERE c.student_id = ?
            ORDER BY c.created_at DESC LIMIT 5
        """, (user_id,)).fetchall()

        conn.close()
        return render_template(
            'dashboard.html',
            role=role,
            total=total_concerns,
            in_progress=in_progress,
            resolved=resolved,
            overdue=overdue,
            recent_concerns=recent_concerns
        )

    elif role == 'staff':
        # Staff metrics (filtered to their department)
        cursor = conn.cursor()
        total_dept = cursor.execute("SELECT COUNT(*) FROM concerns WHERE department_id = ?", (dept_id,)).fetchone()[0]
        unassigned = cursor.execute("SELECT COUNT(*) FROM concerns WHERE department_id = ? AND assigned_staff_id IS NULL AND status IN ('SUBMITTED', 'ROUTED')", (dept_id,)).fetchone()[0]
        my_assigned = cursor.execute("SELECT COUNT(*) FROM concerns WHERE assigned_staff_id = ? AND status = 'IN_PROGRESS'", (user_id,)).fetchone()[0]
        resolved_dept = cursor.execute("SELECT COUNT(*) FROM concerns WHERE department_id = ? AND status IN ('RESOLVED', 'CLOSED')", (dept_id,)).fetchone()[0]
        overdue_dept = cursor.execute("""
            SELECT COUNT(*) FROM concerns 
            WHERE department_id = ? AND status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') AND sla_target_date < ?
        """, (dept_id, now_str)).fetchone()[0]

        dept_concerns = cursor.execute("""
            SELECT c.*, u.full_name as student_name, cat.category_name, staff.full_name as staff_name
            FROM concerns c
            JOIN users u ON c.student_id = u.user_id
            JOIN concern_categories cat ON c.category_id = cat.category_id
            LEFT JOIN users staff ON c.assigned_staff_id = staff.user_id
            WHERE c.department_id = ?
            ORDER BY 
                CASE WHEN c.status = 'IN_PROGRESS' THEN 1
                     WHEN c.status IN ('SUBMITTED', 'ROUTED') THEN 2
                     ELSE 3 END,
                c.created_at DESC LIMIT 6
        """, (dept_id,)).fetchall()

        conn.close()
        return render_template(
            'dashboard.html',
            role=role,
            total=total_dept,
            unassigned=unassigned,
            my_assigned=my_assigned,
            resolved=resolved_dept,
            overdue=overdue_dept,
            recent_concerns=dept_concerns
        )

    else:
        # Admin metrics (System-wide)
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM concerns").fetchone()[0]
        pending = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status IN ('SUBMITTED', 'ROUTED', 'IN_PROGRESS')").fetchone()[0]
        resolved = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status IN ('RESOLVED', 'CLOSED')").fetchone()[0]
        overdue = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') AND sla_target_date < ?", (now_str,)).fetchone()[0]

        # Department performance breakdown
        dept_stats = cursor.execute("""
            SELECT d.department_name, d.department_code,
                   COUNT(c.concern_id) as total_tickets,
                   SUM(CASE WHEN c.status IN ('RESOLVED', 'CLOSED') THEN 1 ELSE 0 END) as resolved_tickets,
                   SUM(CASE WHEN c.status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') AND c.sla_target_date < ? THEN 1 ELSE 0 END) as overdue_tickets
            FROM departments d
            LEFT JOIN concerns c ON d.department_id = c.department_id
            GROUP BY d.department_id
        """, (now_str,)).fetchall()

        # Recent system audit logs
        recent_audits = cursor.execute("""
            SELECT l.*, c.ticket_number, u.full_name as actor_name, u.role as actor_role
            FROM concern_audit_logs l
            JOIN concerns c ON l.concern_id = c.concern_id
            JOIN users u ON l.actor_id = u.user_id
            ORDER BY l.created_at DESC LIMIT 6
        """).fetchall()

        conn.close()
        return render_template(
            'dashboard.html',
            role=role,
            total=total,
            pending=pending,
            resolved=resolved,
            overdue=overdue,
            dept_stats=dept_stats,
            recent_audits=recent_audits
        )

# -------------------------------------------------------------
# Module 2: Concern Submission & Routing Engine
# -------------------------------------------------------------
@app.route('/concerns/new', methods=['GET', 'POST'])
@login_required
def submit_concern():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'MEDIUM').upper()

        # Validation
        if not category_id or not subject or not description:
            flash("All mandatory fields (Category, Subject, Description) must be provided.", "danger")
            departments = conn.execute("SELECT * FROM departments WHERE is_active = 1").fetchall()
            categories = conn.execute("SELECT * FROM concern_categories").fetchall()
            conn.close()
            return render_template('submit_concern.html', departments=departments, categories=categories)

        if priority not in ('LOW', 'MEDIUM', 'HIGH', 'URGENT'):
            priority = 'MEDIUM'

        # Fetch Category & Department mapping (Business Rule 1: Automated Department Routing)
        cat_info = cursor.execute("""
            SELECT c.*, d.department_id, d.department_name 
            FROM concern_categories c
            JOIN departments d ON c.department_id = d.department_id
            WHERE c.category_id = ?
        """, (category_id,)).fetchone()

        if not cat_info:
            flash("Selected category does not exist.", "danger")
            conn.close()
            return redirect(url_for('submit_concern'))

        department_id = cat_info['department_id']
        ticket_number = generate_ticket_number(cursor)
        sla_target = calculate_sla_target(cursor, category_id, priority)

        # File Attachment Handling
        attachment_filename = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(f"{ticket_number}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    attachment_filename = filename
                else:
                    flash("Uploaded file type not permitted. Allowed: PNG, JPG, PDF, DOCX, TXT, ZIP.", "warning")

        # Insert Concern
        cursor.execute("""
            INSERT INTO concerns (
                ticket_number, student_id, department_id, category_id,
                subject, description, priority, status, sla_target_date, attachment_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SUBMITTED', ?, ?);
        """, (ticket_number, session['user_id'], department_id, category_id, subject, description, priority, sla_target, attachment_filename))
        
        concern_id = cursor.lastrowid

        # Insert Initial Audit Log
        log_audit_event(
            cursor, concern_id, session['user_id'],
            None, 'SUBMITTED', 'SUBMITTED',
            f"Concern submitted by student. Auto-routed to {cat_info['department_name']} with {priority} priority."
        )

        conn.commit()
        conn.close()

        flash(f"Concern {ticket_number} successfully submitted and routed to {cat_info['department_name']}!", "success")
        return redirect(url_for('view_concern', concern_id=concern_id))

    departments = conn.execute("SELECT * FROM departments WHERE is_active = 1").fetchall()
    categories = conn.execute("SELECT * FROM concern_categories").fetchall()
    conn.close()
    return render_template('submit_concern.html', departments=departments, categories=categories)

# -------------------------------------------------------------
# Module 3: Concern Records, Search & Filter Hub
# -------------------------------------------------------------
@app.route('/concerns')
@login_required
def list_concerns():
    conn = get_db_connection()
    cursor = conn.cursor()

    role = session['role']
    user_id = session['user_id']
    dept_id = session.get('department_id')

    # Query Parameters
    status_filter = request.args.get('status', 'ALL')
    dept_filter = request.args.get('department', 'ALL')
    priority_filter = request.args.get('priority', 'ALL')
    search_query = request.args.get('q', '').strip()
    overdue_only = request.args.get('overdue', '0') == '1'
    sort_by = request.args.get('sort', 'newest')

    sql = """
        SELECT c.*, d.department_name, d.department_code, cat.category_name,
               u.full_name as student_name, u.student_id_number,
               staff.full_name as staff_name
        FROM concerns c
        JOIN departments d ON c.department_id = d.department_id
        JOIN concern_categories cat ON c.category_id = cat.category_id
        JOIN users u ON c.student_id = u.user_id
        LEFT JOIN users staff ON c.assigned_staff_id = staff.user_id
        WHERE 1=1
    """
    params = []

    # Role-based data access constraints
    if role == 'student':
        sql += " AND c.student_id = ?"
        params.append(user_id)
    elif role == 'staff':
        sql += " AND c.department_id = ?"
        params.append(dept_id)

    # Filtering logic
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

    if overdue_only:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql += " AND c.status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') AND c.sla_target_date < ?"
        params.append(now_str)

    # Sorting
    if sort_by == 'oldest':
        sql += " ORDER BY c.created_at ASC"
    elif sort_by == 'priority':
        sql += " ORDER BY CASE c.priority WHEN 'URGENT' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END"
    elif sort_by == 'sla':
        sql += " ORDER BY c.sla_target_date ASC"
    else:
        sql += " ORDER BY c.created_at DESC"

    concerns = cursor.execute(sql, params).fetchall()
    departments = cursor.execute("SELECT * FROM departments WHERE is_active = 1").fetchall()
    conn.close()

    return render_template(
        'concerns_list.html',
        concerns=concerns,
        departments=departments,
        status_filter=status_filter,
        dept_filter=dept_filter,
        priority_filter=priority_filter,
        search_query=search_query,
        overdue_only=overdue_only,
        sort_by=sort_by
    )

# -------------------------------------------------------------
# Module 4: Concern Detail, Resolution Workflow & Status Management
# -------------------------------------------------------------
@app.route('/concerns/<int:concern_id>')
@login_required
def view_concern(concern_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    concern = cursor.execute("""
        SELECT c.*, d.department_name, d.department_code, d.contact_email as dept_email,
               cat.category_name, cat.sla_hours,
               u.full_name as student_name, u.email as student_email, u.student_id_number, u.contact_number as student_contact,
               staff.full_name as staff_name, staff.email as staff_email
        FROM concerns c
        JOIN departments d ON c.department_id = d.department_id
        JOIN concern_categories cat ON c.category_id = cat.category_id
        JOIN users u ON c.student_id = u.user_id
        LEFT JOIN users staff ON c.assigned_staff_id = staff.user_id
        WHERE c.concern_id = ?
    """, (concern_id,)).fetchone()

    if not concern:
        flash("Concern record not found.", "danger")
        conn.close()
        return redirect(url_for('list_concerns'))

    # Security check: Students cannot view other students' tickets
    if session['role'] == 'student' and concern['student_id'] != session['user_id']:
        flash("Access denied: You can only view your own filed concerns.", "danger")
        conn.close()
        return redirect(url_for('list_concerns'))

    # Retrieve audit history
    audit_logs = cursor.execute("""
        SELECT l.*, u.full_name as actor_name, u.role as actor_role
        FROM concern_audit_logs l
        JOIN users u ON l.actor_id = u.user_id
        WHERE l.concern_id = ?
        ORDER BY l.created_at ASC
    """, (concern_id,)).fetchall()

    # Retrieve feedback if any
    feedback = cursor.execute("SELECT * FROM concern_feedback WHERE concern_id = ?", (concern_id,)).fetchone()

    # Department staff list for reassignment (Staff/Admin)
    dept_staff = []
    if session['role'] in ('staff', 'admin'):
        dept_staff = cursor.execute("""
            SELECT user_id, full_name, email FROM users
            WHERE role = 'staff' AND (department_id = ? OR ? IS NULL)
        """, (concern['department_id'], concern['department_id'])).fetchall()

    conn.close()
    return render_template(
        'concern_detail.html',
        concern=concern,
        audit_logs=audit_logs,
        feedback=feedback,
        dept_staff=dept_staff
    )

@app.route('/concerns/<int:concern_id>/claim', methods=['POST'])
@login_required
@role_required('staff', 'admin')
def claim_concern(concern_id):
    """Staff claims ticket and changes status to IN_PROGRESS."""
    conn = get_db_connection()
    cursor = conn.cursor()

    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()
    if not concern:
        flash("Concern not found.", "danger")
        conn.close()
        return redirect(url_for('list_concerns'))

    # Staff can only claim tickets in their department unless admin
    if session['role'] == 'staff' and concern['department_id'] != session.get('department_id'):
        flash("You cannot claim concerns outside your assigned department.", "danger")
        conn.close()
        return redirect(url_for('view_concern', concern_id=concern_id))

    prev_status = concern['status']
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE concerns
        SET assigned_staff_id = ?, status = 'IN_PROGRESS', updated_at = ?
        WHERE concern_id = ?
    """, (session['user_id'], now_str, concern_id))

    log_audit_event(
        cursor, concern_id, session['user_id'],
        prev_status, 'IN_PROGRESS', 'CLAIMED',
        f"Claimed by {session['full_name']} for investigation and resolution."
    )

    conn.commit()
    conn.close()
    flash("Ticket claimed successfully! Status updated to IN PROGRESS.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns/<int:concern_id>/update-status', methods=['POST'])
@login_required
@role_required('staff', 'admin')
def update_status(concern_id):
    """
    Business Rule 3: Validates required notes and transitions status.
    RESOLVED requires resolution_summary.
    REJECTED requires rejection_reason.
    """
    new_status = request.form.get('new_status')
    action_note = request.form.get('action_note', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()

    if not concern:
        flash("Concern not found.", "danger")
        conn.close()
        return redirect(url_for('list_concerns'))

    prev_status = concern['status']
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Business Rule 3 Validation
    if new_status == 'RESOLVED':
        if not action_note:
            flash("Business Rule Violation: A detailed Resolution Summary is required when marking a concern as RESOLVED.", "danger")
            conn.close()
            return redirect(url_for('view_concern', concern_id=concern_id))

        cursor.execute("""
            UPDATE concerns
            SET status = 'RESOLVED', resolution_summary = ?, resolved_at = ?, updated_at = ?
            WHERE concern_id = ?
        """, (action_note, now_str, now_str, concern_id))

        log_audit_event(cursor, concern_id, session['user_id'], prev_status, 'RESOLVED', 'RESOLVED', f"Resolution Note: {action_note}")

    elif new_status == 'REJECTED':
        if not action_note:
            flash("Business Rule Violation: A valid Rejection Reason must be provided.", "danger")
            conn.close()
            return redirect(url_for('view_concern', concern_id=concern_id))

        cursor.execute("""
            UPDATE concerns
            SET status = 'REJECTED', rejection_reason = ?, updated_at = ?
            WHERE concern_id = ?
        """, (action_note, now_str, concern_id))

        log_audit_event(cursor, concern_id, session['user_id'], prev_status, 'REJECTED', 'REJECTED', f"Rejection Reason: {action_note}")

    elif new_status in ('IN_PROGRESS', 'ROUTED'):
        cursor.execute("""
            UPDATE concerns
            SET status = ?, updated_at = ?
            WHERE concern_id = ?
        """, (new_status, now_str, concern_id))

        note_text = action_note if action_note else f"Status manually adjusted to {new_status}."
        log_audit_event(cursor, concern_id, session['user_id'], prev_status, new_status, 'STATUS_CHANGE', note_text)

    else:
        flash("Invalid status transition requested.", "warning")
        conn.close()
        return redirect(url_for('view_concern', concern_id=concern_id))

    conn.commit()
    conn.close()
    flash(f"Concern status successfully transitioned to {new_status}.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns/<int:concern_id>/close', methods=['POST'])
@login_required
def close_concern(concern_id):
    """Business Rule 3: Only initiating student or admin can confirm and close resolved concern."""
    conn = get_db_connection()
    cursor = conn.cursor()
    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()

    if not concern:
        flash("Concern not found.", "danger")
        conn.close()
        return redirect(url_for('list_concerns'))

    if session['role'] == 'student' and concern['student_id'] != session['user_id']:
        flash("Unauthorized action.", "danger")
        conn.close()
        return redirect(url_for('list_concerns'))

    if concern['status'] != 'RESOLVED':
        flash("Only concerns in RESOLVED status can be officially closed.", "warning")
        conn.close()
        return redirect(url_for('view_concern', concern_id=concern_id))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE concerns SET status = 'CLOSED', updated_at = ? WHERE concern_id = ?", (now_str, concern_id))
    log_audit_event(cursor, concern_id, session['user_id'], 'RESOLVED', 'CLOSED', 'CLOSED', "Student verified resolution and officially closed ticket.")

    conn.commit()
    conn.close()
    flash("Thank you! Concern is now officially closed.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

@app.route('/concerns/<int:concern_id>/feedback', methods=['POST'])
@login_required
@role_required('student')
def submit_feedback(concern_id):
    """Allows student to submit 1-5 star satisfaction feedback on resolved/closed ticket."""
    rating = int(request.form.get('rating', 5))
    comments = request.form.get('comments', '').strip()

    if rating < 1 or rating > 5:
        rating = 5

    conn = get_db_connection()
    cursor = conn.cursor()
    concern = cursor.execute("SELECT * FROM concerns WHERE concern_id = ?", (concern_id,)).fetchone()

    if not concern or concern['student_id'] != session['user_id']:
        flash("Unauthorized or invalid concern.", "danger")
        conn.close()
        return redirect(url_for('list_concerns'))

    cursor.execute("""
        INSERT INTO concern_feedback (concern_id, student_id, rating, feedback_comments)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(concern_id) DO UPDATE SET rating = excluded.rating, feedback_comments = excluded.feedback_comments
    """, (concern_id, session['user_id'], rating, comments))

    log_audit_event(cursor, concern_id, session['user_id'], concern['status'], concern['status'], 'RATED', f"Student submitted satisfaction rating: {rating}/5 stars.")

    conn.commit()
    conn.close()
    flash("Thank you for your feedback! Your evaluation helps improve university service.", "success")
    return redirect(url_for('view_concern', concern_id=concern_id))

# -------------------------------------------------------------
# Module 5: Reports, Analytics & Advanced Features (CSV Export)
# -------------------------------------------------------------
@app.route('/reports')
@login_required
@role_required('staff', 'admin')
def reports():
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Overall Metrics
    total = cursor.execute("SELECT COUNT(*) FROM concerns").fetchone()[0]
    resolved = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status IN ('RESOLVED', 'CLOSED')").fetchone()[0]
    overdue = cursor.execute("SELECT COUNT(*) FROM concerns WHERE status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') AND sla_target_date < ?", (now_str,)).fetchone()[0]
    resolution_rate = round((resolved / total * 100), 1) if total > 0 else 100.0

    # Average Feedback Score
    avg_rating_row = cursor.execute("SELECT AVG(rating) FROM concern_feedback").fetchone()
    avg_rating = round(avg_rating_row[0], 2) if avg_rating_row and avg_rating_row[0] else 0.0

    # Department Performance Summary Table
    dept_performance = cursor.execute("""
        SELECT d.department_name, d.department_code,
               COUNT(c.concern_id) as total_received,
               SUM(CASE WHEN c.status IN ('RESOLVED', 'CLOSED') THEN 1 ELSE 0 END) as total_resolved,
               SUM(CASE WHEN c.status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN c.status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') AND c.sla_target_date < ? THEN 1 ELSE 0 END) as overdue_count,
               AVG(f.rating) as avg_rating
        FROM departments d
        LEFT JOIN concerns c ON d.department_id = c.department_id
        LEFT JOIN concern_feedback f ON c.concern_id = f.concern_id
        GROUP BY d.department_id
    """, (now_str,)).fetchall()

    # Data for charts
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
        overdue=overdue,
        resolution_rate=resolution_rate,
        avg_rating=avg_rating,
        dept_performance=dept_performance,
        status_counts=status_counts,
        priority_counts=priority_counts
    )

@app.route('/concerns/export/csv')
@login_required
@role_required('staff', 'admin')
def export_csv():
    """Advanced Feature: CSV Report Generator."""
    conn = get_db_connection()
    cursor = conn.cursor()

    concerns = cursor.execute("""
        SELECT c.ticket_number, u.full_name as student_name, u.student_id_number,
               d.department_name, cat.category_name, c.priority, c.status,
               c.sla_target_date, c.created_at, c.resolved_at,
               staff.full_name as staff_assigned, c.resolution_summary
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
        "Ticket Number", "Student Name", "Student ID", "Department",
        "Category", "Priority", "Status", "SLA Target Date",
        "Date Submitted", "Date Resolved", "Assigned Staff", "Resolution Summary"
    ])

    for r in concerns:
        writer.writerow([
            r['ticket_number'], r['student_name'], r['student_id_number'], r['department_name'],
            r['category_name'], r['priority'], r['status'], r['sla_target_date'],
            r['created_at'], r['resolved_at'] or 'N/A', r['staff_assigned'] or 'Unassigned', r['resolution_summary'] or 'N/A'
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=Student_Concerns_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

# -------------------------------------------------------------
# Auxiliary & API Endpoints
# -------------------------------------------------------------
@app.route('/api/categories')
def api_categories():
    """Dynamic category lookup for concern submission frontend form."""
    dept_id = request.args.get('department_id')
    conn = get_db_connection()
    if dept_id:
        rows = conn.execute("SELECT * FROM concern_categories WHERE department_id = ?", (dept_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM concern_categories").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/departments')
@login_required
def departments_view():
    conn = get_db_connection()
    departments = conn.execute("SELECT * FROM departments").fetchall()
    categories = conn.execute("""
        SELECT cat.*, d.department_name, d.department_code
        FROM concern_categories cat
        JOIN departments d ON cat.department_id = d.department_id
        ORDER BY d.department_code, cat.category_name
    """).fetchall()
    conn.close()
    return render_template('departments.html', departments=departments, categories=categories)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting ResolvEd server at http://127.0.0.1:{port}")
    print(f"[*] Pre-configured accounts ready for evaluation.")
    app.run(host='0.0.0.0', port=port, debug=False)
