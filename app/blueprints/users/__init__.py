from flask import Blueprint

users_bp = Blueprint('users', __name__)

from . import routes  # noqa: F401, E402
