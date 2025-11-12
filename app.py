from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import os
import json
import time
import sys
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'president-game-secret'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}
connections = {}

def log(msg, level="INFO"):
    """Consistent logging with timestamps"""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] [{level}] {msg}", flush=True)
    sys.stdout.flush()

# ============================================
# HEALTH CHECK
# ============================================
@app.route('/health')
def health():
    log("Health check requested")
    return {'status': 'ok', 'timestamp': time.time()}, 200

@app.route('/')
def index():
    log("Root path requested - serving game")
    return render_template_string(html_template)

# ============================================
# SOCKET.IO EVENTS
# ============================================

@socketio.on('connect')
def on_connect():
    sid = request.sid
    connections[sid] = {'connected_at': time.time()}
    log(f"CLIENT CONNECTED: {sid}", "CONNECT")
    emit('response', {'data': 'Connected to server'})

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in connections:
        del connections[sid]
    log(f"CLIENT DISCONNECTED: {sid}", "DISCONNECT")

@socketio.on('create')
def on_create(data):
    """Create a new game"""
    sid = request.sid
    log(f"[CREATE] Received from {sid}: {data}", "CREATE")

    try:
        # Parse input
        name = data.get('name', 'Player').strip()
        if not name:
            log("CREATE: No name provided", "ERROR")
            emit('error', 'Name required')
            return

        options = data.get('options', {})
        log(f"CREATE: Player name: {name}", "CREATE")
        log(f"CREATE: Options: {options}", "CREATE")

        # Create game
        game_id = os.urandom(4).hex()
        log(f"CREATE: Generated game ID: {game_id}", "CREATE")

        # Extract options
        num_players = options.get('numPlayers', 4)
        num_decks = options.get('numDecks', 1)
        log(f"CREATE: {num_players} players, {num_decks} deck(s)", "CREATE")

        # Store game state
        games[game_id] = {
            'id': game_id,
            'creator': name,
            'creator_sid': sid,
            'options': options,
            'players': [{'name': name, 'sid': sid, 'is_cpu': False}],
            'state': 'waiting',
            'round': 1,
            'created_at': time.time()
        }

        log(f"CREATE: Game object created in memory", "CREATE")

        # Join room
        join_room(game_id)
        log(f"CREATE: {sid} joined room {game_id}", "CREATE")

        # Create state object
        state = {
            'game_id': game_id,
            'round': 1,
            'players': [p['name'] for p in games[game_id]['players']],
            'currentplayer': name,
            'state': 'created'
        }

        log(f"CREATE: Emitting 'created' event with game_id={game_id}", "CREATE")

        # Emit to creator
        emit('created', {'game_id': game_id}, to=sid)

        log(f"CREATE: Emitting 'update' event to room {game_id}", "CREATE")

        # Emit to room
        socketio.emit('update', {'state': state}, to=game_id)

        log(f"✅ CREATE SUCCESS: Game {game_id} created and started", "CREATE")

    except Exception as e:
        log(f"❌ CREATE EXCEPTION: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        emit('error', f'Error: {str(e)}')

@socketio.on('join')
def on_join(data):
    """Join existing game"""
    sid = request.sid
    log(f"[JOIN] Received from {sid}: {data}", "JOIN")

    try:
        game_id = data.get('table_id', '').strip()
        name = data.get('name', 'Player').strip()

        if not game_id:
            log("JOIN: No game ID provided", "ERROR")
            emit('error', 'Game ID required')
            return

        if game_id not in games:
            log(f"JOIN: Game {game_id} not found", "ERROR")
            emit('error', 'Game not found')
            return

        join_room(game_id)
        games[game_id]['players'].append({'name': name, 'sid': sid, 'is_cpu': False})
        log(f"JOIN: {name} added to game {game_id}", "JOIN")

        state = {
            'game_id': game_id,
            'round': games[game_id]['round'],
            'players': [p['name'] for p in games[game_id]['players']],
            'currentplayer': games[game_id]['players'][0]['name']
        }

        socketio.emit('update', {'state': state}, to=game_id)
        log(f"✅ JOIN SUCCESS: {name} joined game {game_id}", "JOIN")

    except Exception as e:
        log(f"❌ JOIN EXCEPTION: {str(e)}", "ERROR")
        emit('error', f'Error: {str(e)}')

@socketio.on('debug')
def on_debug():
    """Debug endpoint to check server state"""
    log(f"DEBUG: Active games: {len(games)}", "DEBUG")
    log(f"DEBUG: Connected clients: {len(connections)}", "DEBUG")
    for gid, game in games.items():
        log(f"  Game {gid}: {len(game['players'])} players", "DEBUG")
    emit('debug', {
        'games': len(games),
        'connections': len(connections),
        'timestamp': time.time()
    })

# ============================================
# HTML TEMPLATE
# ============================================
html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>President Card Game</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #333; padding: 20px; min-height: 100vh; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 40px; }
        .header h1 { font-size: 3em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .setupPhase { background: white; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); padding: 40px; }
        .tabs { display: flex; border-bottom: 2px solid #eee; margin-bottom: 30px; gap: 20px; }
        .tab-btn { padding: 12px 30px; border: none; background: none; cursor: pointer; color: #667eea; font-weight: bold; border-bottom: 3px solid transparent; }
        .tab-btn.active { border-bottom-color: #667eea; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        input, select { width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 6px; margin-top: 5px; }
        .btn-primary { background: #667eea; color: white; padding: 15px 40px; width: 100%; margin-top: 20px; border: none; border-radius: 6px; cursor: pointer; }
        .btn-primary:hover { background: #5568d3; }
        .btn-primary:disabled { background: #999; }
        .loadingMsg { text-align: center; color: #667eea; font-weight: bold; margin-top: 20px; }
        .gameArea { background: white; border-radius: 12px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); text-align: center; }
        .gameCode { background: #f0f0f5; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .gameCode strong { color: #667eea; font-size: 1.3em; }
        .debug { background: #f9f9f9; border: 1px solid #ddd; padding: 10px; border-radius: 6px; margin-top: 20px; font-family: monospace; font-size: 0.9em; max-height: 200px; overflow-y: auto; }
        .debug-line { margin: 3px 0; padding: 3px; }
        .debug-info { color: #667eea; }
        .debug-error { color: #ff6b6b; }
        .debug-success { color: #51cf66; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🎴 President Card Game</h1>
        <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-top: 15px;">
            <span style="background: #ff6b6b; color: white; padding: 5px 12px; border-radius: 20px; font-size: 0.8em;">BETA</span>
            <div style="display: flex; align-items: center; gap: 10px;">
                <label style="color: white; font-weight: bold;">🔊 Sound:</label>
                <input type="checkbox" id="soundToggle" checked style="width: auto; height: 20px;">
            </div>
        </div>
    </div>

    <div class="setupPhase" id="setupPhase">
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('create')">Create New Game</button>
            <button class="tab-btn" onclick="switchTab('join')">Join Existing Game</button>
        </div>

        <div id="create" class="tab-content active">
            <div style="margin-bottom: 20px;">
                <label><strong>Your Name</strong></label>
                <input type="text" id="playerName" placeholder="Enter your name">
            </div>

            <div style="margin-top: 20px; padding: 15px; background: #f0f0f5; border: 2px solid #667eea; border-radius: 8px;">
                <h3 style="color: #667eea; font-weight: bold; margin-bottom: 15px;">⚙️ Game Options</h3>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <div>
                        <label><strong>Number of Players:</strong>
                            <select id="optNumPlayers">
                                <option value="2">2</option><option value="3">3</option><option value="4" selected>4</option>
                                <option value="5">5</option><option value="6">6</option><option value="7">7</option><option value="8">8</option>
                            </select>
                        </label>
                    </div>
                    <div>
                        <label><strong>Amount of Decks:</strong>
                            <select id="optNumDecks">
                                <option value="1" selected>1</option><option value="2">2</option>
                            </select>
                        </label>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <div>
                        <label><strong>Mode:</strong>
                            <select id="optGameMode">
                                <option value="continuous" selected>Continuous</option><option value="noncontinuous">Non-Continuous</option>
                            </select>
                        </label>
                    </div>
                    <div>
                        <label><strong>Run Length:</strong>
                            <select id="optRunMax">
                                <option value="0">None</option><option value="3">3</option><option value="4">4</option><option value="5" selected>5</option>
                            </select>
                        </label>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <label><input type="checkbox" id="optTwosWild" checked> 2s Wild</label>
                    <label><input type="checkbox" id="optBlack3sHigh" checked> Black 3s High</label>
                    <label><input type="checkbox" id="optJackDHigh" checked> J♦ Highest</label>
                    <label><input type="checkbox" id="optWildsBeat" checked> Wilds Beat</label>
                    <label><input type="checkbox" id="opt2sInRuns"> 2s in Runs</label>
                    <label><input type="checkbox" id="optBombs" checked> Bombs</label>
                </div>
            </div>

            <button class="btn-primary" id="createBtn" onclick="createGame()">Create Game</button>
            <div class="loadingMsg" id="creatingMsg" style="display: none;">Creating game...</div>
        </div>

        <div id="join" class="tab-content">
            <div style="margin-bottom: 20px;">
                <label><strong>Your Name</strong></label>
                <input type="text" id="joinPlayerName" placeholder="Enter your name">
            </div>
            <div style="margin-bottom: 20px;">
                <label><strong>Game Code</strong></label>
                <input type="text" id="gameCode" placeholder="Enter game code">
            </div>
            <button class="btn-primary" id="joinBtn" onclick="joinGame()">Join Game</button>
            <div class="loadingMsg" id="joiningMsg" style="display: none;">Joining game...</div>
        </div>
    </div>

    <div class="gameArea" id="gameArea" style="display: none;">
        <h2 style="color: #667eea; margin-bottom: 20px;">🎴 Game Started!</h2>
        <div class="gameCode">
            Game ID: <strong id="gameId"></strong>
        </div>
        <div style="margin: 20px 0; font-size: 1.1em;">
            <p>Players: <strong id="playersList">-</strong></p>
            <p>Round: <strong id="roundNum">1</strong></p>
            <p>Current Player: <strong id="currentPlayer">-</strong></p>
        </div>
    </div>

    <div class="debug" id="debug">
        <div style="font-weight: bold; margin-bottom: 5px;">📋 Debug Console:</div>
        <div id="debugLog"></div>
        <button onclick="clearDebug()" style="margin-top: 10px; padding: 5px 10px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">Clear</button>
    </div>
</div>

<script>
    const socket = io();
    let debugLines = [];

    function addDebug(msg, type = 'info') {
        const ts = new Date().toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'});
        const line = `[${ts}] ${msg}`;
        debugLines.push({msg: line, type});
        if (debugLines.length > 50) debugLines.shift();
        updateDebugDisplay();
        console.log(line);
    }

    function updateDebugDisplay() {
        const logDiv = document.getElementById('debugLog');
        logDiv.innerHTML = debugLines.map(l => 
            `<div class="debug-line debug-${l.type}">${l.msg}</div>`
        ).join('');
        logDiv.scrollTop = logDiv.scrollHeight;
    }

    function clearDebug() {
        debugLines = [];
        updateDebugDisplay();
    }

    function switchTab(tab) {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
        document.getElementById(tab).classList.add('active');
        event.target.classList.add('active');
    }

    function createGame() {
        addDebug('📤 CreateGame clicked', 'info');
        const gameOptions = {
            numPlayers: parseInt(document.getElementById('optNumPlayers').value) || 4,
            numDecks: parseInt(document.getElementById('optNumDecks').value) || 1,
            gameMode: document.getElementById('optGameMode').value || 'continuous',
            runMax: parseInt(document.getElementById('optRunMax').value) || 5,
            twosWild: document.getElementById('optTwosWild').checked,
            blackThreesHigh: document.getElementById('optBlack3sHigh').checked,
            jackDiamondsHigh: document.getElementById('optJackDHigh').checked,
            wildsBeatMultis: document.getElementById('optWildsBeat').checked,
            twosWildInRuns: document.getElementById('opt2sInRuns').checked,
            bombsEnabled: document.getElementById('optBombs').checked
        };
        const myName = document.getElementById('playerName').value.trim();
        if (!myName) { 
            addDebug('❌ No name entered', 'error');
            alert('Enter your name');
            return; 
        }
        addDebug(`📤 Sending create event for: ${myName}`, 'info');
        document.getElementById('createBtn').disabled = true;
        document.getElementById('creatingMsg').style.display = 'block';
        socket.emit('create', { name: myName, options: gameOptions, table_id: '' });
        addDebug('📤 Create event emitted', 'info');
    }

    function joinGame() {
        const myName = document.getElementById('joinPlayerName').value.trim();
        const gameCode = document.getElementById('gameCode').value.trim();
        if (!myName || !gameCode) { 
            alert('Enter name and game code');
            return; 
        }
        document.getElementById('joinBtn').disabled = true;
        document.getElementById('joiningMsg').style.display = 'block';
        socket.emit('join', { name: myName, table_id: gameCode });
    }

    document.getElementById('soundToggle').addEventListener('change', function() {
        localStorage.setItem('soundEnabled', this.checked);
    });

    // Socket events
    socket.on('connect', () => {
        addDebug('✅ Connected to server', 'success');
    });

    socket.on('disconnect', () => {
        addDebug('❌ Disconnected from server', 'error');
    });

    socket.on('created', (data) => {
        addDebug(`✅ Created event received: ${data.game_id}`, 'success');
        document.getElementById('gameId').textContent = data.game_id;
    });

    socket.on('update', (data) => {
        addDebug('✅ Update event received', 'success');
        if (data.state) {
            addDebug(`📊 State: round ${data.state.round}, players: ${data.state.players.join(', ')}`, 'info');
            document.getElementById('roundNum').textContent = data.state.round || '1';
            document.getElementById('currentPlayer').textContent = data.state.currentplayer || '-';
            document.getElementById('playersList').textContent = (data.state.players || []).join(', ');
            document.getElementById('setupPhase').style.display = 'none';
            document.getElementById('gameArea').style.display = 'block';
            addDebug('✅ Game area displayed', 'success');
        }
    });

    socket.on('error', (msg) => {
        addDebug(`❌ Error: ${msg}`, 'error');
        alert('Error: ' + msg);
        document.getElementById('createBtn').disabled = false;
        document.getElementById('joinBtn').disabled = false;
    });

    socket.on('response', (data) => {
        addDebug(`📥 Response: ${JSON.stringify(data)}`, 'info');
    });

    addDebug('🎮 Game client loaded', 'success');
</script>
</body>
</html>"""

if __name__ == '__main__':
    log("="*70)
    log("President Card Game - DEBUG VERSION")
    log("="*70)
    log("Running on 0.0.0.0:8080")
    log("Health check: GET /health")
    log("Game: http://localhost:8080")
    log("="*70)
    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
