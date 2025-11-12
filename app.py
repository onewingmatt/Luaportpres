from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room
import secrets
from enum import Enum
import random
import time
import os
import json
import traceback

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}
SAVE_DIR = 'saved_games'
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

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

class ExchangeState(Enum):
    WAITING_PRESIDENT = 1
    WAITING_ASSHOLE = 2
    WAITING_VP = 3
    WAITING_VA = 4
    COMPLETE = 5

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
        self.finished_position = None
        self.passed = False

    def add_card(self, card):
        self.hand.append(card)
        self.hand.sort(key=lambda c: c.rank.value[0])

    def remove_card(self, card):
        if card in self.hand:
            self.hand.remove(card)
            return True
        return False

    def has_cards(self):
        return len(self.hand) > 0

def is_valid_meld(cards):
    if not cards or len(cards) == 0:
        return False, "No cards"
    if len(cards) > 5:
        return False, "Too many cards"
    if len(cards) == 1:
        return True, "SINGLE"
    ranks = [c.rank for c in cards]
    if all(r == ranks[0] for r in ranks):
        if len(cards) == 2:
            return True, "PAIR"
        elif len(cards) == 3:
            return True, "TRIPLE"
        elif len(cards) == 4:
            return True, "QUAD"
    if len(cards) >= 3:
        rank_values = sorted([c.rank.value[0] for c in cards])
        is_consecutive = all(rank_values[i] + 1 == rank_values[i+1] for i in range(len(rank_values)-1))
        if is_consecutive:
            return True, f"RUN({len(cards)})"
    return False, "Invalid meld"

def get_meld_type(cards):
    valid, mtype = is_valid_meld(cards)
    return mtype if valid else None

def compare_melds(played_meld, table_meld):
    ptype = get_meld_type(played_meld)
    ttype = get_meld_type(table_meld)
    if not ptype or not ttype or ptype != ttype:
        return False, "Invalid meld"
    if ptype == "SINGLE":
        if played_meld[0].rank.value[0] > table_meld[0].rank.value[0]:
            return True, "Valid"
        return False, "Too low"
    if ptype in ["PAIR", "TRIPLE", "QUAD"]:
        played_rank = max(c.rank.value[0] for c in played_meld)
        table_rank = max(c.rank.value[0] for c in table_meld)
        if played_rank > table_rank:
            return True, "Valid"
        return False, "Too low"
    if ptype.startswith("RUN"):
        if len(played_meld) != len(table_meld):
            return False, "Wrong length"
        played_min = min(c.rank.value[0] for c in played_meld)
        table_min = min(c.rank.value[0] for c in table_meld)
        if played_min > table_min:
            return True, "Valid"
        return False, "Too low"
    return False, "Unknown error"

class Game:
    def __init__(self, game_id):
        self.game_id = game_id
        self.players = {}
        self.player_order = []
        self.original_player_order = []
        self.current_player_idx = 0
        self.lead_player_idx = 0
        self.table_cards = []
        self.table_meld_type = None
        self.finished_count = 0
        self.state = 'waiting'
        self.round_num = 0
        self.exchange_state_enum = None
        self.cpu_playing = False

    def add_player(self, player_id, name, is_cpu=False):
        if len(self.players) >= 4:
            return False
        player = Player(player_id, name, is_cpu)
        self.players[player_id] = player
        return True

    def find_player_by_name(self, player_name):
        for player_id, player in self.players.items():
            if player.name.lower() == player_name.lower():
                return player_id, player
        return None, None

    def can_start(self):
        return len(self.players) >= 2

    def start_round(self, preserve_roles=False):
        self.round_num += 1
        if self.round_num == 1:
            deck = []
            for rank in Rank:
                for suit in Suit:
                    deck.append(Card(rank, suit))
            random.shuffle(deck)
            for player in self.players.values():
                player.hand = []
                player.finished_position = None
                player.passed = False
            self.player_order = list(self.players.keys())
            self.original_player_order = list(self.players.keys())
            for i, card in enumerate(deck):
                idx = i % len(self.player_order)
                self.players[self.player_order[idx]].add_card(card)
        else:
            for player in self.players.values():
                player.finished_position = None
                player.passed = False
            self.player_order = self.original_player_order.copy()

        if not preserve_roles:
            for p in self.players.values():
                p.role = 'Citizen'

        self.current_player_idx = 0
        self.lead_player_idx = 0
        self.table_cards = []
        self.table_meld_type = None
        self.finished_count = 0
        self.state = 'playing'
        self.cpu_playing = False

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
            'table': [str(c) for c in self.table_cards],
            'round': self.round_num,
            'players': [{
                'name': p.name,
                'cards': len(p.hand),
                'is_cpu': p.is_cpu,
            } for p in self.players.values()]
        }

@app.route('/')
def index():
    return render_template('president.html')

@socketio.on('connect')
def on_connect():
    pass

@socketio.on('create')
def on_create(data):
    gid = secrets.token_hex(4)
    name = data.get('name', 'Player')
    cpus = data.get('cpus', 2)

    game = Game(gid)
    game.add_player(request.sid, name, is_cpu=False)

    for i in range(cpus):
        cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
        game.add_player(cpu_id, f'CPU-{i+1}', is_cpu=True)

    if game.can_start():
        game.start_round()

    games[gid] = game
    join_room(gid)
    session['game_id'] = gid

    state = game.get_state()
    emit('created', {'game_id': gid, 'state': state})

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=8080)
