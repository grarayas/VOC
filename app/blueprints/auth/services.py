import re
from flask import current_app
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import User, Scope

GROUP_SCOPE_MAP = {
    # VOC convention groups (production naming)
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

    # Demo lab actual AD group names
    'VOC_ADMIN': 'Cyber Security',
    'Datacenter Team':   'Datacenter Team',
    'IT_OPS':            'IT Operations & Infrastructures Ops',
    'Windows Team':      'Windows Team',
    'Linux Team':        'Linux Team',
    'Network Team':      'Network Team',
}


def _extract_cn(dn: str) -> str:
    """Extract CN value from a distinguished name string."""
    match = re.match(r'CN=([^,]+)', dn, re.IGNORECASE)
    return match.group(1) if match else dn


def authenticate_ad(username: str, password: str) -> dict | None:
    """
    Bind with service account, search for the user, then re-bind as the user.
    Returns AD user data dict on success, None on failure.
    """
    try:
        import ldap3

        cfg = current_app.config
        server = ldap3.Server(
            cfg['AD_SERVER'],
            port=cfg['AD_PORT'],
            use_ssl=cfg['AD_USE_SSL'],
            get_info=ldap3.ALL,
        )

        # Bind as service account to search
        svc_conn = ldap3.Connection(
            server,
            user=cfg['AD_BIND_DN'],
            password=cfg['AD_BIND_PWD'],
            auto_bind=True,
        )

        svc_conn.search(
            search_base=cfg['AD_BASE_DN'],
            search_filter=f'(sAMAccountName={ldap3.utils.conv.escape_filter_chars(username)})',
            attributes=['sAMAccountName', 'mail', 'givenName', 'sn', 'memberOf', 'distinguishedName'],
        )

        if not svc_conn.entries:
            return None

        entry = svc_conn.entries[0]
        user_dn = str(entry.distinguishedName)

        # Re-bind as the actual user to verify password
        user_conn = ldap3.Connection(server, user=user_dn, password=password)
        if not user_conn.bind():
            return None

        member_of = entry.memberOf.values if entry.memberOf else []
        ad_groups = [_extract_cn(dn) for dn in member_of]

        return {
            'username':   str(entry.sAMAccountName),
            'email':      str(entry.mail) if entry.mail else f'{username}@demo.lab',
            'first_name': str(entry.givenName) if entry.givenName else '',
            'last_name':  str(entry.sn) if entry.sn else '',
            'ad_groups':  ad_groups,
        }

    except Exception as exc:
        current_app.logger.warning('AD auth error: %s', exc)
        return None


def map_ad_groups_to_scope(ad_groups: list[str]) -> Scope | None:
    """Return the first Scope that matches the user's AD groups."""
    for group in ad_groups:
        scope_name = GROUP_SCOPE_MAP.get(group)
        if scope_name:
            scope = Scope.query.filter_by(scope_name=scope_name).first()
            if scope:
                return scope
    return None


def get_or_create_user(ad_user: dict, scope: Scope) -> User:
    """Find existing user or provision a new one from AD data."""
    user = User.query.filter_by(username=ad_user['username']).first()

    if user:
        if user.email != ad_user['email']:
            user.email = ad_user['email']
            db.session.commit()
        return user

    role = 'admin' if 'VOC_ADMIN' in ad_user['ad_groups'] else 'user'
    user = User(
        username=ad_user['username'],
        email=ad_user['email'],
        role=role,
        scope_id=scope.scope_id,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_local(username: str) -> 'User | None':
    """Dev fallback: accept any password for users that exist in the DB."""
    return User.query.filter_by(username=username, is_active=True).first()


def generate_token(user: User) -> str:
    """Create a signed JWT with user identity and claims."""
    additional_claims = {
        'username': user.username,
        'role':     user.role,
        'scope_id': user.scope_id,
        'scope':    user.scope.scope_name if user.scope else None,
        'is_admin': user.role == 'admin',
    }
    return create_access_token(
        identity=str(user.user_id),
        additional_claims=additional_claims,
    )
