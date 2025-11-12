from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room
import secrets
import os
from enum import Enum
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}

class Rank(Enum):
    THREE = (3, '3')
    FOUR = (4, '4')
    FIVE = (5, '5')
    SIX = (6, '6')
    SEVEN = (7, '7')
    EIGHT = (8, '8')
    NINE = (9, '9')
    TEN = (10, '10')
    JACK = (11, 'J')
    QUEEN = (12, 'Q')
    KING = (13, 'K')
    ACE = (14, 'A')
    TWO = (15, '2')

class Suit(Enum):
    SPADES = '♠'
    HEARTS = '♥'
    DIAMONDS = '♦'
    CLUBS = '♣'

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.display = f"{rank.value[1]}{suit.value}"

    def __repr__(self):
        return self.display

    @staticmethod
    def from_str(card_str):
        suit_map = {'♠': Suit.SPADES, '♥': Suit.HEARTS, '♦': Suit.DIAMONDS, '♣': Suit.CLUBS}
        rank_map = {'3': Rank.THREE, '4': Rank.FOUR, '5': Rank.FIVE, '6': Rank.SIX, '7': Rank.SEVEN,
                    '8': Rank.EIGHT, '9': Rank.NINE, '10': Rank.TEN, 'J': Rank.JACK, 'Q': Rank.QUEEN,
                    'K': Rank.KING, 'A': Rank.ACE, '2': Rank.TWO}
        suit_char = card_str[-1]
        rank_str = card_str[:-1]
        return Card(rank_map[rank_str], suit_map[suit_char])

class Player:
    def __init__(self, player_id, name, is_cpu=False):
        self.player_id = player_id
        self.name = name
        self.is_cpu = is_cpu
        self.hand = []
        self.role = 'Citizen'
        self.finished = False

    def add_card(self, card):
        self.hand.append(card)
        self.hand.sort(key=lambda c: c.rank.value[0])

    def has_cards(self):
        return len(self.hand) > 0

class Game:
    def __init__(self, game_id):
        self.game_id = game_id
        self.players = {}
        self.player_order = []
        self.current_player_idx = 0
        self.state = 'waiting'
        self.round_num = 0

    def add_player(self, player_id, name, is_cpu=False):
        if len(self.players) >= 4:
            return False
        player = Player(player_id, name, is_cpu)
        self.players[player_id] = player
        return True

    def can_start(self):
        return len(self.players) >= 2

    def start_round(self):
        self.round_num += 1
        deck = []
        for rank in Rank:
            for suit in Suit:
                deck.append(Card(rank, suit))
        random.shuffle(deck)

        for player in self.players.values():
            player.hand = []
            player.finished = False

        self.player_order = list(self.players.keys())
        for i, card in enumerate(deck):
            idx = i % len(self.player_order)
            self.players[self.player_order[idx]].add_card(card)

        self.current_player_idx = 0
        self.state = 'playing'

    def get_current_player(self):
        if not self.player_order or self.current_player_idx >= len(self.player_order):
            return None
        current_id = self.player_order[self.current_player_idx]
        return self.players.get(current_id)

    def get_state(self):
        current = self.get_current_player()
        return {
            'game_id': self.game_id,
            'state': self.state,
            'current_player': current.name if current else None,
            'round': self.round_num,
            'players': [{
                'name': p.name,
                'cards': len(p.hand),
                'is_cpu': p.is_cpu,
            } for p in self.players.values()]
        }

@app.route('/')
def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'president.html')
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return '<h1>HTML file not found</h1>'

@socketio.on('connect')
def on_connect():
    pass

@socketio.on('create_game')
def on_create_game(data):
    try:
        game_id = secrets.token_hex(4)
        player_name = data.get('name', 'Player')
        num_cpus = data.get('cpus', 2)

        game = Game(game_id)
        game.add_player(request.sid, player_name, is_cpu=False)

        for i in range(num_cpus):
            cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
            game.add_player(cpu_id, f'CPU-{i+1}', is_cpu=True)

        games[game_id] = game
        join_room(game_id)
        session['game_id'] = game_id

        emit('game_created', {'game_id': game_id, 'state': game.get_state()})
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('start_game')
def on_start_game():
    try:
        game_id = session.get('game_id')
        if not game_id or game_id not in games:
            emit('error', {'message': 'No game'})
            return

        game = games[game_id]
        if game.can_start():
            game.start_round()
            emit('game_started', {'state': game.get_state()}, room=game_id)
        else:
            emit('error', {'message': 'Not enough players'})
    except Exception as e:
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=8080)
