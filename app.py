from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room
import secrets
import os

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}
SAVE_DIR = 'saved_games'
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

@app.route('/')
def index():
    return render_template('president.html')

@socketio.on('connect')
def on_connect():
    pass

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=8080)
