"""
Automated Test Suite for Student Concern Routing and Resolution Tracking System (ResolvEd)
Validates all 8+ required Midterm Examination test cases:
TC01: Valid Login
TC02: Invalid Login
TC03: Concern Record Creation
TC04: Business Rule 1 - Automated Department Routing
TC05: Business Rule 2 - SLA Deadline Calculation
TC06: Status Workflow Processing
TC07: Business Rule 3 - Mandatory Resolution Notes Validation
TC08: Student Resolution Feedback & Closure
TC09: Search & Multi-Filter Querying
TC10: Production Data Persistence
"""

import sys
import os
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database import init_db, get_db_connection

class TestStudentConcernSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize and reseed database
        init_db(force_reseed=True)
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

    def test_tc01_valid_login(self):
        """TC01: Valid Login - Authenticates student with correct credentials."""
        response = self.client.post('/login', data={
            'email': 'student.santos@univ.edu',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back, Maria Clarisse Santos", response.data)
        # Logout after test
        self.client.get('/logout')

    def test_tc02_invalid_login(self):
        """TC02: Invalid Login - Rejects incorrect credentials with error notice."""
        response = self.client.post('/login', data={
            'email': 'student.santos@univ.edu',
            'password': 'WrongPassword999'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid email or password", response.data)

    def test_tc03_record_creation(self):
        """TC03: Record Creation - Student files a new concern."""
        # Login as student
        self.client.post('/login', data={'email': 'student.santos@univ.edu', 'password': 'Student@123'}, follow_redirects=True)

        response = self.client.post('/concerns/new', data={
            'category_id': '1', # Transcript of Records (Registrar)
            'subject': 'Transcript Copy Required for Scholarship Application',
            'description': 'Applying for external scholarship. Need certified true copy of grades.',
            'priority': 'HIGH'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"successfully submitted and routed to Office of the University Registrar", response.data)
        self.client.get('/logout')

    def test_tc04_automated_routing(self):
        """TC04: Business Rule 1 - Auto Department Routing Engine."""
        conn = get_db_connection()
        concern = conn.execute("""
            SELECT c.*, d.department_code 
            FROM concerns c 
            JOIN departments d ON c.department_id = d.department_id
            WHERE c.subject = 'Transcript Copy Required for Scholarship Application'
        """).fetchone()
        conn.close()

        self.assertIsNotNone(concern)
        self.assertEqual(concern['department_code'], 'REG') # Auto-routed to Registrar
        self.assertTrue(concern['ticket_number'].startswith('CRN-'))

    def test_tc05_sla_calculation(self):
        """TC05: Business Rule 2 - SLA Deadline Calculation."""
        conn = get_db_connection()
        concern = conn.execute("""
            SELECT sla_target_date, created_at, priority FROM concerns 
            WHERE subject = 'Transcript Copy Required for Scholarship Application'
        """).fetchone()
        conn.close()

        self.assertIsNotNone(concern['sla_target_date'])
        self.assertGreater(concern['sla_target_date'], concern['created_at'])

    def test_tc06_status_workflow(self):
        """TC06: Status Workflow - Staff claims ticket and marks IN PROGRESS."""
        # Login as Registrar Staff (dept 1)
        self.client.post('/login', data={'email': 'staff.registrar@univ.edu', 'password': 'Staff@123'}, follow_redirects=True)

        conn = get_db_connection()
        concern = conn.execute("SELECT concern_id FROM concerns WHERE subject = 'Transcript Copy Required for Scholarship Application'").fetchone()
        conn.close()
        cid = concern['concern_id']

        # Claim concern
        claim_resp = self.client.post(f'/concerns/{cid}/claim', follow_redirects=True)
        self.assertEqual(claim_resp.status_code, 200)
        self.assertIn(b"Ticket claimed successfully", claim_resp.data)

        # Verify DB state
        conn = get_db_connection()
        updated = conn.execute("SELECT status, assigned_staff_id FROM concerns WHERE concern_id = ?", (cid,)).fetchone()
        conn.close()
        self.assertEqual(updated['status'], 'IN_PROGRESS')
        self.assertIsNotNone(updated['assigned_staff_id'])
        self.client.get('/logout')

    def test_tc07_business_rule_validation(self):
        """TC07: Business Rule 3 - Mandatory notes required to RESOLVE or REJECT."""
        # Login as Registrar Staff
        self.client.post('/login', data={'email': 'staff.registrar@univ.edu', 'password': 'Staff@123'}, follow_redirects=True)

        conn = get_db_connection()
        concern = conn.execute("SELECT concern_id FROM concerns WHERE subject = 'Transcript Copy Required for Scholarship Application'").fetchone()
        conn.close()
        cid = concern['concern_id']

        # Attempt to mark RESOLVED with empty note
        empty_note_resp = self.client.post(f'/concerns/{cid}/update-status', data={
            'new_status': 'RESOLVED',
            'action_note': '' # Empty!
        }, follow_redirects=True)
        self.assertIn(b"Business Rule Violation", empty_note_resp.data)

        # Now resolve properly with valid resolution summary
        valid_resp = self.client.post(f'/concerns/{cid}/update-status', data={
            'new_status': 'RESOLVED',
            'action_note': 'Official transcript issued, sealed, and prepared at Window 2.'
        }, follow_redirects=True)
        self.assertIn(b"successfully transitioned to RESOLVED", valid_resp.data)
        self.client.get('/logout')

    def test_tc08_student_feedback_and_closure(self):
        """TC08: Student closure & satisfaction rating."""
        # Login as student
        self.client.post('/login', data={'email': 'student.santos@univ.edu', 'password': 'Student@123'}, follow_redirects=True)

        conn = get_db_connection()
        concern = conn.execute("SELECT concern_id FROM concerns WHERE subject = 'Transcript Copy Required for Scholarship Application'").fetchone()
        conn.close()
        cid = concern['concern_id']

        # Student confirms and closes ticket
        close_resp = self.client.post(f'/concerns/{cid}/close', follow_redirects=True)
        self.assertEqual(close_resp.status_code, 200)
        self.assertIn(b"Concern is now officially closed", close_resp.data)

        # Student submits 5-star rating
        feedback_resp = self.client.post(f'/concerns/{cid}/feedback', data={
            'rating': '5',
            'comments': 'Extremely fast turnaround time by Registrar. Received in time for my application!'
        }, follow_redirects=True)
        self.assertIn(b"Thank you for your feedback", feedback_resp.data)

        # Verify feedback in DB
        conn = get_db_connection()
        fb = conn.execute("SELECT rating, feedback_comments FROM concern_feedback WHERE concern_id = ?", (cid,)).fetchone()
        conn.close()
        self.assertEqual(fb['rating'], 5)
        self.client.get('/logout')

    def test_tc09_search_and_filtering(self):
        """TC09: Search & Filtering - Verifies filtered views."""
        # Login as Admin
        self.client.post('/login', data={'email': 'demo.admin@email.com', 'password': 'Admin@12345'}, follow_redirects=True)

        # Search by keyword
        resp = self.client.get('/concerns?q=Tuition')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Online Bank Transfer for 2nd Sem Tuition Not Reflected", resp.data)

        # Filter by status
        resp_status = self.client.get('/concerns?status=CLOSED')
        self.assertEqual(resp_status.status_code, 200)
        self.assertIn(b"CRN-2026-0001", resp_status.data)
        self.client.get('/logout')

    def test_tc10_persistence(self):
        """TC10: Production Persistence - Verified record exists across sessions."""
        conn = get_db_connection()
        record = conn.execute("SELECT * FROM concerns WHERE ticket_number = 'CRN-2026-0001'").fetchone()
        conn.close()
        self.assertIsNotNone(record)
        self.assertEqual(record['status'], 'CLOSED')

if __name__ == '__main__':
    unittest.main()
