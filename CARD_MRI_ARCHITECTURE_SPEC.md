# CARD MRI STUDENT CONCERN ROUTING AND RESOLUTION TRACKING SYSTEM (SCRRTS)
## System Architecture & Engineering Implementation Blueprint
### Institutional Client: CARD-MRI Development Institute, Inc. (CMDI)

---

## 1. System Overview

The **CARD MRI Student Concern Routing and Resolution Tracking System (SCRRTS)** is an enterprise academic grievance and inquiry management platform tailored specifically for the campuses and administrative departments of the **CARD-MRI Development Institute, Inc. (CMDI)** (Bay, Laguna Main Campus; Tagum City, Davao del Norte Campus; Pasig City Extension).

---

## 2. Core Functional Specifications

### 2.1 Institutional Registration Module
- **Students**: Requires Full Name, Institutional Email (`@cmdi.edu.ph` / `@student.cmdi.edu.ph`), Password (hashed via Bcrypt/PBKDF2), CARD MRI Student ID Number (`CMDI-YYYY-XXXXX`), Academic Program/Course (`BSIT`, `BSEntrep`, `BSAIS`, `Senior High ABM/TVL`), and Campus/Branch.
- **Department Staff**: Requires Full Name, Institutional Email, Password, Designated Department (`Office of the Registrar`, `Student Accounting & Microfinance Finance`, `Scholarships & CARD Community Assistance`, `Academic Affairs & Dean's Office`, `ICT & Infrastructure Support`), and Campus/Branch.

### 2.2 Standard Credential Authentication
- Standard Email and Password authentication only.
- Strict exclusion of 1-click demo logins, social logins, or magic links.
- Session/JWT-based role protection (`student`, `staff`, `admin`).

### 2.3 Inquiry Intake & Intelligent Auto-Routing
- Ingests Category, Priority (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), Subject, Detailed Description, and File Attachments (`PDF`, `DOCX`, `PNG`, `JPG`, `ZIP`).
- Automatically maps category to target department queue.
- Generates standardized tracking codes: `CMDI-CRN-YYYY-XXXX`.

### 2.4 Resolution Lifecycle & Escalation Workflow
- Explicit states: `Submitted` &rarr; `Routed` &rarr; `In Progress` &rarr; `Escalated` &rarr; `Resolved` &rarr; `Closed` (or `Rejected`).
- Supports confidential internal staff notes alongside student-visible resolution summaries.
- Dedicated escalation trigger requiring mandatory justification notes.
- Immutable event logging into `concern_audit_logs`.
- Post-resolution student 1–5 star satisfaction evaluation.
