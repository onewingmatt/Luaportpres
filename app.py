from flask import Flask, session, request
from flask_socketio import SocketIO, emit, join_room
import os
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

@app.route('/')
def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'president.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        return f.read()

@socketio.on('connect')
def on_connect():
    pass

@socketio.on('create')
def on_create(data):
    try:
        game_id = secrets.token_hex(4)
        games[game_id] = {'id': game_id, 'players': {}}
        join_room(game_id)
        session['game_id'] = game_id
        emit('game_created', {'game_id': game_id})
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('start_game')
def on_start_game():
    try:
        game_id = session.get('game_id')
        if game_id and game_id in games:
            emit('game_started', {'game_id': game_id}, room=game_id)
    except Exception as e:
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=8080)
