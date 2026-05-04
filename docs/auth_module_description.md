# Auth Module Full Description

The auth module handles authentication and authorization for the VOC (Vulnerability Operations Center) application. Here's a detailed breakdown:

---

## 1. Module Structure

| File | Purpose |
|------|---------|
| `__init__.py` | Creates the Flask Blueprint `auth_bp` |
| `routes.py` | Defines HTTP endpoints (login page, REST APIs) |
| `services.py` | Contains core business logic (AD auth, user management, token generation) |

---

## 2. Business Logic Flow

### Login Flow (`/api/auth/login`)

```
User submits credentials
        ↓
authenticate_ad() → Validate against Active Directory
        ↓
map_ad_groups_to_scope() → Map AD groups to internal Scope
        ↓
get_or_create_user() → Provision or update user in database
        ↓
generate_token() → Create JWT with claims
        ↓
Return token + user data
```

---

## 3. Key Functions

### `authenticate_ad(username, password)`

- **Purpose**: Three-way LDAP bind for authentication
- **Steps**:
  1. Connect to AD using service account (from config)
  2. Search for user by `sAMAccountName`
  3. Re-bind with user's credentials to verify password
  4. Extract user attributes: `sAMAccountName`, `mail`, `givenName`, `sn`, `memberOf`
  5. Parse group memberships from `memberOf` attribute

### `map_ad_groups_to_scope(ad_groups)`

- **Purpose**: Map AD group memberships to internal Scope entities
- **Logic**: Iterates through user's AD groups, looks up in `GROUP_SCOPE_MAP` dictionary
- **Returns**: First matching `Scope` object or `None`

### `get_or_create_user(ad_user, scope)`

- **Purpose**: Synchronize AD user with local database
- **Logic**:
  - Find existing user by username
  - If found: update email if changed
  - If new: create user with role based on AD groups (`VOC_ADMIN` → `admin`, else `user`)
- **Note**: Users are auto-provisioned on first login

### `generate_token(user)`

- **Purpose**: Create signed JWT token
- **Claims included**:
  - `username`, `role`, `scope_id`, `scope`, `is_admin`
- **Token stored in HTTP-only cookie** (`voc_token`)

---

## 4. Group-to-Scope Mapping

The system supports two naming conventions:

| AD Group | Internal Scope |
|----------|----------------|
| `VOC_ADMIN` | Cyber Security |
| `VOC_WINDOWS` | Windows Team |
| `VOC_LINUX` | Linux Team |
| `VOC_NETWORK` | Network Team |
| `VOC_DATACENTER` | Datacenter Team |
| `VOC_MIDDLEWARE` | Middleware & Tools |
| `VOC_COREBANKING` | IT Core Banking & Life Insurance |
| `VOC_MARKETS` | IT Markets |
| `VOC_PAYMENT` | IT Payment & Compliance |
| `VOC_CYBERSEC` | Cyber Security |
| `VOC_SDF` | Software Development Factory |
| `VOC_ITOPS` | IT Operations & Infrastructures Ops |

---

## 5. API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/login` | GET | None | Render login HTML page |
| `/api/auth/login` | POST | None | Authenticate user, return JWT |
| `/api/auth/me` | GET | JWT | Get current user info |
| `/api/auth/logout` | POST | JWT | Clear JWT cookies |

---

## 6. User Model

The `User` model stores:
- `username` (unique) - from AD sAMAccountName
- `email` (unique) - from AD mail
- `role` - `admin` or `user`
- `scope_id` - FK to Scope (determines data access)
- `is_active` - account enabled/disabled

---

## 7. Security Features

1. **Password never stored** - authentication done via LDAP bind
2. **JWT in HTTP-only cookies** - prevents XSS token theft
3. **Scope-based access control** - users can only see data for their scope
4. **Auto-provisioning** - new AD users get access based on group membership
5. **Account disabling** - admins can disable accounts via `is_active` flag

---

## 8. Error Handling

| Error | HTTP Code | Cause |
|-------|-----------|-------|
| Missing credentials | 400 | Empty username/password |
| Invalid AD credentials | 401 | Wrong password or user not in AD |
| No valid scope | 403 | User's AD groups don't map to any Scope |
| Account disabled | 403 | `is_active=False` in database |

---

## 9. File Locations

- `app/blueprints/auth/__init__.py` - Blueprint definition
- `app/blueprints/auth/routes.py` - HTTP endpoints
- `app/blueprints/auth/services.py` - Business logic
- `app/models/user.py` - User model
- `app/templates/auth/login.html` - Login page template