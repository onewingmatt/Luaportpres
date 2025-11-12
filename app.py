from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
import os
import secrets
import random
import time
import threading
from datetime import datetime
import json

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

def deep_copy_cards(cards):
    """Deep copy a list of card dicts."""
    return json.loads(json.dumps(cards))

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

def validate_meld(cards, options=None):
    """Validate meld is valid type and passes 3s rule."""
    if options is None:
        options = {}

    if not get_meld_type(cards):
        return False

    if options.get('wild_black3'):
        ranks = [c['rank'] for c in cards]
        suits = [c['suit'] for c in cards]

        if '3' in ranks:
            has_red_3 = any(c['rank'] == '3' and c['suit'] in ('♥', '♦') for c in cards)
            has_black_3 = any(c['rank'] == '3' and c['suit'] in ('♠', '♣') for c in cards)

            if has_red_3 and has_black_3:
                return False

    return True

def compare_melds(played_meld, table_meld, options=None):
    """Compare melds. Returns (is_valid, reason)."""
    if options is None:
        options = {}

    if not validate_meld(played_meld, options):
        return False, 'Invalid meld'
    if not validate_meld(table_meld, options):
        return False, 'Invalid meld'

    p_type = get_meld_type(played_meld)
    t_type = get_meld_type(table_meld)

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
            if validate_meld(meld, options):
                is_valid, _ = compare_melds(meld, table_meld, options)
                if is_valid:
                    candidates.append(meld)

    if candidates:
        return min(candidates, key=lambda m: card_power(m[0], options))

    return None

def assign_roles(game_id):
    """Assign roles based on elimination order."""
    if game_id not in games:
        return

    game = games[game_id]
    num_players = len(game['players'])

    roles = {}

    for player_id in game['players']:
        roles[player_id] = 'Citizen'

    if len(game['elimination_order']) >= 1:
        roles[game['elimination_order'][0]] = 'President'

    if num_players >= 4 and len(game['elimination_order']) >= 2:
        roles[game['elimination_order'][1]] = 'Vice President'

    if num_players >= 4 and len(game['elimination_order']) >= 3:
        roles[game['elimination_order'][num_players - 2]] = 'Vice Asshole'

    if len(game['elimination_order']) >= num_players:
        roles[game['elimination_order'][-1]] = 'Asshole'

    return roles

def get_active_players(game_id):
    """Get list of players with cards (still in game)."""
    if game_id not in games:
        return []

    game = games[game_id]
    return [pid for pid in game['player_order'] if pid in game['players'] and len(game['players'][pid]['hand']) > 0]

def get_current_player_id(game_id):
    """Get the current player ID safely."""
    if game_id not in games:
        return None

    game = games[game_id]

    if game['current_player_idx'] >= len(game['player_order']):
        game['current_player_idx'] = 0

    if game['current_player_idx'] < 0:
        game['current_player_idx'] = 0

    if len(game['player_order']) == 0:
        return None

    return game['player_order'][game['current_player_idx']]

def get_player_status(game_id):
    """Get all players' status (name, card count, is_active)."""
    if game_id not in games:
        return []

    game = games[game_id]
    current_player_id = get_current_player_id(game_id)

    status = []
    for player_id in game['player_order']:
        if player_id not in game['players']:
            continue
        player = game['players'][player_id]
        status.append({
            'name': player['name'],
            'card_count': len(player['hand']),
            'is_active': player_id == current_player_id,
            'is_cpu': player['is_cpu']
        })
    return status

def format_card(card):
    """Format card for display."""
    return f"{card['rank']}{card['suit']}"

def format_cards(cards):
    """Format list of cards for display."""
    return ' '.join(format_card(c) for c in cards)

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
    emit('connected', {'data': 'connected'})

@socketio.on('join_game')
def on_join_game(data):
    """Player joins existing game via share URL."""
    try:
        game_id = data.get('game_id')
        player_name = data.get('player_name', '').strip()

        if not player_name:
            emit('error', {'message': 'Please enter a name'})
            return

        if not game_id or game_id not in games:
            emit('error', {'message': 'Game not found'})
            return

        game = games[game_id]

        if game['state'] not in ['waiting', 'playing']:
            emit('error', {'message': 'Game not available to join'})
            return

        cpu_to_replace = None
        for pid, player in game['players'].items():
            if player['is_cpu']:
                cpu_to_replace = pid
                break

        if not cpu_to_replace:
            emit('error', {'message': 'No CPU slots available'})
            return

        # Deep copy the CPU's hand
        cpu_hand = deep_copy_cards(game['players'][cpu_to_replace]['hand'])

        # Create new player
        game['players'][request.sid] = {
            'name': player_name,
            'hand': cpu_hand,
            'is_cpu': False,
            'player_id': request.sid,
            'role': game['players'][cpu_to_replace].get('role', 'Citizen')
        }

        print(f'[JOIN] {player_name} replaces {game["players"][cpu_to_replace]["name"]} (hand: {format_cards(cpu_hand)})')

        # Find position of CPU in player_order
        cpu_position = game['player_order'].index(cpu_to_replace)

        # Remove old CPU from passes and elimination order if present
        game['passes'].discard(cpu_to_replace)
        if cpu_to_replace in game['elimination_order']:
            game['elimination_order'].remove(cpu_to_replace)

        # Replace CPU with new player in player_order (CRITICAL: keep same position)
        game['player_order'][cpu_position] = request.sid

        # If this is the current player, the new player is now active
        if game['current_player_idx'] == cpu_position:
            print(f'[JOIN] New player {player_name} is now the active player')

        # Remove old CPU from players dict
        del game['players'][cpu_to_replace]

        join_room(game_id)
        session['game_id'] = game_id
        session['player_id'] = request.sid

        # Send full game state
        emit('game_joined', {
            'game_id': game_id,
            'player_name': player_name,
            'hand': cpu_hand,
            'players_status': get_player_status(game_id),
            'game_state': game['state'],
            'table_meld': game['table_meld'],
            'meld_type': get_meld_type(game['table_meld']) if game['table_meld'] else None
        })

        # Notify all players
        with app.app_context():
            socketio.emit('player_joined', {
                'player_name': player_name,
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[JOIN] {player_name} joined game {game_id} (state: {game["state"]})')
        print(f'[JOIN] Player order: {[game["players"][p]["name"] for p in game["player_order"] if p in game["players"]]}')
        print(f'[JOIN] Current player idx: {game["current_player_idx"]}, Current player: {get_current_player_id(game_id)}')
    except Exception as e:
        print(f'[JOIN ERROR] {e}')
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

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
                    'player_id': request.sid,
                    'role': 'Citizen'
                }
            },
            'deck': [],
            'state': 'waiting',
            'player_order': [request.sid],
            'current_player_idx': 0,
            'table_meld': [],
            'last_player_id': None,
            'passes': set(),
            'play_history': [],
            'elimination_order': [],
            'swaps_pending': {}
        }

        for i in range(num_cpus):
            cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
            games[game_id]['players'][cpu_id] = {
                'name': f'CPU-{i+1}',
                'hand': [],
                'is_cpu': True,
                'player_id': cpu_id,
                'role': 'Citizen'
            }
            games[game_id]['player_order'].append(cpu_id)

        join_room(game_id)
        session['game_id'] = game_id
        session['player_id'] = request.sid

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
            if player_id not in game['players']:
                continue
            start = idx * cards_per_player
            end = start + cards_per_player
            player_cards = deck[start:end]
            game['players'][player_id]['hand'] = sort_hand(player_cards, game['options'])

        game['state'] = 'playing'
        game['current_player_idx'] = 0
        game['table_meld'] = []
        game['passes'] = set()
        game['last_player_id'] = None
        game['elimination_order'] = []

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

        print(f'[DEAL] Dealt {cards_per_player} cards to {len(game["players"])} players')
    except Exception as e:
        print(f'[DEAL ERROR] {e}')
        emit('error', {'message': str(e)})

def skip_to_next_active_player(game_id):
    """Skip to next player with cards."""
    if game_id not in games:
        return

    game = games[game_id]
    active_players = get_active_players(game_id)

    if not active_players:
        print(f'[SKIP] No active players!')
        return

    # Increment to next player
    game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])

    current_player_id = get_current_player_id(game_id)
    turns = 0

    # Skip players not in active list
    while current_player_id not in active_players and turns < len(game['player_order']):
        game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])
        current_player_id = get_current_player_id(game_id)
        turns += 1

    if current_player_id and current_player_id in game['players']:
        print(f'[SKIP] Moved to player {game["players"][current_player_id]["name"]} (idx: {game["current_player_idx"]})')

def check_round_end(game_id):
    """Check if round ended (all active players passed)."""
    if game_id not in games:
        return False

    game = games[game_id]
    active_players = get_active_players(game_id)

    if not active_players:
        return False

    # Remove invalid passes (players who don't exist anymore)
    game['passes'] = {p for p in game['passes'] if p in game['players']}

    active_passes = len(game['passes'].intersection(set(active_players)))

    if active_passes == len(active_players) - 1 and game['last_player_id'] is not None and game['last_player_id'] in game['players']:
        print(f'[ROUND] Round ended. Last player was: {game["players"][game["last_player_id"]]["name"]}')

        game['table_meld'] = []
        game['passes'] = set()

        if len(game['players'][game['last_player_id']]['hand']) > 0:
            leader_idx = game['player_order'].index(game['last_player_id'])
            game['current_player_idx'] = leader_idx
        else:
            last_idx = game['player_order'].index(game['last_player_id'])
            game['current_player_idx'] = (last_idx + 1) % len(game['player_order'])
            skip_to_next_active_player(game_id)

        with app.app_context():
            socketio.emit('table_cleared', {
                'players_status': get_player_status(game_id)
            }, room=game_id)

        current_pid = get_current_player_id(game_id)
        if current_pid and current_pid in game['players']:
            print(f'[ROUND] Table cleared. {game["players"][current_pid]["name"]} leads next meld')
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

        # Validate cards are in hand (robust comparison)
        for card in cards:
            found = False
            for hand_card in player['hand']:
                if (hand_card.get('rank') == card.get('rank') and 
                    hand_card.get('suit') == card.get('suit')):
                    found = True
                    break
            if not found:
                print(f'[ERROR] {player["name"]} card validation failed: {card}')
                emit('error', {'message': f'Card not in hand: {card.get("rank")}{card.get("suit")}'})
                return

        meld_type = get_meld_type(cards)
        if not meld_type or not validate_meld(cards, game['options']):
            emit('error', {'message': 'Invalid meld'})
            return

        if game['table_meld']:
            is_valid, reason = compare_melds(cards, game['table_meld'], game['options'])
            if not is_valid:
                emit('error', {'message': reason})
                return

        # Remove cards from hand
        for card in cards:
            for i, hand_card in enumerate(player['hand']):
                if (hand_card.get('rank') == card.get('rank') and 
                    hand_card.get('suit') == card.get('suit')):
                    player['hand'].pop(i)
                    break

        game['table_meld'] = cards
        game['last_player_id'] = request.sid
        game['passes'].clear()

        cards_str = format_cards(cards)
        timestamp = datetime.now().strftime('%H:%M:%S')

        socketio.emit('meld_played', {
            'player': player['name'],
            'meld': cards,
            'meld_type': meld_type,
            'cards_str': cards_str,
            'timestamp': timestamp,
            'my_hand': player['hand'],
            'players_status': get_player_status(game_id)
        }, room=game_id)

        print(f'[PLAY] {player["name"]} played {meld_type}: {cards_str}')

        if len(player['hand']) == 0:
            game['elimination_order'].append(request.sid)
            print(f'[OUT] {player["name"]} is out! Order: {len(game["elimination_order"])}')

            if len(game['elimination_order']) == len(game['player_order']) - 1:
                deck = create_deck()
                cards_per_player = 52 // len(game['players'])
                for idx, player_id in enumerate(game['player_order']):
                    if player_id not in game['players']:
                        continue
                    start = idx * cards_per_player
                    end = start + cards_per_player
                    player_cards = deck[start:end]
                    game['players'][player_id]['hand'] = sort_hand(player_cards, game['options'])

                roles = assign_roles(game_id)
                for pid, role in roles.items():
                    if pid in game['players']:
                        game['players'][pid]['role'] = role

                role_data = {}
                for pid, player_obj in game['players'].items():
                    role_data[player_obj['name']] = {
                        'role': roles.get(pid, 'Citizen'),
                        'hand': player_obj['hand']
                    }

                with app.app_context():
                    socketio.emit('game_ended', {
                        'elimination_order': [game['players'][pid]['name'] for pid in game['elimination_order'] if pid in game['players']],
                        'roles': {game['players'][pid]['name']: role for pid, role in roles.items() if pid in game['players']},
                        'role_data': role_data
                    }, room=game_id)

                threading.Timer(2.0, lambda: cpu_auto_swap(game_id)).start()
                print(f'[END] Game ended!')
                return

        skip_to_next_active_player(game_id)

        threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()

    except Exception as e:
        print(f'[PLAY ERROR] {e}')
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

def cpu_play_turn(game_id):
    """CPU plays turn."""
    if game_id not in games:
        return

    game = games[game_id]
    skip_to_next_active_player(game_id)

    current_player_id = get_current_player_id(game_id)
    if not current_player_id or current_player_id not in game['players']:
        print(f'[CPU] Current player no longer exists')
        return

    player = game['players'][current_player_id]

    if not player['is_cpu'] or game['state'] != 'playing' or len(player['hand']) == 0:
        return

    meld = cpu_play_meld(player['hand'], game['table_meld'], game['options'])

    active_players = get_active_players(game_id)
    human_players = [p for p in active_players if p in game['players'] and not game['players'][p]['is_cpu']]
    delay = 0.3 if not human_players else 1.0

    if meld:
        for card in meld:
            for i, hand_card in enumerate(player['hand']):
                if (hand_card.get('rank') == card.get('rank') and 
                    hand_card.get('suit') == card.get('suit')):
                    player['hand'].pop(i)
                    break

        game['table_meld'] = meld
        game['last_player_id'] = current_player_id
        game['passes'].clear()

        cards_str = format_cards(meld)
        timestamp = datetime.now().strftime('%H:%M:%S')

        with app.app_context():
            socketio.emit('meld_played', {
                'player': player['name'],
                'meld': meld,
                'meld_type': get_meld_type(meld),
                'cards_str': cards_str,
                'timestamp': timestamp,
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[CPU] {player["name"]} played {get_meld_type(meld)}: {cards_str}')

        if len(player['hand']) == 0:
            game['elimination_order'].append(current_player_id)
            print(f'[OUT] {player["name"]} is out! Order: {len(game["elimination_order"])}')

            if len(game['elimination_order']) == len(game['player_order']) - 1:
                deck = create_deck()
                cards_per_player = 52 // len(game['players'])
                for idx, player_id in enumerate(game['player_order']):
                    if player_id not in game['players']:
                        continue
                    start = idx * cards_per_player
                    end = start + cards_per_player
                    player_cards = deck[start:end]
                    game['players'][player_id]['hand'] = sort_hand(player_cards, game['options'])

                roles = assign_roles(game_id)
                for pid, role in roles.items():
                    if pid in game['players']:
                        game['players'][pid]['role'] = role

                role_data = {}
                for pid, player_obj in game['players'].items():
                    role_data[player_obj['name']] = {
                        'role': roles.get(pid, 'Citizen'),
                        'hand': player_obj['hand']
                    }

                with app.app_context():
                    socketio.emit('game_ended', {
                        'elimination_order': [game['players'][pid]['name'] for pid in game['elimination_order'] if pid in game['players']],
                        'roles': {game['players'][pid]['name']: role for pid, role in roles.items() if pid in game['players']},
                        'role_data': role_data
                    }, room=game_id)

                threading.Timer(2.0, lambda: cpu_auto_swap(game_id)).start()
                print(f'[END] Game ended!')
                return

        skip_to_next_active_player(game_id)

        next_player_id = get_current_player_id(game_id)
        if next_player_id and next_player_id in game['players'] and game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
            threading.Timer(delay, lambda: cpu_play_turn(game_id)).start()
    else:
        game['passes'].add(current_player_id)

        timestamp = datetime.now().strftime('%H:%M:%S')

        with app.app_context():
            socketio.emit('player_passed', {
                'player': player['name'],
                'timestamp': timestamp,
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[CPU] {player["name"]} passed')

        round_ended = check_round_end(game_id)

        if not round_ended:
            skip_to_next_active_player(game_id)

            next_player_id = get_current_player_id(game_id)
            if next_player_id and next_player_id in game['players'] and game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(delay, lambda: cpu_play_turn(game_id)).start()
        else:
            next_player_id = get_current_player_id(game_id)
            if next_player_id and next_player_id in game['players'] and game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(delay, lambda: cpu_play_turn(game_id)).start()

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

        if not player:
            emit('error', {'message': 'Not a player'})
            return

        if len(player['hand']) == 0:
            emit('error', {'message': 'You have no cards left. You are out!'})
            return

        game['passes'].add(request.sid)

        timestamp = datetime.now().strftime('%H:%M:%S')

        socketio.emit('player_passed', {
            'player': player['name'],
            'timestamp': timestamp,
            'players_status': get_player_status(game_id)
        }, room=game_id)

        print(f'[PASS] {player["name"]} passed')

        round_ended = check_round_end(game_id)

        if not round_ended:
            skip_to_next_active_player(game_id)

            next_player_id = get_current_player_id(game_id)
            if next_player_id and next_player_id in game['players'] and game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()
        else:
            next_player_id = get_current_player_id(game_id)
            if next_player_id and next_player_id in game['players'] and game['players'][next_player_id]['is_cpu'] and len(game['players'][next_player_id]['hand']) > 0:
                threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()

    except Exception as e:
        print(f'[PASS ERROR] {e}')
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

def cpu_auto_swap(game_id):
    """CPU automatically selects and submits swap cards."""
    if game_id not in games:
        return

    game = games[game_id]

    for player_id, player in game['players'].items():
        if not player['is_cpu']:
            continue

        role = player.get('role')
        hand = player['hand']

        if role == 'Citizen':
            game['swaps_pending'][player_id] = []
        elif role == 'President':
            sorted_hand = sort_hand(hand, game['options'])
            swap_cards = sorted_hand[:2]
            game['swaps_pending'][player_id] = swap_cards
        elif role == 'Vice President':
            sorted_hand = sort_hand(hand, game['options'])
            swap_cards = sorted_hand[:1]
            game['swaps_pending'][player_id] = swap_cards
        elif role == 'Vice Asshole':
            sorted_hand = sort_hand(hand, game['options'])
            swap_cards = sorted_hand[-1:]
            game['swaps_pending'][player_id] = swap_cards
        elif role == 'Asshole':
            sorted_hand = sort_hand(hand, game['options'])
            swap_cards = sorted_hand[-2:]
            game['swaps_pending'][player_id] = swap_cards

    with app.app_context():
        socketio.emit('cpu_swaps_submitted', {
            'total_submitted': len(game['swaps_pending']),
            'total_needed': sum(1 for p in game['players'].values() if p['role'] in ['President', 'Vice President', 'Asshole', 'Vice Asshole'])
        }, room=game_id)

    swappable_players = [p for p in game['players'].values() if p['role'] in ['President', 'Vice President', 'Asshole', 'Vice Asshole']]
    if len(game['swaps_pending']) >= len(swappable_players):
        execute_swaps(game_id)

@socketio.on('submit_swap')
def on_submit_swap(data):
    """Player submits their card swap selection."""
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]
        player = game['players'].get(request.sid)
        role = player.get('role')
        swap_cards = data.get('cards', [])

        if not swap_cards and role != 'Citizen':
            emit('error', {'message': 'Please select cards to swap'})
            return

        game['swaps_pending'][request.sid] = swap_cards

        socketio.emit('swap_submitted', {
            'player': player['name'],
            'player_count': len(game['swaps_pending']),
            'total_needed': sum(1 for p in game['players'].values() if p['role'] in ['President', 'Vice President', 'Asshole', 'Vice Asshole'])
        }, room=game_id)

        swappable_players = [p for p in game['players'].values() if p['role'] in ['President', 'Vice President', 'Asshole', 'Vice Asshole']]
        if len(game['swaps_pending']) == len(swappable_players):
            execute_swaps(game_id)

    except Exception as e:
        print(f'[SWAP ERROR] {e}')
        emit('error', {'message': str(e)})

def execute_swaps(game_id):
    """Execute all pending card swaps."""
    if game_id not in games:
        return

    game = games[game_id]

    president_id = None
    vp_id = None
    va_id = None
    asshole_id = None

    for pid, player in game['players'].items():
        if player['role'] == 'President':
            president_id = pid
        elif player['role'] == 'Vice President':
            vp_id = pid
        elif player['role'] == 'Vice Asshole':
            va_id = pid
        elif player['role'] == 'Asshole':
            asshole_id = pid

    if president_id and asshole_id and president_id in game['players'] and asshole_id in game['players']:
        pres_swap = game['swaps_pending'].get(president_id, [])
        ass_swap = game['swaps_pending'].get(asshole_id, [])

        for card in pres_swap:
            for i, hand_card in enumerate(game['players'][president_id]['hand']):
                if (hand_card.get('rank') == card.get('rank') and 
                    hand_card.get('suit') == card.get('suit')):
                    game['players'][president_id]['hand'].pop(i)
                    break
            game['players'][asshole_id]['hand'].append(card)

        for card in ass_swap:
            for i, hand_card in enumerate(game['players'][asshole_id]['hand']):
                if (hand_card.get('rank') == card.get('rank') and 
                    hand_card.get('suit') == card.get('suit')):
                    game['players'][asshole_id]['hand'].pop(i)
                    break
            game['players'][president_id]['hand'].append(card)

    if vp_id and va_id and vp_id in game['players'] and va_id in game['players']:
        vp_swap = game['swaps_pending'].get(vp_id, [])
        va_swap = game['swaps_pending'].get(va_id, [])

        for card in vp_swap:
            for i, hand_card in enumerate(game['players'][vp_id]['hand']):
                if (hand_card.get('rank') == card.get('rank') and 
                    hand_card.get('suit') == card.get('suit')):
                    game['players'][vp_id]['hand'].pop(i)
                    break
            game['players'][va_id]['hand'].append(card)

        for card in va_swap:
            for i, hand_card in enumerate(game['players'][va_id]['hand']):
                if (hand_card.get('rank') == card.get('rank') and 
                    hand_card.get('suit') == card.get('suit')):
                    game['players'][va_id]['hand'].pop(i)
                    break
            game['players'][vp_id]['hand'].append(card)

    for pid, player in game['players'].items():
        player['hand'] = sort_hand(player['hand'], game['options'])

    game['swaps_pending'] = {}

    with app.app_context():
        socketio.emit('swaps_complete', {}, room=game_id)

    print(f'[SWAP] All swaps executed, starting new round')
    threading.Timer(2.0, lambda: start_new_round(game_id)).start()

def start_new_round(game_id):
    """Start a new round with dealt cards."""
    if game_id not in games:
        return

    game = games[game_id]

    deck = create_deck()
    game['deck'] = deck

    cards_per_player = 52 // len(game['players'])
    player_ids = game['player_order']

    for idx, player_id in enumerate(player_ids):
        if player_id not in game['players']:
            continue
        start = idx * cards_per_player
        end = start + cards_per_player
        player_cards = deck[start:end]
        game['players'][player_id]['hand'] = sort_hand(player_cards, game['options'])
        game['players'][player_id]['role'] = 'Citizen'

    game['state'] = 'playing'
    game['current_player_idx'] = 0
    game['table_meld'] = []
    game['passes'] = set()
    game['last_player_id'] = None
    game['elimination_order'] = []

    with app.app_context():
        socketio.emit('new_round_started', {
            'players_status': get_player_status(game_id)
        }, room=game_id)

    print(f'[ROUND] New round started')

if __name__ == '__main__':
    print('Starting on 0.0.0.0:8080')
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
