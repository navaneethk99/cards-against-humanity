# Cards Against Humanity – CLI Edition

A small, terminal-based, fan-made implementation inspired by the Cards Against Humanity party card game. It runs locally in a single terminal and uses a tiny, built-in sample deck for demo play. It is **not** affiliated with or endorsed by Cards Against Humanity LLC.

---

## Features

- Rich-styled terminal UI
- Card Czar selection and judging
- Scoreboard tracking
- Local multiplayer in one terminal
- Installable `cah` CLI command

---

## Requirements

- Python 3.9+
- `pip`

Check your Python version:

```bash
python3 --version
```

---

## Install

Clone and install in editable mode:

```bash
git clone https://github.com/navaneethk99/cards-against-humanity
cd cards-against-humanity
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

---

## Run

```bash
cah
```

---

## How To Play

1. Run `cah`.
2. Enter player names separated by commas.
3. Each round, a random player becomes the Card Czar.
4. Non-Czar players choose a card from their hand by number.
5. The Czar picks the winning card; the winner gains a point.
6. Choose whether to play another round.

---

## Notes

- The name “Cards Against Humanity” and related marks are trademarks of Cards Against Humanity LLC.
- This project is for learning and personal use; it ships only a minimal, original sample card set.
