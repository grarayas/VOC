"""
AD connection + full login simulation test.
Run with: python reports/test_ad.py
"""
import getpass
import ldap3
import re

AD_SERVER   = '192.168.4.3'
AD_PORT     = 389
AD_BASE_DN  = 'DC=demo,DC=lab'
AD_BIND_DN  = 'ygrara@demo.lab'   # service account (UPN format)
AD_BIND_PWD = 'pfe2026*'

GROUP_SCOPE_MAP = {
    'VOC_ADMIN':         'Cyber Security',
    'VOC_WINDOWS':       'Windows Team',
    'VOC_LINUX':         'Linux Team',
    'VOC_NETWORK':       'Network Team',
    'VOC_DATACENTER':    'Datacenter Team',
    'VOC_MIDDLEWARE':    'Middleware & Tools',
    'VOC_COREBANKING':   'IT Core Banking & Life Insurance',
    'VOC_MARKETS':       'IT Markets',
    'VOC_PAYMENT':       'IT Payment & Compliance',
    'VOC_CYBERSEC':      'Cyber Security',
    'VOC_SDF':           'Software Development Factory',
    'VOC_ITOPS':         'IT Operations & Infrastructures Ops',
    'Admins du domaine': 'Cyber Security',
    'Datacenter Team':   'Datacenter Team',
    'IT_OPS':            'IT Operations & Infrastructures Ops',
    'Windows Team':      'Windows Team',
    'Linux Team':        'Linux Team',
    'Network Team':      'Network Team',
}


def extract_cn(dn):
    match = re.match(r'CN=([^,]+)', dn, re.IGNORECASE)
    return match.group(1) if match else dn


def separator(title=''):
    print(f'\n{"─" * 50}')
    if title:
        print(f'  {title}')
        print(f'{"─" * 50}')


# ── 1. Service account bind ───────────────────────────────────────────────────
separator('STEP 1 — Service account bind')
server = ldap3.Server(AD_SERVER, port=AD_PORT, use_ssl=False, get_info=ldap3.ALL)
try:
    svc_conn = ldap3.Connection(server, user=AD_BIND_DN, password=AD_BIND_PWD, auto_bind=True)
    print(f'[OK] Bound as service account: {AD_BIND_DN}')
except Exception as e:
    print(f'[FAIL] Service account bind failed: {e}')
    exit(1)

# ── 2. User lookup ────────────────────────────────────────────────────────────
separator('STEP 2 — User lookup (simulating a login)')
test_username = input('Username to test login for (e.g. ygrara, mbenaleya): ').strip()
test_password = getpass.getpass(f'Password for {test_username}: ')

svc_conn.search(
    search_base=AD_BASE_DN,
    search_filter=f'(sAMAccountName={ldap3.utils.conv.escape_filter_chars(test_username)})',
    attributes=['sAMAccountName', 'mail', 'givenName', 'sn', 'memberOf', 'distinguishedName'],
)

if not svc_conn.entries:
    print(f'[FAIL] User "{test_username}" not found in AD.')
    exit(1)

entry    = svc_conn.entries[0]
user_dn  = str(entry.distinguishedName)
groups   = [extract_cn(g) for g in (entry.memberOf.values if entry.memberOf else [])]

print(f'[OK] User found:')
print(f'     sAMAccountName : {entry.sAMAccountName}')
print(f'     mail           : {entry.mail}')
print(f'     distinguishedName: {user_dn}')
print(f'     AD groups      : {groups}')

# ── 3. Password verification ──────────────────────────────────────────────────
separator('STEP 3 — Password verification (re-bind as user)')
user_conn = ldap3.Connection(server, user=user_dn, password=test_password)
if user_conn.bind():
    print(f'[OK] Password correct — user authenticated successfully')
    user_conn.unbind()
else:
    print(f'[FAIL] Wrong password for {test_username}')
    exit(1)

# ── 4. Scope mapping ──────────────────────────────────────────────────────────
separator('STEP 4 — Scope mapping')
matched_scope = None
for group in groups:
    scope_name = GROUP_SCOPE_MAP.get(group)
    if scope_name:
        matched_scope = scope_name
        print(f'[OK] Group "{group}" → scope "{scope_name}"')
        break
    else:
        print(f'     Group "{group}" — no VOC mapping')

if not matched_scope:
    print(f'[FAIL] No VOC scope found for user groups: {groups}')
else:
    print(f'\n[OK] Final scope assignment: "{matched_scope}"')

# ── 5. Role determination ─────────────────────────────────────────────────────
separator('STEP 5 — Role determination')
is_admin = 'Admins du domaine' in groups or 'VOC_ADMIN' in groups
role = 'admin' if is_admin else 'user'
print(f'[OK] Role: {role}')

# ── Summary ───────────────────────────────────────────────────────────────────
separator('RESULT')
print(f'  username : {entry.sAMAccountName}')
print(f'  email    : {entry.mail}')
print(f'  role     : {role}')
print(f'  scope    : {matched_scope}')
print()
print('Full login simulation: SUCCESS')

svc_conn.unbind()
