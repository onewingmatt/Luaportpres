#!/usr/bin/env python3
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import os
import sys

print("[INIT] Starting...", flush=True)

app = Flask(__name__, template_folder='.', static_folder='.')
app.config['SECRET_KEY'] = 'president-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25, async_mode='threading')

games = {}

@app.route('/health')
def health():
    return {'status': 'ok'}, 200

@app.route('/')
def index():
    try:
        return render_template('president.html')
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        return f"Error: {e}", 500

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f"[CONNECT] {sid}", flush=True)
    emit('response', {'data': 'Connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[DISCONNECT] {request.sid}", flush=True)

@socketio.on('create')
def handle_create(data):
    sid = request.sid
    print(f"[CREATE] from {sid}", flush=True)
    try:
        name = str(data.get('name', 'Player')).strip()
        options = data.get('options', {})

        if not name:
            raise ValueError("Name required")

        game_id = os.urandom(4).hex()
        print(f"[CREATE] game_id={game_id}, player={name}", flush=True)

        join_room(game_id)
        games[game_id] = {
            'id': game_id,
            'creator': name,
            'players': [name],
            'options': options,
            'round': 1
        }

        state = {
            'game_id': game_id,
            'round': 1,
            'players': [name],
            'currentplayer': name
        }

        emit('created', {'game_id': game_id})
        socketio.emit('update', {'state': state}, to=game_id)

        print(f"[CREATE] SUCCESS: {game_id}", flush=True)
        sys.stdout.flush()

    except Exception as e:
        print(f"[CREATE] ERROR: {str(e)}", flush=True)
        emit('error', {'message': str(e)})
        sys.stdout.flush()

@socketio.on('join')
def handle_join(data):
    sid = request.sid
    print(f"[JOIN] from {sid}", flush=True)
    try:
        game_id = str(data.get('table_id', '')).strip()
        name = str(data.get('name', 'Player')).strip()

        if game_id not in games:
            raise ValueError(f"Game {game_id} not found")

        join_room(game_id)
        games[game_id]['players'].append(name)

        state = {
            'game_id': game_id,
            'players': games[game_id]['players'],
            'currentplayer': games[game_id]['players'][0]
        }

        socketio.emit('update', {'state': state}, to=game_id)
        print(f"[JOIN] SUCCESS: {name} -> {game_id}", flush=True)
        sys.stdout.flush()

    except Exception as e:
        print(f"[JOIN] ERROR: {str(e)}", flush=True)
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    print("="*70, flush=True)
    print("PRESIDENT CARD GAME", flush=True)
    print("="*70, flush=True)
    print("[STARTUP] Running on 0.0.0.0:8080", flush=True)
    sys.stdout.flush()

    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
