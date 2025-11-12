from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
import os
import secrets
import random
import time
import threading

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

    p_power = max(card_power(c, options) for c in played_meld)
    t_power = max(card_power(c, options) for c in table_meld)

    if p_power > t_power:
        return True, f'Valid {p_type}'
    else:
        return False, f'{p_type} too low'

def sort_hand(hand, options=None):
    """Sort hand by card power."""
    if options is None:
        options = {}
    return sorted(hand, key=lambda c: card_power(c, options))

def cpu_play_meld(hand, table_meld, options=None):
    """AI: find a valid meld to play, or return None."""
    if options is None:
        options = {}

    if not table_meld:
        if hand:
            return [sorted(hand, key=lambda c: card_power(c, options), reverse=True)[0]]

    table_type = get_meld_type(table_meld)

    by_rank = {}
    for card in hand:
        rank = card['rank']
        if rank not in by_rank:
            by_rank[rank] = []
        by_rank[rank].append(card)

    candidates = []
    for rank, cards in by_rank.items():
        if len(cards) >= len(table_meld):
            meld = cards[:len(table_meld)]
            is_valid, _ = compare_melds(meld, table_meld, options)
            if is_valid:
                candidates.append(meld)

    if candidates:
        return min(candidates, key=lambda m: card_power(m[0], options))

    return None

def check_game_end(game_id):
    """Check if game ended (only 1 player with cards left)."""
    if game_id not in games:
        return False

    game = games[game_id]
    players_with_cards = [p for p in game['players'].values() if len(p['hand']) > 0]

    if len(players_with_cards) == 1:
        return True
    return False

def get_player_status(game_id):
    """Get all players' status (name, card count, is_active)."""
    if game_id not in games:
        return []

    game = games[game_id]
    current_player_id = game['player_order'][game['current_player_idx']]

    status = []
    for player_id in game['player_order']:
        player = game['players'][player_id]
        status.append({
            'name': player['name'],
            'card_count': len(player['hand']),
            'is_active': player_id == current_player_id,
            'is_cpu': player['is_cpu']
        })
    return status

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
        return f'<h1>Error: {str(e)}</h1>'

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
            'player_order': [request.sid],
            'current_player_idx': 0,
            'table_meld': [],
            'last_player_id': None,
            'passes': set(),
            'play_history': []
        }

        for i in range(num_cpus):
            cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
            games[game_id]['players'][cpu_id] = {
                'name': f'CPU-{i+1}',
                'hand': [],
                'is_cpu': True,
                'player_id': cpu_id
            }
            games[game_id]['player_order'].append(cpu_id)

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

        deck = create_deck()
        game['deck'] = deck

        cards_per_player = 52 // len(game['players'])
        player_ids = game['player_order']

        for idx, player_id in enumerate(player_ids):
            start = idx * cards_per_player
            end = start + cards_per_player
            player_cards = deck[start:end]
            game['players'][player_id]['hand'] = sort_hand(player_cards, game['options'])

        game['state'] = 'playing'
        game['current_player_idx'] = 0
        game['table_meld'] = []
        game['passes'] = set()
        game['last_player_id'] = None

        my_hand = game['players'][request.sid]['hand']
        emit('cards_dealt', {
            'hand': my_hand,
            'hand_size': len(my_hand),
            'player_count': len(game['players']),
            'players_status': get_player_status(game_id)
        })

        socketio.emit('game_started', {
            'game_id': game_id,
            'state': 'playing',
            'players_status': get_player_status(game_id)
        }, room=game_id)

        print(f'[DEAL] Dealt {cards_per_player} cards')
    except Exception as e:
        print(f'[DEAL ERROR] {e}')
        emit('error', {'message': str(e)})

def check_hand_empty(game_id):
    """Check if anyone has empty hand and skip them."""
    if game_id not in games:
        return

    game = games[game_id]
    current_player_id = game['player_order'][game['current_player_idx']]

    turns = 0
    while len(game['players'][current_player_id]['hand']) == 0 and turns < len(game['player_order']):
        game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])
        current_player_id = game['player_order'][game['current_player_idx']]
        turns += 1

def check_round_end(game_id):
    """Check if round ended (all but last player passed)."""
    if game_id not in games:
        return False

    game = games[game_id]
    total_players = len(game['player_order'])
    passes_count = len(game['passes'])

    if passes_count == total_players - 1 and game['last_player_id'] is not None:
        print(f'[ROUND] Round ended. Last player was: {game["players"][game["last_player_id"]]["name"]}')

        game['table_meld'] = []
        game['passes'] = set()

        leader_idx = game['player_order'].index(game['last_player_id'])
        game['current_player_idx'] = leader_idx

        with app.app_context():
            socketio.emit('table_cleared', {
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[ROUND] Table cleared. {game["players"][game["last_player_id"]]["name"]} leads next meld')
        return True
    return False

@socketio.on('start_game')
def on_start_game():
    """Start dealing."""
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
    """Player plays a meld."""
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

        player = game['players'].get(request.sid)
        if not player:
            emit('error', {'message': 'Not a player'})
            return

        for card in cards:
            found = any(h['rank'] == card['rank'] and h['suit'] == card['suit'] for h in player['hand'])
            if not found:
                emit('error', {'message': f'Card not in hand'})
                return

        meld_type = get_meld_type(cards)
        if not meld_type:
            emit('error', {'message': 'Invalid meld'})
            return

        if game['table_meld']:
            is_valid, reason = compare_melds(cards, game['table_meld'], game['options'])
            if not is_valid:
                emit('error', {'message': reason})
                return

        for card in cards:
            player['hand'] = [c for c in player['hand'] if not (c['rank'] == card['rank'] and c['suit'] == card['suit'])]

        game['table_meld'] = cards
        game['last_player_id'] = request.sid
        game['passes'].clear()

        socketio.emit('meld_played', {
            'player': player['name'],
            'meld': cards,
            'meld_type': meld_type,
            'my_hand': player['hand'],
            'players_status': get_player_status(game_id)
        }, room=game_id)

        print(f'[PLAY] {player["name"]} played {meld_type}')

        if check_game_end(game_id):
            with app.app_context():
                socketio.emit('game_ended', {
                    'winner': player['name']
                }, room=game_id)
            print(f'[END] Game ended. {player["name"]} is ASSHOLE!')
            return

        game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])
        check_hand_empty(game_id)

        threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()

    except Exception as e:
        print(f'[PLAY ERROR] {e}')
        emit('error', {'message': str(e)})

def cpu_play_turn(game_id):
    """CPU plays turn."""
    if game_id not in games:
        return

    game = games[game_id]
    check_hand_empty(game_id)

    current_player_id = game['player_order'][game['current_player_idx']]
    player = game['players'][current_player_id]

    if not player['is_cpu'] or game['state'] != 'playing' or len(player['hand']) == 0:
        return

    meld = cpu_play_meld(player['hand'], game['table_meld'], game['options'])

    if meld:
        for card in meld:
            player['hand'] = [c for c in player['hand'] if not (c['rank'] == card['rank'] and c['suit'] == card['suit'])]

        game['table_meld'] = meld
        game['last_player_id'] = current_player_id
        game['passes'].clear()

        with app.app_context():
            socketio.emit('meld_played', {
                'player': player['name'],
                'meld': meld,
                'meld_type': get_meld_type(meld),
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[CPU] {player["name"]} played {get_meld_type(meld)}')

        if check_game_end(game_id):
            with app.app_context():
                socketio.emit('game_ended', {
                    'winner': player['name']
                }, room=game_id)
            print(f'[END] Game ended. {player["name"]} is ASSHOLE!')
            return

        game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])
        check_hand_empty(game_id)

        next_player_id = game['player_order'][game['current_player_idx']]
        if game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
            threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()
    else:
        game['passes'].add(current_player_id)

        with app.app_context():
            socketio.emit('player_passed', {
                'player': player['name'],
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[CPU] {player["name"]} passed')

        round_ended = check_round_end(game_id)

        if not round_ended:
            game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])
            check_hand_empty(game_id)

            next_player_id = game['player_order'][game['current_player_idx']]
            if game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()
        else:
            next_player_id = game['player_order'][game['current_player_idx']]
            if game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(1.5, lambda: cpu_play_turn(game_id)).start()

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

        game['passes'].add(request.sid)

        socketio.emit('player_passed', {
            'player': player['name'],
            'players_status': get_player_status(game_id)
        }, room=game_id)

        print(f'[PASS] {player["name"]} passed')

        round_ended = check_round_end(game_id)

        if not round_ended:
            game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])
            check_hand_empty(game_id)

            next_player_id = game['player_order'][game['current_player_idx']]
            if game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()
        else:
            next_player_id = game['player_order'][game['current_player_idx']]
            if game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(1.5, lambda: cpu_play_turn(game_id)).start()

    except Exception as e:
        print(f'[PASS ERROR] {e}')
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    print('Starting on 0.0.0.0:8080')
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
