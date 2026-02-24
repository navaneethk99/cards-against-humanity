import asyncio
import os
import sys
try:
    import termios
    import tty
except ImportError:  # Windows
    termios = None
    tty = None

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console()


def clear_screen():
    console.clear()
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def splash():
    clear_screen()
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


def build_hand_table(player_name, hand):
    table = Table(title=f"{player_name}'s Hand", box=box.ROUNDED)
    table.add_column("Index", style="cyan")
    table.add_column("Card", style="white")

    for i, card in enumerate(hand):
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
        clear_screen()
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


async def prompt_async(prompt, **kwargs):
    return await asyncio.to_thread(Prompt.ask, prompt, **kwargs)


async def select_from_list_async(prompt, options, header_renderables=None):
    return await asyncio.to_thread(
        select_from_list, prompt, options, header_renderables
    )
