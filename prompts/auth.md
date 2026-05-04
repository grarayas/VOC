# Auth Implementation — Prompt for Claude Code

## Context

You are working on the **VOC Platform** — a Flask vulnerability management web application for a banking enterprise. Read `PROJECT.md` and `MODELS.md` before starting. The project uses **Flask App Factory pattern** with SQLAlchemy ORM and modular Blueprint architecture.

---

## Architecture Decision

Authentication uses **JWT tokens** (not Flask-Login sessions).
- Active Directory = **authentication provider** (validates credentials)
- VOC_DB = **authorization provider** (stores users, scopes, permissions)
- Every protected route requires a valid JWT + valid scope

---

## Project Structure for Auth Module

```
app/
├── extensions.py              # Initialize db, jwt — CREATE THIS FILE
├── auth/
│   ├── __init__.py            # Blueprint declaration
│   ├── routes.py              # API endpoints only
│   ├── services.py            # Business logic — CREATE THIS FILE
│   └── models.py              # Auth-related DB models — CREATE THIS FILE
```

---

## Active Directory Configuration

```
AD_SERVER   = 192.168.4.3
AD_PORT     = 389
AD_DOMAIN   = DEMO
AD_BASE_DN  = DC=demo,DC=lab
AD_BIND_DN  = CN=svc-voc,OU=ServiceAccounts,DC=demo,DC=lab
AD_BIND_PWD = pfe2026*
AD_USE_SSL  = false
```

---

## Step 1 — `app/extensions.py`

Centralize all Flask extensions initialization here to avoid circular imports:

```python
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db  = SQLAlchemy()
jwt = JWTManager()
```

Update `app/__init__.py` to import `db` and `jwt` from `extensions.py` and call `db.init_app(app)` and `jwt.init_app(app)`.

---

## Step 2 — `config.py`

Add JWT configuration:

```python
from datetime import timedelta

JWT_SECRET_KEY           = os.getenv('JWT_SECRET_KEY', 'voc-jwt-secret-change-in-prod')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
```

Add all AD config:

```python
AD_SERVER   = os.getenv('AD_SERVER',   '192.168.4.3')
AD_PORT     = int(os.getenv('AD_PORT', 389))
AD_DOMAIN   = os.getenv('AD_DOMAIN',   'DEMO')
AD_BASE_DN  = os.getenv('AD_BASE_DN',  'DC=demo,DC=lab')
AD_BIND_DN  = os.getenv('AD_BIND_DN',  'CN=svc-voc,OU=ServiceAccounts,DC=demo,DC=lab')
AD_BIND_PWD = os.getenv('AD_BIND_PWD', 'pfe2026*')
AD_USE_SSL  = os.getenv('AD_USE_SSL',  'false').lower() == 'true'
```

---

## Step 3 — `app/auth/models.py`

The `users` and `scopes` tables already exist in SQL Server (created by `voc_schema_v2.sql`). Map them with SQLAlchemy:

```python
# Table: scopes
class Scope(db.Model):
    __tablename__ = 'scopes'
    scope_id    # INT PK
    scope_name  # VARCHAR(150)
    category    # VARCHAR(50) — 'applicatif' | 'systeme' | 'systeme_app'
    bv_name     # VARCHAR(150) NULL
    description # VARCHAR(255) NULL

# Table: users
class User(db.Model):
    __tablename__ = 'users'
    user_id    # INT PK IDENTITY
    username   # VARCHAR(100) UNIQUE NOT NULL — matches AD sAMAccountName
    email      # VARCHAR(150) UNIQUE NOT NULL
    role       # VARCHAR(50) DEFAULT 'user' — 'admin' | 'user'
    is_active  # BIT DEFAULT 1
    scope_id   # INT FK → scopes.scope_id

    scope = db.relationship('Scope', backref='users')

    def to_dict(self):
        return {
            'user_id':  self.user_id,
            'username': self.username,
            'email':    self.email,
            'role':     self.role,
            'scope':    self.scope.scope_name if self.scope else None,
            'scope_id': self.scope_id,
            'category': self.scope.category if self.scope else None,
        }
```

---

## Step 4 — `app/auth/services.py`

### `authenticate_ad(username, password) -> dict | None`

LDAP3 service account pattern:

```
1. Connect: Server(AD_SERVER, port=AD_PORT, get_info=ALL)
2. Bind using service account (AD_BIND_DN / AD_BIND_PWD)
3. Search:
   - base:   AD_BASE_DN
   - filter: (sAMAccountName={username})
   - attrs:  ['sAMAccountName', 'mail', 'givenName', 'sn', 'memberOf', 'distinguishedName']
4. If no result → return None
5. Extract user distinguishedName
6. Second bind using user DN + provided password
7. If fails → return None
8. Return:
   {
     'username':   sAMAccountName,
     'email':      mail or f"{username}@demo.lab",
     'first_name': givenName,
     'last_name':  sn,
     'ad_groups':  [CN extracted from each memberOf DN]
   }
```

### `map_ad_groups_to_scope(ad_groups) -> Scope | None`

```python
GROUP_SCOPE_MAP = {
    'VOC_ADMIN':       'Cyber Security',
    'VOC_WINDOWS':     'Windows Team',
    'VOC_LINUX':       'Linux Team',
    'VOC_NETWORK':     'Network Team',
    'VOC_DATACENTER':  'Datacenter Team',
    'VOC_MIDDLEWARE':  'Middleware & Tools',
    'VOC_COREBANKING': 'IT Core Banking & Life Insurance',
    'VOC_MARKETS':     'IT Markets',
    'VOC_PAYMENT':     'IT Payment & Compliance',
    'VOC_CYBERSEC':    'Cyber Security',
    'VOC_SDF':         'Software Development Factory',
    'VOC_ITOPS':       'IT Operations & Infrastructures Ops',
}
# Extract CN from memberOf DN strings
# Match against GROUP_SCOPE_MAP
# Query Scope table by scope_name
# Return first matching Scope or None
```

### `get_or_create_user(ad_user_data, scope) -> User`

```
Search: User.query.filter_by(username=ad_user_data['username']).first()

Case A — User exists:
  - Update email if changed
  - db.session.commit()
  - Return user

Case B — User does not exist:
  - role = 'admin' if 'VOC_ADMIN' in ad_groups else 'user'
  - Create User(username, email, role, scope_id, is_active=True)
  - db.session.add() + commit()
  - Return new user
```

### `generate_token(user) -> str`

```python
from flask_jwt_extended import create_access_token

identity = str(user.user_id)
additional_claims = {
    'username': user.username,
    'role':     user.role,
    'scope_id': user.scope_id,
    'scope':    user.scope.scope_name if user.scope else None,
    'is_admin': user.role == 'admin',
}
return create_access_token(identity=identity, additional_claims=additional_claims)
```

---

## Step 5 — `app/auth/routes.py`

### `POST /api/auth/login`

```
1. Parse JSON body: username, password
2. Validate not empty → 400 if missing
3. authenticate_ad(username, password) → None = 401
4. map_ad_groups_to_scope(ad_groups) → None = 403
5. get_or_create_user(ad_user, scope)
6. Check is_active → False = 403
7. generate_token(user)
8. Return 200:
   {
     "access_token": "eyJ...",
     "user": user.to_dict()
   }
```

### `GET /api/auth/me` — `@jwt_required()`

Returns claims from JWT (no DB query):

```python
claims = get_jwt()
return jsonify({
    'username': claims['username'],
    'role':     claims['role'],
    'scope':    claims['scope'],
    'scope_id': claims['scope_id'],
    'is_admin': claims['is_admin'],
}), 200
```

### `POST /api/auth/logout` — `@jwt_required()`

```python
return jsonify({'message': 'Successfully logged out'}), 200
```

---

## Step 6 — `app/utils/decorators.py`

```python
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt

def scope_required(*allowed_scopes):
    """
    Restricts to users whose scope is in allowed_scopes.
    Admins bypass all scope checks.
    Usage: @scope_required('Windows Team', 'Linux Team')
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            claims = get_jwt()
            if claims.get('is_admin'):
                return f(*args, **kwargs)
            if claims.get('scope') not in allowed_scopes:
                return jsonify({'error': 'Insufficient scope permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        claims = get_jwt()
        if not claims.get('is_admin'):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated
```

---

## Step 7 — `app/templates/auth/login.html`

Professional banking-style login page:

- Full-page centered card, Bootstrap 5 CDN
- VOC Platform branding with shield/lock icon (Bootstrap Icons)
- Fields: `username` (text), `password` (password)
- Submit → `fetch('POST /api/auth/login', JSON body)`
- On success → `localStorage.setItem('voc_token', token)` + `localStorage.setItem('voc_user', JSON.stringify(user))` + redirect to `/vtracker/`
- On error → show error alert below form (no page reload)
- Dark navy professional color scheme
- Responsive

---

## Step 8 — `app/templates/shared/base.html`

Master Jinja2 template for all module pages:

- Bootstrap 5 + Bootstrap Icons + Chart.js (all CDN)
- Left sidebar:
  - VOC Platform logo + title
  - Nav items: V-Tracker, V-Hub (submenu: CTI / BitSight / Red Team), Reporting, Admin (hidden if not admin)
  - Active page highlighted via Jinja2 `request.endpoint`
  - Bottom: username + scope badge + logout button
- Top navbar: `{% block page_title %}{% endblock %}`
- Content: `{% block content %}{% endblock %}`
- Flash messages: `{% block messages %}{% endblock %}`
- `{% block extra_js %}{% endblock %}` before `</body>`
- JWT auth check on load:
  ```javascript
  if (!localStorage.getItem('voc_token')) {
      window.location.href = '/auth/login';
  }
  ```
- Logout clears localStorage and redirects to `/auth/login`
- All API calls from pages add header: `Authorization: Bearer {voc_token}`

---

## `requirements.txt` — Add

```
flask-jwt-extended==4.6.0
```

---

## Files to Create / Modify

| File | Action |
|---|---|
| `requirements.txt` | Add `flask-jwt-extended==4.6.0` |
| `app/extensions.py` | Create |
| `app/__init__.py` | Modify — use extensions.py |
| `config.py` | Modify — JWT + AD config |
| `.env` | Add `JWT_SECRET_KEY` |
| `app/auth/__init__.py` | Modify — register blueprint at `/api/auth` |
| `app/auth/routes.py` | Rewrite — REST endpoints |
| `app/auth/services.py` | Create — AD auth + scope mapping + user logic |
| `app/auth/models.py` | Create — User + Scope models |
| `app/utils/decorators.py` | Create — scope_required + admin_required |
| `app/templates/auth/login.html` | Create |
| `app/templates/shared/base.html` | Create |

---

## Testing

```bash
pip install flask-jwt-extended==4.6.0
python run.py
```

```bash
# Test login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your_ad_user", "password": "your_password"}'

# Test protected route
curl http://localhost:5000/api/auth/me \
  -H "Authorization: Bearer eyJ..."
```

Expected responses:

```json
// 200 login success
{
  "access_token": "eyJ...",
  "user": {
    "username": "john.doe",
    "email": "john.doe@demo.lab",
    "role": "user",
    "scope": "Windows Team",
    "scope_id": 17,
    "category": "systeme"
  }
}

// 401 bad credentials
{"error": "Invalid Active Directory credentials"}

// 403 no scope
{"error": "No valid scope assigned. Contact administrator."}
```

---

## Business Rules (Non-Negotiable)

- AD is always validated first — no bypass allowed
- No local password storage — never save credentials in DB
- Every protected route: `@jwt_required()` + scope decorator
- Admins (`role='admin'`) bypass all scope restrictions
- JWT payload contains: `user_id`, `username`, `role`, `scope_id`, `scope`, `is_admin`
- Token expiry: 8 hours
- On expiry or missing token → redirect to `/auth/login`
