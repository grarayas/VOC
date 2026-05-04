from app.extensions import db


class Scope(db.Model):
    __tablename__ = 'scopes'

    scope_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scope_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'applicatif' | 'systeme' | 'systeme_app'
    bv_name = db.Column(db.String(150), nullable=True)
    description = db.Column(db.String(255), nullable=True)

    users = db.relationship('User', backref='scope', lazy='select')
    assets = db.relationship('Asset', backref='scope', lazy='select')

    def __repr__(self):
        return f'<Scope {self.scope_name}>'
