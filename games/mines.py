import random
import threading
import time
from typing import Dict, List, Optional, Callable
import socketio

class MinesGame:
    def __init__(self, sid: str, emit_callback: Callable, socketio_instance):
        self.sid = sid
        self.emit = emit_callback
        self.socketio_instance = socketio_instance
        self._lock = threading.Lock()
        self.game_state = 'waiting'  # waiting, betting, running, finished
        self.grid_size = 5  # 5x5 grid
        self.mines_count = 3
        self.current_multiplier = 1.0
        self.mines_positions: List[int] = []
        self.revealed_positions: List[int] = []
        self.player_bet: Optional[float] = None
        self.player_cashout_multiplier: Optional[float] = None
        self._game_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.history: List[Dict] = []  # List to store game history

    def _add_to_history(self, result: str, multiplier: float = None):
        """Add a result to the game history"""
        history_item = {
            'result': result,
            'multiplier': multiplier
        }
        self.history.append(history_item)
        # Keep only last 10 results
        if len(self.history) > 10:
            self.history = self.history[-10:]
        # Emit updated history
        self.emit('game_history', {'history': self.history})

    def start_new_round(self):
        with self._lock:
            print(f'[Mines] SID {self.sid}: Starting new round. Resetting game state and variables.')

            self.game_state = 'betting'
            self.current_multiplier = 1.0
            self.mines_positions = []
            self.revealed_positions = []
            self.player_bet = None
            self.player_cashout_multiplier = None
            self._stop_event.clear()
            
            # Emit initial game state
            self.emit('game_state', {
                'game_state': 'betting',
                'grid_size': self.grid_size,
                'mines_count': self.mines_count,
                'current_multiplier': self.current_multiplier,
                'revealed_positions': self.revealed_positions
            })

    def place_bet(self, bet_amount: float) -> bool:
        with self._lock:
            if self.game_state != 'betting' or self.player_bet is not None:
                return False
            
            self.player_bet = bet_amount
            self.game_state = 'running'
            
            # Generate mines positions
            available_positions = list(range(self.grid_size * self.grid_size))
            self.mines_positions = random.sample(available_positions, self.mines_count)
            
            # Emit game state update
            self.emit('game_state', {
                'game_state': 'running',
                'grid_size': self.grid_size,
                'mines_count': self.mines_count,
                'current_multiplier': self.current_multiplier,
                'revealed_positions': self.revealed_positions
            })
            
            return True

    def reveal_position(self, position: int) -> bool:
        with self._lock:
            if self.game_state != 'running' or position in self.revealed_positions:
                return False
            
            if position in self.mines_positions:
                # Hit a mine - game over
                print(f'[Mines] SID {self.sid}: Mine hit at position {position}. Game finished.')
                self.game_state = 'finished'
                self.revealed_positions.append(position)
                self._add_to_history('mine')  # Add mine hit to history
                self.emit('game_state', {
                    'game_state': 'finished',
                    'grid_size': self.grid_size,
                    'mines_count': self.mines_count,
                    'current_multiplier': self.current_multiplier,
                    'revealed_positions': self.revealed_positions,
                    'mines_positions': self.mines_positions,
                    'win': False,
                    'win_amount': 0
                })
                return True
            
            # Safe position revealed
            print(f'[Mines] SID {self.sid}: Safe position {position} revealed.')
            self.revealed_positions.append(position)
            self.current_multiplier = self._calculate_multiplier()
            print(f'[Mines] SID {self.sid}: New multiplier: {self.current_multiplier:.2f}x')
            
            # Check if all safe positions are revealed
            if len(self.revealed_positions) == (self.grid_size * self.grid_size - self.mines_count):
                print(f'[Mines] SID {self.sid}: All safe positions revealed. Game finished.')
                self.game_state = 'finished'
                win_amount = self.player_bet * self.current_multiplier if self.player_bet else 0
                self._add_to_history('win', self.current_multiplier)  # Add win to history
                self.emit('game_state', {
                    'game_state': 'finished',
                    'grid_size': self.grid_size,
                    'mines_count': self.mines_count,
                    'current_multiplier': self.current_multiplier,
                    'revealed_positions': self.revealed_positions,
                    'mines_positions': self.mines_positions,
                    'win': True,
                    'win_amount': win_amount
                })
            else:
                self.emit('game_state', {
                    'game_state': 'running',
                    'grid_size': self.grid_size,
                    'mines_count': self.mines_count,
                    'current_multiplier': self.current_multiplier,
                    'revealed_positions': self.revealed_positions
                })
            
            return True

    def cashout(self) -> bool:
        with self._lock:
            if self.game_state != 'running' or not self.player_bet:
                return False
            
            print(f'[Mines] SID {self.sid}: Player cashing out at {self.current_multiplier:.2f}x')
            self.game_state = 'finished'
            self.player_cashout_multiplier = self.current_multiplier
            win_amount = self.player_bet * self.current_multiplier
            
            self._add_to_history('cashout', self.current_multiplier)  # Add cashout to history
            
            self.emit('game_state', {
                'game_state': 'finished',
                'grid_size': self.grid_size,
                'mines_count': self.mines_count,
                'current_multiplier': self.current_multiplier,
                'revealed_positions': self.revealed_positions,
                'mines_positions': self.mines_positions,
                'win': True,
                'win_amount': win_amount
            })
            
            return True

    def _calculate_multiplier(self) -> float:
        """Calculate current multiplier based on revealed positions and mines count"""
        total_positions = self.grid_size * self.grid_size
        safe_positions = total_positions - self.mines_count
        revealed_safe = len(self.revealed_positions)
        
        if revealed_safe == 0:
            return 1.0
        
        # Simple multiplier calculation
        # Can be adjusted for different payout schemes
        return round(1.0 + (revealed_safe / safe_positions) * 2.0, 2)

    def stop_game(self):
        self._stop_event.set()
        if self._game_thread and self._game_thread.is_alive():
            self._game_thread.join()

    def _schedule_next_round(self):
        """Schedules the start of a new round after a delay."""
        print(f'[Mines] SID {self.sid}: Scheduling next round start in 5 seconds.')
        time.sleep(5) # Wait for 5 seconds
        print(f'[Mines] SID {self.sid}: Starting new round now.')
        with self._lock:
            # Reset game state before starting a new round
            self.game_state = 'waiting' # Ensure state is waiting before starting new round
            self.player_bet = None # Reset player bet
            self.player_cashout_multiplier = None # Reset cashout multiplier
            # The initializeGrid on client side when receiving 'betting' state will clear revealed_positions
            # No need to clear mines_positions here as they are regenerated in start_new_round
            self.start_new_round() 