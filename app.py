from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room
import secrets
from enum import Enum
import random
import time
import os
import json
import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

games = {}
SAVE_DIR = 'saved_games'
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# ============================================================================
# ENUMS & CLASSES
# ============================================================================

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

# ============================================================================
# GAME OPTIONS - FROM TIC-80
# ============================================================================

def get_default_options():
    """Return default game options matching TIC-80 version."""
    return {
        "nplayers": 4,
        "num_decks": 1,
        "clear_with_2": False,
        "twos_wild": True,
        "twos_wild_in_run": False,
        "bombs": True,
        "run_max": 5,
        "black_3_high": True,
        "jack_diamonds_high": True,
        "wilds_beat_multis": True,
        "continuous_mode": "ON"
    }

# ============================================================================
# RANK VALUE FUNCTION - PRIORITY: Red 3 (LOWEST) < normal < Black 3 < JD
# ============================================================================

def rank_value(rank, suit="", game_options=None):
    """Calculate rank value considering game options."""
    if game_options is None:
        game_options = {}

    # Extract string values from Enums if needed
    rank_str = rank.value[1] if hasattr(rank, 'value') else str(rank)
    suit_str = suit.value if hasattr(suit, 'value') else str(suit)

    # Red 3s (Hearts, Diamonds) are LOWEST
    if rank_str == "3" and suit_str in ["♥", "♦"]:
        return -100

    # Black 3s can be made HIGH
    if game_options.get("black_3_high", False) and rank_str == "3" and suit_str in ["♠", "♣"]:
        return 50

    # Jack of Diamonds can be made HIGH
    if game_options.get("jack_diamonds_high", False) and rank_str == "J" and suit_str == "♦":
        return 100

    # Base rank ordering
    rank_order = {"3": 1, "4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7,
                  "10": 8, "J": 9, "Q": 10, "K": 11, "A": 12, "2": 13}
    base_val = rank_order.get(rank_str, 0)

    # 2s wild: makes 2s highest
    if game_options.get("twos_wild", False) and rank_str == "2":
        return 14

    return base_val

# ============================================================================
# MELD VALIDATION
# ============================================================================

def is_valid_meld(cards, game_options=None):
    """Check if cards form a valid meld. Returns (is_valid, meld_type_str)"""
    if game_options is None:
        game_options = {}

    if not cards or len(cards) == 0:
        return False, "No cards"

    if len(cards) > 5:
        return False, "Too many cards (max 5)"

    # BOMB CHECK (triple 6s) - must come first!
    if game_options.get("bombs", True) and len(cards) == 3:
        if all(c.rank == Rank.SIX for c in cards):
            return True, "BOMB"

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
        else:
            return False, "Invalid same-rank meld"

    # Run check - respect run_max
    if len(cards) >= 3:
        run_max = game_options.get("run_max", 5)
        if run_max == 0 or len(cards) > run_max:
            return False, f"Run too long (max {run_max})"

        rank_values = sorted([c.rank.value[0] for c in cards])
        is_consecutive = all(rank_values[i] + 1 == rank_values[i+1] for i in range(len(rank_values)-1))

        if is_consecutive:
            return True, f"RUN({len(cards)})"

    return False, "Invalid meld"

def get_meld_type(cards, game_options=None):
    """Get the type of meld. Returns None if invalid."""
    valid, mtype = is_valid_meld(cards, game_options)
    return mtype if valid else None

def compare_melds(played_meld, table_meld, game_options=None):
    """Check if played_meld beats table_meld. Returns (is_valid, reason_str)"""
    if game_options is None:
        game_options = {}

    ptype = get_meld_type(played_meld, game_options)
    ttype = get_meld_type(table_meld, game_options)

    if not ptype or not ttype:
        return False, "Invalid meld format"

    if ptype != ttype:
        return False, f"Meld type mismatch: {ptype} vs {ttype}"

    # ===== WILDS BEAT MULTIS LOGIC =====
    if game_options.get("wilds_beat_multis", False):
        # Single 3 beats ANYTHING
        if len(played_meld) == 1 and played_meld[0].rank == Rank.THREE:
            return True, "Single 3 beats anything"

        # Multiple 3s beat anything
        if all(c.rank == Rank.THREE for c in played_meld) and len(played_meld) > 1:
            return True, "Multiple 3s beat anything"

        # Single 2 beats runs and pairs
        if len(played_meld) == 1 and played_meld[0].rank == Rank.TWO:
            if ptype.startswith("RUN"):
                return True, "2 beats run"
            if ptype in ["PAIR", "SINGLE"]:
                return True, "2 beats pair/single"

        # Pair of 2s beats triple
        if len(played_meld) == 2 and all(c.rank == Rank.TWO for c in played_meld):
            if ttype == "TRIPLE":
                return True, "Pair of 2s beats triple"

    # ===== STANDARD COMPARISON =====
    if ptype == "SINGLE":
        played_rank = rank_value(played_meld[0].rank, played_meld[0].suit, game_options)
        table_rank = rank_value(table_meld[0].rank, table_meld[0].suit, game_options)

        if played_rank > table_rank:
            return True, "Valid single"
        else:
            return False, "Card must be higher rank"

    if ptype in ["PAIR", "TRIPLE", "QUAD"]:
        played_rank = max(rank_value(c.rank, c.suit, game_options) for c in played_meld)
        table_rank = max(rank_value(c.rank, c.suit, game_options) for c in table_meld)

        if played_rank > table_rank:
            return True, f"Valid {ptype}"
        else:
            return False, f"{ptype} must be higher rank"

    if ptype.startswith("RUN"):
        if len(played_meld) != len(table_meld):
            return False, f"Run must be same length: {len(table_meld)} cards"

        played_min = min(rank_value(c.rank, c.suit, game_options) for c in played_meld)
        table_min = min(rank_value(c.rank, c.suit, game_options) for c in table_meld)

        if played_min > table_min:
            return True, f"Valid RUN({len(played_meld)})"
        else:
            return False, f"Run must start with higher card"

    return False, "Unknown error"

# ============================================================================
# GAME CLASS - WITH OPTIONS
# ============================================================================

class Game:
    def __init__(self, game_id, options=None):
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
        self.pending_exchanges = {}
        self.human_player_id = None
        self.cpu_playing = False
        self.exchanges_complete = False
        self._showing_2 = False

        # GAME OPTIONS FROM TIC-80
        self.options = get_default_options()
        if options:
            self.options.update(options)

    def add_player(self, player_id, name, is_cpu=False):
        if len(self.players) >= 8:  # Support up to 8 players now
            return False
        player = Player(player_id, name, is_cpu)
        self.players[player_id] = player
        if not is_cpu:
            self.human_player_id = player_id
        return True

    def find_player_by_name(self, player_name):
        for player_id, player in self.players.items():
            if player.name.lower() == player_name.lower():
                return player_id, player
        return None, None

    def rejoin_player(self, old_player_id, new_player_id, name):
        old_player = self.players.get(old_player_id)
        if not old_player or old_player_id not in self.original_player_order:
            return False

        print(f"[REJOIN] {name} rejoining: {old_player_id} -> {new_player_id}")
        old_player.player_id = new_player_id
        old_player.is_cpu = False
        self.players[new_player_id] = old_player
        del self.players[old_player_id]

        pos = self.original_player_order.index(old_player_id)
        self.original_player_order[pos] = new_player_id

        if old_player_id in self.player_order:
            pos = self.player_order.index(old_player_id)
            self.player_order[pos] = new_player_id

        self.human_player_id = new_player_id
        return True

    def cleanup_player_order(self):
        before = self.player_order.copy()
        removed_count = 0
        for i in range(min(self.current_player_idx, len(self.player_order))):
            if i < len(self.player_order) and self.player_order[i] not in self.players:
                removed_count += 1

        self.player_order = [pid for pid in self.player_order if pid in self.players]
        if removed_count > 0:
            self.current_player_idx = max(0, self.current_player_idx - removed_count)

        if before != self.player_order:
            print(f"[CLEANUP] player_order: {before} -> {self.player_order}")

    def can_start(self):
        return len(self.players) >= 2

    def start_round(self, preserve_roles=False):
        self.round_num += 1

        if self.round_num == 1:
            # Build deck based on num_decks option
            num_decks = self.options.get("num_decks", 1)
            deck = []
            for _ in range(num_decks):
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

            print(f"[START] Original seating: {[self.players[pid].name for pid in self.original_player_order]}")

            for i, card in enumerate(deck):
                idx = i % len(self.player_order)
                self.players[self.player_order[idx]].add_card(card)
        else:
            for player in self.players.values():
                player.finished_position = None
                player.passed = False

            self.player_order = self.original_player_order.copy()

        self.current_player_idx = 0
        self.table_cards = []
        self.table_meld_type = None
        self.state = 'playing'
        self.exchange_state_enum = None
        self.exchanges_complete = False

    def get_current_player(self):
        if 0 <= self.current_player_idx < len(self.player_order):
            pid = self.player_order[self.current_player_idx]
            return self.players.get(pid)
        return None

    def pass_turn(self, player_id):
        return {'success': True}

    def play_cards(self, player_id, card_displays):
        player = self.players.get(player_id)
        if not player:
            return {'ok': False, 'msg': 'Player not found'}

        cards = []
        for display in card_displays:
            found = None
            for c in player.hand:
                if str(c) == display:
                    found = c
                    break
            if not found:
                return {'ok': False, 'msg': f'Card {display} not found'}
            cards.append(found)

        if not cards:
            return {'ok': False, 'msg': 'No cards selected'}

        # Validate meld
        valid, mtype = is_valid_meld(cards, self.options)
        if not valid:
            return {'ok': False, 'msg': f'Invalid meld: {mtype}'}

        # Check if beats table
        if self.table_cards:
            valid_beat, reason = compare_melds(cards, self.table_cards, self.options)
            if not valid_beat:
                return {'ok': False, 'msg': reason}

        # Remove cards from hand
        for card in cards:
            player.remove_card(card)

        # Update table
        self.table_cards = cards
        self.table_meld_type = mtype

        return {'ok': True}

    def to_dict(self):
        return {
            'game_id': self.game_id,
            'options': self.options,
            'players': [{
                'player_id': p.player_id,
                'name': p.name,
                'is_cpu': p.is_cpu,
                'hand': [str(card) for card in p.hand],
                'role': p.role,
                'finished_position': p.finished_position,
                'passed': p.passed,
            } for p in self.players.values()],
            'player_order': self.player_order,
            'original_player_order': self.original_player_order,
            'current_player_idx': self.current_player_idx,
            'lead_player_idx': self.lead_player_idx,
            'table_cards': [str(c) for c in self.table_cards],
            'table_meld_type': self.table_meld_type,
            'finished_count': self.finished_count,
            'state': self.state,
            'round_num': self.round_num,
            'exchange_state': None,
            'pending_exchanges': {},
            'exchanges_complete': self.exchanges_complete,
        }

    @classmethod
    def from_dict(cls, data):
        game = cls(data['game_id'], options=data.get('options'))
        game.players = {}
        for pdata in data['players']:
            p = Player(pdata['player_id'], pdata['name'], pdata['is_cpu'])
            p.hand = [Card.from_str(c) for c in pdata['hand']]
            p.role = pdata['role']
            p.finished_position = pdata['finished_position']
            p.passed = pdata['passed']
            game.players[p.player_id] = p

        game.player_order = data['player_order']
        game.original_player_order = data.get('original_player_order', [])
        game.current_player_idx = data['current_player_idx']
        game.cleanup_player_order()
        game.lead_player_idx = data['lead_player_idx']
        game.table_cards = [Card.from_str(c) for c in data['table_cards']]
        game.table_meld_type = data.get('table_meld_type')
        game.finished_count = data['finished_count']
        game.state = data['state']
        game.round_num = data['round_num']
        game.exchange_state_enum = None
        game.pending_exchanges = {}
        game.exchanges_complete = data['exchanges_complete']
        game.cpu_playing = False
        game._showing_2 = False

        return game

    def get_state(self):
        current = self.get_current_player()
        lead_player = None
        if self.lead_player_idx < len(self.player_order):
            lead_pid = self.player_order[self.lead_player_idx]
            lead_player = self.players.get(lead_pid)

        state = {
            'game_id': self.game_id,
            'state': self.state,
            'exchange_state': None,
            'current_player': current.name if current else None,
            'current_is_cpu': current.is_cpu if current else False,
            'lead_player': lead_player.name if lead_player else None,
            'table': [str(c) for c in self.table_cards],
            'table_meld_type': self.table_meld_type,
            'round': self.round_num,
            'options': self.options,  # SEND OPTIONS TO FRONTEND
            'players': []
        }

        for p in self.players.values():
            pdata = {
                'id': p.player_id,
                'name': p.name,
                'role': p.role,
                'cards': len(p.hand),
                'is_cpu': p.is_cpu,
                'finished': p.finished_position,
                'hand': [str(c) for c in p.hand]
            }
            state['players'].append(pdata)

        return state

def save_game_to_disk(game):
    try:
        filename = f'{SAVE_DIR}/save_{game.game_id}.json'
        with open(filename, 'w') as f:
            json.dump(game.to_dict(), f, indent=2)
    except Exception as e:
        print(f"[SAVE ERROR] {e}")

def load_game_from_disk(game_id):
    try:
        filename = f'{SAVE_DIR}/save_{game_id}.json'
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
            return Game.from_dict(data)
    except Exception as e:
        print(f"[LOAD ERROR] {e}")
    return None

# ============================================================================
# VALID PLAYS / CPU
# ============================================================================

def get_valid_plays(player, table_meld_type, table_cards, game_options=None):
    """Generate all valid plays for CPU."""
    if game_options is None:
        game_options = {}

    plays = []

    if not table_cards:
        # No cards on table - generate opening plays
        all_ranks = set(c.rank for c in player.hand)
        for card in player.hand:
            plays.append([card])

        for rank in all_ranks:
            matching = [c for c in player.hand if c.rank == rank]
            if len(matching) >= 2:
                plays.append(matching[:2])
            if len(matching) >= 3:
                plays.append(matching[:3])
            if len(matching) >= 4:
                plays.append(matching[:4])

        # Runs
        run_max = game_options.get("run_max", 5)
        if run_max > 0:
            sorted_cards = sorted(player.hand, key=lambda c: c.rank.value[0])
            for run_length in range(3, min(run_max + 1, 6)):
                for i in range(len(sorted_cards) - run_length + 1):
                    run = sorted_cards[i:i+run_length]
                    is_run = all(run[j].rank.value[0] + 1 == run[j+1].rank.value[0]
                                for j in range(len(run)-1))
                    if is_run:
                        plays.append(run)
    else:
        # Cards on table - match or beat
        table_rank = table_cards[0].rank
        table_count = len(table_cards)

        if table_meld_type == "SINGLE":
            for card in player.hand:
                if rank_value(card.rank, card.suit, game_options) > rank_value(table_rank, table_cards[0].suit, game_options):
                    plays.append([card])
        elif table_meld_type in ["PAIR", "TRIPLE", "QUAD"]:
            all_ranks = set(c.rank for c in player.hand)
            for rank in all_ranks:
                matching = [c for c in player.hand if c.rank == rank]
                if len(matching) >= table_count:
                    meld = matching[:table_count]
                    if rank_value(rank, meld[0].suit, game_options) > rank_value(table_rank, table_cards[0].suit, game_options):
                        plays.append(meld)
        elif table_meld_type and table_meld_type.startswith("RUN"):
            sorted_cards = sorted(player.hand, key=lambda c: rank_value(c.rank, c.suit, game_options))
            for i in range(len(sorted_cards) - table_count + 1):
                run = sorted_cards[i:i+table_count]
                is_run = all(run[j].rank.value[0] + 1 == run[j+1].rank.value[0]
                            for j in range(len(run)-1))
                if is_run:
                    run_min = min(c.rank.value[0] for c in run)
                    table_min = min(c.rank.value[0] for c in table_cards)
                    if run_min > table_min:
                        plays.append(run)

    return plays

# ============================================================================
# SOCKET HANDLERS
# ============================================================================

@app.route('/')
def index():
    return render_template('president.html')

@socketio.on('connect')
def on_connect():
    pass

@socketio.on('create')
def on_create(data):
    name = data.get('name', 'Player')
    cpus = data.get('cpus', 2)
    custom_table_id = data.get('table_id', None)

    # EXTRACT GAME OPTIONS FROM FRONTEND
    game_options = {
        'nplayers': int(data.get('nplayers', 4)),
        'num_decks': int(data.get('num_decks', 1)),
        'clear_with_2': bool(data.get('clear_with_2', False)),
        'twos_wild': bool(data.get('twos_wild', True)),
        'twos_wild_in_run': bool(data.get('twos_wild_in_run', False)),
        'bombs': bool(data.get('bombs', True)),
        'run_max': int(data.get('run_max', 5)),
        'black_3_high': bool(data.get('black_3_high', True)),
        'jack_diamonds_high': bool(data.get('jack_diamonds_high', True)),
        'wilds_beat_multis': bool(data.get('wilds_beat_multis', True)),
        'continuous_mode': str(data.get('continuous_mode', 'ON'))
    }

    if custom_table_id and custom_table_id.strip():
        gid = custom_table_id.strip().lower()
    else:
        gid = secrets.token_hex(4)

    if gid in games:
        emit('error', {'msg': f'Game {gid} already exists'})
        return

    game = Game(gid, options=game_options)
    game.add_player(request.sid, name, is_cpu=False)

    for i in range(cpus):
        cpu_id = f'cpu_{i}_{secrets.token_hex(2)}'
        game.add_player(cpu_id, f'CPU-{i+1}', is_cpu=True)

    games[gid] = game
    join_room(gid)

    print(f"[CREATE] Game {gid} created by {name}")
    print(f"[OPTIONS] {game_options}")

    emit('game_created', {
        'game_id': gid,
        'state': game.get_state()
    })

@socketio.on('start')
def on_start(data):
    gid = data.get('game_id')
    game = games.get(gid)

    if not game:
        emit('error', {'msg': f'Game {gid} not found'})
        return

    if not game.can_start():
        emit('error', {'msg': 'Not enough players'})
        return

    game.start_round()
    socketio.emit('state', game.get_state(), room=gid)
    print(f"[START] Game {gid} started with options: {game.options}")

@socketio.on('play')
def on_play(data):
    gid = data.get('game_id')
    cards = data.get('cards', [])
    game = games.get(gid)

    if not game:
        emit('error', {'msg': 'Game not found'})
        return

    player = game.players.get(request.sid)
    if not player:
        emit('error', {'msg': 'Player not found'})
        return

    result = game.play_cards(request.sid, cards)
    socketio.emit('state', game.get_state(), room=gid)

@socketio.on('pass')
def on_pass(data):
    gid = data.get('game_id')
    game = games.get(gid)

    if not game:
        emit('error', {'msg': 'Game not found'})
        return

    socketio.emit('state', game.get_state(), room=gid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
