from datetime import datetime
from app.extensions import db


class EtlLog(db.Model):
    __tablename__ = 'etl_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='running')
    records_extracted = db.Column(db.Integer, default=0)
    records_matched = db.Column(db.Integer, default=0)
    records_inserted = db.Column(db.Integer, default=0)
    records_skipped = db.Column(db.Integer, default=0)
    error_msg = db.Column(db.Text, nullable=True)
    duration_sec = db.Column(db.Numeric(8, 2), nullable=True)
    run_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<EtlLog source={self.source} status={self.status}>'
