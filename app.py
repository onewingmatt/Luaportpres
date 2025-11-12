from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
import os
import secrets
import random
import threading
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
SUITS = ['♠', '♥', '♦', '♣']

def create_deck():
    deck = []
    for rank in RANKS:
        for suit in SUITS:
            deck.append({'rank': rank, 'suit': suit})
    random.shuffle(deck)
    return deck

def deep_copy_cards(cards):
    return json.loads(json.dumps(cards))

def card_power(card, options=None):
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
    if len(cards) == 1:
        return 'SINGLE'
    if len(cards) == 2 and cards[0]['rank'] == cards[1]['rank']:
        return 'PAIR'
    if len(cards) == 3 and cards[0]['rank'] == cards[1]['rank'] == cards[2]['rank']:
        return 'TRIPLE'
    if len(cards) == 4 and cards[0]['rank'] == cards[1]['rank'] == cards[2]['rank'] == cards[3]['rank']:
        return 'QUAD'
    return None

def validate_meld(cards, options=None):
    if options is None:
        options = {}
    if not get_meld_type(cards):
        return False
    if options.get('wild_black3'):
        if '3' in [c['rank'] for c in cards]:
            has_red_3 = any(c['rank'] == '3' and c['suit'] in ('♥', '♦') for c in cards)
            has_black_3 = any(c['rank'] == '3' and c['suit'] in ('♠', '♣') for c in cards)
            if has_red_3 and has_black_3:
                return False
    return True

def compare_melds(played_meld, table_meld, options=None):
    if options is None:
        options = {}
    if not validate_meld(played_meld, options) or not validate_meld(table_meld, options):
        return False, 'Invalid meld'
    p_type = get_meld_type(played_meld)
    t_type = get_meld_type(table_meld)
    if p_type != t_type:
        return False, f'Must play {t_type} (not {p_type})'
    p_power = max(card_power(c, options) for c in played_meld)
    t_power = max(card_power(c, options) for c in table_meld)
    if p_power > t_power:
        return True, f'Valid {p_type}'
    return False, f'{p_type} too low'

def sort_hand(hand, options=None):
    if options is None:
        options = {}
    return sorted(hand, key=lambda c: card_power(c, options))

def cpu_play_meld(hand, table_meld, options=None):
    if options is None:
        options = {}
    if not table_meld:
        return [sorted(hand, key=lambda c: card_power(c, options), reverse=True)[0]] if hand else None
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
    if game_id not in games:
        return {}
    game = games[game_id]
    num_players = len(game['players'])
    roles = {player_id: 'Citizen' for player_id in game['players']}
    if len(game['elimination_order']) >= 1:
        roles[game['elimination_order'][0]] = 'President'
    if num_players >= 4 and len(game['elimination_order']) >= 2:
        roles[game['elimination_order'][1]] = 'Vice President'
    if num_players >= 4 and len(game['elimination_order']) >= 3:
        roles[game['elimination_order'][num_players - 2]] = 'Vice Asshole'
    if len(game['elimination_order']) >= num_players:
        roles[game['elimination_order'][-1]] = 'Asshole'
    return roles

def format_card(card):
    return f"{card['rank']}{card['suit']}"

def format_cards(cards):
    return ' '.join(format_card(c) for c in cards)

@app.route('/')
def index():
    try:
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'president.html')
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                return f.read()
    except:
        pass
    return '<h1>president.html not found</h1>'

@socketio.on('connect')
def on_connect():
    print('[CONNECT]', request.sid)
    emit('connected', {'data': 'connected'})

@socketio.on('join_game')
def on_join_game(data):
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

        cpu_hand = deep_copy_cards(game['players'][cpu_to_replace]['hand'])
        game['players'][request.sid] = {
            'name': player_name,
            'hand': cpu_hand,
            'is_cpu': False,
            'player_id': request.sid,
            'role': game['players'][cpu_to_replace].get('role', 'Citizen')
        }

        cpu_position = game['player_order'].index(cpu_to_replace)
        game['passes'].discard(cpu_to_replace)
        if cpu_to_replace in game['elimination_order']:
            game['elimination_order'].remove(cpu_to_replace)
        game['player_order'][cpu_position] = request.sid
        del game['players'][cpu_to_replace]

        join_room(game_id)
        session['game_id'] = game_id
        session['player_id'] = request.sid

        emit('game_joined', {
            'game_id': game_id,
            'player_name': player_name,
            'hand': cpu_hand,
            'players_status': get_player_status(game_id),
            'game_state': game['state'],
            'table_meld': game['table_meld'],
            'meld_type': get_meld_type(game['table_meld']) if game['table_meld'] else None
        })

        with app.app_context():
            socketio.emit('player_joined', {
                'player_name': player_name,
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[JOIN] {player_name} joined at position {cpu_position}')
    except Exception as e:
        print(f'[JOIN ERROR] {e}')
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
        print(f'[CREATE] Game {game_id}')
    except Exception as e:
        print(f'[CREATE ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('deal_cards')
def on_deal_cards():
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]
        deck = create_deck()
        cards_per_player = 52 // len(game['players'])

        for idx, player_id in enumerate(game['player_order']):
            if player_id not in game['players']:
                continue
            start = idx * cards_per_player
            end = start + cards_per_player
            game['players'][player_id]['hand'] = sort_hand(deck[start:end], game['options'])

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

        print(f'[DEAL] Dealt to {len(game["players"])} players')
    except Exception as e:
        print(f'[DEAL ERROR] {e}')
        emit('error', {'message': str(e)})

def get_player_status(game_id):
    if game_id not in games:
        return []
    game = games[game_id]
    idx = game['current_player_idx']
    if idx < 0 or idx >= len(game['player_order']):
        idx = 0
    current_player_id = game['player_order'][idx] if game['player_order'] else None
    status = []
    for player_id in game['player_order']:
        if player_id not in game['players']:
            continue
        player = game['players'][player_id]
        status.append({
            'name': player['name'],
            'card_count': len(player['hand']),
            'is_active': player_id == current_player_id and len(player['hand']) > 0,
            'is_cpu': player['is_cpu']
        })
    return status

def advance_to_next_valid_player(game_id):
    """Move to next player with cards. Returns player ID or None. NO RECURSION."""
    if game_id not in games:
        return None

    game = games[game_id]

    if len(game['player_order']) == 0:
        return None

    # Move index forward once
    start_idx = game['current_player_idx']
    game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])

    # Check up to N players
    for _ in range(len(game['player_order'])):
        current_id = game['player_order'][game['current_player_idx']]

        # Is this player valid (exists and has cards)?
        if current_id in game['players'] and len(game['players'][current_id]['hand']) > 0:
            pname = game['players'][current_id]['name']
            is_cpu = game['players'][current_id]['is_cpu']
            print(f'[ADVANCE] -> {pname} (CPU: {is_cpu})')
            return current_id

        # Move to next
        game['current_player_idx'] = (game['current_player_idx'] + 1) % len(game['player_order'])

        # Stop if we've looped back
        if game['current_player_idx'] == start_idx:
            print(f'[ADVANCE] No valid players (all have 0 cards)')
            return None

    return None

def check_round_end(game_id):
    if game_id not in games:
        return False

    game = games[game_id]
    game['passes'] = {p for p in game['passes'] if p in game['players'] and len(game['players'][p]['hand']) > 0}
    active = [p for p in game['player_order'] if p in game['players'] and len(game['players'][p]['hand']) > 0]

    if not active or not game['last_player_id'] or game['last_player_id'] not in game['players']:
        return False

    if len(game['passes']) == len(active) - 1:
        print(f'[ROUND] Round ended')
        game['table_meld'] = []
        game['passes'] = set()

        if len(game['players'][game['last_player_id']]['hand']) > 0:
            game['current_player_idx'] = game['player_order'].index(game['last_player_id'])
        else:
            idx = game['player_order'].index(game['last_player_id'])
            game['current_player_idx'] = (idx + 1) % len(game['player_order'])
            advance_to_next_valid_player(game_id)

        with app.app_context():
            socketio.emit('table_cleared', {'players_status': get_player_status(game_id)}, room=game_id)
        return True
    return False

@socketio.on('start_game')
def on_start_game():
    try:
        game_id = session.get('game_id')
        if game_id and game_id in games:
            games[game_id]['state'] = 'dealing'
            socketio.emit('ready_to_deal', {'game_id': game_id}, room=game_id)
    except Exception as e:
        print(f'[START ERROR] {e}')

@socketio.on('play_meld')
def on_play_meld(data):
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]
        cards = data.get('cards', [])

        if not cards:
            emit('error', {'message': 'Select at least 1 card'})
            return

        player = game['players'].get(request.sid)
        if not player:
            emit('error', {'message': 'Not a player'})
            return

        for card in cards:
            found = any(hand_card.get('rank') == card.get('rank') and hand_card.get('suit') == card.get('suit') for hand_card in player['hand'])
            if not found:
                emit('error', {'message': 'Card not in hand'})
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

        for card in cards:
            for i, hand_card in enumerate(player['hand']):
                if hand_card.get('rank') == card.get('rank') and hand_card.get('suit') == card.get('suit'):
                    player['hand'].pop(i)
                    break

        game['table_meld'] = cards
        game['last_player_id'] = request.sid
        game['passes'].clear()

        socketio.emit('meld_played', {
            'player': player['name'],
            'meld': cards,
            'meld_type': meld_type,
            'cards_str': format_cards(cards),
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'my_hand': player['hand'],
            'players_status': get_player_status(game_id)
        }, room=game_id)

        print(f'[PLAY] {player["name"]} played {meld_type}')

        if len(player['hand']) == 0:
            game['elimination_order'].append(request.sid)
            if len(game['elimination_order']) == len(game['player_order']) - 1:
                deck = create_deck()
                cards_per_player = 52 // len(game['players'])
                for idx, player_id in enumerate(game['player_order']):
                    if player_id not in game['players']:
                        continue
                    start = idx * cards_per_player
                    end = start + cards_per_player
                    game['players'][player_id]['hand'] = sort_hand(deck[start:end], game['options'])

                roles = assign_roles(game_id)
                for pid, role in roles.items():
                    if pid in game['players']:
                        game['players'][pid]['role'] = role

                role_data = {game['players'][pid]['name']: {'role': roles.get(pid, 'Citizen'), 'hand': game['players'][pid]['hand']} for pid in game['players']}

                with app.app_context():
                    socketio.emit('game_ended', {
                        'elimination_order': [game['players'][pid]['name'] for pid in game['elimination_order'] if pid in game['players']],
                        'roles': {game['players'][pid]['name']: role for pid, role in roles.items() if pid in game['players']},
                        'role_data': role_data
                    }, room=game_id)

                threading.Timer(2.0, lambda: cpu_auto_swap(game_id)).start()
                return

        # IMPORTANT: Advance FIRST, then check who is next
        next_player_id = advance_to_next_valid_player(game_id)

        # Broadcast the updated status to everyone (so UI shows correct active player)
        with app.app_context():
            socketio.emit('player_status_update', {'players_status': get_player_status(game_id)}, room=game_id)

        # Now schedule CPU if next is CPU
        if next_player_id and game['players'][next_player_id]['is_cpu']:
            print(f'[PLAY] Next is CPU, scheduling turn')
            threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()
        else:
            print(f'[PLAY] Next is human or none, waiting')

    except Exception as e:
        print(f'[PLAY ERROR] {e}')
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

def cpu_play_turn(game_id):
    """CPU plays or passes."""
    if game_id not in games:
        return

    game = games[game_id]

    if game['state'] != 'playing' or len(game['player_order']) == 0:
        print(f'[CPU] Game not playing')
        return

    if game['current_player_idx'] < 0 or game['current_player_idx'] >= len(game['player_order']):
        print(f'[CPU] Index invalid')
        return

    current_id = game['player_order'][game['current_player_idx']]

    if current_id not in game['players']:
        print(f'[CPU] Current player {current_id} not in game')
        return

    player = game['players'][current_id]

    if not player['is_cpu'] or len(player['hand']) == 0:
        print(f'[CPU] Current player is not CPU or has no cards')
        return

    print(f'[CPU] {player["name"]} playing...')
    meld = cpu_play_meld(player['hand'], game['table_meld'], game['options'])

    if meld:
        for card in meld:
            for i, hand_card in enumerate(player['hand']):
                if hand_card.get('rank') == card.get('rank') and hand_card.get('suit') == card.get('suit'):
                    player['hand'].pop(i)
                    break

        game['table_meld'] = meld
        game['last_player_id'] = current_id
        game['passes'].clear()

        with app.app_context():
            socketio.emit('meld_played', {
                'player': player['name'],
                'meld': meld,
                'meld_type': get_meld_type(meld),
                'cards_str': format_cards(meld),
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[CPU] {player["name"]} played: {format_cards(meld)}')

        if len(player['hand']) == 0:
            game['elimination_order'].append(current_id)
            if len(game['elimination_order']) == len(game['player_order']) - 1:
                deck = create_deck()
                cards_per_player = 52 // len(game['players'])
                for idx, player_id in enumerate(game['player_order']):
                    if player_id not in game['players']:
                        continue
                    start = idx * cards_per_player
                    end = start + cards_per_player
                    game['players'][player_id]['hand'] = sort_hand(deck[start:end], game['options'])

                roles = assign_roles(game_id)
                for pid, role in roles.items():
                    if pid in game['players']:
                        game['players'][pid]['role'] = role

                role_data = {game['players'][pid]['name']: {'role': roles.get(pid, 'Citizen'), 'hand': game['players'][pid]['hand']} for pid in game['players']}

                with app.app_context():
                    socketio.emit('game_ended', {
                        'elimination_order': [game['players'][pid]['name'] for pid in game['elimination_order'] if pid in game['players']],
                        'roles': {game['players'][pid]['name']: role for pid, role in roles.items() if pid in game['players']},
                        'role_data': role_data
                    }, room=game_id)

                threading.Timer(2.0, lambda: cpu_auto_swap(game_id)).start()
                return

        next_player_id = advance_to_next_valid_player(game_id)

        with app.app_context():
            socketio.emit('player_status_update', {'players_status': get_player_status(game_id)}, room=game_id)

        if next_player_id and game['players'][next_player_id]['is_cpu']:
            threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()
    else:
        game['passes'].add(current_id)

        with app.app_context():
            socketio.emit('player_passed', {
                'player': player['name'],
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'players_status': get_player_status(game_id)
            }, room=game_id)

        print(f'[CPU] {player["name"]} passed')

        check_round_end(game_id)

        next_player_id = advance_to_next_valid_player(game_id)

        with app.app_context():
            socketio.emit('player_status_update', {'players_status': get_player_status(game_id)}, room=game_id)

        if next_player_id and game['players'][next_player_id]['is_cpu']:
            threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()

@socketio.on('pass_turn')
def on_pass_turn():
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]
        player = game['players'].get(request.sid)

        if not player or len(player['hand']) == 0:
            emit('error', {'message': 'Cannot pass'})
            return

        game['passes'].add(request.sid)

        socketio.emit('player_passed', {
            'player': player['name'],
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'players_status': get_player_status(game_id)
        }, room=game_id)

        print(f'[PASS] {player["name"]} passed')

        check_round_end(game_id)

        next_player_id = advance_to_next_valid_player(game_id)

        with app.app_context():
            socketio.emit('player_status_update', {'players_status': get_player_status(game_id)}, room=game_id)

        if next_player_id and game['players'][next_player_id]['is_cpu']:
            print(f'[PASS] Next is CPU, scheduling')
            threading.Timer(1.0, lambda: cpu_play_turn(game_id)).start()
        else:
            print(f'[PASS] Next is human, waiting')

    except Exception as e:
        print(f'[PASS ERROR] {e}')
        emit('error', {'message': str(e)})

def cpu_auto_swap(game_id):
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
            game['swaps_pending'][player_id] = sort_hand(hand, game['options'])[:2]
        elif role == 'Vice President':
            game['swaps_pending'][player_id] = sort_hand(hand, game['options'])[:1]
        elif role == 'Vice Asshole':
            game['swaps_pending'][player_id] = sort_hand(hand, game['options'])[-1:]
        elif role == 'Asshole':
            game['swaps_pending'][player_id] = sort_hand(hand, game['options'])[-2:]
    with app.app_context():
        socketio.emit('cpu_swaps_submitted', {'total_submitted': len(game['swaps_pending'])}, room=game_id)
    swappable = [p for p in game['players'].values() if p['role'] in ['President', 'Vice President', 'Asshole', 'Vice Asshole']]
    if len(game['swaps_pending']) >= len(swappable):
        execute_swaps(game_id)

@socketio.on('submit_swap')
def on_submit_swap(data):
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            return
        game = games[game_id]
        game['swaps_pending'][request.sid] = data.get('cards', [])
        swappable = [p for p in game['players'].values() if p['role'] in ['President', 'Vice President', 'Asshole', 'Vice Asshole']]
        if len(game['swaps_pending']) == len(swappable):
            execute_swaps(game_id)
    except Exception as e:
        print(f'[SWAP ERROR] {e}')

def execute_swaps(game_id):
    if game_id not in games:
        return
    game = games[game_id]
    pres_id = next((p for p in game['players'] if game['players'][p]['role'] == 'President'), None)
    ass_id = next((p for p in game['players'] if game['players'][p]['role'] == 'Asshole'), None)
    vp_id = next((p for p in game['players'] if game['players'][p]['role'] == 'Vice President'), None)
    va_id = next((p for p in game['players'] if game['players'][p]['role'] == 'Vice Asshole'), None)
    if pres_id and ass_id:
        for card in game['swaps_pending'].get(pres_id, []):
            for i, c in enumerate(game['players'][pres_id]['hand']):
                if c.get('rank') == card.get('rank') and c.get('suit') == card.get('suit'):
                    game['players'][pres_id]['hand'].pop(i)
                    break
            game['players'][ass_id]['hand'].append(card)
        for card in game['swaps_pending'].get(ass_id, []):
            for i, c in enumerate(game['players'][ass_id]['hand']):
                if c.get('rank') == card.get('rank') and c.get('suit') == card.get('suit'):
                    game['players'][ass_id]['hand'].pop(i)
                    break
            game['players'][pres_id]['hand'].append(card)
    if vp_id and va_id:
        for card in game['swaps_pending'].get(vp_id, []):
            for i, c in enumerate(game['players'][vp_id]['hand']):
                if c.get('rank') == card.get('rank') and c.get('suit') == card.get('suit'):
                    game['players'][vp_id]['hand'].pop(i)
                    break
            game['players'][va_id]['hand'].append(card)
        for card in game['swaps_pending'].get(va_id, []):
            for i, c in enumerate(game['players'][va_id]['hand']):
                if c.get('rank') == card.get('rank') and c.get('suit') == card.get('suit'):
                    game['players'][va_id]['hand'].pop(i)
                    break
            game['players'][vp_id]['hand'].append(card)
    game['swaps_pending'] = {}
    with app.app_context():
        socketio.emit('swaps_complete', {}, room=game_id)
    threading.Timer(2.0, lambda: start_new_round(game_id)).start()

def start_new_round(game_id):
    if game_id not in games:
        return
    game = games[game_id]
    deck = create_deck()
    cards_per_player = 52 // len(game['players'])
    for idx, player_id in enumerate(game['player_order']):
        if player_id not in game['players']:
            continue
        start = idx * cards_per_player
        end = start + cards_per_player
        game['players'][player_id]['hand'] = sort_hand(deck[start:end], game['options'])
        game['players'][player_id]['role'] = 'Citizen'
    game['state'] = 'playing'
    game['current_player_idx'] = 0
    game['table_meld'] = []
    game['passes'] = set()
    game['last_player_id'] = None
    game['elimination_order'] = []
    with app.app_context():
        socketio.emit('new_round_started', {'players_status': get_player_status(game_id)}, room=game_id)

if __name__ == '__main__':
    print('Starting on 0.0.0.0:8080')
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
