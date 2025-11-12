from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import os
import random
from collections import defaultdict

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

class Card:
    SUITS = ['♠', '♥', '♦', '♣']
    RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
    RANK_VALUES = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15}

    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def to_dict(self):
        return {'rank': self.rank, 'suit': self.suit}

class Game:
    def __init__(self, game_id, creator_name, options):
        self.id = game_id
        self.creator = creator_name
        self.options = options
        self.players = [{'name': creator_name, 'hand': [], 'score': 0, 'status': 'playing'}]
        self.round = 1
        self.current_player_idx = 0
        self.table = []
        self.deck = self.create_deck()
        self.game_started = False

    def create_deck(self):
        num_decks = self.options.get('numDecks', 1)
        deck = []
        for _ in range(num_decks):
            for suit in Card.SUITS:
                for rank in Card.RANKS:
                    deck.append(Card(rank, suit))
        random.shuffle(deck)
        return deck

    def add_player(self, name):
        if len(self.players) >= self.options.get('numPlayers', 4):
            return False
        self.players.append({'name': name, 'hand': [], 'score': 0, 'status': 'playing'})
        return True

    def deal_cards(self):
        cards_per_player = len(self.deck) // len(self.players)
        for i, player in enumerate(self.players):
            player['hand'] = [self.deck.pop() for _ in range(cards_per_player)]
        self.game_started = True

    def get_state(self):
        current_player = self.players[self.current_player_idx]
        return {
            'game_id': self.id,
            'round': self.round,
            'players': [p['name'] for p in self.players],
            'currentplayer': current_player['name'],
            'current_player_idx': self.current_player_idx,
            'table': [c.to_dict() for c in self.table],
            'hands': {p['name']: [c.to_dict() for c in p['hand']] for p in self.players},
            'player_count': len(self.players),
            'game_started': self.game_started
        }

    def get_player_state(self, player_name):
        player = next((p for p in self.players if p['name'] == player_name), None)
        state = self.get_state()
        if player:
            state['my_hand'] = [c.to_dict() for c in player['hand']]
        return state

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

        state = game.get_state()
        emit('created', {'game_id': game_id})
        socketio.emit('update', {'state': state}, to=game_id)
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
        if not game.add_player(name):
            raise ValueError("Game full")

        join_room(game_id)
        state = game.get_state()
        socketio.emit('update', {'state': state}, to=game_id)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('start_game')
def start_game(data):
    try:
        game_id = str(data.get('game_id', '')).strip()
        if game_id not in games:
            raise ValueError("Game not found")

        game = games[game_id]
        if len(game.players) < 2:
            raise ValueError("Need at least 2 players")

        game.deal_cards()
        state = game.get_state()
        socketio.emit('game_started', {'state': state}, to=game_id)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('play_cards')
def play_cards(data):
    try:
        game_id = str(data.get('game_id', '')).strip()
        player_name = str(data.get('player_name', '')).strip()
        card_indices = data.get('card_indices', [])

        if game_id not in games:
            raise ValueError("Game not found")

        game = games[game_id]
        player = next((p for p in game.players if p['name'] == player_name), None)
        if not player:
            raise ValueError("Player not found")

        # Play cards
        cards = [player['hand'][i] for i in sorted(card_indices, reverse=True) if i < len(player['hand'])]
        for card in cards:
            player['hand'].remove(card)
            game.table.append(card)

        # Move to next player
        game.current_player_idx = (game.current_player_idx + 1) % len(game.players)

        state = game.get_state()
        socketio.emit('update', {'state': state}, to=game_id)
    except Exception as e:
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
