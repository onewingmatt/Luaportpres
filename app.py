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
    rank_str = card.get('rank', '')
    suit = card.get('suit', '')

    rank_values = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15}
    power = rank_values.get(rank_str, 0)

    if options.get('wild_black3') and rank_str == '3' and suit in ('♠', '♣'):
        return 16
    if options.get('wild_jd') and rank_str == 'J' and suit == '♦':
        return 17

    return power

def compare_cards(played_card, table_card, options=None):
    """Compare two cards. Returns True if played_card beats table_card."""
    played_power = card_power(played_card, options)
    table_power = card_power(table_card, options)
    return played_power > table_power

def sort_hand(hand, options=None):
    """Sort hand by card power."""
    if options is None:
        options = {}
    return sorted(hand, key=lambda c: card_power(c, options))

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
            'options': options,
            'players': {}
        }
        join_room(game_id)
        session['game_id'] = game_id
        emit('game_created', {'game_id': game_id, 'options': options})
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

@socketio.on('compare_play')
def on_compare_play(data):
    """Validate a card play against the table card."""
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        played = data.get('card')
        table = data.get('table_card')
        options = games[game_id].get('options', {})

        if table is None:
            is_valid = True
            reason = 'First card'
        else:
            is_valid = compare_cards(played, table, options)
            reason = 'Valid' if is_valid else 'Too low'

        emit('play_validated', {
            'is_valid': is_valid,
            'reason': reason,
            'card_power': card_power(played, options)
        })
    except Exception as e:
        print(f'[PLAY ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('sort_hand_request')
def on_sort_hand_request(data):
    """Sort a hand using game options."""
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        hand = data.get('hand', [])
        options = games[game_id].get('options', {})
        sorted_hand = sort_hand(hand, options)

        emit('hand_sorted', {'hand': sorted_hand})
    except Exception as e:
        print(f'[SORT ERROR] {e}')
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    print('Starting on 0.0.0.0:8080')
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
