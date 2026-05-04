# VOC Platform - Project Description

> Generated: April 30, 2026
> Version: 2.0 (Refactored)

---

## 1. Project Overview

### 1.1 Purpose

The **VOC (Vulnerability Operation Center) Platform** is a centralized web application designed for managing IT vulnerabilities within a banking organization. It serves as the backbone of the organization's vulnerability management lifecycle, providing comprehensive tracking, reporting, and remediation workflows.

### 1.2 Context

This project represents a **refactoring initiative** of an existing legacy system that relied on:
- Scattered Python scripts
- PowerShell automation
- JSON flat files (e.g., `tenable_cmdb_match.json`)

The refactoring consolidates all vulnerability management operations into a structured, scalable **Flask + SQL Server** stack with proper role-based access control.

---

## 2. Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Backend** | Python | 3.11 |
| **Framework** | Flask | 3.0 |
| **Database** | Microsoft SQL Server | - |
| **ORM** | SQLAlchemy | 2.0 |
| **Authentication** | Active Directory (LDAP3) + Flask-Login | - |
| **Frontend** | HTML / CSS / JavaScript | - |
| **UI Framework** | Bootstrap | 5 |
| **ETL** | Python scripts (pandas, pyodbc) | - |
| **Reporting** | Power BI (DirectQuery) + ReportLab | - |

---

## 3. Project Architecture

### 3.1 Directory Structure

```
VOC/
├── run.py                    # Application entry point
├── config.py                 # Configuration classes
├── requirements.txt         # Python dependencies
│
├── app/                      # Main application package
│   ├── __init__.py          # Application factory
│   ├── extensions.py        # Flask extensions (db, jwt)
│   │
│   ├── blueprints/          # Route blueprints
│   │   ├── auth/            # Authentication module
│   │   └── vtracker/       # Vulnerability tracking module
│   │
│   ├── models/              # SQLAlchemy models
│   │   ├── scope.py
│   │   ├── user.py
│   │   ├── asset.py
│   │   ├── vulnerability.py
│   │   ├── asset_vulnerability.py
│   │   ├── sla_tracking.py
│   │   ├── vuln_history.py
│   │   └── etl_log.py
│   │
│   ├── templates/           # Jinja2 templates
│   │   ├── auth/
│   │   ├── vtracker/
│   │   ├── vhub/
│   │   ├── reporting/
│   │   └── shared/
│   │
│   ├── static/              # Static assets
│   │   └── css/
│   │
│   └── utils/               # Utility functions
│       ├── auth.py
│       └── decorators.py
│
├── etl/                     # ETL pipeline scripts
│   ├── etl_cmdb.py         # CMDB CSV → assets
│   ├── etl_tenable.py      # Tenable export → vulnerabilities
│   └── etl_scoring.py      # Risk scoring & SLA calculation
│
└── db/                      # Database scripts
    ├── voc_schema_v2.sql   # Database schema
    └── voc_seed_v2.sql     # Seed data
```

---

## 4. Database Schema

### 4.1 Tables Overview

The platform uses **8 relational tables** in SQL Server:

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `scopes` | Organizational perimeters | scope_id, scope_name, category |
| `users` | Platform users (AD-authenticated) | user_id, username, email, role, scope_id |
| `assets` | IT assets from CMDB | asset_id, name, ip_address, scope_id |
| `vulnerabilities` | Vulnerability definitions | vuln_id, plugin_name, cve, severity |
| `asset_vulnerabilities` | **Central junction table** | av_id, vuln_id, asset_id, vuln_status |
| `sla_tracking` | SLA monitoring | sla_id, av_id, sla_status, remed_target_date |
| `vuln_history` | Audit trail | history_id, av_id, user_id, entry_type |
| `etl_log` | ETL pipeline logs | log_id, source, status, records_* |

### 4.2 Key Relationships

```
Scope (1) ──────< User
Scope (1) ──────< Asset
Asset (1) ──────< AssetVulnerability >── (1) Vulnerability
AssetVulnerability (1) ──────< SlaTracking
AssetVulnerability (1) ──────< VulnHistory
```

---

## 5. Blueprints & Features

### 5.1 Authentication Module (`auth/`)

**Status:** ✅ Implemented

**Purpose:** Handle user authentication via Active Directory

**Routes:**
| Route | Method | Description |
|-------|--------|-------------|
| `/auth/login` | GET | Display login page |
| `/api/auth/login` | POST | Authenticate user (JWT) |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/logout` | POST | Logout and clear JWT |

**Key Features:**
- Active Directory bind authentication
- Group-to-scope mapping
- JWT token generation with 8-hour expiry
- Cookie-based token storage

---

### 5.2 Vulnerability Tracker Module (`vtracker/`)

**Status:** ✅ Implemented (Partial)

**Purpose:** Core vulnerability tracking and management

**Routes:**
| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Dashboard with KPIs |
| `/list` | GET | Paginated vulnerability list |
| `/detail/<id>` | GET | Vulnerability detail view |

**Key Features:**
- Scope-based filtering (admins see all)
- Severity, status, and source filtering
- Search by plugin name, CVE, asset name, IP
- SLA breach tracking

---

### 5.3 Vulnerability Hub Module (`vhub/`)

**Status:** ❌ Not Implemented (Templates exist)

**Purpose:** Manual vulnerability input from external sources

**Expected Routes:**
- Manual CTI (Cyber Threat Intelligence) input
- BitSight integration data entry
- Red Team findings input

**Templates Available:**
- `bitsight.html`
- `cti.html`
- `redteam.html`
- `_vuln_form.html`

---

### 5.4 Reporting Module (`reporting/`)

**Status:** ❌ Not Implemented (Templates exist)

**Purpose:** Analytics and reporting dashboards

**Expected Features:**
- Vulnerability trend analysis
- Scope-based reporting
- SLA compliance reports
- Export to PDF/Excel

**Templates Available:**
- `dashboard.html`

---

### 5.5 Admin Module (`admin/`)

**Status:** ❌ Not Implemented

**Purpose:** System administration

**Expected Features:**
- User management
- ETL log monitoring
- System configuration
- Scope management

---

## 6. Security Features

### 6.1 Authentication
- Active Directory integration via LDAP3
- JWT-based session management
- Role-based access control (admin/user)

### 6.2 Authorization
- Scope-based data isolation
- Admin bypass for full visibility
- Decorator-based route protection

### 6.3 Current Security Settings
| Setting | Value | Notes |
|---------|-------|-------|
| JWT_COOKIE_SECURE | False | Dev only - set True in prod |
| JWT_CSRF_PROTECT | False | Dev only |
| AD_USE_SSL | False | LDAP port 389 |

---

## 7. ETL Pipelines

### 7.1 CMDB ETL (`etl_cmdb.py`)
- Imports assets from CMDB CSV files
- Maps assets to scopes based on business vertical
- Updates inventory data

### 7.2 Tenable ETL (`etl_tenable.py`)
- Imports vulnerability scan results
- Creates/updates vulnerability records
- Links vulnerabilities to assets

### 7.3 Scoring ETL (`etl_scoring.py`)
- Calculates risk scores based on CVSS
- Determines SLA targets
- Computes asset exposure metrics

---

## 8. Configuration

### 8.1 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| SECRET_KEY | change-me-in-production | Flask secret key |
| DB_SERVER | localhost | SQL Server host |
| DB_NAME | VOC_DataBase | Database name |
| JWT_SECRET_KEY | voc-jwt-secret-change-in-prod | JWT signing key |
| AD_SERVER | 192.168.4.3 | Active Directory server |
| AD_DOMAIN | DEMO | AD domain name |

### 8.2 Config Classes
- `Config` - Base configuration
- `DevelopmentConfig` - DEBUG=True
- `ProductionConfig` - DEBUG=False

---

## 9. User Workflow

### 9.1 Login Flow
```
1. User visits /auth/login
2. Enters AD credentials
3. System binds to AD, verifies password
4. AD groups mapped to scope
5. JWT token generated
6. User redirected to vtracker dashboard
```

### 9.2 Vulnerability Management Flow
```
1. View dashboard (KPIs: total, open, critical, breached)
2. Browse vulnerability list with filters
3. View vulnerability details
4. Update status (Open → In Progress → Fixed → Closed)
5. Add comments/notes to history
6. Track SLA compliance
```

---

## 10. Current Project Status

| Component | Status |
|-----------|--------|
| Application Factory | ❌ Empty (broken) |
| Config | ⚠️ Syntax error (broken) |
| Auth Blueprint | ✅ Working |
| VTracker Blueprint | ⚠️ Partial |
| VHub Blueprint | ❌ Not implemented |
| Reporting Blueprint | ❌ Not implemented |
| Admin Blueprint | ❌ Not implemented |
| Models | ✅ Complete |
| Templates | ⚠️ Partial |
| ETL Scripts | ✅ Present |

---

## 11. Known Issues

See [bug.md](bug.md) for detailed bug report.

---

## 12. Future Enhancements

- Complete VHub blueprint implementation
- Complete Reporting blueprint implementation
- Add Admin blueprint
- Implement Power BI integration
- Add email notifications for SLA breaches
- Add vulnerability remediation workflows
- Implement API rate limiting
- Add audit logging for compliance

---

*This document provides a comprehensive overview of the VOC Platform for project supervision and advancement tracking.*