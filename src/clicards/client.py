import asyncio
import json
import os
import random
import sys
try:
    import termios
    import tty
except ImportError:  # Windows
    termios = None
    tty = None
from pathlib import Path

import websockets
from websockets.exceptions import InvalidURI
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console()

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    DATA_DIR = Path(sys._MEIPASS) / "clicards" / "data"
else:
    DATA_DIR = Path(__file__).resolve().parent / "data"
SERVER_URL = os.getenv("CAH_SERVER_URL", "ws://localhost:8765")


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


def render_czar_panel(czar_name):
    return Panel(
        Align.center(Text(czar_name, style="bold white", justify="center")),
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
    if termios is None:
        import msvcrt

        first = msvcrt.getch()
        if first in (b"\x00", b"\xe0"):
            second = msvcrt.getch()
            if second == b"H":
                return "\x1b[A"
            if second == b"P":
                return "\x1b[B"
            return ""
        if first == b"\r":
            return "\n"
        try:
            return first.decode()
        except UnicodeDecodeError:
            return ""

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


def normalize_server_url(value):
    value = value.strip()
    if value.startswith("https://"):
        return "wss://" + value[len("https://") :]
    if value.startswith("http://"):
        return "ws://" + value[len("http://") :]
    if value.startswith("ws://") or value.startswith("wss://"):
        return value
    return "ws://" + value


def play_round(players):
    console.rule("[bold red]New Round[/bold red]")

    black_card = random.choice(black_cards)
    czar = random.choice(players)

    black_panel = Panel(black_card, title="Black Card", style="bold white")
    czar_panel = render_czar_panel(czar.name)
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


def generate_room_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(length))


async def prompt_async(prompt, **kwargs):
    return await asyncio.to_thread(Prompt.ask, prompt, **kwargs)


async def select_from_list_async(prompt, options, header_renderables=None):
    return await asyncio.to_thread(
        select_from_list, prompt, options, header_renderables
    )


async def play_online():
    create_room_index = await select_from_list_async(
        "Create a new room?",
        ["Yes, create a room", "No, join a room"],
    )
    create_room = create_room_index == 0

    server_url = await prompt_async("Enter server URL", default=SERVER_URL)
    server_url = normalize_server_url(server_url)

    console.print(f"[dim]Server:[/dim] {server_url}")

    if create_room:
        room_code = generate_room_code()
        console.print(f"[bold cyan]Room Code:[/bold cyan] {room_code}")
    else:
        room_code = await prompt_async("Enter room code")
        room_code = room_code.strip().upper()

    username = await prompt_async("Choose a username")
    username = username.strip()

    black_panel = None
    czar_panel = None

    try:
        async with websockets.connect(server_url) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "join",
                        "room": room_code,
                        "name": username,
                        "create": create_room,
                    }
                )
            )

            is_host = False
            pending_start_task = None

            async for raw in ws:
                message = json.loads(raw)
                msg_type = message.get("type")

                if msg_type == "error":
                    console.print(
                        f"[bold red]Error:[/bold red] {message.get('message')}"
                    )
                    return

                if msg_type == "joined":
                    console.print(
                        f"[bold green]Joined room {message['room']}[/bold green]"
                    )
                    console.print(
                        f"[dim]Players:[/dim] {', '.join(message['players'])}"
                    )
                    is_host = message.get("host") == username
                    if is_host:
                        console.print(
                            "[dim]You are the host. Press Enter to start when ready.[/dim]"
                        )

                        async def wait_for_start():
                            await asyncio.to_thread(input)
                            await ws.send(json.dumps({"type": "start"}))

                        pending_start_task = asyncio.create_task(wait_for_start())

                elif msg_type == "players":
                    console.print(
                        f"[dim]Players:[/dim] {', '.join(message['players'])}"
                    )

                elif msg_type == "round_start":
                    black_panel = Panel(
                        message["black_card"], title="Black Card", style="bold white"
                    )
                    czar_panel = render_czar_panel(message["czar"])
                    console.clear()
                    console.print(black_panel)
                    console.print(czar_panel)

                elif msg_type == "request_submit":
                    hand = message["hand"]
                    hand_table = Table(title=f"{username}'s Hand", box=box.ROUNDED)
                    hand_table.add_column("Index", style="cyan")
                    hand_table.add_column("Card", style="white")
                    for i, card in enumerate(hand):
                        hand_table.add_row(str(i + 1), card)
                    choice_index = await select_from_list_async(
                        f"{username}, choose a card",
                        hand,
                        header_renderables=[black_panel, czar_panel, hand_table],
                    )
                    await ws.send(
                        json.dumps({"type": "submit", "index": choice_index})
                    )

                elif msg_type == "judge_request":
                    cards = message["cards"]
                    submissions_table = build_submissions_table(
                        list(enumerate(cards))
                    )
                    choice_index = await select_from_list_async(
                        f"{username}, choose the winner",
                        cards,
                        header_renderables=[
                            black_panel,
                            czar_panel,
                            submissions_table,
                        ],
                    )
                    await ws.send(
                        json.dumps({"type": "judge", "index": choice_index})
                    )

                elif msg_type == "round_result":
                    console.print(
                        f"\n[bold green]Winner:[/bold green] {message['winner']}"
                    )
                    console.print(
                        f"[dim]Winning card:[/dim] {message['winning_card']}"
                    )
                    scores = message.get("scores", {})
                    if scores:
                        table = Table(title="Scoreboard", box=box.DOUBLE)
                        table.add_column("Player", style="yellow")
                        table.add_column("Score", style="green")
                        for name, score in scores.items():
                            table.add_row(name, str(score))
                        console.print(table)

                elif msg_type == "wait":
                    console.print(
                        f"[dim]{message.get('message', 'Waiting...')}[/dim]"
                    )

                elif msg_type == "continue_request":
                    if is_host:
                        again = await prompt_async(
                            "Play another round?", choices=["y", "n"]
                        )
                        await ws.send(
                            json.dumps(
                                {"type": "continue", "again": again.lower() == "y"}
                            )
                        )

                elif msg_type == "game_over":
                    console.print(
                        f"[bold magenta]{message['message']}[/bold magenta]"
                    )
                    return
    except InvalidURI:
        console.print(
            "[bold red]Invalid server URL.[/bold red] Use ws:// or wss://"
        )
        return
    except OSError:
        console.print(
            "[bold red]Could not connect to server.[/bold red] "
            f"Is it running at {server_url}?"
        )
        return


def main():
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
