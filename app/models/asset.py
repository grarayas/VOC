from app.extensions import db


class Asset(db.Model):
    __tablename__ = 'assets'

    asset_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inventory_number = db.Column(db.String(100), nullable=True)
    rec_id = db.Column(db.String(100), nullable=True)
    ci_class = db.Column(db.String(100), nullable=True)
    ci_type = db.Column(db.String(100), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    ip_address = db.Column(db.String(50), nullable=True)
    mac_address = db.Column(db.String(50), nullable=True)
    operating_system = db.Column(db.String(150), nullable=True)
    server_usage = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(50), default='Active')
    environment = db.Column(db.String(100), nullable=True)
    trigramm = db.Column(db.String(50), nullable=True)
    vlan = db.Column(db.String(50), nullable=True)
    subnet_id = db.Column(db.String(50), nullable=True)
    architecture = db.Column(db.String(100), nullable=True)
    criticality = db.Column(db.String(50), default='Important')
    app_name = db.Column(db.String(150), nullable=True)
    dev_team = db.Column(db.String(100), nullable=True)
    it_team = db.Column(db.String(100), nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    scope_id = db.Column(db.Integer, db.ForeignKey('scopes.scope_id'), nullable=False)

    occurrences = db.relationship('AssetVulnerability', backref='asset', lazy='select')

    def __repr__(self):
        return f'<Asset {self.name} ({self.ip_address})>'
