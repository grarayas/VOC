from flask import render_template_string
from flask_jwt_extended import jwt_required
from . import assets_bp


@assets_bp.route('/')
@jwt_required()
def index():
    return render_template_string(
        '{% extends "shared/base.html" %}'
        '{% block page_title %}<i class="bi bi-hdd-network me-2"></i>Assets{% endblock %}'
        '{% block content %}<p class="text-muted mt-3">Coming soon.</p>{% endblock %}'
    )
