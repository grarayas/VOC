from datetime import datetime, date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func
from . import vtracker_bp
from app.extensions import db
from app.models import AssetVulnerability, Asset, Vulnerability, SlaTracking, VulnHistory, Scope


def _base_query(claims):
    """Return a base AV query filtered to the user's scope (admins see all)."""
    q = (
        AssetVulnerability.query
        .join(Asset,          AssetVulnerability.asset_id == Asset.asset_id)
        .join(Vulnerability,  AssetVulnerability.vuln_id  == Vulnerability.vuln_id)
        .filter(AssetVulnerability.vuln_status != 'Closed')
    )
    if not claims.get('is_admin'):
        q = q.filter(Asset.scope_id == claims.get('scope_id'))
    return q


# ── Scopes + counts (mega-dropdown) ───────────────────────────────────────────

@vtracker_bp.route('/api/scopes')
@jwt_required()
def api_scopes():
    claims = get_jwt()
    if not claims.get('is_admin'):
        return jsonify({'error': 'Admin only'}), 403

    count_rows = (
        db.session.query(
            Asset.scope_id,
            func.count(AssetVulnerability.av_id).label('open'),
            func.sum(
                db.case((Vulnerability.severity == 'Critical', 1), else_=0)
            ).label('critical'),
        )
        .join(Asset,         AssetVulnerability.asset_id == Asset.asset_id)
        .join(Vulnerability, AssetVulnerability.vuln_id  == Vulnerability.vuln_id)
        .filter(AssetVulnerability.vuln_status.in_(['Open', 'In Progress', 'Risk Assessment']))
        .group_by(Asset.scope_id)
        .all()
    )
    counts = {r.scope_id: {'open': r.open, 'critical': int(r.critical or 0)} for r in count_rows}

    scopes = Scope.query.order_by(Scope.category, Scope.scope_name).all()

    return jsonify([
        {
            'scope_id':   s.scope_id,
            'scope_name': s.scope_name,
            'category':   s.category,
            'open':       counts.get(s.scope_id, {}).get('open', 0),
            'critical':   counts.get(s.scope_id, {}).get('critical', 0),
        }
        for s in scopes
    ])


# ── Dashboard ─────────────────────────────────────────────────────────────────

@vtracker_bp.route('/')
@jwt_required()
def dashboard():
    claims = get_jwt()
    q = _base_query(claims)

    total    = q.count()
    open_cnt = q.filter(AssetVulnerability.vuln_status == 'Open').count()
    critical = q.filter(Vulnerability.severity == 'Critical').count()

    breached = (
        AssetVulnerability.query
        .join(Asset,         AssetVulnerability.asset_id == Asset.asset_id)
        .join(SlaTracking,   AssetVulnerability.av_id    == SlaTracking.av_id)
        .filter(AssetVulnerability.vuln_status != 'Closed')
        .filter(SlaTracking.sla_status == 'Breached')
    )
    if not claims.get('is_admin'):
        breached = breached.filter(Asset.scope_id == claims.get('scope_id'))

    return render_template('dashboard.html', kpis={
        'total':       total,
        'open':        open_cnt,
        'critical':    critical,
        'breached_sla': breached.count(),
    })


# ── List ──────────────────────────────────────────────────────────────────────

@vtracker_bp.route('/list')
@jwt_required()
def vuln_list():
    claims = get_jwt()

    severity_filter  = request.args.get('severity',  '')
    status_filter    = request.args.get('status',    '')
    source_filter    = request.args.get('source',    '')
    search           = request.args.get('search',    '').strip()
    scope_cat        = request.args.get('scope_cat', '')
    scope_id_filter  = request.args.get('scope_id',  0, type=int)
    page             = request.args.get('page', 1, type=int)

    q = _base_query(claims)

    if claims.get('is_admin'):
        if scope_id_filter:
            q = q.filter(Asset.scope_id == scope_id_filter)
        elif scope_cat:
            q = q.join(Scope, Asset.scope_id == Scope.scope_id)
            q = q.filter(Scope.category == scope_cat)

    # Resolve a human-readable title for filtered views
    scope_name = None
    if scope_id_filter and claims.get('is_admin'):
        s = Scope.query.get(scope_id_filter)
        scope_name = s.scope_name if s else None

    if severity_filter:
        q = q.filter(Vulnerability.severity == severity_filter)
    if status_filter:
        q = q.filter(AssetVulnerability.vuln_status == status_filter)
    if source_filter:
        q = q.filter(AssetVulnerability.source == source_filter)
    if search:
        like = f'%{search}%'
        q = q.filter(
            Vulnerability.plugin_name.ilike(like) |
            Vulnerability.cve.ilike(like)         |
            Asset.name.ilike(like)                |
            AssetVulnerability.ip_address.ilike(like)
        )

    pagination = q.order_by(AssetVulnerability.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False
    )

    return render_template('list.html',
        pagination       = pagination,
        severity_filter  = severity_filter,
        status_filter    = status_filter,
        source_filter    = source_filter,
        search           = search,
        scope_cat        = scope_cat,
        scope_id_filter  = scope_id_filter,
        scope_name       = scope_name,
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@vtracker_bp.route('/detail/<int:av_id>')
@jwt_required()
def detail(av_id):
    claims = get_jwt()
    av = AssetVulnerability.query.get_or_404(av_id)

    if not claims.get('is_admin') and av.asset.scope_id != claims.get('scope_id'):
        flash('Accès refusé.', 'danger')
        return redirect(url_for('vtracker.vuln_list'))

    return render_template('detail.html', av=av, is_admin=claims.get('is_admin', False))


# ── Change status ─────────────────────────────────────────────────────────────

@vtracker_bp.route('/status/<int:av_id>', methods=['POST'])
@jwt_required()
def change_status(av_id):
    claims     = get_jwt()
    av         = AssetVulnerability.query.get_or_404(av_id)
    new_status = request.form.get('new_status', '').strip()
    comment    = request.form.get('comment', '').strip()

    if not claims.get('is_admin') and av.asset.scope_id != claims.get('scope_id'):
        flash('Accès refusé.', 'danger')
        return redirect(url_for('vtracker.vuln_list'))

    if new_status not in av.next_statuses:
        flash(f'Transition vers "{new_status}" non autorisée.', 'danger')
        return redirect(url_for('vtracker.detail', av_id=av_id))

    if new_status == 'Accepted Risk' and not claims.get('is_admin'):
        flash('Seul un admin peut accepter un risque.', 'danger')
        return redirect(url_for('vtracker.detail', av_id=av_id))

    old_status = av.vuln_status
    av.vuln_status = new_status
    av.updated_at  = datetime.utcnow()

    # Set branch on first transition out of Open
    if old_status == 'Open':
        av.branch = 'risk_assessment' if new_status == 'Risk Assessment' else 'standard'

    # Log status change
    db.session.add(VulnHistory(
        av_id      = av_id,
        user_id    = int(claims['sub']),
        entry_type = 'status_change',
        old_status = old_status,
        new_status = new_status,
        created_at = datetime.utcnow(),
    ))

    # Log optional comment
    if comment:
        db.session.add(VulnHistory(
            av_id      = av_id,
            user_id    = int(claims['sub']),
            entry_type = 'comment',
            content    = comment,
            created_at = datetime.utcnow(),
        ))

    # Update SLA if now fixed or closed
    if av.sla and new_status in ('Fixed', 'Closed'):
        av.sla.sla_status = 'Completed'
    if av.sla and new_status == 'Accepted Risk':
        av.sla.risk_acceptance = True

    db.session.commit()
    flash(f'Statut mis à jour : {old_status} → {new_status}', 'success')
    return redirect(url_for('vtracker.detail', av_id=av_id))


# ── Add comment ───────────────────────────────────────────────────────────────

@vtracker_bp.route('/comment/<int:av_id>', methods=['POST'])
@jwt_required()
def add_comment(av_id):
    claims  = get_jwt()
    av      = AssetVulnerability.query.get_or_404(av_id)
    content = request.form.get('comment', '').strip()

    if not claims.get('is_admin') and av.asset.scope_id != claims.get('scope_id'):
        flash('Accès refusé.', 'danger')
        return redirect(url_for('vtracker.vuln_list'))

    if not content:
        flash('Le commentaire ne peut pas être vide.', 'warning')
        return redirect(url_for('vtracker.detail', av_id=av_id))

    db.session.add(VulnHistory(
        av_id      = av_id,
        user_id    = int(claims['sub']),
        entry_type = 'comment',
        content    = content,
        created_at = datetime.utcnow(),
    ))
    db.session.commit()
    flash('Commentaire ajouté.', 'success')
    return redirect(url_for('vtracker.detail', av_id=av_id))

