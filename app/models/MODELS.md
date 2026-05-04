# VOC Platform — Models Reference

> SQLAlchemy models split across `app/models/` (one file per class).
> `app/models/__init__.py` re-exports all 8 classes — no logic lives there.
> Database: Microsoft SQL Server — `VOC_DataBase`
> All models use `db` from `app/__init__.py` (Flask-SQLAlchemy).

### Directory layout

```
app/models/
├── __init__.py              ← re-exports all 8 classes (no logic)
├── scope.py                 ← Scope
├── user.py                  ← User
├── asset.py                 ← Asset
├── vulnerability.py         ← Vulnerability
├── asset_vulnerability.py   ← AssetVulnerability
├── sla_tracking.py          ← SlaTracking
├── vuln_history.py          ← VulnHistory
└── etl_log.py               ← EtlLog
```

---

## Table of Contents

1. [Scope](#1-scope)
2. [User](#2-user)
3. [Asset](#3-asset)
4. [Vulnerability](#4-vulnerability)
5. [AssetVulnerability](#5-assetvulnerability) ← central table
6. [SlaTracking](#6-slatracking)
7. [VulnHistory](#7-vulnhistory)
8. [EtlLog](#8-etllog)
9. [Relationships Map](#9-relationships-map)
10. [Enum Values Reference](#10-enum-values-reference)

---

## 1. Scope

**File**: `app/models/scope.py` | **Table**: `scopes`

Represents an organizational perimeter. Every user and every asset belongs to exactly one scope.

```python
class Scope(db.Model):
    scope_id    # INT PK IDENTITY
    scope_name  # VARCHAR(150) NOT NULL  — e.g. "Cyber Security"
    category    # VARCHAR(50)  NOT NULL  — 'applicatif' | 'systeme' | 'systeme_app'
    bv_name     # VARCHAR(150) NULL      — Business Vertical name from CMDB
    description # VARCHAR(255) NULL
```

**Relationships**:
- `scope.users` → list of `User` (backref: `user.scope`)
- `scope.assets` → list of `Asset` (backref: `asset.scope`)

**20 scopes in seed data**:

| scope_id | scope_name | category |
|---|---|---|
| 1 | Digital Workspace | applicatif |
| 2 | Cyber Security | applicatif |
| 3 | ITAM | applicatif |
| 4 | IT Core Banking & Life Insurance | applicatif |
| 5 | IT Data & Corporate Functions | applicatif |
| 6 | IT Financial Control & PMO | applicatif |
| 7 | IT Governance | applicatif |
| 8 | IT ICB | applicatif |
| 9 | IT Markets | applicatif |
| 10 | IT Operations & Infrastructures | applicatif |
| 11 | IT Payment & Compliance | applicatif |
| 12 | IT PWM & IFA | applicatif |
| 13 | Software Development Factory | applicatif |
| 14 | Other | applicatif |
| 15 | Datacenter Team | systeme |
| 16 | Linux Team | systeme |
| 17 | Windows Team | systeme |
| 18 | Network Team | systeme |
| 19 | Middleware & Tools | systeme |
| 20 | IT Operations & Infrastructures Ops | systeme_app |

---

## 2. User

**File**: `app/models/user.py` | **Table**: `users`

Platform users, authenticated via Active Directory. Inherits `UserMixin` for Flask-Login.

```python
class User(UserMixin, db.Model):
    user_id   # INT PK IDENTITY
    username  # VARCHAR(100) NOT NULL UNIQUE — AD username e.g. "resp.cybersec"
    email     # VARCHAR(150) NOT NULL UNIQUE — e.g. "resp.cybersec@bank.local"
    role      # VARCHAR(50)  NOT NULL DEFAULT 'user' — 'admin' | 'user'
    is_active # BIT NOT NULL DEFAULT 1
    scope_id  # INT FK → scopes.scope_id NOT NULL
```

**Properties**:
```python
user.is_admin       # bool — True if role == 'admin'
user.get_id()       # str(user_id) — required by Flask-Login
```

**Relationships**:
- `user.scope` → `Scope` (backref from Scope.users)
- `user.sla_assignments` → list of `SlaTracking` where user is remed_responsible
- `user.history_entries` → list of `VulnHistory` authored by this user

**Access rules**:
- `role='admin'` → sees all scopes, all data
- `role='user'` → sees only data where `asset.scope_id == user.scope_id`

---

## 3. Asset

**File**: `app/models/asset.py` | **Table**: `assets`

IT assets sourced from the CMDB. Two CMDB files are merged: `Server_Usage_List` (provides scope/BV info) and `All Active CIs` (provides technical details).

```python
class Asset(db.Model):
    asset_id            # INT PK IDENTITY
    inventory_number    # VARCHAR(100) — from All Active CIs
    rec_id              # VARCHAR(100) — CMDB record ID
    ci_class            # VARCHAR(100) — 'Server' | 'Network' | 'Application'
    ci_type             # VARCHAR(100) — 'Physical' | 'Virtual' | 'Firewall' | ...
    name                # VARCHAR(150) NOT NULL — hostname e.g. "SRV-AD-001"
    ip_address          # VARCHAR(50)  — primary IP
    mac_address         # VARCHAR(50)
    operating_system    # VARCHAR(150) — e.g. "Windows Server 2019"
    server_usage        # VARCHAR(150) — e.g. "Active Directory"
    status              # VARCHAR(50)  DEFAULT 'Active'
    environment         # VARCHAR(100) — 'Production' | 'Development' | 'Staging'
    trigramm            # VARCHAR(50)  — team code e.g. "WIN", "NET", "CBC"
    vlan                # VARCHAR(50)  — e.g. "VLAN-305"
    subnet_id           # VARCHAR(50)  — e.g. "10.30.3.0/24"
    architecture        # VARCHAR(100) — e.g. "x86_64"
    criticality         # VARCHAR(50)  DEFAULT 'Important' — 'Critical'|'Important'|'Standard'
    app_name            # VARCHAR(150) — application running on asset
    dev_team            # VARCHAR(100)
    it_team             # VARCHAR(100)
    last_synced_at      # DATETIME     — last CMDB sync timestamp
    scope_id            # INT FK → scopes.scope_id NOT NULL
```

**Relationships**:
- `asset.scope` → `Scope`
- `asset.occurrences` → list of `AssetVulnerability`

**Criticality → SLA mapping** (used in ETL):
```
Critical  → 15 days SLA
Important → 30 days SLA
Standard  → 90 days SLA
```

**Asset matching in ETL** (correlation with Tenable data):
Priority: `ip_address` → `netbios_name` → `dns_name`

---

## 4. Vulnerability

**File**: `app/models/vulnerability.py` | **Table**: `vulnerabilities`

Pure vulnerability data from Tenable (or other sources). One row = one unique vulnerability, independent of which asset it affects. The same CVE on two different assets = one `Vulnerability` row + two `AssetVulnerability` rows.

```python
class Vulnerability(db.Model):
    vuln_id                  # VARCHAR(200) PK — format: {ip}PL{plugin_id}PO{port}
    plugin_id                # VARCHAR(50)  — Tenable plugin ID e.g. "96982"
    plugin_name              # VARCHAR(255) — e.g. "MS17-010: EternalBlue"
    cve                      # VARCHAR(100) — e.g. "CVE-2021-44228" (NULL if no CVE)
    family                   # VARCHAR(100) — e.g. "Windows", "Web Servers", "General"
    synopsis                 # VARCHAR(500) — one-line description
    description              # TEXT         — full technical description
    plugin_output            # TEXT         — raw scanner output
    steps_to_remediate       # TEXT         — remediation steps
    see_also                 # VARCHAR(500) — reference URLs
    cpe                      # VARCHAR(255) — Common Platform Enumeration
    check_type               # VARCHAR(100) — 'remote' | 'local' | 'combined'
    exploit_frameworks       # VARCHAR(255) — e.g. "Metasploit, Core Impact"
    exploit_ease             # VARCHAR(100) — e.g. "Exploits are available"
    exploitable              # BIT          DEFAULT 0
    cvss_v2_score            # DECIMAL(4,1) — 0.0 to 10.0
    cvss_v3_score            # DECIMAL(4,1) — 0.0 to 10.0
    severity                 # VARCHAR(50)  — 'Critical'|'High'|'Medium'|'Low'|'Info'
    vuln_publication_date    # DATE
    patch_publication_date   # DATE         — NULL if no patch available
    plugin_publication_date  # DATE
    plugin_modification_date # DATE
```

**Properties**:
```python
vuln.severity_color  # Bootstrap color string: 'danger'|'warning'|'info'|'secondary'|'light'
```

**Relationships**:
- `vuln.occurrences` → list of `AssetVulnerability`

**vuln_id format**:
```
{ip_address}PL{plugin_id}PO{port}
Examples:
  10.30.3.10PL96982PO445       ← EternalBlue on AD server
  10.20.13.10PL156032PO8080    ← Log4Shell on GitLab server
  10.20.2.11PL999001PO443      ← CTI finding on CyberArk PAM
```

For manual sources (CTI, BitSight, RedTeam), `plugin_id` is replaced by a source-specific identifier.

---

## 5. AssetVulnerability

**File**: `app/models/asset_vulnerability.py` | **Table**: `asset_vulnerabilities`

**The central table of the platform.** Each row is one vulnerability occurrence on one specific asset. Replaces the old `tenable_cmdb_match.json` file.

```python
class AssetVulnerability(db.Model):
    av_id                # INT PK IDENTITY — unique occurrence ID
    vuln_id              # VARCHAR(200) FK → vulnerabilities.vuln_id NOT NULL
    asset_id             # INT FK → assets.asset_id NOT NULL
    source               # VARCHAR(50) NOT NULL DEFAULT 'tenable'
                         # 'tenable' | 'cti' | 'bitsight' | 'redteam'
    ip_address           # VARCHAR(50)  — IP at time of detection
    netbios_name         # VARCHAR(150)
    dns_name             # VARCHAR(150)
    port                 # INT          — e.g. 445, 443, 8080
    first_discovered     # DATE         — first scan date
    last_observed        # DATE         — last scan date (updated by ETL)

    # Workflow fields
    vuln_status          # VARCHAR(50) NOT NULL DEFAULT 'Open'
                         # 'Open'|'In Progress'|'Risk Assessment'|'Accepted Risk'|'Fixed'|'Closed'
    branch               # VARCHAR(30) NULL
                         # NULL (Open) | 'standard' | 'risk_assessment'

    # Calculated fields (ETL / scoring)
    vuln_type            # VARCHAR(100) — 'RCE'|'Privilege Esc'|'Configuration'|...
    vul_scope            # VARCHAR(150) — scope name at detection time
    reassigned_scope     # VARCHAR(150) — if vuln was reassigned to another scope
    asset_exposure       # DECIMAL(5,2) — 0–100 exposure score
    likelihood           # DECIMAL(5,2) — 0.0–1.0 exploitation likelihood
    impact               # DECIMAL(5,2) — 0.0–1.0 business impact
    risk_score           # DECIMAL(5,2) — composite risk score (used for prioritization)
    remediation_strategy # VARCHAR(100) — 'Patch'|'Upgrade'|'Configuration'|'Accept Risk'|...
    action_plan_provided # BIT NOT NULL DEFAULT 0

    created_at           # DATETIME NOT NULL DEFAULT GETDATE()
    updated_at           # DATETIME NOT NULL DEFAULT GETDATE()
```

**Properties**:
```python
av.status_color    # Bootstrap color for vuln_status badge
av.next_statuses   # list[str] — allowed transitions from current status

# Transition map:
# 'Open'            → ['In Progress']
# 'In Progress'     → ['Fixed', 'Risk Assessment']
# 'Risk Assessment' → ['Accepted Risk', 'In Progress']
# 'Accepted Risk'   → ['In Progress']
# 'Fixed'           → ['Closed']
# 'Closed'          → []
```

**Relationships**:
- `av.vulnerability` → `Vulnerability` (backref)
- `av.asset` → `Asset` (backref)
- `av.sla` → `SlaTracking` (1:1, uselist=False)
- `av.history` → list of `VulnHistory` ordered by `created_at`

**Important query patterns**:

```python
# Always filter out Closed vulns in V-Tracker
AssetVulnerability.query.filter(AssetVulnerability.vuln_status != 'Closed')

# Always apply scope filter
from app.utils.auth import scope_filter
q = AssetVulnerability.query.join(Asset)
q = scope_filter(q, Asset.scope_id)

# Full join for list view
q = (
    AssetVulnerability.query
    .join(Asset,         AssetVulnerability.asset_id == Asset.asset_id)
    .join(Vulnerability, AssetVulnerability.vuln_id  == Vulnerability.vuln_id)
    .filter(AssetVulnerability.vuln_status != 'Closed')
)
```

---

## 6. SlaTracking

**File**: `app/models/sla_tracking.py` | **Table**: `sla_tracking`

One SLA record per `AssetVulnerability`. Tracks remediation deadlines and compliance status.

```python
class SlaTracking(db.Model):
    sla_id            # INT PK IDENTITY
    av_id             # INT FK → asset_vulnerabilities.av_id UNIQUE NOT NULL
    sla_days_target   # INT — target days: 15 (Critical) | 30 (Important) | 90 (Standard)
    sla_due_date      # DATE — first_discovered + sla_days_target
    sla_status        # VARCHAR(50) DEFAULT 'On Track'
                      # 'On Track' | 'At Risk' | 'Breached' | 'Completed'
    remed_target_date # DATE — date committed by the responsible team
    risk_acceptance   # BIT NOT NULL DEFAULT 0 — True if risk accepted by admin
    remed_responsible # INT FK → users.user_id NULL — user responsible for fix
```

**Properties**:
```python
sla.status_color   # Bootstrap color: 'success'|'warning'|'danger'|'secondary'
sla.responsible    # User object (nullable)
```

**Relationships**:
- `sla.av` → `AssetVulnerability` (backref)
- `sla.responsible` → `User`

**SLA status update logic**:
- Updated to `'Completed'` automatically when `vuln_status` transitions to `'Fixed'` or `'Closed'`
- `'Breached'` when today > `sla_due_date` and status not Completed
- `'At Risk'` when approaching due date (ETL scoring script handles this)

---

## 7. VulnHistory

**File**: `app/models/vuln_history.py` | **Table**: `vuln_history`

Unified activity log for each vulnerability occurrence. Stores both status transitions and free-text comments in the same table. Displayed as a chronological timeline in the detail view.

```python
class VulnHistory(db.Model):
    history_id # INT PK IDENTITY
    av_id      # INT FK → asset_vulnerabilities.av_id NOT NULL
    user_id    # INT FK → users.user_id NOT NULL
    entry_type # VARCHAR(30) NOT NULL — 'status_change' | 'comment'
    old_status # VARCHAR(50) NULL — filled only for 'status_change'
    new_status # VARCHAR(50) NULL — filled only for 'status_change'
    content    # TEXT NULL        — filled only for 'comment'
    created_at # DATETIME NOT NULL DEFAULT GETDATE()
```

**Nullable logic**:

| entry_type | old_status | new_status | content |
|---|---|---|---|
| `status_change` | ✅ filled | ✅ filled | NULL |
| `comment` | NULL | NULL | ✅ filled |

**Relationships**:
- `history.av` → `AssetVulnerability` (backref)
- `history.author` → `User`

**Creating a history entry** (always use this pattern in routes):

```python
# Status change
db.session.add(VulnHistory(
    av_id=av_id, user_id=current_user.user_id,
    entry_type='status_change',
    old_status=old_status, new_status=new_status,
    created_at=datetime.utcnow()
))

# Comment
db.session.add(VulnHistory(
    av_id=av_id, user_id=current_user.user_id,
    entry_type='comment',
    content=comment_text,
    created_at=datetime.utcnow()
))
```

---

## 8. EtlLog

**File**: `app/models/etl_log.py` | **Table**: `etl_logs`

Logs each ETL pipeline execution. No foreign keys — fully independent.

```python
class EtlLog(db.Model):
    log_id            # INT PK IDENTITY
    source            # VARCHAR(50) — 'cmdb'|'tenable'|'cti'|'bitsight'|'redteam'
    status            # VARCHAR(20) DEFAULT 'running' — 'running'|'success'|'error'
    records_extracted # INT DEFAULT 0
    records_matched   # INT DEFAULT 0 — matched to CMDB assets
    records_inserted  # INT DEFAULT 0 — new records created
    records_skipped   # INT DEFAULT 0 — duplicates or unmatched
    error_msg         # TEXT NULL — exception message if status='error'
    duration_sec      # DECIMAL(8,2)
    run_at            # DATETIME NOT NULL DEFAULT GETDATE()
```

---

## 9. Relationships Map

```
SCOPES (1)
  ├── (N) USERS
  └── (N) ASSETS
              └── (N) ASSET_VULNERABILITIES ←── (N) VULNERABILITIES
                          ├── (1) SLA_TRACKING
                          └── (N) VULN_HISTORY ──── (1) USERS

ETL_LOGS  [standalone — no FK]
```

---

## 10. Enum Values Reference

### Scope.category
```
'applicatif'   — app team vulnerabilities
'systeme'      — system/infra team vulnerabilities
'systeme_app'  — cross-cutting (IT Ops & Infra)
```

### User.role
```
'admin'   — full access, all scopes
'user'    — scoped access only
```

### Asset.criticality
```
'Critical'   → SLA 15 days
'Important'  → SLA 30 days  (default)
'Standard'   → SLA 90 days
```

### Vulnerability.severity
```
'Critical'   → Bootstrap: danger
'High'       → Bootstrap: warning
'Medium'     → Bootstrap: info
'Low'        → Bootstrap: secondary
'Info'       → Bootstrap: light
```

### AssetVulnerability.vuln_status
```
'Open'            → primary    (default, not yet handled)
'In Progress'     → warning    (team is working on it)
'Risk Assessment' → info       (under evaluation for acceptance)
'Accepted Risk'   → secondary  (cannot fix now, admin decision)
'Fixed'           → success    (remediated, pending verification)
'Closed'          → dark       (verified and closed — hidden from V-Tracker)
```

### AssetVulnerability.branch
```
NULL               — status is still 'Open', path not decided
'standard'         — heading toward Fixed → Closed
'risk_assessment'  — heading toward Accepted Risk
```

### AssetVulnerability.source
```
'tenable'   — automated scan (Tenable.io)
'cti'       — Cyber Threat Intelligence manual input
'bitsight'  — third-party risk score input
'redteam'   — penetration test finding
```

### SlaTracking.sla_status
```
'On Track'   → success   (within deadline)
'At Risk'    → warning   (approaching deadline)
'Breached'   → danger    (past deadline)
'Completed'  → secondary (remediated)
```

### VulnHistory.entry_type
```
'status_change'   — old_status + new_status filled, content NULL
'comment'         — content filled, old_status + new_status NULL
```

### EtlLog.status
```
'running'   — pipeline currently executing
'success'   — completed successfully
'error'     — failed, see error_msg
```
