from typing import Dict, Any
from models import db, User, Transaction

class Game:
    def __init__(self, user: User):
        self.user = user

    def place_bet(self, amount: float) -> bool:
        if amount <= 0:
            return False
        if self.user.balance < amount:
            return False
        
        self.user.balance -= amount
        self.user.total_expense += amount
        transaction = Transaction(user_id=self.user.id, amount=-amount, type="bet")
        db.session.add(transaction)
        db.session.commit()
        return True

    def add_win(self, amount: float):
        self.user.balance += amount
        self.user.total_income += amount
        transaction = Transaction(user_id=self.user.id, amount=amount, type="win")
        db.session.add(transaction)
        db.session.commit() 