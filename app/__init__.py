import os
from flask import Flask, redirect, request, jsonify
from app.extensions import db, jwt

_LOGIN_URL = '/auth/login'


def _wants_json():
    """True when the client explicitly asked for JSON (API call), not a browser page load."""
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json'


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, template_folder='templates', static_folder='static')

    from config import config
    app.config.from_object(config.get(config_name, config['default']))

    db.init_app(app)
    jwt.init_app(app)

    # ── JWT error handlers ────────────────────────────────────────────────────
    # API calls get JSON; browser page loads get a redirect to the login page.

    @jwt.unauthorized_loader
    def missing_token(reason):
        if _wants_json():
            return jsonify({'error': 'Missing or invalid token', 'detail': reason}), 401
        return redirect(_LOGIN_URL)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        if _wants_json():
            return jsonify({'error': 'Token expired. Please log in again.'}), 401
        return redirect(_LOGIN_URL)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        if _wants_json():
            return jsonify({'error': 'Invalid token', 'detail': reason}), 422
        return redirect(_LOGIN_URL)

    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)

    # These blueprints will be implemented in subsequent modules
    try:
        from app.blueprints.vtracker import vtracker_bp
        app.register_blueprint(vtracker_bp, url_prefix='/vtracker')
    except ImportError:
        pass

    try:
        from app.blueprints.vhub import vhub_bp
        app.register_blueprint(vhub_bp, url_prefix='/vhub')
    except ImportError:
        pass

    try:
        from app.blueprints.reporting import reporting_bp
        app.register_blueprint(reporting_bp, url_prefix='/reporting')
    except ImportError:
        pass

    try:
        from app.blueprints.admin import admin_bp, overview_bp
        app.register_blueprint(overview_bp, url_prefix='/overview')
        app.register_blueprint(admin_bp,    url_prefix='/admin')
    except ImportError:
        pass

    try:
        from app.blueprints.assets import assets_bp
        app.register_blueprint(assets_bp, url_prefix='/assets')
    except ImportError:
        pass

    try:
        from app.blueprints.users import users_bp
        app.register_blueprint(users_bp, url_prefix='/users')
    except ImportError:
        pass

    @app.route('/')
    def index():
        return redirect('/auth/login')

    return app
