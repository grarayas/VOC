from app.extensions import db


class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    role = db.Column(db.String(50), nullable=False, default='user')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    scope_id = db.Column(db.Integer, db.ForeignKey('scopes.scope_id'), nullable=False)

    sla_assignments = db.relationship(
        'SlaTracking', lazy='select',
        foreign_keys='SlaTracking.remed_responsible',
        backref=db.backref('responsible', lazy='select')
    )
    history_entries = db.relationship(
        'VulnHistory', lazy='select',
        foreign_keys='VulnHistory.user_id',
        backref=db.backref('author', lazy='select')
    )

    @property
    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self):
        return {
            'user_id':  self.user_id,
            'username': self.username,
            'email':    self.email,
            'role':     self.role,
            'scope':    self.scope.scope_name if self.scope else None,
            'scope_id': self.scope_id,
            'category': self.scope.category if self.scope else None,
        }

    def __repr__(self):
        return f'<User {self.username}>'
