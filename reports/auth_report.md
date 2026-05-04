# Auth Module — Implementation Report

> **Branch**: `yas` | **Date**: 2026-04-30 | **Module**: Authentication & Authorization

---

## Table of Contents

1. [What Changed and Why](#1-what-changed-and-why)
2. [Architecture Overview](#2-architecture-overview)
3. [File-by-File Documentation](#3-file-by-file-documentation)
   - [extensions.py](#31-appextensionspy)
   - [config.py](#32-configpy)
   - [app/__init__.py](#33-app__init__py)
   - [auth/services.py](#34-appblueprintsauthservicespy)
   - [auth/routes.py](#35-appblueprintsauthroutespy)
   - [auth/__init__.py](#36-appblueprintsauth__init__py)
   - [utils/decorators.py](#37-apputilsdecoratorspy)
   - [utils/auth.py](#38-apputilsauthpy)
   - [models/user.py](#39-appmodelsuserpy)
4. [Login Page](#4-login-page-apptemplatesauthloginhtmlhtmlhtml)
5. [Base Template](#5-base-template-apptemplatessharedbasehtmlhtml)
6. [Authentication Flow — Step by Step](#6-authentication-flow--step-by-step)
7. [Token Structure (JWT)](#7-token-structure-jwt)
8. [API Reference](#8-api-reference)
9. [How to Use Auth in Future Blueprints](#9-how-to-use-auth-in-future-blueprints)
10. [Files Changed Summary](#10-files-changed-summary)

---

## 1. What Changed and Why

### Before — Flask-Login (session-based)

The original implementation used **Flask-Login**, which stores the logged-in user in a **server-side session** (a signed cookie). The browser sends the session cookie on every request, and Flask looks up the user in the database on every request.

```
Browser ──(cookie: session_id)──► Flask ──► DB lookup on every request ──► User object
```

This works for classic server-rendered web apps, but it has limitations:
- Requires the server to maintain session state
- Hard to use with JavaScript `fetch()` calls (CSRF tokens needed)
- Not compatible with stateless REST APIs

### After — JWT (token-based)

The new implementation uses **JWT (JSON Web Tokens)**. After login, the server creates a **signed token** that contains the user's identity and permissions directly inside it. The browser stores this token in `localStorage` and sends it with every API request.

```
Browser ──(header: Authorization: Bearer <token>)──► Flask ──► Verify signature ──► Done (no DB lookup)
```

Benefits for this project:
- No session state on the server — the token is self-contained
- Works naturally with JavaScript `fetch()` calls
- Easier to build the REST API for future Power BI / third-party integrations
- No CSRF protection needed (tokens sent in headers, not cookies)

---

## 2. Architecture Overview

```
app/
├── extensions.py                   ← db + jwt initialized here (avoids circular imports)
├── __init__.py                     ← App factory: wires everything together
│
├── blueprints/
│   └── auth/
│       ├── __init__.py             ← Declares the Blueprint
│       ├── routes.py               ← HTTP endpoints (login page + REST API)
│       └── services.py             ← Business logic (AD auth, scope mapping, token)
│
├── utils/
│   ├── auth.py                     ← scope_filter() — used in all data queries
│   └── decorators.py               ← @jwt_required, @scope_required, @admin_required
│
├── models/
│   └── user.py                     ← User model (updated: removed Flask-Login, added to_dict)
│
└── templates/
    ├── auth/login.html             ← Standalone login page (no sidebar, dark theme)
    └── shared/base.html            ← Master layout for all app pages (sidebar + JWT guard)
```

### The two providers

| Concern | Provider | Where |
|---|---|---|
| **Authentication** (is this really John?) | Active Directory (LDAP) | `services.py → authenticate_ad()` |
| **Authorization** (what can John access?) | VOC Database (SQL Server) | `services.py → get_or_create_user()` + JWT claims |

---

## 3. File-by-File Documentation

### 3.1 `app/extensions.py`

```python
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db  = SQLAlchemy()
jwt = JWTManager()
```

**Why this file exists**: Flask extensions like SQLAlchemy need to be created once and shared across the entire application. The problem is that `app/__init__.py` creates the Flask app, and all models need `db` — but if models import from `app/__init__.py`, and `app/__init__.py` imports models, you get a **circular import** (A imports B, B imports A → Python crashes).

The fix: create `extensions.py` as a neutral file that neither imports from `app` nor from `models`. Everyone imports from here safely:
- `app/__init__.py` does `from app.extensions import db, jwt` then `db.init_app(app)`
- All models do `from app.extensions import db`

**`db.init_app(app)`** — this "late binding" pattern means SQLAlchemy knows which Flask app (and therefore which database) to use, even though `db` was created before the app existed.

---

### 3.2 `config.py`

Holds all configuration values. Flask reads them with `app.config.from_object(...)`.

**Key additions:**

```python
JWT_SECRET_KEY           = os.environ.get('JWT_SECRET_KEY', 'voc-jwt-secret-change-in-prod')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
```

`JWT_SECRET_KEY` is the password used to **sign** tokens. Anyone with this key can create valid tokens — keep it secret in production. `timedelta(hours=8)` means tokens expire after 8 hours (one work day).

```python
AD_SERVER  = '192.168.4.3'    # IP of the Active Directory server
AD_PORT    = 389               # Standard LDAP port (636 for SSL)
AD_DOMAIN  = 'DEMO'           # NetBIOS domain name
AD_BASE_DN = 'DC=demo,DC=lab' # Where to search for users in AD tree
AD_BIND_DN = 'CN=svc-voc,...' # Service account distinguished name
AD_BIND_PWD = 'pfe2026*'      # Service account password
AD_USE_SSL  = False            # Set True in production with port 636
```

The **service account** (`svc-voc`) is a special read-only AD account the application uses to search the directory. It is NOT a user account — it's a technical account created specifically for this application.

---

### 3.3 `app/__init__.py`

The **application factory** — a function that builds and returns the Flask app. Using a factory (instead of a global `app` variable) allows creating multiple app instances (e.g., one for testing, one for production).

```python
def create_app(config_name=None):
    app = Flask(__name__, ...)
    app.config.from_object(config[config_name])

    db.init_app(app)   # Bind SQLAlchemy to this app
    jwt.init_app(app)  # Bind JWTManager to this app

    # Register blueprints (each blueprint = one module)
    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)
    ...
```

The `try/except ImportError` blocks for vtracker/vhub/etc. mean the app still starts even if those modules aren't coded yet — useful during incremental development.

---

### 3.4 `app/blueprints/auth/services.py`

This is the **core business logic** for authentication. Routes are thin — all the real work happens here.

#### `authenticate_ad(username, password) → dict | None`

The AD authentication uses the **service account pattern** (more secure than direct bind):

```
Step 1: Connect to AD server at 192.168.4.3:389
Step 2: Bind (login) as the service account (svc-voc)
        — this proves we're the VOC application, not just anyone
Step 3: Search the directory for the user by their sAMAccountName
        — sAMAccountName is the AD login field (e.g. "john.doe")
Step 4: Get the user's distinguishedName (their full AD path)
        — e.g. "CN=John Doe,OU=Users,DC=demo,DC=lab"
Step 5: Try to bind again, this time AS the user with their password
        — if this succeeds, the password is correct
Step 6: Return user data (username, email, groups they belong to)
```

Why two binds? Because you can't search the directory as an anonymous user — you need to authenticate first (step 2), then search (step 3), then verify the user's password (step 5).

`ldap3.utils.conv.escape_filter_chars(username)` sanitizes the username to prevent **LDAP injection** (the LDAP equivalent of SQL injection).

#### `map_ad_groups_to_scope(ad_groups) → Scope | None`

AD groups are organizational — `VOC_WINDOWS` means "Windows team member". This function translates that to a VOC scope:

```python
GROUP_SCOPE_MAP = {
    'VOC_ADMIN':   'Cyber Security',   # Admins are in the Cyber Security scope
    'VOC_WINDOWS': 'Windows Team',
    'VOC_LINUX':   'Linux Team',
    ...
}
```

If the user belongs to none of the known VOC groups → returns `None` → login is rejected with 403. This means you can't log in without being in a VOC AD group, even with valid AD credentials.

`_extract_cn('CN=VOC_WINDOWS,OU=Groups,DC=demo,DC=lab')` → `'VOC_WINDOWS'`

#### `get_or_create_user(ad_user, scope) → User`

**Just-in-time provisioning**: users don't need to be pre-created in the VOC database. The first time someone logs in, their account is automatically created from their AD data.

On subsequent logins, it just updates the email if it changed in AD (users sometimes get new email addresses).

Role assignment: if the user is in `VOC_ADMIN` group → `role='admin'`, otherwise → `role='user'`.

#### `generate_token(user) → str`

Creates the JWT. The token contains **claims** — key/value pairs embedded in the token:

```python
{
    'sub':      '42',              # subject = user_id (standard JWT field)
    'username': 'john.doe',
    'role':     'user',
    'scope_id': 17,
    'scope':    'Windows Team',
    'is_admin': False,
    'exp':      1746000000,        # expiry timestamp (auto-added by flask-jwt-extended)
}
```

These claims are available in any route via `get_jwt()` — no database query needed to know who the user is or what they can access.

---

### 3.5 `app/blueprints/auth/routes.py`

Four routes:

| Route | Method | Auth | Description |
|---|---|---|---|
| `/auth/login` | GET | None | Serves the HTML login page |
| `/api/auth/login` | POST | None | REST: validates credentials, returns JWT |
| `/api/auth/me` | GET | JWT | REST: returns current user info from token |
| `/api/auth/logout` | POST | JWT | REST: signals logout (client clears token) |

**Why is logout a no-op on the server?**

JWTs are stateless — the server doesn't store them, so it can't "invalidate" one. The client simply deletes the token from `localStorage`. For this project's security requirements this is sufficient. A production system would add a token blocklist (revocation list) in Redis.

**`POST /api/auth/login` logic:**

```
1. Parse JSON body → extract username + password
2. Call authenticate_ad() → None means wrong credentials → 401
3. Call map_ad_groups_to_scope() → None means no VOC group → 403
4. Call get_or_create_user() → get/create the DB record
5. Check is_active → disabled account → 403
6. Call generate_token() → build the JWT
7. Return 200 with { access_token, user }
```

---

### 3.6 `app/blueprints/auth/__init__.py`

```python
auth_bp = Blueprint('auth', __name__, template_folder='../../templates/auth')
```

Declares the Blueprint (a Flask concept for grouping related routes into a module). The name `'auth'` is used in `url_for('auth.login_page')` etc.

`template_folder='../../templates/auth'` tells Flask where to find templates when `render_template('login.html')` is called from within this blueprint.

---

### 3.7 `app/utils/decorators.py`

Decorators are functions that wrap other functions to add behavior before/after them. These two protect routes.

#### `@scope_required('Windows Team', 'Network Team')`

```python
@auth_bp.route('/some-route')
@jwt_required()          # 1st: verify token is valid and not expired
@scope_required('Windows Team', 'Network Team')  # 2nd: verify user's scope
def some_route():
    ...
```

Admins (`is_admin=True` in JWT claims) bypass all scope checks — they see everything.

#### `@admin_required`

```python
@auth_bp.route('/admin-only')
@jwt_required()
@admin_required
def admin_route():
    ...
```

Returns 403 JSON if the user is not an admin. Note: always pair with `@jwt_required()` first — the decorator order matters (outer → inner).

---

### 3.8 `app/utils/auth.py`

```python
def scope_filter(query, model_scope_field):
    claims = get_jwt()
    if claims.get('is_admin'):
        return query
    return query.filter(model_scope_field == claims.get('scope_id'))
```

**Every data query in the app must go through this function.** It ensures users only see data belonging to their scope.

Usage in any route:
```python
@jwt_required()
def my_route():
    q = AssetVulnerability.query.join(Asset)
    q = scope_filter(q, Asset.scope_id)   # ← apply scope restriction
    results = q.all()
```

Admins pass through with no filter added. Regular users get `.filter(Asset.scope_id == user_scope_id)` appended automatically.

---

### 3.9 `app/models/user.py`

Key change: **removed `UserMixin`** (a Flask-Login class that adds session helpers). With JWT, we don't need session helpers.

**Added `to_dict()`** — serializes the user to a JSON-safe dictionary. Used in the login response:

```python
return jsonify({
    'access_token': token,
    'user': user.to_dict(),   # ← this method
})
```

Result:
```json
{
    "user_id": 3,
    "username": "john.doe",
    "email": "john.doe@demo.lab",
    "role": "user",
    "scope": "Windows Team",
    "scope_id": 17,
    "category": "systeme"
}
```

---

## 4. Login Page (`app/templates/auth/login.html`)

A **standalone** HTML page (does not extend `base.html` — it has no sidebar). Dark navy theme matching banking security aesthetics.

### What it does

```javascript
form.addEventListener('submit', async (e) => {
    e.preventDefault();   // prevent normal form submission (page reload)

    const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });

    const data = await resp.json();

    if (resp.ok) {
        localStorage.setItem('voc_token', data.access_token);  // store token
        localStorage.setItem('voc_user', JSON.stringify(data.user));  // store user info
        window.location.href = '/vtracker/';  // redirect into the app
    } else {
        showError(data.error);  // show error inline (no page reload)
    }
});
```

`localStorage` persists across browser tabs and page refreshes, but is cleared when the user logs out or clears their browser data.

**Already-logged-in redirect**: if a token exists in `localStorage` when the login page loads, the user is redirected directly to `/vtracker/` — no need to log in again.

---

## 5. Base Template (`app/templates/shared/base.html`)

The master layout for all authenticated pages. Every module page (vtracker, vhub, etc.) will start with `{% extends "shared/base.html" %}`.

### JWT Guard

```javascript
const vocToken = localStorage.getItem('voc_token');
const vocUser  = JSON.parse(localStorage.getItem('voc_user') || 'null');

if (!vocToken || !vocUser) {
    window.location.href = '/auth/login';   // not logged in → kick to login page
}
```

This runs on every page load. If the token is missing (never logged in, or logged out), the user is immediately redirected. This is the **client-side guard**.

> Note: The server-side guard is `@jwt_required()` on API routes. Both are needed — the client guard gives a good UX (instant redirect), the server guard enforces security.

### `vocFetch()` helper

```javascript
window.vocFetch = function(url, options = {}) {
    options.headers['Authorization'] = 'Bearer ' + vocToken;
    return fetch(url, options).then(resp => {
        if (resp.status === 401) { /* token expired → redirect to login */ }
        return resp;
    });
};
```

All pages that make API calls should use `vocFetch()` instead of `fetch()`. It automatically:
- Adds the `Authorization: Bearer <token>` header
- Handles token expiry (401 → redirect to login)

Example usage in a page:
```javascript
const data = await vocFetch('/api/vtracker/list').then(r => r.json());
```

### Sidebar user info

```javascript
document.getElementById('sidebarUsername').textContent = vocUser.username;
document.getElementById('sidebarScope').textContent = vocUser.scope;
if (vocUser.role === 'admin') {
    document.getElementById('adminSection').classList.remove('d-none');
}
```

The sidebar reads user info from `localStorage` (no extra API call needed) and shows the Admin menu item only to admins.

### Blocks for child templates

```
{% block page_title %}  ← shown in the top bar (page heading)
{% block content %}     ← main page content
{% block extra_js %}    ← page-specific JavaScript (charts, etc.)
```

---

## 6. Authentication Flow — Step by Step

```
┌─────────────────────────────────────────────────────────────────┐
│                        LOGIN FLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User opens browser → navigates to /vtracker/               │
│     base.html JS detects no token → redirects to /auth/login   │
│                                                                 │
│  2. User enters credentials → form submits via fetch()         │
│     POST /api/auth/login  { username, password }               │
│                                                                 │
│  3. routes.py calls services.py:                               │
│     a. authenticate_ad(username, password)                     │
│        → svc-voc binds to AD                                   │
│        → searches for (sAMAccountName=username)                │
│        → rebinds as the user with their password               │
│        → returns { username, email, ad_groups: [...] }         │
│                                                                 │
│     b. map_ad_groups_to_scope(ad_groups)                       │
│        → finds first matching VOC group in the user's groups   │
│        → queries Scope table for matching scope_name           │
│        → returns Scope object                                  │
│                                                                 │
│     c. get_or_create_user(ad_user, scope)                      │
│        → looks up User by username in VOC DB                   │
│        → creates if first login, updates email if changed      │
│        → returns User object                                   │
│                                                                 │
│     d. generate_token(user)                                    │
│        → creates JWT signed with JWT_SECRET_KEY                │
│        → embeds: user_id, username, role, scope, is_admin      │
│        → returns token string "eyJ..."                         │
│                                                                 │
│  4. Response 200: { access_token, user }                       │
│     login.html JS stores token in localStorage                 │
│     → redirects to /vtracker/                                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    SUBSEQUENT REQUESTS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  5. User navigates to /vtracker/                               │
│     base.html loads, JS reads token from localStorage          │
│     → token exists → page renders normally                     │
│                                                                 │
│  6. Page JS calls vocFetch('/api/vtracker/list')               │
│     → adds header: Authorization: Bearer eyJ...               │
│     → Flask verifies JWT signature (no DB call)                │
│     → @jwt_required() passes                                   │
│     → scope_filter() applies scope from JWT claims             │
│     → returns scoped data                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Token Structure (JWT)

A JWT has 3 parts separated by dots: `header.payload.signature`

The **payload** (decoded) for a typical user looks like:

```json
{
  "sub":      "17",
  "iat":      1746000000,
  "nbf":      1746000000,
  "jti":      "abc123-unique-id",
  "exp":      1746028800,
  "username": "john.doe",
  "role":     "user",
  "scope_id": 17,
  "scope":    "Windows Team",
  "is_admin": false
}
```

| Field | Meaning |
|---|---|
| `sub` | Subject = `user_id` from the DB |
| `iat` | Issued at (Unix timestamp) |
| `exp` | Expires at (`iat + 8 hours`) |
| `jti` | Unique token ID |
| `username` | AD username |
| `role` | `'admin'` or `'user'` |
| `scope_id` | FK to `scopes` table |
| `scope` | Scope name (e.g. `'Windows Team'`) |
| `is_admin` | Convenience boolean |

The signature ensures nobody can **tamper** with the payload (e.g., change `is_admin` to `true`). Without the `JWT_SECRET_KEY`, a modified token fails verification.

---

## 8. API Reference

### `POST /api/auth/login`

**No authentication required.**

Request body:
```json
{ "username": "john.doe", "password": "MyPassword123" }
```

Responses:

| Status | Body | Reason |
|---|---|---|
| 200 | `{ "access_token": "eyJ...", "user": {...} }` | Success |
| 400 | `{ "error": "Username and password are required" }` | Missing fields |
| 401 | `{ "error": "Invalid Active Directory credentials" }` | Wrong username/password |
| 403 | `{ "error": "No valid scope assigned. Contact administrator." }` | Not in a VOC AD group |
| 403 | `{ "error": "Account is disabled. Contact administrator." }` | `is_active=False` in DB |

---

### `GET /api/auth/me`

**Requires**: `Authorization: Bearer <token>`

Returns the current user's identity from the JWT (no DB query):

```json
{
  "username": "john.doe",
  "role":     "user",
  "scope":    "Windows Team",
  "scope_id": 17,
  "is_admin": false
}
```

---

### `POST /api/auth/logout`

**Requires**: `Authorization: Bearer <token>`

```json
{ "message": "Successfully logged out" }
```

The client must delete `voc_token` and `voc_user` from `localStorage` after receiving this response (the login page's `vocLogout()` function does this automatically).

---

## 9. How to Use Auth in Future Blueprints

When implementing vtracker, vhub, admin, etc., follow this pattern:

### Protecting a route

```python
from flask_jwt_extended import jwt_required, get_jwt
from app.utils.decorators import admin_required, scope_required
from app.utils.auth import scope_filter

@vtracker_bp.route('/api/vtracker/list')
@jwt_required()                          # always first
def vuln_list():
    claims = get_jwt()                   # read token claims
    user_scope = claims['scope']         # e.g. "Windows Team"
    is_admin   = claims['is_admin']

    q = AssetVulnerability.query.join(Asset)
    q = scope_filter(q, Asset.scope_id)  # applies scope filter automatically
    q = q.filter(AssetVulnerability.vuln_status != 'Closed')
    return jsonify([...])
```

### Admin-only route

```python
@admin_bp.route('/api/admin/users')
@jwt_required()
@admin_required
def list_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])
```

### Scope-restricted route

```python
@vhub_bp.route('/api/vhub/cti', methods=['POST'])
@jwt_required()
@scope_required('Cyber Security', 'Windows Team')
def add_cti():
    ...
```

### Making API calls from page JavaScript

```javascript
// In any page that extends base.html:
const resp = await vocFetch('/api/vtracker/list');
const data = await resp.json();
```

`vocFetch` (defined in `base.html`) automatically adds the `Authorization` header and handles token expiry.

---

## 10. Files Changed Summary

| File | Action | Key Change |
|---|---|---|
| `app/extensions.py` | **Created** | Centralized `db` + `jwt` to avoid circular imports |
| `config.py` | Modified | Added `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRES`, full AD config |
| `app/__init__.py` | Modified | Uses `extensions.py`; removed Flask-Login/CSRF; graceful optional blueprint loading |
| `app/models/user.py` | Modified | Removed `UserMixin` (Flask-Login); added `to_dict()` |
| `app/models/*.py` (×7) | Modified | `from app import db` → `from app.extensions import db` |
| `app/blueprints/auth/__init__.py` | Modified | Removed URL prefix (routes use explicit paths) |
| `app/blueprints/auth/routes.py` | **Rewritten** | 4 routes: login page + 3 REST endpoints |
| `app/blueprints/auth/services.py` | **Created** | AD auth, scope mapping, user provisioning, token generation |
| `app/utils/auth.py` | Modified | `scope_filter()` uses JWT claims instead of `current_user` |
| `app/utils/decorators.py` | **Created** | `@scope_required()` + `@admin_required` |
| `app/templates/auth/login.html` | **Rewritten** | Standalone dark login page with `fetch()` + localStorage |
| `app/templates/shared/base.html` | **Rewritten** | Left sidebar + JWT guard + `vocFetch()` helper |
| `requirements.txt` | Modified | Added `flask-jwt-extended==4.6.0`; removed Flask-Login, Flask-WTF |
| `.env.example` | Modified | Added `JWT_SECRET_KEY`, full AD parameters |
