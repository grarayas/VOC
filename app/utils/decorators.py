from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt


def scope_required(*allowed_scopes):
    """
    Restricts access to users whose scope is in allowed_scopes.
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
