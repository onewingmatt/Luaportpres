from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import os

app = Flask(__name__, template_folder='.', static_folder='.')
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

@app.route('/health')
def health():
    return {'status': 'ok'}, 200

@app.route('/')
def index():
    return render_template('president.html')

@socketio.on('connect')
def handle_connect():
    emit('response', {'data': 'Connected'})

@socketio.on('disconnect')
def handle_disconnect():
    pass

@socketio.on('create')
def handle_create(data):
    try:
        name = str(data.get('name', 'Player')).strip()
        options = data.get('options', {})

        game_id = os.urandom(4).hex()
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

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('join')
def handle_join(data):
    try:
        game_id = str(data.get('table_id', '')).strip()
        name = str(data.get('name', 'Player')).strip()

        if game_id not in games:
            raise ValueError(f"Game not found")

        join_room(game_id)
        games[game_id]['players'].append(name)

        state = {
            'game_id': game_id,
            'players': games[game_id]['players'],
            'currentplayer': games[game_id]['players'][0]
        }

        socketio.emit('update', {'state': state}, to=game_id)

    except Exception as e:
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
