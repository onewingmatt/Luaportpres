# President Card Game - Web Version with Full Options

A multiplayer card game implementation with comprehensive game options ported from the TIC-80 version.

## Features

### Game Options (All Configurable)
- **Players**: 3-8 players support
- **Decks**: 1-2 deck options
- **Run Max**: 0-7 card run length limit
- **2s Wild**: Toggle wild card option
- **Black 3s High**: Make black 3s rank above normal
- **Jack of Diamonds High**: Make JD rank above normal
- **Bombs**: Triple 6s clear table instantly
- **Wilds Beat Multis**: Special rules for wild card precedence
- **Clear with 2s**: Allow 2s to clear the table
- **2s in Runs**: Allow 2s as wild cards in runs
- **Continuous Mode**: ON/OFF for round continuation

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py

# Access at http://localhost:8080
```

## Deployment to Fly.io

```bash
# Login to Fly
flyctl auth login

# Deploy
flyctl deploy -a presidentfly

# Or with custom app name
flyctl deploy --config fly.toml
```

## Game Options Integration

All options from TIC-80 version are now integrated:
- Options UI on game creation screen
- Options sent to backend and stored in Game instance
- Options affect card validation (rank_value, bombs, run limits)
- Options sent to frontend for reference

### Option Examples

**High-Value Ranks (when enabled):**
- Red 3s: -100 (lowest)
- Normal 3-A: 1-12
- Black 3s (if enabled): 50
- 2s (if wild): 14
- JD (if enabled): 100

**Bombs:**
- Triple 6s can beat anything (if enabled)
- Clears table immediately

**Run Max:**
- 0 = Runs disabled
- 3-7 = Max cards in a run

## Code Structure

```
├── app.py                 # Flask + SocketIO backend with game logic
├── templates/
│   └── president.html     # Web UI with options form
├── requirements.txt       # Python dependencies
├── fly.toml              # Fly.io configuration
├── Dockerfile            # Container config
└── saved_games/          # Persistent game saves
```

## Key Functions

- `rank_value()` - Calculate card rank with options support
- `is_valid_meld()` - Validate card combinations respecting options
- `compare_melds()` - Compare melds with wilds beat multis logic
- `get_valid_plays()` - Generate CPU valid moves
- `Game.options` - Dict storing all game options

## Testing

Create a game and test different option combinations:
1. Enable/disable bombs
2. Change run_max
3. Toggle wild card options
4. Test with 3-8 players
5. Use 1-2 deck options

## TODO / Future Enhancements

- [ ] CPU difficulty levels (Easy/Normal/Hard)
- [ ] Exchange/swap phase logic
- [ ] Role assignments (President, VP, etc)
- [ ] Play animations and sound
- [ ] Game statistics and history
- [ ] Mobile responsive improvements
- [ ] Persistent game state across disconnects

## Author

Built from TIC-80 President game adaptation

## License

MIT
