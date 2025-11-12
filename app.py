from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import os
import time
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = 'president-secret'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

def log_msg(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

@app.route('/health')
def health():
    return {'status': 'ok'}, 200

@app.route('/')
def index():
    return render_template_string(html_content)

@socketio.on('connect')
def on_connect():
    log_msg(f"CLIENT CONNECTED: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    log_msg(f"CLIENT DISCONNECTED: {request.sid}")

@socketio.on('create')
def on_create(data):
    try:
        sid = request.sid
        name = data.get('name', 'Player').strip()
        options = data.get('options', {})

        if not name:
            raise ValueError("No name provided")

        game_id = os.urandom(4).hex()
        log_msg(f"CREATE: game_id={game_id}, player={name}")

        join_room(game_id)
        log_msg(f"CREATE: {sid} joined room {game_id}")

        games[game_id] = {
            'id': game_id,
            'creator': name,
            'players': [name],
            'options': options,
            'round': 1
        }
        log_msg(f"CREATE: Game stored")

        emit('created', {'game_id': game_id, 'success': True})
        log_msg(f"CREATE: Emitted 'created' event")

        state = {
            'game_id': game_id,
            'round': 1,
            'players': [name],
            'currentplayer': name
        }

        socketio.emit('update', {'state': state}, to=game_id)
        log_msg(f"CREATE: Emitted 'update' to room {game_id}")
        log_msg(f"✅ GAME STARTED: {game_id}")

    except Exception as e:
        log_msg(f"ERROR: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('join')
def on_join(data):
    try:
        sid = request.sid
        game_id = data.get('table_id', '').strip()
        name = data.get('name', 'Player').strip()

        log_msg(f"JOIN: {name} -> {game_id}")

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
        log_msg(f"✅ {name} joined {game_id}")

    except Exception as e:
        log_msg(f"ERROR: {str(e)}")
        emit('error', {'message': str(e)})

html_content = """<!DOCTYPE html>
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
        .setupPhase { background: white; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); padding: 40px; transition: all 0.3s; }
        .setupPhase.hidden { display: none !important; }
        .tabs { display: flex; border-bottom: 2px solid #eee; margin-bottom: 30px; gap: 20px; }
        .tab-btn { padding: 12px 30px; border: none; background: none; cursor: pointer; color: #667eea; font-weight: bold; border-bottom: 3px solid transparent; transition: all 0.3s; }
        .tab-btn.active { border-bottom-color: #667eea; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        input, select { width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 6px; margin-top: 5px; }
        .btn-primary { background: #667eea; color: white; padding: 15px 40px; width: 100%; margin-top: 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 1em; transition: all 0.3s; }
        .btn-primary:hover { background: #5568d3; }
        .btn-primary:disabled { background: #999; cursor: not-allowed; }
        .loadingMsg { text-align: center; color: #667eea; font-weight: bold; margin-top: 20px; font-size: 1.1em; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        .gameArea { background: white; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); padding: 40px; text-align: center; display: none !important; min-height: 400px; transition: all 0.3s; }
        .gameArea.active { display: block !important; }
        .gameCode { background: #f0f0f5; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .gameCode strong { color: #667eea; font-size: 1.3em; }
        .gameInfo { margin: 30px 0; font-size: 1.1em; }
        .gameInfo p { margin: 10px 0; }
        .debugPanel { background: #1a1a1a; color: #0f0; border: 2px solid #0f0; border-radius: 8px; padding: 15px; margin-top: 20px; font-family: monospace; font-size: 0.85em; max-height: 300px; overflow-y: auto; }
        .debugPanel h3 { color: #0f0; margin-bottom: 10px; }
        .debugLine { margin: 3px 0; padding: 2px; }
        .debug-success { color: #0f0; }
        .debug-error { color: #ff6b6b; }
        .debug-info { color: #00ffff; }
        .debug-btn { background: #333; color: #0f0; border: 1px solid #0f0; padding: 5px 10px; margin-top: 10px; cursor: pointer; font-family: monospace; border-radius: 4px; }
        .debug-btn:hover { background: #0f0; color: #000; }
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

    <div class="gameArea" id="gameArea">
        <h2 style="color: #667eea; margin-bottom: 20px;">🎴 Game Started!</h2>
        <div class="gameCode">
            Game ID: <strong id="gameId">-</strong>
        </div>
        <div class="gameInfo">
            <p>Players: <strong id="playersList">-</strong></p>
            <p>Round: <strong id="roundNum">1</strong></p>
            <p>Current Player: <strong id="currentPlayer">-</strong></p>
        </div>
    </div>

    <div class="debugPanel">
        <h3>📋 Debug Console (Last 30 events)</h3>
        <div id="debugLog"></div>
        <button class="debug-btn" onclick="clearDebug()">Clear</button>
        <button class="debug-btn" onclick="toggleDebug()">Toggle Details</button>
    </div>
</div>

<script>
    const socket = io();
    let debugLogs = [];
    let debugVerbose = false;

    function addDebug(msg, type = 'info') {
        const ts = new Date().toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'});
        const line = `[${ts}] ${msg}`;
        debugLogs.push({line, type});
        if (debugLogs.length > 30) debugLogs.shift();
        updateDebugDisplay();
        console.log(line);
    }

    function updateDebugDisplay() {
        const box = document.getElementById('debugLog');
        box.innerHTML = debugLogs.map(l => 
            `<div class="debugLine debug-${l.type}">${l.line}</div>`
        ).join('');
        box.scrollTop = box.scrollHeight;
    }

    function clearDebug() {
        debugLogs = [];
        updateDebugDisplay();
    }

    function toggleDebug() {
        debugVerbose = !debugVerbose;
        addDebug(`Debug verbose: ${debugVerbose ? 'ON' : 'OFF'}`, 'info');
    }

    function switchTab(tab) {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
        document.getElementById(tab).classList.add('active');
        event.target.classList.add('active');
    }

    function createGame() {
        addDebug('► CreateGame clicked', 'info');
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
            alert('Please enter your name');
            return; 
        }
        addDebug(`📤 Emitting create: ${myName}`, 'info');
        document.getElementById('createBtn').disabled = true;
        document.getElementById('creatingMsg').style.display = 'block';
        socket.emit('create', { name: myName, options: gameOptions, table_id: '' });
    }

    function joinGame() {
        const myName = document.getElementById('joinPlayerName').value.trim();
        const gameCode = document.getElementById('gameCode').value.trim();
        if (!myName || !gameCode) { 
            alert('Please enter your name and game code');
            return; 
        }
        document.getElementById('joinBtn').disabled = true;
        document.getElementById('joiningMsg').style.display = 'block';
        socket.emit('join', { name: myName, table_id: gameCode });
    }

    document.getElementById('soundToggle').addEventListener('change', function() {
        localStorage.setItem('soundEnabled', this.checked);
    });

    window.addEventListener('load', function() {
        const saved = localStorage.getItem('soundEnabled');
        if (saved !== null) {
            document.getElementById('soundToggle').checked = saved === 'true';
        }
    });

    socket.on('connect', () => {
        addDebug('✅ Connected to server', 'success');
    });

    socket.on('disconnect', () => {
        addDebug('❌ Disconnected from server', 'error');
    });

    socket.on('created', (data) => {
        addDebug(`✅ 'created' event: ${data.game_id}`, 'success');
        document.getElementById('gameId').textContent = data.game_id;
    });

    socket.on('update', (data) => {
        if (data.state) {
            addDebug(`✅ 'update' event received`, 'success');
            document.getElementById('playersList').textContent = (data.state.players || []).join(', ');
            document.getElementById('roundNum').textContent = data.state.round || '1';
            document.getElementById('currentPlayer').textContent = data.state.currentplayer || '-';

            // FORCE display
            document.getElementById('setupPhase').classList.add('hidden');
            document.getElementById('gameArea').classList.add('active');
            addDebug('✅ Game area now visible', 'success');
        }
    });

    socket.on('error', (data) => {
        addDebug(`❌ Error: ${data.message || data}`, 'error');
        alert('Error: ' + (data.message || data));
        document.getElementById('createBtn').disabled = false;
        document.getElementById('joinBtn').disabled = false;
        document.getElementById('creatingMsg').style.display = 'none';
        document.getElementById('joiningMsg').style.display = 'none';
    });

    addDebug('🎮 Game client loaded', 'success');
</script>
</body>
</html>"""

if __name__ == '__main__':
    log_msg("="*70)
    log_msg("President Card Game Server")
    log_msg("="*70)
    log_msg("Running on 0.0.0.0:8080")
    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
