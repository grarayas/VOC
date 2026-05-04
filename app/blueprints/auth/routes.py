from flask import render_template, request, jsonify, make_response, current_app
from flask_jwt_extended import jwt_required, get_jwt, set_access_cookies, unset_jwt_cookies
from . import auth_bp
from .services import authenticate_ad, authenticate_local, map_ad_groups_to_scope, get_or_create_user, generate_token
from app.utils.decorators import admin_required
from app.models import Scope


# ─── HTML page ────────────────────────────────────────────────────────────────

@auth_bp.route('/auth/login')
def login_page():
    return render_template('auth/login.html')


# ─── REST API ─────────────────────────────────────────────────────────────────

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    ad_user = authenticate_ad(username, password)
    if ad_user is None:
        # Dev fallback: when AD is unreachable, accept any password for DB users
        if current_app.debug:
            user = authenticate_local(username)
            if user:
                token = generate_token(user)
                resp = make_response(jsonify({'access_token': token, 'user': user.to_dict()}), 200)
                set_access_cookies(resp, token)
                return resp
        return jsonify({'error': 'Invalid Active Directory credentials'}), 401

    scope = map_ad_groups_to_scope(ad_user['ad_groups'])
    if scope is None:
        return jsonify({'error': 'No valid scope assigned. Contact administrator.'}), 403

    user = get_or_create_user(ad_user, scope)
    if not user.is_active:
        return jsonify({'error': 'Account is disabled. Contact administrator.'}), 403

    token = generate_token(user)
    resp = make_response(jsonify({
        'access_token': token,
        'user': user.to_dict(),
    }), 200)
    set_access_cookies(resp, token)   # sets voc_token cookie server-side
    return resp


@auth_bp.route('/api/auth/me', methods=['GET'])
@jwt_required()
def me():
    claims = get_jwt()
    return jsonify({
        'username': claims['username'],
        'role':     claims['role'],
        'scope':    claims['scope'],
        'scope_id': claims['scope_id'],
        'is_admin': claims['is_admin'],
    }), 200


@auth_bp.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    resp = make_response(jsonify({'message': 'Successfully logged out'}), 200)
    unset_jwt_cookies(resp)   # clears voc_token cookie server-side
    return resp


@auth_bp.route('/api/scopes')
@jwt_required()
@admin_required
def scopes():
    rows = Scope.query.order_by(Scope.scope_id).all()
    result = {'systeme': [], 'applicatif': [], 'systeme_app': []}
    for s in rows:
        if s.category in result:
            result[s.category].append({'scope_id': s.scope_id, 'scope_name': s.scope_name})
    return jsonify(result), 200
