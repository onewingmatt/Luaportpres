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

def get_meld_type(cards):
    """Determine meld type: SINGLE, PAIR, TRIPLE, QUAD."""
    if len(cards) == 1:
        return 'SINGLE'
    if len(cards) == 2:
        if cards[0]['rank'] == cards[1]['rank']:
            return 'PAIR'
    if len(cards) == 3:
        if cards[0]['rank'] == cards[1]['rank'] == cards[2]['rank']:
            return 'TRIPLE'
    if len(cards) == 4:
        if cards[0]['rank'] == cards[1]['rank'] == cards[2]['rank'] == cards[3]['rank']:
            return 'QUAD'
    return None

def compare_melds(played_meld, table_meld, options=None):
    """Compare melds. Returns (is_valid, reason)."""
    if options is None:
        options = {}

    p_type = get_meld_type(played_meld)
    t_type = get_meld_type(table_meld)

    if not p_type or not t_type:
        return False, 'Invalid meld'

    if p_type != t_type:
        return False, f'Must play {t_type} (not {p_type})'

    # Get power of played and table melds
    p_power = max(card_power(c, options) for c in played_meld)
    t_power = max(card_power(c, options) for c in table_meld)

    if p_power > t_power:
        return True, f'Valid {p_type}'
    else:
        return False, f'{p_type} too low'

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
                    'is_cpu': False,
                    'player_id': request.sid
                }
            },
            'deck': [],
            'state': 'waiting',
            'current_player_idx': 0,
            'table_meld': [],
            'play_history': []
        }

        # Add CPU players
        for i in range(num_cpus):
            cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
            games[game_id]['players'][cpu_id] = {
                'name': f'CPU-{i+1}',
                'hand': [],
                'is_cpu': True,
                'player_id': cpu_id
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
        game['current_player_idx'] = 0
        game['table_meld'] = []

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

@socketio.on('play_meld')
def on_play_meld(data):
    """Player plays a meld (1+ cards)."""
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]
        cards = data.get('cards', [])

        if not cards or len(cards) == 0:
            emit('error', {'message': 'Select at least 1 card'})
            return

        # Validate cards
        player = game['players'].get(request.sid)
        if not player:
            emit('error', {'message': 'Not a player in this game'})
            return

        # Check all cards are in hand
        for card in cards:
            found = False
            for hand_card in player['hand']:
                if hand_card['rank'] == card['rank'] and hand_card['suit'] == card['suit']:
                    found = True
                    break
            if not found:
                emit('error', {'message': f'Card {card["rank"]}{card["suit"]} not in your hand'})
                return

        # Validate meld type
        meld_type = get_meld_type(cards)
        if not meld_type:
            emit('error', {'message': 'Invalid meld (not all same rank for 2+ cards)'})
            return

        # Validate against table
        if game['table_meld']:
            is_valid, reason = compare_melds(cards, game['table_meld'], game['options'])
            if not is_valid:
                emit('error', {'message': reason})
                return

        # Remove cards from hand
        for card in cards:
            for i, hand_card in enumerate(player['hand']):
                if hand_card['rank'] == card['rank'] and hand_card['suit'] == card['suit']:
                    player['hand'].pop(i)
                    break

        # Update table
        game['table_meld'] = cards

        # Broadcast play
        socketio.emit('meld_played', {
            'player': player['name'],
            'meld': cards,
            'meld_type': meld_type,
            'my_hand_size': len(player['hand'])
        }, room=game_id)

        game['play_history'].append({
            'player': player['name'],
            'meld': cards
        })

        print(f'[PLAY] {player["name"]} played {meld_type}: {[c["rank"]+c["suit"] for c in cards]}')
    except Exception as e:
        print(f'[PLAY ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('pass_turn')
def on_pass_turn():
    """Player passes."""
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]
        player = game['players'].get(request.sid)

        socketio.emit('player_passed', {
            'player': player['name']
        }, room=game_id)

        print(f'[PASS] {player["name"]} passed')
    except Exception as e:
        print(f'[PASS ERROR] {e}')
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    print('Starting on 0.0.0.0:8080')
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
