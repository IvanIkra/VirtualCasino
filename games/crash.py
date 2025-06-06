import random
import time
from threading import Timer, Lock
from typing import Optional
import socketio

class CrashGame:
    def __init__(self, emit_callback, sid: str):
        self.emit = emit_callback # Callback function to emit SocketIO events
        self.sid = sid # Store the client's SocketIO SID
        self.current_multiplier = 1.00
        self.game_state = 'waiting' # waiting, betting, running, crashed
        self.crash_point = None
        self.bets = {}
        self._timer: Optional[Timer] = None
        self._lock = Lock()
        self._update_interval = 0.05 # seconds for multiplier update (faster updates)
        self._game_speed = 0.02 # how fast the multiplier increases per interval
        self._start_time: Optional[float] = None
        self._betting_timer: Optional[Timer] = None
        self._betting_phase_duration = 10 # seconds for betting phase
        self._wait_between_rounds = 5 # seconds between rounds
        self._game_loop_running = False # Flag to control the main game loop background task

    def start_new_round(self):
        with self._lock:
            if self.game_state not in ['waiting', 'crashed']:
                print(f"[CrashGame] SID {self.sid}: Cannot start new round, game state is {self.game_state}")
                return False # Cannot start if a round is already in progress

            # Reset state
            self.current_multiplier = 1.00
            self.crash_point = self._calculate_crash_point()
            self.bets = {}
            self._start_time = None
            self.game_state = 'betting'
            self._betting_start_time = time.time() # Record betting start time
            self._game_loop_running = False # Ensure game loop is stopped before betting
            print(f"[CrashGame] SID {self.sid}: New round started. Betting phase. Crash point: {self.crash_point:.2f}x")

        # Get game state BEFORE emitting
        current_state = self.get_state()
        print(f"[CrashGame] SID {self.sid}: Got game state before emit.", current_state)

        # Emit game state AFTER releasing the lock and getting state
        print(f"[CrashGame] SID {self.sid}: Calling emit('game_state') to {self.sid}...")
        try:
            self.emit('game_state', current_state, room=self.sid) # Notify THIS client of betting phase
            print(f"[CrashGame] SID {self.sid}: emit('game_state') called successfully to {self.sid}.")
        except Exception as e:
            print(f"[CrashGame] SID {self.sid}: Error during emit('game_state') to {self.sid}: {e}")

        # Schedule transition to running state (can be outside lock)
        if self._betting_timer:
            self._betting_timer.cancel()
        self._betting_timer = Timer(self._betting_phase_duration, self._run_game)
        self._betting_timer.start()
        print(f"[CrashGame] SID {self.sid}: Betting phase lasts for {self._betting_phase_duration} seconds.")

        return True

    def _calculate_crash_point(self):
        # Generates a crash point such that P(crash <= x) = 1 - (1/x)
        # To avoid extremely high values and ensure it's at least 1.00
        while True:
            # Use a base that makes 1.00x less likely, e.g., start from 0.05
            random_value = random.uniform(0.05, 1)
            crash = 1 / (1 - random_value)
            if crash >= 1.01: # Ensure crash point is at least 1.01x
                 return round(min(crash, 200.0), 2) # Cap at 200x for this example and round

    def _run_game(self):
        with self._lock:
            if self.game_state != 'betting':
                print(f"[CrashGame] SID {self.sid}: _run_game called but state is {self.game_state}")
                return # Should only run after betting phase

            self.game_state = 'running'
            self._start_time = time.time() # Record start time
            self._game_loop_running = True # Set flag to start the game loop
            print(f"[CrashGame] SID {self.sid}: Game is running...")

        # Emit state change outside lock
        self.emit('game_state', self.get_state(), room=self.sid) # Notify THIS client game is running

        # Start the main game loop in a background task
        print(f"[CrashGame] SID {self.sid}: Starting main game loop background task...")
        # Use socketio.start_background_task to run the game loop in a Socket.IO managed thread
        socketio.start_background_task(self._game_loop_task)
        print(f"[CrashGame] SID {self.sid}: Main game loop background task started.")

    def _game_loop_task(self):
        # This function runs in a Socket.IO background task.
        print(f"[CrashGame] SID {self.sid}: Game loop background task started.")
        try:
            while True:
                print(f"[CrashGame] SID {self.sid}: Top of game loop, state: {self.game_state}.")
                # Check if the game loop should continue running
                # Acquire lock for checking/modifying _game_loop_running flag and game_state
                print(f"[CrashGame] SID {self.sid}: Attempting to acquire lock for loop check...")
                with self._lock:
                    print(f"[CrashGame] SID {self.sid}: Lock acquired for loop check.")
                    should_continue = self._game_loop_running and self.game_state == 'running'
                    print(f"[CrashGame] SID {self.sid}: Lock released for loop check. Should continue: {should_continue}.")

                if not should_continue:
                    print(f"[CrashGame] SID {self.sid}: Game loop stopping due to flag or state.")
                    break # Exit the loop if flag is false or state is not running

                # Get the current time elapsed for multiplier calculation (can be outside lock if _start_time is only written in _run_game)
                # For safety, let's acquire lock to read _start_time if it could change elsewhere.
                # In this structure, _start_time is set once in _run_game, so reading outside lock is fine.
                elapsed_time = time.time() - self._start_time

                # Calculate the new multiplier
                new_multiplier = 1.00 * (2**(elapsed_time * 0.1)) # Use the rate defined in _update_multiplier

                # Acquire lock to update multiplier and check for crash/auto-cashout conditions
                players_to_cashout = []
                print(f"[CrashGame] SID {self.sid}: Attempting to acquire lock for update/check...")
                with self._lock:
                    print(f"[CrashGame] SID {self.sid}: Lock acquired for update/check.")
                    self.current_multiplier = new_multiplier
                    print(f"[CrashGame] SID {self.sid}: Multiplier updated to {self.current_multiplier:.2f}x.")

                    # Check for crash
                    if self.current_multiplier >= self.crash_point - 0.005: # Allow small floating point tolerance
                        self.current_multiplier = self.crash_point # Cap at crash point
                        self.game_state = 'crashed'
                        print(f"[CrashGame] SID {self.sid}: CRASH at {self.crash_point:.2f}x.")
                        self._game_loop_running = False # Signal loop to stop

                        # Collect players to cashout before releasing lock
                        for user_id in list(self.bets.keys()):
                             bet_info = self.bets[user_id]
                             if bet_info['cashout_multiplier'] is None: # Only consider players who haven't manually cashed out
                                 # For auto-cashout at crash point, all remaining players auto-cashout
                                 if bet_info.get('auto_cashout') is not None: # If they set auto-cashout, it's processed at crash point if not reached earlier
                                      players_to_cashout.append(user_id) # Add to list to process cashout later
                                 elif bet_info.get('auto_cashout') is None: # If no auto-cashout set, they cashout at crash point by default
                                      players_to_cashout.append(user_id) # Add to list to process cashout later

                        print(f"[CrashGame] SID {self.sid}: Lock released after update/check (crash). Players to cashout: {players_to_cashout}.")

                        # Emit final multiplier update and handle round end AFTER setting state to crashed and stopping loop
                        # These will be scheduled as background tasks by emit_callback
                        self.emit('multiplier_update', {'multiplier': self.current_multiplier, 'game_state': self.game_state}, room=self.sid) # Final update to THIS client
                        print(f"[CrashGame] SID {self.sid}: Final multiplier_update emit scheduled.")

                        # Handle round end (calculates wins for cashed out players, emits round_result, schedules next round)
                        # Pass the list of players who cashed out at crash point to _handle_round_end
                        self._handle_round_end(players_at_crash=players_to_cashout)
                        print(f"[CrashGame] SID {self.sid}: _handle_round_end called after crash.")
                        break # Exit loop after crash

                    # Check for auto-cashouts if not crashed
                    for user_id in list(self.bets.keys()):
                         bet_info = self.bets[user_id]
                         if bet_info['cashout_multiplier'] is None and bet_info.get('auto_cashout') is not None and self.current_multiplier >= bet_info['auto_cashout']:
                             players_to_cashout.append(user_id)

                    print(f"[CrashGame] SID {self.sid}: Lock released after update/check (no crash). Players to auto-cashout: {players_to_cashout}.")

                # Process auto-cashouts (outside the main lock for better concurrency)
                for user_id in players_to_cashout:
                     # The cashout method acquires its own lock internally
                     print(f"[CrashGame] SID {self.sid}: Auto-cashout triggered for user {user_id}.")
                     self.cashout(user_id) # Call cashout logic (it handles win calculation and emits user_cashout)
                     print(f"[CrashGame] SID {self.sid}: cashout called for auto-cashout.")

                # Emit multiplier update if game is still running (check state again outside lock)
                # Use a try-except block around emit as it's a potential failure point
                # We need to acquire lock again to check game_state just before emitting
                should_emit_update = False
                with self._lock:
                    if self.game_state == 'running':
                        should_emit_update = True
                        current_multiplier_for_emit = self.current_multiplier
                        game_state_for_emit = self.game_state
                    print(f"[CrashGame] SID {self.sid}: Lock released before multiplier_update emit.")

                if should_emit_update:
                    try:
                        self.emit('multiplier_update', {'multiplier': current_multiplier_for_emit, 'game_state': game_state_for_emit}, room=self.sid) # Send update to THIS client
                        print(f"[CrashGame] SID {self.sid}: Multiplier_update emitted successfully.")
                    except Exception as e:
                        print(f"[CrashGame] SID {self.sid}: Error during multiplier_update emit: {e}")

                # Wait for the next update interval
                print(f"[CrashGame] SID {self.sid}: Waiting for next interval ({self._update_interval}s)...")
                time.sleep(self._update_interval)
                print(f"[CrashGame] SID {self.sid}: Wait finished.")

        except Exception as e:
            print(f"[CrashGame] SID {self.sid}: Exception in game loop background task: {e}")
            # Attempt to stop the game gracefully on error
            self.stop_game()
            # Re-raise the exception if necessary, or just log it
            # raise # Optionally re-raise
        finally:
            print(f"[CrashGame] SID {self.sid}: Game loop background task finished.")

    # The _update_multiplier method is no longer used for the main loop
    # Keep it as a placeholder or remove if no longer needed elsewhere.
    # Renamed to prevent accidental calls.
    def _old_update_multiplier_logic(self):
         print(f"[CrashGame] SID {self.sid}: _old_update_multiplier_logic was called. This should not happen in game loop.")
         pass # This method should not be called in the new loop structure

    def place_bet(self, user_id: int, bet_amount: int, auto_cashout: Optional[float] = None) -> tuple[bool, str]:
        with self._lock:
            if self.game_state != 'betting':
                message = f'Можно ставить только во время фазы ставок ({self.game_state})'
                print(f"[CrashGame] Bet rejected for user {user_id}. {message}")
                return False, message
            if user_id in self.bets:
                 message = 'Вы уже сделали ставку в этом раунде.'
                 print(f"[CrashGame] Bet rejected for user {user_id}. {message}")
                 return False, message

            # Validate auto_cashout if provided
            if auto_cashout is not None:
                 if auto_cashout < 1.01:
                     message = 'Авто-кэшаут должен быть не менее 1.01.'
                     print(f"[CrashGame] Bet rejected for user {user_id}. {message}")
                     return False, message
                 # Round auto_cashout to 2 decimal places for consistency
                 auto_cashout = round(auto_cashout, 2)


            self.bets[user_id] = {'bet_amount': bet_amount, 'cashout_multiplier': None, 'auto_cashout': auto_cashout}
            print(f"[CrashGame] Bet placed by user {user_id}: {bet_amount}, Auto-cashout: {auto_cashout}")
            # Maybe update players_betting state here and emit game_state
            
            # Get game state BEFORE emitting from place_bet
            current_state = self.get_state()
            print(f"[CrashGame] SID {self.sid}: Got game state after bet placement.", current_state)

            # Emit game state AFTER releasing the lock and getting state
            print(f"[CrashGame] SID {self.sid}: Calling emit('game_state') after bet placement...")
            try:
                self.emit('game_state', current_state, room=self.sid)
                print(f"[CrashGame] SID {self.sid}: emit('game_state') called successfully after bet placement.")
            except Exception as e:
                print(f"[CrashGame] SID {self.sid}: Error during emit('game_state') after bet placement: {e}")

            return True, "Ставка принята."

    def cashout(self, user_id: int) -> tuple[Optional[float], Optional[int], str]:
        with self._lock:
            # Allow cashout if game is running or crashed (for processing crash point cashouts)
            if self.game_state not in ['running', 'crashed']:
                 message = f'Можно забрать выигрыш только во время раунда ({self.game_state})'
                 print(f"[CrashGame] SID {self.sid}: Cashout rejected for user {user_id}. {message}")
                 return None, None, message
            if user_id not in self.bets or self.bets[user_id]['cashout_multiplier'] is not None:
                 message = 'У вас нет активной ставки или вы уже забрали выигрыш.'
                 print(f"[CrashGame] SID {self.sid}: Cashout rejected for user {user_id}. No active bet or already cashed out.")
                 return None, None, message

            # If game state is crashed, cashout multiplier is the crash point
            cashout_multiplier = self.current_multiplier # This will be crash_point if game_state is crashed
            self.bets[user_id]['cashout_multiplier'] = cashout_multiplier # Mark bet as cashed out
            win_amount = int(self.bets[user_id]['bet_amount'] * cashout_multiplier)
            self.bets[user_id]['win_amount'] = win_amount # Store win amount in bet info
            self.bets[user_id]['win'] = True # Mark as win

            print(f"[CrashGame] SID {self.sid}: User {user_id} cashed out at {cashout_multiplier:.2f}x. Win amount: {win_amount}")
            # Emit a user-specific event for immediate feedback via emit_callback
            # This will be handled in app.py to update balance and create transaction
            # emit_callback already uses self.sid as the default room
            self.emit('user_cashout', {
                'user_id': user_id,
                'win_amount': win_amount,
                'multiplier': cashout_multiplier,
                'message': f'Вы успешно забрали выигрыш на {cashout_multiplier:.2f}x. Выигрыш: {win_amount}₽'
            }, room=self.sid)

            # The message returned here is less important as feedback is via socket event
            return cashout_multiplier, win_amount, "Cashout processed." # message no longer used by app.py handle_cashout

    # Modified _handle_round_end to accept players who cashed out at crash point
    # Renaming back to original name now that it handles the logic
    def _handle_round_end(self, players_at_crash: list = None):
        # This method is called when the game crashes or manually stopped.
        # It should notify the client of the round result and schedule the next round.
        print(f"[CrashGame] SID {self.sid}: Handling round end...")

        # Process cashouts for players who hit auto-cashout during the multiplier increase
        # These are handled in the _game_loop_task before the crash check

        # Process cashouts for players who cashed out exactly at the crash point
        if players_at_crash:
            print(f"[CrashGame] SID {self.sid}: Processing cashouts for players at crash point: {players_at_crash}")
            for user_id in players_at_crash:
                # Call cashout logic. It will update bet_info, calculate win, and emit user_cashout.
                # We need to ensure cashout can be called even if game_state is 'crashed'
                # Modify cashout method to allow processing if game_state is 'running' or 'crashed'
                # Also need to ensure win amount is calculated correctly based on crash_point if cashout_multiplier is None
                # The existing cashout logic uses self.current_multiplier, which is set to crash_point before calling _handle_round_end, so it should be fine.
                self.cashout(user_id) # Call cashout logic
                print(f"[CrashGame] SID {self.sid}: cashout called for player {user_id} at crash point.")

        # Emit the final state and results data for app.py to process and emit to THIS client
        # Use a try-except block around emit as it's a potential failure point
        try:
            # Include final bets state for result processing
            final_bets_state = {user_id: self.bets.get(user_id) for user_id in self.bets}
            self.emit('round_result', {
                'crash_point': self.crash_point,
                'results': final_bets_state # Emit the final state of all bets for processing in app.py
            }, room=self.sid)
            print(f"[CrashGame] SID {self.sid}: round_result emitted successfully.")
        except Exception as e:
            print(f"[CrashGame] SID {self.sid}: Error during round_result emit: {e}")

        print(f"[CrashGame] SID {self.sid}: Round result data emitted to app.py for final processing for SID {self.sid}.")

        # After handling results, schedule the start of the next betting phase
        print(f"[CrashGame] SID {self.sid}: Scheduling next round in {self._wait_between_rounds}s.")
        if self._betting_timer:
            self._betting_timer.cancel()
        # Schedule the start of the next round using Timer (can be outside lock)
        self._betting_timer = Timer(self._wait_between_rounds, self.start_new_round)
        self._betting_timer.start()
        print(f"[CrashGame] SID {self.sid}: Next round scheduled.")

        self._start_time = None # Reset start time for the next round
        # Game state is set to 'crashed' before calling _handle_round_end
        # The state will be set to 'betting' in start_new_round after the wait_between_rounds

    def get_state(self) -> dict:
        with self._lock:
            state = {
                'game_state': self.game_state,
                'current_multiplier': self.current_multiplier,
                'crash_point': self.crash_point,
                'players_betting': len(self.bets),
                'betting_time_left': max(0, self._betting_phase_duration - (time.time() - self._betting_start_time)) if self.game_state == 'betting' else 0
            }
            return state

    def stop_game(self):
        with self._lock:
            print(f"[CrashGame] SID {self.sid}: Stopping game...")
            self._game_loop_running = False # Signal the game loop to stop

            # Cancel any active timers (betting phase timer, wait between rounds timer)
            if self._betting_timer:
                self._betting_timer.cancel()
                self._betting_timer = None

            # The game loop background task will exit on its own when _game_loop_running is False

            self.game_state = 'waiting' # Reset state
            self.bets = {}
            self.crash_point = None
            self.current_multiplier = 1.00
            self._start_time = None
            self._betting_start_time = None
            print(f"[CrashGame] SID {self.sid}: Game stopped for SID {self.sid}.")

# Example Usage (for testing)
if __name__ == '__main__':
    # Dummy emit function for testing
    def dummy_emit(event, data, room=None):
        print(f"[DummyEmit] Event: {event}, Data: {data}, Room: {room}")

    # Need a dummy SID for testing
    game = CrashGame(dummy_emit, "dummy_sid")
    game.start_new_round()

    # Simulate placing bets
    time.sleep(1) # Wait 1 second into betting phase
    game.place_bet(1, 100, auto_cashout=3.5)
    time.sleep(2) # Wait 3 seconds into betting phase
    game.place_bet(2, 50, auto_cashout=None) # No auto-cashout
    game.place_bet(3, 200, auto_cashout=2.0)

    # Let the game run and crash
    try:
        while True:
            time.sleep(1) # Keep script running to allow timers to execute
    except KeyboardInterrupt:
        game.stop_game() 