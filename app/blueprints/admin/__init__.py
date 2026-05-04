from flask import Blueprint

overview_bp = Blueprint('overview', __name__)
admin_bp    = Blueprint('admin',    __name__)

from . import routes  # noqa: F401, E402
