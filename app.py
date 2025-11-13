from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
import os
import secrets
import random
import threading
from datetime import datetime
import json

print("[STARTUP] Initializing Flask app...")

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)

print("[STARTUP] Initializing SocketIO...")
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
    except Exception as e:
        print(f"[ERROR] Loading HTML: {e}")
        return '<h1>Error loading president.html</h1>'

@socketio.on('connect')
def on_connect():
    print(f'[SOCKET] Client connected: {request.sid}')
    emit('connected', {'status': 'connected'})

@socketio.on('create')
def on_create(data):
    try:
        game_id = secrets.token_hex(4)
        player_name = data.get('name', 'Player')
        num_cpus = int(data.get('cpus', 3))
        options = data.get('options', {})

        print(f'[GAME] Creating game {game_id}: {player_name}, {num_cpus} CPUs, options={options}')

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
            'player_order': [request.sid],
            'current_turn': request.sid,
            'state': 'waiting',
            'table_meld': [],
            'passes': set()
        }

        # Add CPUs
        for i in range(num_cpus):
            cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
            games[game_id]['players'][cpu_id] = {
                'name': f'CPU-{i+1}',
                'hand': [],
                'is_cpu': True
            }
            games[game_id]['player_order'].append(cpu_id)

        join_room(game_id)
        session['game_id'] = game_id
        session['player_id'] = request.sid

        print(f'[GAME] Game {game_id} created with {len(games[game_id]["players"])} players')
        emit('game_created', {'game_id': game_id})

    except Exception as e:
        print(f'[ERROR] create: {e}')
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

@socketio.on('deal_cards')
def on_deal_cards():
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No game'})
            return

        game = games[game_id]
        deck = create_deck()
        cards_per = 52 // len(game['players'])

        for idx, pid in enumerate(game['player_order']):
            start = idx * cards_per
            end = start + cards_per
            game['players'][pid]['hand'] = sort_hand(deck[start:end], game['options'])

        game['state'] = 'playing'
        game['current_turn'] = game['player_order'][0]

        my_hand = game['players'][request.sid]['hand']

        print(f'[GAME] Dealt cards to {len(game["players"])} players')
        emit('cards_dealt', {
            'hand': my_hand,
            'players_status': get_status(game_id)
        })
        socketio.emit('game_started', {
            'players_status': get_status(game_id)
        }, room=game_id)

    except Exception as e:
        print(f'[ERROR] deal: {e}')
        emit('error', {'message': str(e)})

@socketio.on('join_game')
def on_join_game(data):
    try:
        game_id = data.get('game_id')
        name = data.get('player_name', 'Player')

        if not game_id or game_id not in games:
            emit('error', {'message': 'Game not found'})
            return

        game = games[game_id]

        # Find CPU to replace
        cpu_id = None
        for pid in game['players']:
            if game['players'][pid]['is_cpu']:
                cpu_id = pid
                break

        if not cpu_id:
            emit('error', {'message': 'No CPU slots'})
            return

        game['players'][request.sid] = {
            'name': name,
            'hand': game['players'][cpu_id]['hand'][:],
            'is_cpu': False
        }

        idx = game['player_order'].index(cpu_id)
        game['player_order'][idx] = request.sid
        del game['players'][cpu_id]

        join_room(game_id)
        session['game_id'] = game_id
        session['player_id'] = request.sid

        print(f'[GAME] {name} joined game {game_id}')
        emit('game_joined', {
            'game_id': game_id,
            'hand': game['players'][request.sid]['hand'],
            'players_status': get_status(game_id)
        })
        socketio.emit('player_joined', {
            'players_status': get_status(game_id)
        }, room=game_id)

    except Exception as e:
        print(f'[ERROR] join: {e}')
        emit('error', {'message': str(e)})

@socketio.on('play_meld')
def on_play_meld(data):
    emit('error', {'message': 'Play not implemented'})

@socketio.on('pass_turn')
def on_pass_turn():
    emit('error', {'message': 'Pass not implemented'})

def get_status(game_id):
    if game_id not in games:
        return []
    game = games[game_id]
    return [{
        'name': game['players'][pid]['name'],
        'card_count': len(game['players'][pid]['hand']),
        'is_active': (pid == game.get('current_turn')),
        'is_leader': False,
        'is_cpu': game['players'][pid]['is_cpu']
    } for pid in game['player_order']]

print("[STARTUP] Routes and handlers defined")
print("[STARTUP] Ready to start server...")

if __name__ == '__main__':
    print("[STARTUP] ========================================")
    print("[STARTUP] Starting on 0.0.0.0:8080")
    print("[STARTUP] ========================================")
    socketio.run(app, debug=False, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True)
