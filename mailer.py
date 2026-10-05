"""
CARD-MRI Development Institute, Inc. (CMDI)
Student Concern Routing and Resolution Tracking System (CARD MRI SCRRTS)
Automated Email Notification Service & Dispatcher
"""

import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# SMTP Configuration from Environment Variables (or default fallback for staging/dev)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USER or "no-reply@cmdi.edu.ph")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "CARD MRI SCRRTS - CMDI Portal")
APP_URL = os.environ.get("APP_URL", "https://student-concern-system.onrender.com")

def _send_email_async(to_email, subject, html_content, text_content=None):
    """Sends an email synchronously in a background thread."""
    if not SMTP_USER or not SMTP_PASS:
        print(f"[MAILER SIMULATION] To: {to_email} | Subject: {subject}")
        print("[MAILER SIMULATION] Note: Set SMTP_USER and SMTP_PASS environment variables to dispatch live emails.")
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

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())
        server.quit()
        print(f"[MAILER SUCCESS] Email successfully dispatched to {to_email} [{subject}]")
    except Exception as e:
        print(f"[MAILER ERROR] Failed to send email to {to_email}: {str(e)}")

def dispatch_email(to_email, subject, html_content, text_content=None):
    """Dispatches email asynchronously to avoid blocking the HTTP request thread."""
    thread = threading.Thread(
        target=_send_email_async,
        args=(to_email, subject, html_content, text_content),
        daemon=True
    )
    thread.start()

def send_registration_email(to_email, full_name, role, student_id=None, course_program=None, department_name=None, campus_branch=None):
    """
    Dispatches a branded CARD MRI welcome email upon successful account registration.
    """
    subject = "Welcome to CARD MRI SCRRTS - Registration Confirmation"

    role_badge = role.upper()
    campus_text = campus_branch or "Bay, Laguna (Main Campus)"
    
    details_html = ""
    if role == 'student':
        details_html = f"""
        <tr>
            <td style="padding: 8px 12px; font-weight: bold; color: #555;">Student ID:</td>
            <td style="padding: 8px 12px; color: #002d62; font-weight: bold;">{student_id or 'Pending'}</td>
        </tr>
        <tr>
            <td style="padding: 8px 12px; font-weight: bold; color: #555;">Academic Program:</td>
            <td style="padding: 8px 12px; color: #333;">{course_program or 'N/A'}</td>
        </tr>
        """
    elif role == 'staff':
        details_html = f"""
        <tr>
            <td style="padding: 8px 12px; font-weight: bold; color: #555;">Designated Department:</td>
            <td style="padding: 8px 12px; color: #006837; font-weight: bold;">{department_name or 'Department Resolver'}</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>CARD MRI Account Registration</title>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.08); border-top: 5px solid #002d62;">
            
            <!-- Header -->
            <div style="background-color: #002d62; color: #ffffff; padding: 25px; text-align: center;">
                <h2 style="margin: 0; font-size: 22px; letter-spacing: 0.5px;">CARD-MRI Development Institute, Inc.</h2>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #e5a823; font-weight: bold; text-transform: uppercase;">
                    Student Concern Routing & Resolution Tracking System
                </p>
            </div>

            <!-- Body -->
            <div style="padding: 30px 25px; color: #333333; line-height: 1.6;">
                <h3 style="color: #002d62; margin-top: 0;">Welcome, {full_name}!</h3>
                <p>Your institutional account has been successfully created in the <strong>CARD MRI SCRRTS Portal</strong>.</p>
                
                <!-- Account Summary Box -->
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; margin: 20px 0; padding: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: #006837; font-size: 14px; text-transform: uppercase; border-bottom: 2px solid #006837; padding-bottom: 5px;">
                        Institutional Account Summary
                    </h4>
                    <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 12px; font-weight: bold; color: #555; width: 40%;">Account Role:</td>
                            <td style="padding: 8px 12px; color: #002d62; font-weight: bold;">{role_badge}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 12px; font-weight: bold; color: #555;">Institutional Email:</td>
                            <td style="padding: 8px 12px; color: #333;">{to_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 12px; font-weight: bold; color: #555;">Campus Branch:</td>
                            <td style="padding: 8px 12px; color: #333;">{campus_text}</td>
                        </tr>
                        {details_html}
                    </table>
                </div>

                <p style="font-size: 14px;">You can now log in to the portal using your institutional email and password to submit academic, accounting, and scholarship inquiries or track ticket resolutions.</p>

                <!-- CTA Button -->
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{APP_URL}/login" style="background-color: #002d62; color: #ffffff; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 15px; display: inline-block;">
                        Sign In to CARD MRI Portal &rarr;
                    </a>
                </div>

                <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px; margin-top: 20px; font-size: 13px; color: #92400e;">
                    <strong>Security Notice:</strong> CARD MRI will never ask for your password. Please keep your credentials secure.
                </div>
            </div>

            <!-- Footer -->
            <div style="background-color: #f1f5f9; padding: 15px 25px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0 0 5px 0;"><strong>CARD-MRI Development Institute, Inc. (CMDI)</strong></p>
                <p style="margin: 0;">Bay, Laguna | Tagum City, Davao del Norte | Pasig City</p>
                <p style="margin: 5px 0 0 0; color: #94a3b8;">This is an automated system notification. Please do not reply directly to this email.</p>
            </div>

        </div>
    </body>
    </html>
    """

    text_content = f"""
    CARD-MRI Development Institute, Inc. (CMDI)
    Student Concern Routing & Resolution Tracking System (SCRRTS)

    Welcome, {full_name}!

    Your institutional account has been successfully registered.
    - Role: {role_badge}
    - Email: {to_email}
    - Campus: {campus_text}

    Sign In to the portal at: {APP_URL}/login

    CARD MRI Development Institute, Inc.
    """

    dispatch_email(to_email, subject, html_content, text_content)

def send_concern_status_email(to_email, student_name, ticket_number, subject_text, new_status, department_name, action_notes=None):
    """
    Dispatches an email notification when a student's concern ticket status changes.
    """
    subject = f"[{ticket_number}] Concern Status Update: {new_status}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Inquiry Status Update</title>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.08); border-top: 5px solid #002d62;">
            <div style="background-color: #002d62; color: #ffffff; padding: 20px; text-align: center;">
                <h3 style="margin: 0;">CARD-MRI Development Institute</h3>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #e5a823;">Inquiry Tracking Notification</p>
            </div>
            <div style="padding: 25px; color: #333333; line-height: 1.6;">
                <p>Hello <strong>{student_name}</strong>,</p>
                <p>There is an official status update regarding your filed concern ticket:</p>

                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 15px 0;">
                    <p style="margin: 0 0 8px 0;"><strong>Tracking Ticket:</strong> <span style="color: #002d62;">{ticket_number}</span></p>
                    <p style="margin: 0 0 8px 0;"><strong>Subject:</strong> {subject_text}</p>
                    <p style="margin: 0 0 8px 0;"><strong>Department:</strong> {department_name}</p>
                    <p style="margin: 0 0 8px 0;"><strong>New Status:</strong> <span style="background-color: #006837; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px;">{new_status}</span></p>
                    {f'<p style="margin: 10px 0 0 0; padding-top: 8px; border-top: 1px dashed #cbd5e1;"><strong>Resolution / Action Notes:</strong><br>{action_notes}</p>' if action_notes else ''}
                </div>

                <div style="text-align: center; margin: 25px 0;">
                    <a href="{APP_URL}/login" style="background-color: #002d62; color: #ffffff; padding: 10px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 14px; display: inline-block;">
                        View Concern Timeline &rarr;
                    </a>
                </div>
            </div>
            <div style="background-color: #f1f5f9; padding: 12px; text-align: center; font-size: 11px; color: #64748b;">
                CARD-MRI Development Institute, Inc. &bull; Automated Tracking System
            </div>
        </div>
    </body>
    </html>
    """

    dispatch_email(to_email, subject, html_content)
