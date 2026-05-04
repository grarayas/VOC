from app.extensions import db


class SlaTracking(db.Model):
    __tablename__ = 'sla_tracking'

    sla_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    av_id = db.Column(db.Integer, db.ForeignKey('asset_vulnerabilities.av_id'), unique=True, nullable=False)
    sla_days_target = db.Column(db.Integer, nullable=True)
    sla_due_date = db.Column(db.Date, nullable=True)
    sla_status = db.Column(db.String(50), default='On Track')
    remed_target_date = db.Column(db.Date, nullable=True)
    risk_acceptance = db.Column(db.Boolean, nullable=False, default=False)
    remed_responsible = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)

    _STATUS_COLOR = {
        'On Track':  'success',
        'At Risk':   'warning',
        'Breached':  'danger',
        'Completed': 'secondary',
    }

    @property
    def status_color(self):
        return self._STATUS_COLOR.get(self.sla_status, 'secondary')

    def __repr__(self):
        return f'<SlaTracking av_id={self.av_id} status={self.sla_status}>'
