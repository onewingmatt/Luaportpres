from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
import os
import secrets
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

# Card definitions
RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
SUITS = ['♠', '♥', '♦', '♣']

def create_deck():
    """Create a shuffled deck of cards."""
    deck = []
    for rank in RANKS:
        for suit in SUITS:
            deck.append({'rank': rank, 'suit': suit})
    random.shuffle(deck)
    return deck

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
        player_name = data.get('name', 'Player')
        num_cpus = data.get('cpus', 2)

        games[game_id] = {
            'id': game_id,
            'options': options,
            'players': {
                request.sid: {
                    'name': player_name,
                    'hand': [],
                    'is_cpu': False
                }
            },
            'deck': [],
            'state': 'waiting'  # waiting, dealing, playing
        }

        # Add CPU players
        for i in range(num_cpus):
            cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
            games[game_id]['players'][cpu_id] = {
                'name': f'CPU-{i+1}',
                'hand': [],
                'is_cpu': True
            }

        join_room(game_id)
        session['game_id'] = game_id
        emit('game_created', {'game_id': game_id, 'options': options})
        print(f'[CREATE] Game {game_id} with {len(games[game_id]["players"])} players')
    except Exception as e:
        print(f'[CREATE ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('deal_cards')
def on_deal_cards():
    """Deal cards to all players."""
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]

        # Create and shuffle deck
        deck = create_deck()
        game['deck'] = deck

        # Deal cards evenly (13 each in 4-player game)
        cards_per_player = 52 // len(game['players'])
        player_ids = list(game['players'].keys())

        for idx, player_id in enumerate(player_ids):
            start = idx * cards_per_player
            end = start + cards_per_player
            player_cards = deck[start:end]
            # Sort hand with options
            game['players'][player_id]['hand'] = sort_hand(player_cards, game['options'])

        game['state'] = 'playing'

        # Send dealt cards to human player
        my_hand = game['players'][request.sid]['hand']
        emit('cards_dealt', {
            'hand': my_hand,
            'hand_size': len(my_hand),
            'player_count': len(game['players'])
        })

        # Broadcast game started
        socketio.emit('game_started', {
            'game_id': game_id,
            'state': 'playing'
        }, room=game_id)

        print(f'[DEAL] Dealt {cards_per_player} cards to {len(player_ids)} players')
    except Exception as e:
        print(f'[DEAL ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('start_game')
def on_start_game():
    """Start dealing - triggers the deal_cards flow."""
    try:
        game_id = session.get('game_id')
        if game_id and game_id in games:
            game = games[game_id]
            game['state'] = 'dealing'
            socketio.emit('ready_to_deal', {'game_id': game_id}, room=game_id)
            print(f'[START] Game {game_id} ready to deal')
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
