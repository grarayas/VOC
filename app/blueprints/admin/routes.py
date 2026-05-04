from flask import render_template, render_template_string, redirect
from flask_jwt_extended import jwt_required, get_jwt
from . import admin_bp, overview_bp
from app.extensions import db
from app.models import AssetVulnerability, Asset, Vulnerability, SlaTracking, Scope


def _cat_stats(cat):
    base = (
        AssetVulnerability.query
        .join(Asset,          AssetVulnerability.asset_id == Asset.asset_id)
        .join(Scope,          Asset.scope_id              == Scope.scope_id)
        .join(Vulnerability,  AssetVulnerability.vuln_id  == Vulnerability.vuln_id)
        .filter(AssetVulnerability.vuln_status != 'Closed')
        .filter(Scope.category == cat)
    )
    return {
        'total':    base.count(),
        'critical': base.filter(Vulnerability.severity == 'Critical').count(),
        'open':     base.filter(AssetVulnerability.vuln_status == 'Open').count(),
        'breached': (
            base
            .join(SlaTracking, AssetVulnerability.av_id == SlaTracking.av_id)
            .filter(SlaTracking.sla_status == 'Breached')
            .count()
        ),
    }


@overview_bp.route('/')
@jwt_required()
def overview():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return redirect('/vtracker/')

    stats = {cat: _cat_stats(cat) for cat in ('applicatif', 'systeme', 'systeme_app')}

    recent_critical = (
        AssetVulnerability.query
        .join(Vulnerability, AssetVulnerability.vuln_id  == Vulnerability.vuln_id)
        .join(Asset,         AssetVulnerability.asset_id == Asset.asset_id)
        .filter(Vulnerability.severity == 'Critical')
        .filter(AssetVulnerability.vuln_status != 'Closed')
        .order_by(AssetVulnerability.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template('admin/overview.html', stats=stats, recent_critical=recent_critical)


@admin_bp.route('/')
@jwt_required()
def admin_panel():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return redirect('/vtracker/')
    return render_template_string(
        '{% extends "shared/base.html" %}'
        '{% block page_title %}<i class="bi bi-gear me-2"></i>Admin Panel{% endblock %}'
        '{% block content %}<p class="text-muted mt-3">Coming soon.</p>{% endblock %}'
    )
