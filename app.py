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
    RANK_INDEX = {r: i+1 for i, r in enumerate(RANKS)}

    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def strength(self):
        """Get display strength (3=lowest, 2=highest)"""
        if self.rank == '3' and self.suit in ['♥', '♦']:
            return -100  # Red 3s lowest
        if self.rank == '2':
            return 1000  # 2s highest
        return self.RANK_STRENGTH.get(self.rank, 0)

    def rank_value(self, options):
        """Get play strength for game rules"""
        # Red 3s (Hearts, Diamonds) are LOWEST
        if self.rank == '3' and self.suit in ['♥', '♦']:
            return -100

        # Black 3s can be HIGH (if enabled)
        if options.get('blackThreesHigh') and self.rank == '3' and self.suit in ['♠', '♣']:
            return 1000

        # Jack of Diamonds HIGH (if enabled)
        if options.get('jackDiamondsHigh') and self.rank == 'J' and self.suit == '♦':
            return 1001

        # 2s wild: makes 2s high (if enabled)
        if options.get('twosWild') and self.rank == '2':
            return 999

        # Regular rank value
        return self.RANK_INDEX.get(self.rank, 0)

    def to_dict(self):
        return {'rank': self.rank, 'suit': self.suit, 'is_red': self.suit in ['♥', '♦']}

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
        """Sort player hand by card strength"""
        player['hand'].sort(key=lambda c: (c.strength(), Card.SUITS.index(c.suit)))

    def get_play_type(self, cards):
        """Get type of play and its value"""
        if not cards:
            return None, 0

        # Check SET (all same rank)
        if len(set(c.rank for c in cards)) == 1:
            card_value = cards[0].rank_value(self.options)
            return 'set', card_value

        # Check RUN (consecutive ranks)
        if len(cards) >= 3 and self.options.get('runMax', 5) > 0:
            indices = [Card.RANK_INDEX.get(c.rank, 0) for c in cards]
            indices.sort()

            # Check if consecutive
            is_consecutive = all(indices[i+1] == indices[i] + 1 for i in range(len(indices)-1))

            if is_consecutive and len(cards) <= self.options.get('runMax', 5):
                # Run value is highest card
                card_value = max(c.rank_value(self.options) for c in cards)
                return 'run', card_value

        return None, 0

    def is_valid_play(self, cards, last_play):
        """Check if cards are a valid play"""
        if not cards:
            return True  # Pass is always valid

        # BOMBS: Triple 6s beat anything
        if self.options.get('bombsEnabled') and len(cards) == 3:
            if all(c.rank == '6' for c in cards):
                return True

        if not last_play:
            # First play can be anything valid
            return self.get_play_type(cards) is not None

        play_type, play_value = self.get_play_type(cards)
        last_type, last_value = last_play

        if not play_type or play_type != last_type:
            return False

        if len(cards) != len(self.current_play):
            return False

        return play_value > last_value

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
        cards_to_play = data.get('cards', [])

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
                card = next((c for c in player['hand'] if c.rank == rank and c.suit == suit), None)
                if card:
                    player['hand'].remove(card)
                    cards_played.append(card)

        # Validate play
        last_play = game.get_play_type(game.current_play) if game.current_play else None
        if not game.is_valid_play(cards_played, last_play):
            # Invalid play, return cards
            for card in cards_played:
                player['hand'].append(card)
            socketio.emit('error', {'message': 'Invalid play'}, to=game_id)
            return

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

    hand = current_player['hand']
    last_play = game.get_play_type(game.current_play) if game.current_play else None

    # Find valid plays
    valid_plays = []

    if not last_play:
        # Opening: find pairs or low singles
        by_rank = {}
        for card in hand:
            if card.rank not in by_rank:
                by_rank[card.rank] = []
            by_rank[card.rank].append(card)

        # Prefer pairs
        for cards in by_rank.values():
            if len(cards) >= 2:
                valid_plays.append(cards[:2])

        # If no pairs, add singles
        if not valid_plays:
            for card in hand:
                valid_plays.append([card])
    else:
        # Find plays that beat
        play_type, _ = last_play

        if play_type == 'set':
            # Find sets that beat
            by_rank = {}
            for card in hand:
                if card.rank not in by_rank:
                    by_rank[card.rank] = []
                by_rank[card.rank].append(card)

            for cards in by_rank.values():
                if len(cards) >= len(game.current_play):
                    test_play = cards[:len(game.current_play)]
                    if game.is_valid_play(test_play, last_play):
                        valid_plays.append(test_play)

        # Single card options
        for card in hand:
            if game.is_valid_play([card], last_play):
                valid_plays.append([card])

    if valid_plays:
        play = random.choice(valid_plays)
    else:
        play = []

    # Execute play
    if play:
        for card in play:
            current_player['hand'].remove(card)
        game.current_play = play
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
