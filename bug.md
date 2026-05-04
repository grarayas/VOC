# VOC Platform - Bug Report

> Generated: April 30, 2026

---

## Critical Issues

### 1. Empty Application Factory (CRITICAL)
**File:** `app/__init__.py`

The application factory file is completely empty. The `run.py` calls `create_app()` but this function doesn't exist.

```python
# run.py
from app import create_app
app = create_app()  # This will fail!
```

**Impact:** Application cannot start.

---

### 2. Missing Closing Brace in Config
**File:** `config.py` (line 48-50)

```python
config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
# Missing closing brace
```

**Impact:** Syntax error, application cannot start.

---

### 3. Missing Blueprints (MAJOR)

According to `PROJECT.md`, the project should have 5 blueprints, but only 2 exist:

| Blueprint | Status | File Location |
|-----------|--------|---------------|
| auth/ | ✅ Implemented | `app/blueprints/auth/` |
| vtracker/ | ✅ Implemented | `app/blueprints/vtracker/` |
| vhub/ | ❌ Missing | Templates exist at `app/templates/vhub/` |
| reporting/ | ❌ Missing | Templates exist at `app/templates/reporting/` |
| admin/ | ❌ Missing | Not in templates |

**Impact:** Core features unavailable.

---

### 4. Templates Without Blueprints
**Folders:** `app/templates/vhub/`, `app/templates/reporting/`

These template folders exist but have no corresponding blueprint code:
- `app/templates/vhub/` - Contains: `_vuln_form.html`, `bitsight.html`, `cti.html`, `redteam.html`
- `app/templates/reporting/` - Contains: `dashboard.html`

**Impact:** Routes will return 404 errors.

---

## Medium Issues

### 5. JWT Configuration Insecure for Production
**File:** `config.py` (lines 20-23)

```python
JWT_COOKIE_SECURE        = False   # set True in production (HTTPS only)
JWT_COOKIE_CSRF_PROTECT  = False   # simplified for dev
```

**Impact:** Security vulnerabilities in production.

---

### 6. Hardcoded Credentials in Config
**File:** `config.py` (lines 26-31)

```python
AD_BIND_DN = os.environ.get('AD_BIND_DN',  'ygrara@demo.lab')
AD_BIND_PWD = os.environ.get('AD_BIND_PWD', 'pfe2026*')
```

**Impact:** Security risk - credentials in source code.

---

### 7. Missing .env File
No `.env` file present in the project. Default values are used which may not be appropriate for all environments.

---

## Minor Issues

### 8. Incomplete vtracker Routes
**File:** `app/blueprints/vtracker/routes.py` (line 100-101)

The detail function appears incomplete:
```python
def detail(av_id):
    claims = get_jwt()
```

**Impact:** Detail page may not work properly.

---

### 9. Missing Error Handling in Auth Service
**File:** `app/blueprints/auth/services.py`

The `map_ad_groups_to_scope` function appears incomplete (line 100):
```python
            scope = Scope.query.filter_by(scope_name=scope_name).first()
# Missing return statement
```

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 2 |
| Major | 2 |
| Medium | 3 |
| Minor | 2 |
| **Total** | **9** |

---

## Recommended Actions

1. **Immediate:** Fix `app/__init__.py` - implement `create_app()` factory
2. **Immediate:** Fix `config.py` - add closing brace
3. **High:** Implement missing blueprints (vhub, reporting, admin)
4. **Medium:** Move credentials to environment variables
5. **Low:** Add proper error handling and logging