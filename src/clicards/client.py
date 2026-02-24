import asyncio
import json
import sys
from pathlib import Path

from rich.prompt import Prompt

from .game_local import Deck, Player, deal_cards, play_round
from .game_online import play_online
from .ui import select_from_list, show_scores, splash
from .updater import check_for_updates

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    DATA_DIR = Path(sys._MEIPASS) / "clicards" / "data"
else:
    DATA_DIR = Path(__file__).resolve().parent / "data"


def load_cards(filename):
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


black_cards = load_cards("black_cards.json")
white_cards = load_cards("white_cards.json")


def main():
    check_for_updates()
    splash()

    mode_index = select_from_list(
        "Play online or locally?",
        ["Online", "Local"],
    )
    if mode_index == 0:
        asyncio.run(play_online())
    else:
        names = Prompt.ask("Enter player names (comma separated)")
        players = [Player(name.strip()) for name in names.split(",")]

        white_deck = Deck(white_cards)
        black_deck = Deck(black_cards)
        deal_cards(players, white_deck)

        while True:
            if not play_round(
                players,
                white_deck,
                black_deck,
                select_from_list,
            ):
                break
            show_scores(players)

            again = Prompt.ask("\nPlay another round?", choices=["y", "n"])
            if again.lower() != "y":
                break

        from .ui import console

        console.print("\n[bold magenta]Thanks for playing![/bold magenta]")


if __name__ == "__main__":
    main()
