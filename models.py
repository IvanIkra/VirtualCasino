from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    total_bets = db.Column(db.Float, default=0.0)
    total_wins = db.Column(db.Float, default=0.0)
    total_income = db.Column(db.Float, default=0.0)
    total_expense = db.Column(db.Float, default=0.0)
    games_played = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "balance": self.balance,
            "total_bets": self.total_bets,
            "total_wins": self.total_wins,
            "games_played": self.games_played,
            "is_admin": self.is_admin,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "transactions": [t.to_dict() for t in self.transactions[-10:]]
        }

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    game_type = db.Column(db.String(20), nullable=True)
    bet_type = db.Column(db.String(20), nullable=True)
    bet_value = db.Column(db.String(20), nullable=True)
    result = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "amount": self.amount,
            "type": self.type,
            "game_type": self.game_type,
            "bet_type": self.bet_type,
            "bet_value": self.bet_value,
            "result": self.result,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }

class GameConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_type = db.Column(db.String(50), unique=True, nullable=False)
    config_data = db.Column(db.Text, nullable=False) # Store config as JSON string
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "game_type": self.game_type,
            "config_data": json.loads(self.config_data) if self.config_data else {},
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        }

    def from_dict(self, data):
        import json
        for field in ['game_type']:
            if field in data:
                setattr(self, field, data[field])
        if 'config_data' in data:
            self.config_data = json.dumps(data['config_data']) 