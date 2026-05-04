from flask_jwt_extended import get_jwt


def scope_filter(query, model_scope_field):
    """Apply scope restriction — admins see everything, users see their scope only."""
    claims = get_jwt()
    if claims.get('is_admin'):
        return query
    return query.filter(model_scope_field == claims.get('scope_id'))
