from typing import List, Dict, Any
import random
import time
from .base import Game
# from config.slots_config import SYMBOLS, WEIGHTS, PAYOUTS # Удаляем импорт из файла конфигурации
from models import db, GameConfig # Импортируем db и GameConfig
import json

class Slots(Game):
    # Удаляем статические переменные SYMBOLS и PAYOUTS
    # SYMBOLS = ["🍒", "🍊", "🍋", "🍇", "7️⃣", "💎"]
    # PAYOUTS = {
    #     "🍒": 2,
    #     "🍊": 3,
    #     "🍋": 4,
    #     "🍇": 5,
    #     "7️⃣": 10,
    #     "💎": 20
    # }

    def __init__(self, user):
        super().__init__(user)
        self.reels = 3
        self.rows = 3
        # Инициализируем генератор случайных чисел
        random.seed(time.time())
        # Загружаем конфигурацию слотов из БД
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        # Пытаемся загрузить конфигурацию из базы данных
        config_entry = GameConfig.query.filter_by(game_type='slots').first()
        if config_entry and config_entry.config_data:
            try:
                return json.loads(config_entry.config_data)
            except json.JSONDecodeError:
                # Fallback на дефолтную конфигурацию при ошибке парсинга
                print("Error decoding slots config from DB, using default.")
                return self._get_default_config()
        else:
            # Fallback на дефолтную конфигурацию если нет записи в БД
            print("Slots config not found in DB, using default.")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        # Дефолтная конфигурация (если нет в БД или ошибка)
        return {
            "SYMBOLS": ["🍒", "🍊", "🍋", "🍇", "7️⃣", "💎"],
            "WEIGHTS": {
                "🍒": 30,
                "🍊": 25,
                "🍋": 20,
                "🍇": 15,
                "7️⃣": 7,
                "💎": 3
            },
            "PAYOUTS": {
                "🍒": 2,
                "🍊": 3,
                "🍋": 4,
                "🍇": 5,
                "7️⃣": 10,
                "💎": 20
            }
        }


    def generate_reel(self) -> List[str]:
        # Генерируем случайные символы с разными весами
        # Используем веса из загруженной конфигурации
        symbols = self.config.get('SYMBOLS', [])
        weights = self.config.get('WEIGHTS', {})
        weights_list = [weights.get(s, 0) for s in symbols]
        
        if not symbols or sum(weights_list) == 0:
             # Fallback на дефолтные символы и веса если конфиг пустой или некорректный
             default_config = self._get_default_config()
             symbols = default_config['SYMBOLS']
             weights = default_config['WEIGHTS']
             weights_list = [weights.get(s, 0) for s in symbols]
             
        total_weight = sum(weights_list)
        if total_weight == 0:
             # Если веса все еще нулевые, используем равномерное распределение
             probabilities = [1 / len(symbols)] * len(symbols) if symbols else []
        else:
             probabilities = [w / total_weight for w in weights_list]
        
        if not symbols or not probabilities:
            # Если символы или вероятности все еще пустые, возвращаем пустой список
            print("Warning: Could not generate reel due to invalid configuration.")
            return [""] * self.rows # Возвращаем пустые символы или обработать ошибку иначе
            
        return [random.choices(symbols, weights=probabilities)[0] for _ in range(self.rows)]

    def calculate_win(self, symbols: List[List[str]], bet_amount: float) -> tuple[float, List[str]]:
        total_win = 0
        winning_lines = []
        
        # Проверяем горизонтальные линии
        for row_idx, row in enumerate(symbols):
            if len(set(row)) == 1:
                symbol = row[0]
                # Используем выплаты из загруженной конфигурации
                payouts = self.config.get('PAYOUTS', {})
                win = bet_amount * payouts.get(symbol, 0)
                total_win += win
                # Формируем описание для выигрышной линии по строке (называем её Вертикальной по запросу пользователя)
                winning_lines.append(f"Вертикальная линия {row_idx + 1}: {''.join(row)} Выигрыш: {win}₽")
        
        # Проверяем вертикальные линии (т.е. столбцы)
        for col_idx in range(self.reels):
            column = [symbols[row][col_idx] for row in range(self.rows)]
            if len(set(column)) == 1:
                symbol = column[0]
                # Используем выплаты из загруженной конфигурации
                payouts = self.config.get('PAYOUTS', {})
                win = bet_amount * payouts.get(symbol, 0)
                total_win += win
                # Формируем описание для выигрышной линии по столбцу (называем её Горизонтальной по запросу пользователя)
                winning_lines.append(f"Горизонтальная линия {col_idx + 1}: {''.join(column)} Выигрыш: {win}₽")
        
        # Проверяем диагонали
        diagonal1 = [symbols[i][i] for i in range(self.rows)]
        diagonal2 = [symbols[i][self.rows-1-i] for i in range(self.rows)]
        
        if len(set(diagonal1)) == 1:
            symbol = diagonal1[0]
            # Используем выплаты из загруженной конфигурации
            payouts = self.config.get('PAYOUTS', {})
            win = bet_amount * payouts.get(symbol, 0)
            total_win += win
            # Изменяем формат строки для выигрышной линии
            winning_lines.append(f"Диагональ \\: {''.join(diagonal1)} Выигрыш: {win}₽")
        
        if len(set(diagonal2)) == 1:
            symbol = diagonal2[0]
            # Используем выплаты из загруженной конфигурации
            payouts = self.config.get('PAYOUTS', {})
            win = bet_amount * payouts.get(symbol, 0)
            total_win += win
            # Изменяем формат строки для выигрышной линии
            winning_lines.append(f"Диагональ /: {''.join(diagonal2)} Выигрыш: {win}₽")
        
        return total_win, winning_lines

    def play(self, bet_amount: float) -> Dict[str, Any]:
        if not self.place_bet(bet_amount):
            return {
                "success": False,
                "message": "Недостаточно средств или неверная сумма ставки"
            }
        
        # Генерируем случайные символы для каждого барабана
        result = [self.generate_reel() for _ in range(self.reels)]
        win_amount, winning_lines = self.calculate_win(result, bet_amount)
        
        if win_amount > 0:
            self.add_win(win_amount)
        
        return {
            "success": True,
            "result": result,
            "win_amount": win_amount,
            "balance": self.user.balance,
            "winning_lines": winning_lines
        } 