import json
import random
from pathlib import Path

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

console = Console()

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_cards(filename):
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


black_cards = load_cards("black_cards.json")
white_cards = load_cards("white_cards.json")


class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.score = 0


def splash():
    console.clear()
    title = Text("CARDS AGAINST HUMANITY", style="bold magenta")
    subtitle = Text("CLI Edition", style="bold cyan")
    console.print(Align.center(title))
    console.print(Align.center(subtitle))
    console.print("\n")


def deal_cards(players, deck, num=5):
    for player in players:
        player.hand = random.sample(deck, num)


def show_hand(player):
    table = Table(title=f"{player.name}'s Hand", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Card", style="white")

    for i, card in enumerate(player.hand):
        table.add_row(str(i + 1), card)

    console.print(table)


def show_scores(players):
    table = Table(title="Scoreboard", box=box.DOUBLE)
    table.add_column("Player", style="yellow")
    table.add_column("Score", style="green")

    for p in players:
        table.add_row(p.name, str(p.score))

    console.print(table)


def play_round(players):
    console.rule("[bold red]New Round[/bold red]")

    black_card = random.choice(black_cards)
    czar = random.choice(players)

    console.print(Panel(black_card, title="Black Card", style="bold white"))
    console.print(f"\n[bold cyan]Card Czar:[/bold cyan] {czar.name}")

    submissions = {}

    for player in players:
        if player == czar:
            continue

        show_hand(player)
        choice = IntPrompt.ask(
            f"{player.name}, choose a card",
            choices=[str(i + 1) for i in range(len(player.hand))],
        )
        submissions[player] = player.hand[choice - 1]
        console.clear()

    console.print("\n[bold green]Submissions:[/bold green]")

    shuffled = list(submissions.items())
    random.shuffle(shuffled)

    for i, (_, card) in enumerate(shuffled):
        console.print(f"[cyan]{i + 1}.[/cyan] {card}")

    winner_choice = IntPrompt.ask(
        f"\n{czar.name}, choose the winner",
        choices=[str(i + 1) for i in range(len(shuffled))],
    )
    winner = shuffled[winner_choice - 1][0]
    winner.score += 1

    console.print(f"\n🎉 [bold green]Winner:[/bold green] {winner.name} 🎉")


def main():
    splash()

    names = Prompt.ask("Enter player names (comma separated)")
    players = [Player(name.strip()) for name in names.split(",")]

    deal_cards(players, white_cards)

    while True:
        play_round(players)
        show_scores(players)

        again = Prompt.ask("\nPlay another round?", choices=["y", "n"])
        if again.lower() != "y":
            break

    console.print("\n[bold magenta]Thanks for playing![/bold magenta]")


if __name__ == "__main__":
    main()
