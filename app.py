from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import os
import time
import sys
import traceback

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = 'president-secret'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

def log_msg(msg, level="INFO"):
    """Log with timestamp"""
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    sys.stdout.flush()

# ============================================
# HTTP ROUTES
# ============================================

@app.route('/health')
def health():
    log_msg("Health check")
    return {'status': 'ok'}, 200

@app.route('/')
def index():
    log_msg("Serving president.html")
    try:
        return render_template('president.html')
    except Exception as e:
        log_msg(f"ERROR serving HTML: {str(e)}", "ERROR")
        return str(e), 500

# ============================================
# SOCKET.IO EVENTS
# ============================================

@socketio.on('connect')
def on_connect():
    """Client connects"""
    sid = request.sid
    log_msg(f"CLIENT CONNECTED: {sid}")
    try:
        emit('response', {'data': 'Connected to server'})
    except Exception as e:
        log_msg(f"ERROR on connect: {str(e)}", "ERROR")

@socketio.on('disconnect')
def on_disconnect():
    """Client disconnects"""
    log_msg(f"CLIENT DISCONNECTED: {request.sid}")

@socketio.on('error')
def on_error(error):
    """Socket error"""
    log_msg(f"SOCKET ERROR: {error}", "ERROR")

@socketio.on('connect_error')
def on_connect_error(data):
    """Connection error"""
    log_msg(f"CONNECTION ERROR: {data}", "ERROR")

@socketio.on('create')
def on_create(data):
    """Handle game creation"""
    sid = request.sid
    log_msg(f"CREATE EVENT from {sid}")

    try:
        # Validate input
        log_msg(f"  Received data: {type(data)}")

        name = data.get('name', 'Player').strip()
        options = data.get('options', {})

        log_msg(f"  Player: {name}")
        log_msg(f"  Options keys: {list(options.keys())}")

        if not name:
            raise ValueError("No player name")

        # Generate game ID
        game_id = os.urandom(4).hex()
        log_msg(f"  Generated game_id: {game_id}")

        # Join room
        join_room(game_id)
        log_msg(f"  {sid} joined room {game_id}")

        # Store game
        games[game_id] = {
            'id': game_id,
            'creator': name,
            'players': [name],
            'options': options,
            'round': 1,
            'created_at': time.time()
        }
        log_msg(f"  Game stored in memory")

        # Create state
        state = {
            'game_id': game_id,
            'round': 1,
            'players': [name],
            'currentplayer': name
        }

        # Emit created event
        log_msg(f"  Emitting 'created' with game_id={game_id}")
        emit('created', {'game_id': game_id, 'success': True})

        # Emit update to room
        log_msg(f"  Emitting 'update' to room {game_id}")
        socketio.emit('update', {'state': state}, to=game_id)

        log_msg(f"✅ GAME CREATED: {game_id} by {name}")

    except Exception as e:
        log_msg(f"❌ EXCEPTION in on_create:", "ERROR")
        log_msg(f"   Error type: {type(e).__name__}", "ERROR")
        log_msg(f"   Error msg: {str(e)}", "ERROR")
        log_msg(f"   Traceback:\n{traceback.format_exc()}", "ERROR")

        try:
            emit('error', {'message': str(e)})
        except:
            log_msg("   Could not emit error to client", "ERROR")

@socketio.on('join')
def on_join(data):
    """Handle game join"""
    sid = request.sid
    log_msg(f"JOIN EVENT from {sid}")

    try:
        game_id = data.get('table_id', '').strip()
        name = data.get('name', 'Player').strip()

        log_msg(f"  Game: {game_id}, Player: {name}")

        if game_id not in games:
            raise ValueError(f"Game {game_id} not found")

        join_room(game_id)
        games[game_id]['players'].append(name)
        log_msg(f"  {name} added to {game_id}")

        state = {
            'game_id': game_id,
            'players': games[game_id]['players'],
            'currentplayer': games[game_id]['players'][0]
        }

        socketio.emit('update', {'state': state}, to=game_id)
        log_msg(f"✅ {name} joined {game_id}")

    except Exception as e:
        log_msg(f"❌ ERROR in on_join: {str(e)}", "ERROR")
        try:
            emit('error', {'message': str(e)})
        except:
            pass

# ============================================
# STARTUP
# ============================================

if __name__ == '__main__':
    log_msg("="*70)
    log_msg("PRESIDENT CARD GAME SERVER")
    log_msg("="*70)
    log_msg("Health check: http://localhost:8080/health")
    log_msg("Game: http://localhost:8080/")
    log_msg("="*70)
    log_msg("Starting SocketIO server...")

    try:
        socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        log_msg(f"FATAL ERROR: {str(e)}", "ERROR")
        log_msg(traceback.format_exc(), "ERROR")
        sys.exit(1)
