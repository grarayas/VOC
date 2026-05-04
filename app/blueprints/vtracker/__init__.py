from flask import Blueprint

vtracker_bp = Blueprint('vtracker', __name__, template_folder='../../templates/vtracker')

from . import routes  # noqa: F401, E402
