from typing import Dict, Any
import random
from .base import Game

class Roulette(Game):
    def __init__(self, user):
        super().__init__(user)
        self.numbers = list(range(37))
        # Словарь для сопоставления номера с цветом (на русском) по стандартным правилам рулетки
        self.colors_russian = {
            0: "зеленый",
            1: "красный", 2: "черный", 3: "красный", 4: "черный", 5: "красный", 6: "черный",
            7: "красный", 8: "черный", 9: "красный", 10: "черный", 11: "черный", 12: "красный",
            13: "черный", 14: "красный", 15: "черный", 16: "красный", 17: "черный", 18: "красный",
            19: "красный", 20: "черный", 21: "красный", 22: "черный", 23: "красный", 24: "черный",
            25: "красный", 26: "черный", 27: "красный", 28: "черный", 29: "черный", 30: "красный",
            31: "черный", 32: "красный", 33: "черный", 34: "красный", 35: "черный", 36: "красный",
        }
        # Словарь для сопоставления английских названий цветов с русскими
        self.color_map = {
            "red": "красный",
            "black": "черный"
        }

    def play(self, bet_type: str, bet_amount: float, bet_value: Any = None) -> Dict[str, Any]:
        if not self.place_bet(bet_amount):
            return {
                "success": False,
                "message": "Недостаточно средств или неверная сумма ставки"
            }

        result = random.choice(self.numbers)
        result_color_russian = self.colors_russian[result]
        win_amount = 0
        win_description = None
        
        if bet_type == "number":
            # Проверяем, является ли bet_value числом и находится ли оно в допустимом диапазоне
            try:
                bet_number = int(bet_value)
                if 0 <= bet_number <= 36:
                    if bet_number == result:
                        win_amount = bet_amount * 35
                        win_description = f"Выпало число {result}"
                else:
                     return {
                        "success": False,
                        "message": "Неверное число для ставки (допустимо 0-36)"
                    }
            except (ValueError, TypeError):
                 return {
                    "success": False,
                    "message": "Неверное значение для ставки на число"
                }
        elif bet_type == "red" or bet_type == "black":
             # Для ставок на цвет используем color_map для сопоставления
            target_color_russian = self.color_map.get(bet_type)
            if target_color_russian and target_color_russian == result_color_russian:
                win_amount = bet_amount * 2
                win_description = f"Выпал {result_color_russian} цвет"
        elif bet_type == "even":
            if result != 0 and result % 2 == 0:
                win_amount = bet_amount * 2
                win_description = "Выпало четное число"
        elif bet_type == "odd":
            if result != 0 and result % 2 == 1:
                win_amount = bet_amount * 2
                win_description = "Выпало нечетное число"
        # Добавляем проверку для других некорректных bet_type, если необходимо
        else:
             return {
                "success": False,
                "message": "Неверный тип ставки"
            }

        if win_amount > 0:
            self.add_win(win_amount)

        return {
            "success": True,
            "result": result,
            "result_color": result_color_russian, # Возвращаем русский цвет
            "win_amount": win_amount,
            "balance": self.user.balance,
            "win_description": win_description
        } 