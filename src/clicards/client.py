import json
import random
import sys
import termios
import tty
from pathlib import Path

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
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
    title = Text(
        """
░█████╗░██╗░░░░░██╗░█████╗░░█████╗░██████╗░██████╗░░██████╗
██╔══██╗██║░░░░░██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝
██║░░╚═╝██║░░░░░██║██║░░╚═╝███████║██████╔╝██║░░██║╚█████╗░
██║░░██╗██║░░░░░██║██║░░██╗██╔══██║██╔══██╗██║░░██║░╚═══██╗
╚█████╔╝███████╗██║╚█████╔╝██║░░██║██║░░██║██████╔╝██████╔╝
░╚════╝░╚══════╝╚═╝░╚════╝░╚═╝░░╚═╝╚═╝░░╚═╝╚═════╝░╚═════╝░
""",
        style="red",
    )
    subtitle = Text(
        """█▀▀ ▄▀█ █▀█ █▀▄ █▀   ▄▀█ █▀▀ ▄▀█ █ █▄░█ █▀ ▀█▀   █░█ █░█ █▀▄▀█ ▄▀█ █▄░█ █ ▀█▀ █▄█
█▄▄ █▀█ █▀▄ █▄▀ ▄█   █▀█ █▄█ █▀█ █ █░▀█ ▄█ ░█░   █▀█ █▄█ █░▀░█ █▀█ █░▀█ █ ░█░ ░█░
""",
        style="red",
    )
    console.print(Align.center(title))
    console.print(Align.center(subtitle))
    console.print("\n")


def deal_cards(players, deck, num=5):
    for player in players:
        player.hand = random.sample(deck, num)


def build_hand_table(player):
    table = Table(title=f"{player.name}'s Hand", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Card", style="white")

    for i, card in enumerate(player.hand):
        table.add_row(str(i + 1), card)

    return table


def show_scores(players):
    table = Table(title="Scoreboard", box=box.DOUBLE)
    table.add_column("Player", style="yellow")
    table.add_column("Score", style="green")

    for p in players:
        table.add_row(p.name, str(p.score))

    console.print(table)


def render_czar_panel(czar):
    return Panel(
        Align.center(Text(czar.name, style="bold white", justify="center")),
        title="CARD CZAR",
        border_style="bright_cyan",
        style="bold cyan",
        padding=(1, 6),
        box=box.DOUBLE,
    )


def build_submissions_table(shuffled):
    table = Table(title="Submissions", box=box.SIMPLE_HEAVY)
    table.add_column("#", style="cyan", justify="right", no_wrap=True)
    table.add_column("Card", style="white")

    for i, (_, card) in enumerate(shuffled):
        table.add_row(str(i + 1), card)

    return table


def read_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def select_from_list(prompt, options, header_renderables=None):
    if not options:
        raise ValueError("options must be non-empty")

    index = 0
    header_renderables = header_renderables or []

    def render():
        console.clear()
        for renderable in header_renderables:
            console.print(renderable)
        console.print(f"\n[bold yellow]{prompt}[/bold yellow]")
        console.print("[dim]Use Up/Down and Enter[/dim]\n")
        for i, option in enumerate(options):
            prefix = "> " if i == index else "  "
            style = "bold black on bright_white" if i == index else ""
            console.print(Text(prefix + option, style=style))

    while True:
        render()
        key = read_key()
        if key in ("\x1b[A", "k", "K"):
            index = (index - 1) % len(options)
        elif key in ("\x1b[B", "j", "J"):
            index = (index + 1) % len(options)
        elif key in ("\r", "\n"):
            return index


def play_round(players):
    console.rule("[bold red]New Round[/bold red]")

    black_card = random.choice(black_cards)
    czar = random.choice(players)

    black_panel = Panel(black_card, title="Black Card", style="bold white")
    czar_panel = render_czar_panel(czar)
    console.print(black_panel)
    console.print(czar_panel)

    submissions = {}

    for player in players:
        if player == czar:
            continue

        hand_table = build_hand_table(player)
        choice_index = select_from_list(
            f"{player.name}, choose a card",
            player.hand,
            header_renderables=[black_panel, czar_panel, hand_table],
        )
        submissions[player] = player.hand[choice_index]

    shuffled = list(submissions.items())
    random.shuffle(shuffled)

    submissions_table = build_submissions_table(shuffled)

    winner_index = select_from_list(
        f"{czar.name}, choose the winner",
        [card for _, card in shuffled],
        header_renderables=[black_panel, czar_panel, submissions_table],
    )
    winner = shuffled[winner_index][0]
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
