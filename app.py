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

def sort_hand(hand, options=None):
    if options is None:
        options = {}
    return sorted(hand, key=lambda c: card_power(c, options))

@app.route('/')
def index():
    try:
        with open('president.html', 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return '<h1>Error: president.html not found</h1>'

@socketio.on('connect')
def on_connect():
    print('[CONNECT]', request.sid)
    emit('connected', {'data': 'connected'})

@socketio.on('create')
def on_create(data):
    try:
        game_id = secrets.token_hex(4)
        options = data.get('options', {})
        player_name = data.get('name', 'Player')
        num_cpus = data.get('cpus', 3)

        games[game_id] = {
            'id': game_id,
            'options': options,
            'players': {},
            'player_order': [],
            'current_turn_player_id': None,
            'state': 'waiting'
        }

        # Add human player
        games[game_id]['players'][request.sid] = {
            'name': player_name,
            'hand': [],
            'is_cpu': False,
            'player_id': request.sid
        }
        games[game_id]['player_order'].append(request.sid)

        # Add CPUs
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
        session['player_id'] = request.sid

        emit('game_created', {'game_id': game_id, 'options': options})
        print(f'[CREATE] Game {game_id} created')
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
        game['current_turn_player_id'] = game['player_order'][0]

        my_hand = game['players'][request.sid]['hand']

        emit('cards_dealt', {
            'hand': my_hand,
            'hand_size': len(my_hand),
            'players_status': get_player_status(game_id)
        })

        socketio.emit('game_started', {
            'game_id': game_id,
            'state': 'playing',
            'players_status': get_player_status(game_id)
        }, room=game_id)

    except Exception as e:
        print(f'[DEAL ERROR] {e}')
        emit('error', {'message': str(e)})

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

        # Replace first CPU
        cpu_to_replace = None
        for pid, player in game['players'].items():
            if player['is_cpu']:
                cpu_to_replace = pid
                break

        if not cpu_to_replace:
            emit('error', {'message': 'No CPU slots available'})
            return

        game['players'][request.sid] = {
            'name': player_name,
            'hand': game['players'][cpu_to_replace]['hand'][:],
            'is_cpu': False,
            'player_id': request.sid
        }

        cpu_position = game['player_order'].index(cpu_to_replace)
        game['player_order'][cpu_position] = request.sid
        del game['players'][cpu_to_replace]

        join_room(game_id)
        session['game_id'] = game_id
        session['player_id'] = request.sid

        emit('game_joined', {
            'game_id': game_id,
            'player_name': player_name,
            'hand': game['players'][request.sid]['hand'],
            'players_status': get_player_status(game_id)
        })

        socketio.emit('player_joined', {
            'player_name': player_name,
            'players_status': get_player_status(game_id)
        }, room=game_id)
    except Exception as e:
        print(f'[JOIN ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('play_meld')
def on_play_meld(data):
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        game = games[game_id]
        emit('error', {'message': 'Not yet implemented'})
    except Exception as e:
        print(f'[PLAY ERROR] {e}')
        emit('error', {'message': str(e)})

@socketio.on('pass_turn')
def on_pass_turn():
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No active game'})
            return

        emit('error', {'message': 'Not yet implemented'})
    except Exception as e:
        print(f'[PASS ERROR] {e}')
        emit('error', {'message': str(e)})

def get_player_status(game_id):
    if game_id not in games:
        return []
    game = games[game_id]
    status = []
    for player_id in game['player_order']:
        if player_id not in game['players']:
            continue
        player = game['players'][player_id]
        is_active = (player_id == game.get('current_turn_player_id') and len(player['hand']) > 0)
        status.append({
            'name': player['name'],
            'card_count': len(player['hand']),
            'is_active': is_active,
            'is_leader': False,
            'is_cpu': player['is_cpu']
        })
    return status

if __name__ == '__main__':
    print('Starting app on 0.0.0.0:8080...')
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
