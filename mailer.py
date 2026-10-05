"""
CARD-MRI Development Institute, Inc. (CMDI)
Student Concern Routing and Resolution Tracking System (CARD MRI SCRRTS)
Comprehensive Automated Multi-Channel Email Notification Dispatcher
"""

import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# SMTP Configuration from Environment Variables
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USER or "no-reply@cmdi.edu.ph")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "CARD MRI SCRRTS Notification Desk")
APP_URL = os.environ.get("APP_URL", "https://student-concern-system.onrender.com")

def _send_email_async(to_email, subject, html_content, text_content=None):
    """Sends an email synchronously in a background thread with error handling and fallback simulation."""
    if not to_email:
        return

    if not SMTP_USER or not SMTP_PASS:
        print(f"[MAILER SIMULATION] Dispatched email to: {to_email} | Subject: {subject}")
        print("[MAILER SIMULATION] Configure SMTP_USER and SMTP_PASS environment variables on Render to send live inbox emails.")
        return

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, 'plain'))
        if html_content:
            msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())
        server.quit()
        print(f"[MAILER SUCCESS] Live email successfully dispatched to {to_email} [{subject}]")
    except Exception as e:
        print(f"[MAILER ERROR] Failed to dispatch email to {to_email}: {str(e)}")

def dispatch_email(to_email, subject, html_content, text_content=None):
    """Dispatches email asynchronously to ensure non-blocking HTTP requests (<50ms response)."""
    thread = threading.Thread(
        target=_send_email_async,
        args=(to_email, subject, html_content, text_content),
        daemon=True
    )
    thread.start()

def _base_email_template(title_header, content_html):
    """Master CARD MRI institutional email HTML envelope."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title_header}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 25px 15px;">
        <div style="max-width: 620px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border-top: 5px solid #002d62;">
            
            <!-- CARD MRI Header Banner -->
            <div style="background-color: #002d62; color: #ffffff; padding: 25px 20px; text-align: center;">
                <div style="display: inline-block; background-color: #ffffff; color: #006837; font-weight: 800; font-size: 13px; padding: 3px 10px; border-radius: 4px; margin-bottom: 8px; letter-spacing: 1px;">CMDI</div>
                <h2 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff;">CARD-MRI Development Institute, Inc.</h2>
                <p style="margin: 6px 0 0 0; font-size: 12px; color: #e5a823; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                    Student Concern Routing &amp; Resolution Tracking System (SCRRTS)
                </p>
            </div>

            <!-- Main Body Content -->
            <div style="padding: 30px 25px; color: #1e293b; line-height: 1.6; font-size: 14px;">
                {content_html}
            </div>

            <!-- Footer -->
            <div style="background-color: #f8fafc; padding: 20px 25px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0 0 4px 0; font-weight: 600; color: #334155;">CARD-MRI Development Institute, Inc. (CMDI)</p>
                <p style="margin: 0 0 8px 0;">Bay, Laguna (Main Campus) &bull; Tagum City Campus &bull; Pasig Extension</p>
                <p style="margin: 0; color: #94a3b8; font-size: 11px;">
                    This is an automated institutional service notification. To access your portal, visit <a href="{APP_URL}" style="color: #002d62; text-decoration: underline;">{APP_URL}</a>.
                </p>
            </div>

        </div>
    </body>
    </html>
    """

# -------------------------------------------------------------
# 1. Registration Confirmation Welcome Email
# -------------------------------------------------------------
def send_registration_email(to_email, full_name, role, student_id=None, course_program=None, department_name=None, campus_branch=None):
    """Dispatches a branded CARD MRI welcome email upon user registration."""
    subject = "Welcome to CARD MRI SCRRTS - Registration Confirmation"
    role_badge = role.upper()
    campus_text = campus_branch or "Bay, Laguna (Main Campus)"

    details_html = ""
    if role == 'student':
        details_html = f"""
        <tr>
            <td style="padding: 8px 12px; font-weight: 600; color: #64748b;">Student ID:</td>
            <td style="padding: 8px 12px; color: #002d62; font-weight: 700;">{student_id or 'Pending'}</td>
        </tr>
        <tr>
            <td style="padding: 8px 12px; font-weight: 600; color: #64748b;">Academic Program:</td>
            <td style="padding: 8px 12px; color: #0f172a;">{course_program or 'N/A'}</td>
        </tr>
        """
    elif role == 'staff':
        details_html = f"""
        <tr>
            <td style="padding: 8px 12px; font-weight: 600; color: #64748b;">Department Queue:</td>
            <td style="padding: 8px 12px; color: #006837; font-weight: 700;">{department_name or 'Department Resolver'}</td>
        </tr>
        """

    content_html = f"""
        <h3 style="color: #002d62; margin-top: 0; font-size: 18px;">Welcome, {full_name}!</h3>
        <p>Your institutional account has been successfully created in the <strong>CARD MRI Student Concern Routing &amp; Resolution Tracking System</strong>.</p>
        
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin: 20px 0; padding: 15px;">
            <div style="font-weight: 700; color: #006837; font-size: 13px; text-transform: uppercase; border-bottom: 2px solid #006837; padding-bottom: 5px; margin-bottom: 10px;">
                Verified Account Credentials Summary
            </div>
            <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 12px; font-weight: 600; color: #64748b; width: 38%;">Institutional Role:</td>
                    <td style="padding: 8px 12px; color: #002d62; font-weight: 700;">{role_badge}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: 600; color: #64748b;">Registered Email:</td>
                    <td style="padding: 8px 12px; color: #0f172a;">{to_email}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: 600; color: #64748b;">Campus / Branch:</td>
                    <td style="padding: 8px 12px; color: #0f172a;">{campus_text}</td>
                </tr>
                {details_html}
            </table>
        </div>

        <p>You can now sign in using your institutional email and password to submit inquiries, monitor auto-routing, and track departmental resolutions in real-time.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{APP_URL}/login" style="background-color: #002d62; color: #ffffff; padding: 12px 32px; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; display: inline-block;">
                Sign In to CARD MRI Portal &rarr;
            </a>
        </div>

        <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px; margin-top: 20px; font-size: 12px; color: #92400e; border-radius: 4px;">
            <strong>Security Notice:</strong> CARD MRI will never ask for your password. Please protect your institutional credentials.
        </div>
    """
    dispatch_email(to_email, subject, _base_email_template(subject, content_html))

# -------------------------------------------------------------
# 2. Student Concern Intake Confirmation Email
# -------------------------------------------------------------
def send_new_ticket_student_email(to_email, student_name, ticket_number, subject_text, category_name, department_name, priority, sla_target_date):
    """Notifies student that their inquiry has been successfully submitted and auto-routed."""
    email_subject = f"[{ticket_number}] Inquiry Intake Confirmation - CARD MRI SCRRTS"
    
    priority_color = "#ef4444" if priority == 'URGENT' else ("#f97316" if priority == 'HIGH' else "#0284c7")

    content_html = f"""
        <h3 style="color: #002d62; margin-top: 0; font-size: 18px;">Hello {student_name},</h3>
        <p>Your concern has been successfully filed and auto-routed to the designated CARD MRI department.</p>

        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin: 20px 0; padding: 18px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #002d62; padding-bottom: 8px; margin-bottom: 12px;">
                <span style="font-weight: 700; color: #002d62; font-size: 15px;">Tracking Code: {ticket_number}</span>
                <span style="background-color: {priority_color}; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">{priority} PRIORITY</span>
            </div>
            <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b; width: 35%;">Subject / Title:</td>
                    <td style="padding: 6px 0; color: #0f172a; font-weight: 600;">{subject_text}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b;">Inquiry Category:</td>
                    <td style="padding: 6px 0; color: #0f172a;">{category_name}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b;">Routed Department:</td>
                    <td style="padding: 6px 0; color: #006837; font-weight: 700;">{department_name}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b;">Target SLA Resolution:</td>
                    <td style="padding: 6px 0; color: #0f172a;"><strong>{sla_target_date}</strong></td>
                </tr>
            </table>
        </div>

        <p>The handling department will review your concern and provide official updates. You will be notified automatically via email on status progress.</p>

        <div style="text-align: center; margin: 25px 0;">
            <a href="{APP_URL}/login" style="background-color: #002d62; color: #ffffff; padding: 11px 28px; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; display: inline-block;">
                Track Ticket Timeline &rarr;
            </a>
        </div>
    """
    dispatch_email(to_email, email_subject, _base_email_template(email_subject, content_html))

# -------------------------------------------------------------
# 3. Department Staff New Ticket Queue Alert
# -------------------------------------------------------------
def send_new_ticket_department_email(dept_email, department_name, ticket_number, student_name, student_id, program, subject_text, priority, sla_target_date):
    """Notifies department resolvers when a new inquiry lands in their action queue."""
    email_subject = f"[Action Required - {priority}] New Ticket {ticket_number} in {department_name} Queue"
    
    content_html = f"""
        <h3 style="color: #006837; margin-top: 0; font-size: 18px;">New Student Inquiry Dispatched</h3>
        <p>A new concern ticket has been auto-routed to the <strong>{department_name}</strong> action queue.</p>

        <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; margin: 20px 0; padding: 18px;">
            <div style="font-weight: 700; color: #002d62; font-size: 15px; border-bottom: 2px solid #006837; padding-bottom: 6px; margin-bottom: 12px;">
                Ticket #{ticket_number} &bull; Priority: {priority}
            </div>
            <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b; width: 35%;">Student Name:</td>
                    <td style="padding: 6px 0; color: #0f172a; font-weight: 700;">{student_name} ({student_id or 'N/A'})</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b;">Academic Program:</td>
                    <td style="padding: 6px 0; color: #0f172a;">{program or 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b;">Inquiry Subject:</td>
                    <td style="padding: 6px 0; color: #0f172a; font-weight: 600;">{subject_text}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: 600; color: #64748b;">SLA Target Deadline:</td>
                    <td style="padding: 6px 0; color: #b91c1c; font-weight: 700;">{sla_target_date}</td>
                </tr>
            </table>
        </div>

        <p>Please log in to claim this ticket, post confidential internal notes, and initiate investigation.</p>

        <div style="text-align: center; margin: 25px 0;">
            <a href="{APP_URL}/login" style="background-color: #006837; color: #ffffff; padding: 11px 28px; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; display: inline-block;">
                Open Department Action Queue &rarr;
            </a>
        </div>
    """
    dispatch_email(dept_email, email_subject, _base_email_template(email_subject, content_html))

# -------------------------------------------------------------
# 4. Ticket Claimed by Staff Notification Email
# -------------------------------------------------------------
def send_ticket_claimed_email(to_email, student_name, ticket_number, staff_name, department_name):
    """Notifies student that a specific department officer has claimed and is handling their ticket."""
    email_subject = f"[{ticket_number}] Officer Assigned: In Progress - CARD MRI SCRRTS"
    
    content_html = f"""
        <h3 style="color: #002d62; margin-top: 0; font-size: 18px;">Hello {student_name},</h3>
        <p>Good news! Your concern ticket <strong>{ticket_number}</strong> has been claimed for investigation.</p>

        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin: 20px 0; padding: 18px;">
            <p style="margin: 0 0 10px 0;"><strong>Assigned Resolver Officer:</strong> <span style="color: #002d62; font-weight: 700;">{staff_name}</span></p>
            <p style="margin: 0 0 10px 0;"><strong>Handling Department:</strong> <span style="color: #006837; font-weight: 600;">{department_name}</span></p>
            <p style="margin: 0;"><strong>Current Status:</strong> <span style="background-color: #eab308; color: #000000; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 700;">IN PROGRESS</span></p>
        </div>

        <p>Officer {staff_name} is actively working on your request. You will receive an email once an official resolution or progress note is posted.</p>

        <div style="text-align: center; margin: 25px 0;">
            <a href="{APP_URL}/login" style="background-color: #002d62; color: #ffffff; padding: 11px 28px; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; display: inline-block;">
                View Ticket Timeline &rarr;
            </a>
        </div>
    """
    dispatch_email(to_email, email_subject, _base_email_template(email_subject, content_html))

# -------------------------------------------------------------
# 5. Escalation Notification Email
# -------------------------------------------------------------
def send_ticket_escalated_email(to_email, recipient_name, ticket_number, subject_text, department_name, escalation_reason, is_admin=False):
    """High-priority notification when a ticket is escalated for supervisory intervention."""
    email_subject = f"[ESCALATION ALERT] Ticket {ticket_number} Requires Supervisory Action"
    
    content_html = f"""
        <h3 style="color: #dc2626; margin-top: 0; font-size: 18px;">⚠️ Escalation Alert: Ticket #{ticket_number}</h3>
        <p>Hello <strong>{recipient_name}</strong>,</p>
        <p>This inquiry ticket has been escalated for departmental supervisory / administrative intervention.</p>

        <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626; border-radius: 6px; margin: 20px 0; padding: 16px;">
            <p style="margin: 0 0 8px 0; color: #991b1b; font-weight: 700;">ESCALATION JUSTIFICATION:</p>
            <p style="margin: 0 0 12px 0; color: #450a0a; font-style: italic;">"{escalation_reason}"</p>
            <p style="margin: 0; font-size: 13px; color: #7f1d1d;"><strong>Department Involved:</strong> {department_name} &bull; <strong>Subject:</strong> {subject_text}</p>
        </div>

        <p>{'Please log in to the administrative command console to review and expedite this ticket.' if is_admin else 'Our department supervisor has been alerted and will fast-track your inquiry resolution.'}</p>

        <div style="text-align: center; margin: 25px 0;">
            <a href="{APP_URL}/login" style="background-color: #dc2626; color: #ffffff; padding: 11px 28px; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; display: inline-block;">
                Open Escalated Ticket &rarr;
            </a>
        </div>
    """
    dispatch_email(to_email, email_subject, _base_email_template(email_subject, content_html))

# -------------------------------------------------------------
# 6. Ticket Status Update / Resolution Email
# -------------------------------------------------------------
def send_concern_status_email(to_email, student_name, ticket_number, subject_text, new_status, department_name, action_notes=None):
    """Dispatches formal resolution notification or status transition details."""
    subject = f"[{ticket_number}] Concern Status Update: {new_status}"
    
    badge_bg = "#006837" if new_status == 'Resolved' else ("#dc2626" if new_status == 'Rejected' else "#002d62")

    content_html = f"""
        <h3 style="color: #002d62; margin-top: 0; font-size: 18px;">Hello {student_name},</h3>
        <p>An official status update has been recorded on your filed inquiry ticket:</p>

        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 20px 0;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid {badge_bg}; padding-bottom: 8px; margin-bottom: 12px;">
                <span style="font-weight: 700; color: #002d62; font-size: 15px;">Ticket #{ticket_number}</span>
                <span style="background-color: {badge_bg}; color: #ffffff; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 12px; text-transform: uppercase;">
                    {new_status}
                </span>
            </div>
            <p style="margin: 0 0 8px 0;"><strong>Inquiry Subject:</strong> {subject_text}</p>
            <p style="margin: 0 0 8px 0;"><strong>Handling Department:</strong> {department_name}</p>
            {f'''
            <div style="margin-top: 12px; padding: 12px; background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;">
                <strong style="color: #002d62; font-size: 13px; display: block; margin-bottom: 4px;">Official Resolution / Policy Remarks:</strong>
                <span style="color: #334155;">{action_notes}</span>
            </div>
            ''' if action_notes else ''}
        </div>

        <p>{'Please log in to your portal to review the resolution details, confirm closure of your ticket, and submit your satisfaction rating (1-5 stars).' if new_status == 'Resolved' else 'You may review the full audit trail and resolution timeline in your portal.'}</p>

        <div style="text-align: center; margin: 25px 0;">
            <a href="{APP_URL}/login" style="background-color: #002d62; color: #ffffff; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; display: inline-block;">
                View Concern &amp; Rate Service &rarr;
            </a>
        </div>
    """
    dispatch_email(to_email, subject, _base_email_template(subject, content_html))

# -------------------------------------------------------------
# 7. Student Satisfaction Feedback Notification
# -------------------------------------------------------------
def send_feedback_notification_email(resolver_email, student_name, ticket_number, rating, comments, department_name):
    """Notifies handling staff when student evaluates and closes the ticket."""
    email_subject = f"[{ticket_number}] Service Evaluation Feedback: {rating}/5 Stars"
    
    stars_rendered = "&#9733;" * rating + "&#9734;" * (5 - rating)

    content_html = f"""
        <h3 style="color: #006837; margin-top: 0; font-size: 18px;">Student Service Evaluation Received</h3>
        <p>Student <strong>{student_name}</strong> has confirmed resolution and rated the service quality for Ticket <strong>{ticket_number}</strong>.</p>

        <div style="background-color: #fefce8; border: 1px solid #fef08a; border-radius: 8px; padding: 18px; margin: 20px 0; text-align: center;">
            <div style="font-size: 24px; color: #eab308; margin-bottom: 6px;">{stars_rendered}</div>
            <div style="font-size: 16px; font-weight: 700; color: #713f12;">{rating} out of 5 Stars Rating</div>
            {f'<p style="margin: 12px 0 0 0; font-style: italic; color: #854d0e; font-size: 13px;">"{comments}"</p>' if comments else ''}
        </div>

        <p style="font-size: 13px; color: #64748b;">This rating has been incorporated into {department_name}'s SLA Quality Scorecard.</p>
    """
    dispatch_email(resolver_email, email_subject, _base_email_template(email_subject, content_html))
