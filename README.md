# Online Casino Platform

Welcome to the Online Casino Platform project! This is a web-based application built with Flask and Socket.IO, offering a variety of engaging casino games.

## Features:

*   **User Accounts:** Secure user registration, login, and profile management.
*   **Balance Management:** Users can view and manage their balance, including deposits via advertising.
*   **Diverse Games:** Play popular casino games like Crash and Mines, Slots and Roulette.
*   **Game Logic:** Robust server-side game logic ensuring fair play.
*   **Real-time Updates:** Seamless gameplay experience with real-time updates using Socket.IO.
*   **Transaction History:** Detailed history of all user transactions (bets, wins, deposits).
*   **Admin Panel:** Administrative interface for managing users and game configurations.

This platform is designed to be a foundation for a feature-rich online casino experience.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the development server:
```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:5000`

## Project Structure

```
casino/
├── app.py              # Main application file, Flask routes, Socket.IO handlers
├── models.py           # Database models (User, Transaction, GameConfig)
├── requirements.txt    # Project dependencies
├── config/
│   └── slots_config.py # Example game configuration
├── games/
│   ├── __init__.py     # Initializes game modules
│   ├── base.py         # Base class for games
│   ├── crash.py        # Crash game logic
│   ├── mines.py        # Mines game logic
│   ├── roulette.py     # Roulette game logic
│   └── slots.py        # Slots game logic
├── static/
│   ├── ad/             # Advertisement video files
│   ├── css/            # CSS files
│   └── js/             # JavaScript files
└── templates/
    ├── base.html       # Base template
    ├── index.html      # Main page with game links
    ├── login.html        # Login page
    ├── register.html     # Registration page
    ├── profile.html      # User profile page
    ├── admin/          # Admin panel templates
    │   ├── index.html
    │   └── users.html
    └── games/          # Game templates
        ├── crash.html
        ├── mines.html
        ├── roulette.html
        └── slots.html
```

## Games

### Crash
- A multiplier increases until it crashes.
- Players bet and try to cash out before the crash.

### Mines
- Players choose a bet amount and the number of mines.
- Click cells to reveal multipliers, avoiding mines.
- Players can cash out at any time for accumulated winnings.

### Slots
- 3x3 grid with various symbols.
- Winning combinations on horizontal, vertical, and diagonal lines.
- Configurable payout multipliers.

### Roulette
- Classic roulette with bets on numbers, colors, even/odd.
- Configurable payouts.

## Technologies Used

- Python 3.x
- Flask
- Flask-SQLAlchemy
- Flask-SocketIO
- Socket.IO (Client-side JavaScript library)
- Bootstrap 5
- JavaScript
- HTML5/CSS3
