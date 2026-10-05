# ResolvEd: Student Concern Routing and Resolution Tracking System (SCRRTS)

> **Systems Analysis and Design Development (SAD)**  
> **Midterm Hands-on Practical Examination Project**  
> *Analyze &rarr; Design &rarr; Develop &rarr; Deploy &rarr; Test &rarr; Defend*

---

## 📌 Executive Summary

**ResolvEd (Student Concern Routing and Resolution Tracking System)** is an enterprise-grade academic grievance and inquiry management platform designed to automate the intake, intelligent categorization, departmental routing, Service Level Agreement (SLA) monitoring, and resolution verification of student concerns.

By replacing chaotic multi-channel communication (email, social media, walk-ins) with a centralized, auditable workflow engine, ResolvEd provides complete operational transparency for students, departmental resolvers (Registrar, Accounting, Academic Affairs, Student Affairs, ICTO), and university administrators.

---

## 🚀 Live Production & Deployment Guide

### Deployment Options

#### Option A: Deploy to Render (Recommended - Free Tier)
1. Push this repository to your GitHub account:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/student-concern-system.git
   git branch -M main
   git push -u origin main
   ```
2. Log in to [Render.com](https://render.com).
3. Click **New +** &rarr; **Web Service**.
4. Connect your GitHub repository.
5. Configure the service settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && python database.py`
   - **Start Command**: `gunicorn app:app`
6. Click **Deploy Web Service**. Render will assign your public production URL (e.g., `https://resolved-student-concern-system.onrender.com`).

#### Option B: Deploy to Railway
1. Install Railway CLI or connect via [Railway.app](https://railway.app).
2. Create **New Project** &rarr; **Deploy from GitHub repo**.
3. Railway automatically detects the `Procfile` and `requirements.txt`.
4. Generate a public domain under Settings.

---

## 🔑 Production Test Accounts

| Role | Username / Email | Password | Scope & Department |
| :--- | :--- | :--- | :--- |
| **System Administrator** | `demo.admin@email.com` | `Admin@12345` | Global campus management, reassignments, audits |
| **Registrar Staff** | `staff.registrar@univ.edu` | `Staff@123` | Office of the University Registrar (REG) |
| **Accounting Staff** | `staff.finance@univ.edu` | `Staff@123` | Student Accounting & Finance (FIN) |
| **Department Resolver (Demo)** | `demo.staff@email.com` | `Staff@12345` | Demonstrator department queue |
| **Student (Demo)** | `demo.user@email.com` | `Student@12345` | Student User (ID: `2023-99999`) |
| **Student** | `student.santos@univ.edu` | `Student@123` | Maria Santos (ID: `2023-01042`) |

*Tip: The login page includes 1-click credential buttons for swift testing during defense evaluation.*

---

## 🛠️ Technology Stack

- **Backend Framework**: Python 3.9+ / Flask 3.1
- **Database Engine**: Relational SQLite3 / PostgreSQL compatible
- **Security & Auth**: Werkzeug Password Hashing (PBKDF2/Bcrypt equivalent), Role-based Decorators, Session Isolation
- **Frontend / UI**: HTML5, Jinja2 Templates, Bootstrap 5.3, Bootstrap Icons, Chart.js 4.4
- **Reporting & Export**: CSV Streaming Engine, Browser Print Driver
- **Production Server**: Gunicorn WSGI Container

---

## 💻 Local Setup & Execution

### 1. Prerequisites
Ensure Python 3.9+ is installed on your machine.

### 2. Install Dependencies
```bash
py -m pip install -r requirements.txt
```

### 3. Initialize & Seed Database
```bash
py database.py
```

### 4. Run Development Server
```bash
py app.py
```
Open your browser at `http://127.0.0.1:5000`.

### 5. Run Automated Test Suite (10 Automated Test Cases)
```bash
py -m unittest tests/test_system.py
```

---

## 📊 Core Modules

1. **User Authentication & Role-Based Access Control Module**  
   Strict authorization boundaries across Student, Staff, and Administrator tiers with password hashing.
2. **Concern Submission & Multi-Attribute Routing Engine**  
   Intelligently parses concern categories, routes tickets to correct department queues, and generates standardized `CRN-YYYY-XXXX` tickets.
3. **Resolution Lifecycle & Status Management Module**  
   Strict state transitions (`SUBMITTED` &rarr; `ROUTED` &rarr; `IN_PROGRESS` &rarr; `RESOLVED` / `REJECTED` &rarr; `CLOSED`) with mandatory resolution notes.
4. **SLA Monitoring, Overdue Detection & Activity Audit Trail**  
   Dynamic computation of SLA deadlines based on priority and category; live flags for overdue tickets; immutable audit history.
5. **Analytics Dashboard & Reporting Hub**  
   Live summary cards, Department SLA scorecards, dynamic charts (Status distribution, Priority volume), and CSV export.

---

## 📜 Business Rules Enforced

- **BR1 (Automated Department Routing & Ticket Code Generation)**: Every concern is classified by category and dispatched to its respective department with a sequential, unique ticket number.
- **BR2 (Dynamic SLA Target & Escalation Calculation)**: Computes turnaround deadlines based on priority (`URGENT`=24h, `HIGH`=48h, `MEDIUM`=72h, `LOW`=120h). Tickets past their SLA target are flagged as `OVERDUE`.
- **BR3 (Strict State Transition & Resolution Note Mandate)**: Resolvers cannot mark a ticket `RESOLVED` without entering an official resolution summary, or `REJECTED` without a policy reason. Only the student can confirm closure and rate satisfaction.
- **BR4 (Audit Trail Immutability)**: Every status change, assignment, note, or evaluation creates a timestamped, non-deletable audit log entry.
