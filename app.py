from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import os
import random
import time

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

class Card:
    SUITS = ['♠', '♥', '♦', '♣']
    RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
    RANK_STRENGTH = {'3': 1, '4': 2, '5': 3, '6': 4, '7': 5, '8': 6, '9': 7, '10': 8, 'J': 9, 'Q': 10, 'K': 11, 'A': 12, '2': 13}

    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def strength(self):
        return self.RANK_STRENGTH.get(self.rank, 0)

    def to_dict(self):
        return {'rank': self.rank, 'suit': self.suit, 'is_red': self.suit in ['♥', '♦']}

    def matches(self, rank, suit):
        return self.rank == rank and self.suit == suit

class Game:
    def __init__(self, game_id, creator_name, options):
        self.id = game_id
        self.creator = creator_name
        self.options = options
        self.players = [{'name': creator_name, 'hand': [], 'is_cpu': False}]
        self.round = 1
        self.current_player_idx = 0
        self.current_play = []
        self.play_history = []
        self.deck = self.create_deck()
        self.game_started = False

        num_players = options.get('numPlayers', 4)
        for i in range(num_players - 1):
            self.players.append({'name': f'CPU {i+1}', 'hand': [], 'is_cpu': True})

    def create_deck(self):
        num_decks = self.options.get('numDecks', 1)
        deck = []
        for _ in range(num_decks):
            for suit in Card.SUITS:
                for rank in Card.RANKS:
                    deck.append(Card(rank, suit))
        random.shuffle(deck)
        return deck

    def deal_cards(self):
        cards_per_player = len(self.deck) // len(self.players)
        for player in self.players:
            player['hand'] = [self.deck.pop() for _ in range(cards_per_player)]
        self.game_started = True

    def sort_hand(self, player):
        """Sort player hand by strength"""
        player['hand'].sort(key=lambda c: (c.strength(), Card.SUITS.index(c.suit)))

    def get_state(self):
        current_player = self.players[self.current_player_idx]

        for p in self.players:
            self.sort_hand(p)

        return {
            'game_id': self.id,
            'round': self.round,
            'players': [{'name': p['name'], 'is_cpu': p['is_cpu'], 'hand_count': len(p['hand'])} for p in self.players],
            'currentplayer': current_player['name'],
            'current_player_idx': self.current_player_idx,
            'table': [c.to_dict() for c in self.current_play],
            'hands': {p['name']: [c.to_dict() for c in p['hand']] for p in self.players},
            'player_count': len(self.players),
            'game_started': self.game_started
        }

@app.route('/health')
def health():
    return 'OK', 200

@app.route('/')
def index():
    return render_template('president.html')

@socketio.on('connect')
def connect():
    emit('response', {'data': 'Connected'})

@socketio.on('disconnect')
def disconnect():
    pass

@socketio.on('create')
def create(data):
    try:
        name = str(data.get('name', 'Player')).strip()
        options = data.get('options', {})
        game_id = os.urandom(4).hex()
        join_room(game_id)

        game = Game(game_id, name, options)
        games[game_id] = game
        game.deal_cards()

        state = game.get_state()
        emit('created', {'game_id': game_id})
        socketio.emit('update', {'state': state}, to=game_id)

        if game.players[0]['is_cpu']:
            socketio.start_background_task(cpu_turn_handler, game_id)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('join')
def join(data):
    try:
        game_id = str(data.get('table_id', '')).strip()
        name = str(data.get('name', 'Player')).strip()

        if game_id not in games:
            raise ValueError("Game not found")

        game = games[game_id]
        if len(game.players) >= game.options.get('numPlayers', 4):
            raise ValueError("Game full")

        join_room(game_id)
        game.players.append({'name': name, 'hand': [], 'is_cpu': False})

        state = game.get_state()
        socketio.emit('update', {'state': state}, to=game_id)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('play_cards')
def play_cards(data):
    try:
        game_id = str(data.get('game_id', '')).strip()
        player_name = str(data.get('player_name', '')).strip()
        cards_to_play = data.get('cards', [])  # List of {rank, suit}

        if game_id not in games:
            return

        game = games[game_id]
        player = next((p for p in game.players if p['name'] == player_name), None)
        if not player:
            return

        # Find and remove cards from hand
        cards_played = []
        if cards_to_play:
            for card_data in cards_to_play:
                rank = card_data.get('rank')
                suit = card_data.get('suit')
                card = next((c for c in player['hand'] if c.matches(rank, suit)), None)
                if card:
                    player['hand'].remove(card)
                    cards_played.append(card)

        # Update table
        game.play_history.extend(cards_played)
        game.current_play = cards_played

        # Next player
        game.current_player_idx = (game.current_player_idx + 1) % len(game.players)

        state = game.get_state()
        socketio.emit('update', {'state': state}, to=game_id)

        if game.players[game.current_player_idx]['is_cpu']:
            socketio.start_background_task(cpu_turn_handler, game_id)
    except Exception as e:
        print(f"Error: {e}")

def cpu_turn_handler(game_id):
    """Handle CPU turn"""
    time.sleep(1.5)

    if game_id not in games:
        return

    game = games[game_id]
    current_player = game.players[game.current_player_idx]

    if not current_player['is_cpu']:
        return

    # CPU play logic
    if current_player['hand'] and random.random() < 0.7:
        num_to_play = min(random.randint(1, 3), len(current_player['hand']))
        cards_to_play = random.sample(current_player['hand'], num_to_play)
        for card in cards_to_play:
            current_player['hand'].remove(card)
            game.play_history.append(card)
            game.current_play.append(card)
    else:
        game.current_play = []

    # Next turn
    game.current_player_idx = (game.current_player_idx + 1) % len(game.players)

    state = game.get_state()
    with app.app_context():
        socketio.emit('update', {'state': state}, to=game_id)

    if game.players[game.current_player_idx]['is_cpu']:
        socketio.start_background_task(cpu_turn_handler, game_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
