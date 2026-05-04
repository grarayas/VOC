from flask import render_template_string
from flask_jwt_extended import jwt_required
from . import users_bp


@users_bp.route('/')
@jwt_required()
def index():
    return render_template_string(
        '{% extends "shared/base.html" %}'
        '{% block page_title %}<i class="bi bi-people me-2"></i>Users{% endblock %}'
        '{% block content %}<p class="text-muted mt-3">Coming soon.</p>{% endblock %}'
    )
