from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
import os
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

def card_power(card, options=None):
    """Calculate card power with wild options."""
    if options is None:
        options = {}
    # card is a dict: {'rank': 'K', 'suit': '♠'}
    rank_str = card.get('rank', '')
    suit = card.get('suit', '')

    rank_values = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15}
    power = rank_values.get(rank_str, 0)

    # Black 3s get power 16 when enabled
    if options.get('wild_black3') and rank_str == '3' and suit in ('♠', '♣'):
        return 16
    # JD gets power 17 when enabled
    if options.get('wild_jd') and rank_str == 'J' and suit == '♦':
        return 17

    return power

@app.route('/')
def index():
    try:
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'president.html')
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return '<h1>president.html not found</h1>'
    except Exception as e:
        return f'<h1>Error loading page: {str(e)}</h1>'

@socketio.on('connect')
def on_connect():
    print('[CONNECT]', request.sid)

@socketio.on('create')
def on_create(data):
    try:
        game_id = secrets.token_hex(4)
        options = data.get('options', {})
        games[game_id] = {
            'id': game_id,
            'players': {},
            'options': options
        }
        join_room(game_id)
        session['game_id'] = game_id
        emit('game_created', {'game_id': game_id})
        print(f'[CREATE] Game {game_id} created with options: {options}')
    except Exception as e:
        print(f'[CREATE ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('start_game')
def on_start_game():
    try:
        game_id = session.get('game_id')
        if game_id and game_id in games:
            emit('game_started', {'game_id': game_id}, room=game_id)
            print(f'[START] Game {game_id} started')
    except Exception as e:
        print(f'[START ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('play_card')
def on_play_card(data):
    """Test endpoint to verify card_power"""
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        card = data.get('card')
        options = games[game_id].get('options', {})
        power = card_power(card, options)

        print(f'[PLAY] Card {card} in game {game_id} with options {options} = power {power}')
        emit('card_power', {'card': card, 'power': power})
    except Exception as e:
        print(f'[PLAY ERROR] {e}')
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    print('Starting on 0.0.0.0:8080')
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
