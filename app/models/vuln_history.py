from datetime import datetime
from app.extensions import db


class VulnHistory(db.Model):
    __tablename__ = 'vuln_history'

    history_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    av_id = db.Column(db.Integer, db.ForeignKey('asset_vulnerabilities.av_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    entry_type = db.Column(db.String(30), nullable=False)  # 'status_change' | 'comment'
    old_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=True)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<VulnHistory av_id={self.av_id} type={self.entry_type}>'
