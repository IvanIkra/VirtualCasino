# Online Casino Platform

Welcome to the Online Casino Platform project! This is a web-based application built with Flask and Socket.IO, offering a variety of engaging casino games.

## Features:

*   **User Accounts:** Secure user registration, login, and profile management.
*   **Balance Management:** Users can view and manage their balance, including deposits via advertising.
*   **Diverse Games:** Play popular casino games like Crash and Mines.
*   **Game Logic:** Robust server-side game logic ensuring fair play.
*   **Real-time Updates:** Seamless gameplay experience with real-time updates using Socket.IO.
*   **Transaction History:** Detailed history of all user transactions (bets, wins, deposits).
*   **Admin Panel:** Administrative interface for managing users and potentially game configurations.

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
├── app.py              # Main application file
├── static/
│   └── css/
│       └── style.css   # Styles
└── templates/
    ├── base.html       # Base template
    ├── index.html      # Main page
    └── login.html      # Login page
```

## Games

### Slots
- 3x3 grid with 6 different symbols
- Winning combinations on horizontal, vertical, and diagonal lines
- Payout multipliers from x2 to x20

### Roulette
- Bet on numbers (x35)
- Bet on colors (x2)
- Bet on even/odd (x2)
- Realistic number colors (red/black/green)

## Technologies Used

- Python 3.x
- Flask
- Bootstrap 5
- JavaScript
- HTML5/CSS3 # VirtualCasino
# VirtualCasino
