from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime
from games.slots import Slots
from games.roulette import Roulette
from models import db, User, Transaction, GameConfig
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from functools import wraps
import json
import time
from games.crash import CrashGame
from typing import Optional
from games.mines import MinesGame
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///casino.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

socketio = SocketIO(app)

# Модели базы данных
# slots = Slots()
# roulette = Roulette()
# Удаляем инициализацию pvp_game
# pvp_game = PvPGame()

# Инициализация Crash игры
# Словарь для хранения активных игр по SID
active_crash_games_by_sid = {}

# Store active mines games by SID
active_mines_games = {}

def create_new_crash_game_for_client(sid: str, user_id: int):
    # Передаем emit_callback, который запускает socketio.emit в фоновой задаче
    def client_emit_callback(event, data, room=None):
        # Если комната не указана явно, отправляем только текущему клиенту (владельцу игры)
        target_room = room if room is not None else sid
        #print(f"[CrashGame] Scheduling emit '{event}' to room {target_room}") # Added print
        socketio.start_background_task(
            emit, event, data, room=target_room
        )
        #print(f"[CrashGame] Emit background task scheduled for event '{event}' to room {target_room}.") # Added print

    # Создаем новую игру и передаем user_id (для логики ставок) и sid (для эмита)
    new_game = CrashGame(client_emit_callback, sid)
    active_crash_games_by_sid[sid] = new_game
    print(f"[CrashGame] Created new game instance for SID {sid}.")
    return new_game

def get_crash_game_by_sid(sid: str) -> Optional[CrashGame]:
    return active_crash_games_by_sid.get(sid)

def get_user_mines_game(sid):
    if sid not in active_mines_games:
        # Pass the socketio instance to the MinesGame constructor
        active_mines_games[sid] = MinesGame(sid, lambda event, data: socketio.emit(event, data, room=sid), socketio)
    return active_mines_games[sid]

# Создание таблиц базы данных и дефолтных конфигов
with app.app_context():
    db.create_all()
    # Создаем дефолтные конфиги если их нет
    default_configs = [
        {'game_type': 'slots', 'config_data': {
            'SYMBOLS': ["🍒", "🍊", "🍋", "🍇", "7️⃣", "💎"],
            'WEIGHTS': {
                '🍒': 30,
                '🍊': 25,
                '🍋': 20,
                '🍇': 15,
                '7️⃣': 7,
                '💎': 3
            },
            'PAYOUTS': {
                '🍒': 2,
                '🍊': 3,
                '🍋': 4,
                '🍇': 5,
                '7️⃣': 10,
                '💎': 20
            }
        }},
        # Можно добавить дефолтные конфиги для других игр здесь
        # {'game_type': 'roulette', 'config_data': {...}}
        # {'game_type': 'crash', 'config_data': {...}}
    ]
    
    for config_data in default_configs:
        if not GameConfig.query.filter_by(game_type=config_data['game_type']).first():
            new_config = GameConfig(
                game_type=config_data['game_type'],
                config_data=json.dumps(config_data['config_data'])
            )
            db.session.add(new_config)

    # Создаем пользователя админа, если его нет
    admin_user = User.query.filter_by(username='admin', is_admin=True).first()
    if not admin_user:
        admin_user = User(username='admin', is_admin=True)
        admin_user.set_password('admin') # Установите безопасный пароль в реальном приложении
        db.session.add(admin_user)
        print("Admin user created with username 'admin' and password 'admin'")

    db.session.commit()

# Декоратор для проверки авторизации пользователя
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Необходимо войти для доступа к этой странице.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Декоратор для проверки административных прав
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = None
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Недостаточно прав доступа')
            return redirect(url_for('index')) # Перенаправляем куда-то при отказе в доступе
        return f(*args, **kwargs)
    return decorated_function

# Контекстный процессор для передачи пользователя в шаблоны
@app.context_processor
def inject_user():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        return {'current_user': user}
    return {'current_user': None}

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username and password:
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session['user_id'] = user.id
                return redirect(url_for('index'))
            flash('Неверное имя пользователя или пароль')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not password:
            flash('Все поля обязательны для заполнения')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Пароли не совпадают')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует')
            return render_template('register.html')
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin_index():
    configs = GameConfig.query.all()
    return render_template('admin/index.html', configs=configs)

@app.route('/admin/config/<game_type>', methods=['GET', 'POST'])
@admin_required
def edit_game_config(game_type):
    config = GameConfig.query.filter_by(game_type=game_type).first()
    if not config:
        flash(f'Конфигурация для игры {game_type} не найдена.', 'danger')
        return redirect(url_for('admin_index'))

    if request.method == 'POST':
        config_data_str = request.form.get('config_data')
        try:
            # Проверяем, что данные в формате JSON
            json.loads(config_data_str)
            config.config_data = config_data_str
            db.session.commit()
            flash(f'Конфигурация для игры {game_type} успешно обновлена!', 'success')
            return redirect(url_for('admin_index'))
        except json.JSONDecodeError:
            flash('Ошибка: Неверный формат JSON.', 'danger')
        except Exception as e:
            flash(f'Ошибка при сохранении: {e}', 'danger')
            db.session.rollback() # Откатываем изменения при ошибке

    return render_template('admin/edit_game_config.html', config=config)

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/balance', methods=['POST'])
@admin_required
def update_user_balance(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin_users'))
    
    try:
        amount = float(request.form.get('amount', 0))
        action = request.form.get('action')
        
        if action == 'add':
            user.balance += amount
            transaction = Transaction(
                user_id=user.id,
                type='admin_add',
                amount=amount,
                game_type='admin'
            )
        elif action == 'subtract':
            if user.balance < amount:
                flash('Недостаточно средств на балансе', 'danger')
                return redirect(url_for('admin_users'))
            user.balance -= amount
            transaction = Transaction(
                user_id=user.id,
                type='admin_subtract',
                amount=amount,
                game_type='admin'
            )
        else:
            flash('Неверное действие', 'danger')
            return redirect(url_for('admin_users'))
        
        db.session.add(transaction)
        db.session.commit()
        flash(f'Баланс пользователя {user.username} успешно обновлен', 'success')
    except ValueError:
        flash('Неверная сумма', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении баланса: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/play/slots', methods=['POST'])
def play_slots():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.json
    bet_amount = data.get('bet_amount')

    if not isinstance(bet_amount, (int, float)) or bet_amount <= 0:
        return jsonify({'error': 'Invalid bet amount'}), 400
    
    if user.balance < bet_amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    slots = Slots(user)
    result = slots.play(bet_amount)
    
    print("Slots result:", result)  # Отладочный вывод
    
    if not result['success']:
        return jsonify({'error': result['message']}), 400
    
    if result['win_amount'] > 0:
        transaction = Transaction(
            user_id=user.id,
            type='win',
            amount=result['win_amount'],
            game_type='slots'
        )
    else:
        transaction = Transaction(
            user_id=user.id,
            type='loss',
            amount=bet_amount,
            game_type='slots'
        )
    
    db.session.add(transaction)
    db.session.commit()
    
    response_data = {
        'reels': result['result'],
        'win': result['win_amount'] > 0,
        'win_amount': result['win_amount'],
        'balance': result['balance'],
        'winning_lines': result['winning_lines']
    }
    print("Response data:", response_data)  # Отладочный вывод
    
    return jsonify(response_data)

@app.route('/play/roulette', methods=['POST'])
def play_roulette():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = db.session.get(User, session['user_id'])
    if not user:
         return jsonify({'error': 'User not found'}), 404

    data = request.json
    bet_type = data.get('bet_type')
    bet_amount = data.get('bet_amount')
    bet_value = data.get('bet_value')

    if not bet_type or not bet_amount or bet_amount <= 0:
        return jsonify({'error': 'Invalid bet data'}), 400

    if user.balance < bet_amount:
        return jsonify({'error': 'Insufficient balance'}), 400

    roulette = Roulette(user)
    result = roulette.play(bet_type, bet_amount, bet_value)

    if not result.get('success', False):
        return jsonify({'error': result.get('message', 'Game error')}), 400

    # Проверяем win_amount для определения выигрыша и создаем транзакцию
    win_amount = result.get('win_amount', 0)
    if win_amount > 0:
        transaction_type = 'win'
        transaction_amount = win_amount
    else:
        transaction_type = 'loss'
        transaction_amount = bet_amount # В случае проигрыша записываем сумму ставки

    transaction = Transaction(
        user_id=user.id,
        type=transaction_type,
        amount=transaction_amount,
        game_type='roulette'
    )
    db.session.add(transaction)
    db.session.commit()

    # Формируем ответ для фронтенда, добавляя ключ 'win'
    response_data = {
        'success': True,
        'result': result.get('result'), # Выпавшее число
        'result_color': result.get('result_color'), # Выпавший цвет
        'win_amount': win_amount,
        'balance': result.get('balance'),
        'win_description': result.get('win_description'),
        'win': win_amount > 0 # Добавляем булевый ключ 'win'
    }

    return jsonify(response_data)

@app.route('/slots')
def slots():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('games/slots.html')

@app.route('/roulette')
def roulette():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('games/roulette.html')

@app.route('/crash')
def crash():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('games/crash.html')

@app.route('/games/mines')
@login_required
def mines():
    return render_template('games/mines.html')

@app.route('/deposit/ad', methods=['POST'])
@login_required
def deposit_ad():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Вы не авторизованы'})
    
    user_id = session['user_id']
    with app.app_context():
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Пользователь не найден'})
        
        # Add 1000 to balance
        user.balance += 1000
        user.total_income += 1000  # Update total income
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            type='deposit',
            amount=1000,
            game_type='ad',
            result='Пополнение за просмотр рекламы'
        )
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Баланс успешно пополнен',
            'balance': user.balance
        })

@app.route('/get_random_ad')
@login_required
def get_random_ad():
    ad_dir = os.path.join('static', 'ad')
    ad_files = [f for f in os.listdir(ad_dir) if f.endswith('.mp4')]
    if not ad_files:
        return jsonify({'success': False, 'message': 'Нет доступных видео'})
    
    random_ad = random.choice(ad_files)
    return jsonify({
        'success': True,
        'video_url': url_for('static', filename=f'ad/{random_ad}')
    })

# Socket.IO обработчики для Crash игры
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f'Client connected: {sid}')
    mines_game = get_user_mines_game(sid)
    mines_game.start_new_round()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f'Client disconnected: {sid}')
    if sid in active_mines_games:
        active_mines_games[sid].stop_game()
        del active_mines_games[sid]

@socketio.on('place_bet')
def handle_place_bet(data):
    sid = request.sid
    print(f'[Mines] Received place_bet event from SID: {sid} with data: {data}')
    mines_game = get_user_mines_game(sid)
    
    if not mines_game:
        print(f'[Mines] No game instance found for SID: {sid}')
        socketio.emit('bet_response', {
            'success': False,
            'message': 'Игровая сессия не найдена.'
        }, room=sid)
        return

    # If the game is in 'finished' state, start a new round before processing the bet
    if mines_game.game_state == 'finished':
        print(f'[Mines] SID {sid}: Game state is finished. Attempting to start new round...')
        mines_game.start_new_round()
        print(f'[Mines] SID {sid}: start_new_round() called. Current state after call: {mines_game.game_state}')

    try:
        if mines_game.game_state != 'betting':
             print(f'[Mines] SID {sid}: Game is NOT in betting state ({mines_game.game_state}). Emitting failure response.')
             socketio.emit('bet_response', {
                'success': False,
                'message': 'Нельзя сделать ставку в текущий момент'
            }, room=sid)
             return

        bet_amount = float(data['bet_amount'])
        mines_count = int(data['mines_count'])
        print(f'[Mines] Parsed bet_amount: {bet_amount}, mines_count: {mines_count}')
        
        if bet_amount < 1:
            print(f'[Mines] Invalid bet amount: {bet_amount}')
            socketio.emit('bet_response', {
                'success': False,
                'message': 'Минимальная ставка - 1₽'
            }, room=sid)
            print(f'[Mines] Emitted bet_response (invalid amount) to SID: {sid}')
            return
        
        if mines_count not in [3, 5, 7]:
            print(f'[Mines] Invalid mines count: {mines_count}')
            socketio.emit('bet_response', {
                'success': False,
                'message': 'Некорректное количество мин'
            }, room=sid)
            print(f'[Mines] Emitted bet_response (invalid mines) to SID: {sid}')
            return
        
        if 'user_id' not in session:
             socketio.emit('bet_response', {'success': False, 'message': 'Вы не авторизованы.'}, room=sid)
             return
        
        user_id = session['user_id']
        with app.app_context():
            user = db.session.get(User, user_id)
            if not user:
                socketio.emit('bet_response', {'success': False, 'message': 'Пользователь не найден.'}, room=sid)
                return
            
            if user.balance < bet_amount:
                socketio.emit('bet_response', {'success': False, 'message': 'Недостаточно средств.'}, room=sid)
                return

            # Deduct bet amount and create transaction
            user.balance -= bet_amount
            user.total_expense += bet_amount  # Update total expense
            db.session.add(user)
            transaction = Transaction(
                user_id=user.id,
                type='bet',
                amount=bet_amount,
                game_type='mines',
                result=f"Ставка {bet_amount}₽ в игре Сапер ({mines_count} мин)"
            )
            db.session.add(transaction)
            db.session.commit()
            print(f'[Mines] SID {sid} (User {user_id}): Bet of {bet_amount}₽ deducted. New balance: {user.balance}₽')
            socketio.emit('balance_update', {'balance': user.balance}, room=sid)

        # Update mines count
        mines_game.mines_count = mines_count
        print(f'[Mines] Updated mines count for game SID: {sid} to {mines_game.mines_count}')
        
        # Place bet in game logic
        print(f'[Mines] Calling mines_game.place_bet for SID: {sid} with amount: {bet_amount}')
        bet_successful = mines_game.place_bet(bet_amount)
        print(f'[Mines] mines_game.place_bet returned: {bet_successful} for SID: {sid}')

        if bet_successful:
            socketio.emit('bet_response', {
                'success': True,
                'message': 'Ставка принята'
            }, room=sid)
            print(f'[Mines] Emitted bet_response (success) to SID: {sid}')
        else:
            socketio.emit('bet_response', {
                'success': False,
                'message': 'Ошибка при размещении ставки'
            }, room=sid)
            print(f'[Mines] Emitted bet_response (error) to SID: {sid}')
    except Exception as e:
        print(f'[Mines] Error in handle_place_bet for SID {sid}: {str(e)}')
        socketio.emit('bet_response', {
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, room=sid)

@socketio.on('reveal_position')
def handle_reveal_position(data):
    sid = request.sid
    mines_game = get_user_mines_game(sid)
    
    if not mines_game:
        socketio.emit('reveal_response', {
            'success': False,
            'message': 'Игровая сессия не найдена'
        }, room=sid)
        return
    
    try:
        position = int(data['position'])
        result = mines_game.reveal_position(position)
        
        if result['success']:
            if result['win_amount'] > 0:
                # Update user's balance and total income
                user = db.session.get(User, session['user_id'])
                user.balance += result['win_amount']
                user.total_income += result['win_amount']  # Update total income
                db.session.commit()
                
                socketio.emit('balance_update', {
                    'balance': user.balance
                }, room=sid)
            
            socketio.emit('reveal_response', {
                'success': True,
                'position': position,
                'is_mine': result['is_mine'],
                'multiplier': result['multiplier'],
                'win_amount': result['win_amount']
            }, room=sid)
        else:
            socketio.emit('reveal_response', {
                'success': False,
                'message': result['message']
            }, room=sid)
    except Exception as e:
        print(f'Error in handle_reveal_position: {str(e)}')
        socketio.emit('reveal_response', {
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, room=sid)

@socketio.on('cashout')
def handle_cashout(data):
    sid = request.sid
    mines_game = get_user_mines_game(sid)
    
    if not mines_game:
        socketio.emit('cashout_response', {
            'success': False,
            'message': 'Игровая сессия не найдена'
        }, room=sid)
        return
    
    try:
        result = mines_game.cashout()
        
        if result['success']:
            # Update user's balance and total income
            user = db.session.get(User, session['user_id'])
            user.balance += result['win_amount']
            user.total_income += result['win_amount']  # Update total income
            db.session.commit()
            
            socketio.emit('balance_update', {
                'balance': user.balance
            }, room=sid)
            
            socketio.emit('cashout_response', {
                'success': True,
                'win_amount': result['win_amount'],
                'multiplier': result['multiplier']
            }, room=sid)
        else:
            socketio.emit('cashout_response', {
                'success': False,
                'message': result['message']
            }, room=sid)
    except Exception as e:
        print(f'Error in handle_cashout: {str(e)}')
        socketio.emit('cashout_response', {
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, room=sid)

if __name__ == '__main__':
    socketio.run(app, debug=True) 