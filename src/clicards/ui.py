import asyncio
import os
import sys
import time
try:
    import termios
    import tty
except ImportError:  # Windows
    termios = None
    tty = None

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.padding import Padding
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "accent": "bold bright_cyan",
        "accent_alt": "bold bright_magenta",
        "muted": "dim",
        "card_white": "bold white",
        "card_black": "bold white on black",
        "highlight": "bold black on bright_white",
        "warning": "bold yellow",
        "success": "bold green",
    }
)

console = Console(theme=THEME, highlight=False)


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
        style="bright_red",
    )
    subtitle = Text(
        "Deal weird. Laugh louder. Win no prizes.",
        style="accent",
    )
    card_faces = ["♠", "♥", "♦", "♣"]
    shuffle = Text("Shuffling the terrible ideas...", style="accent_alt")

    def frame(pulse):
        glow = "bright_magenta" if pulse else "bright_cyan"
        header = Panel(
            Align.center(title),
            border_style=glow,
            box=box.DOUBLE,
            padding=(1, 4),
        )
        chips = Columns(
            [Text(face, style="accent") for face in card_faces],
            expand=True,
            equal=True,
        )
        footer = Panel(Align.center(shuffle), style="muted", box=box.MINIMAL)
        return Group(
            header,
            Padding(Align.center(chips), (1, 0)),
            footer,
            Align.center(subtitle),
        )

    try:
        for i in range(10):
            clear_screen()
            console.print(frame(i % 2 == 0))
            time.sleep(0.08)
        clear_screen()
        console.print(Align.center(title))
        console.print(Align.center(subtitle))
        console.print("\n")
    except Exception:
        clear_screen()
        console.print("Cards Against Humanity")
        console.print("Deal weird. Laugh louder. Win no prizes.")
        console.print("")


def build_hand_table(player_name, hand):
    table = Table(title=f"{player_name}'s Hand", box=box.HEAVY_EDGE)
    table.add_column("Index", style="accent", justify="right", no_wrap=True)
    table.add_column("Card", style="card_white")

    for i, card in enumerate(hand):
        table.add_row(str(i + 1), card)

    return table


def render_black_card_panel(card_text):
    return Panel(
        Text(card_text, style="card_black", justify="center"),
        title="BLACK CARD",
        border_style="bright_white",
        style="bold white on black",
        box=box.HEAVY,
        padding=(2, 6),
    )


def show_scores(players):
    table = Table(title="Scoreboard", box=box.DOUBLE_EDGE)
    table.add_column("Player", style="warning")
    table.add_column("Score", style="success", justify="right")

    for p in players:
        table.add_row(p.name, str(p.score))

    console.print(Panel(table, title="Standings", border_style="accent"))


def show_loading(message, duration=1.6, spinner_name="dots"):
    panel = Panel(
        Align.center(Spinner(spinner_name, text=message, style="accent")),
        border_style="accent_alt",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    with Live(panel, refresh_per_second=12, console=console, transient=True):
        time.sleep(duration)


async def show_loading_async(message, duration=1.6, spinner_name="dots"):
    panel = Panel(
        Align.center(Spinner(spinner_name, text=message, style="accent")),
        border_style="accent_alt",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    with Live(panel, refresh_per_second=12, console=console, transient=True):
        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            await asyncio.sleep(0.1)


async def spinner_until(message, stop_event, spinner_name="dots"):
    panel = Panel(
        Align.center(Spinner(spinner_name, text=message, style="accent")),
        border_style="accent_alt",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    with Live(panel, refresh_per_second=12, console=console, transient=True):
        while not stop_event.is_set():
            await asyncio.sleep(0.1)


def render_czar_panel(czar_name):
    return Panel(
        Align.center(Text(czar_name, style="bold white", justify="center")),
        title="Card Czar",
        border_style="cyan",
        style="cyan",
        padding=(1, 4),
        box=box.ROUNDED,
    )


def build_submissions_table(shuffled):
    table = Table(title="Submissions", box=box.HEAVY_HEAD)
    table.add_column("#", style="accent", justify="right", no_wrap=True)
    table.add_column("Card", style="card_white")

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


def _build_menu_layout(prompt, options, index, header_renderables):
    header_renderables = header_renderables or []
    height = console.size.height
    width = console.size.width
    compact = height < 30 or width < 90

    if header_renderables and not compact:
        header = Panel(
            Group(*header_renderables),
            border_style="accent",
            title="Round",
            box=box.DOUBLE,
            padding=(1, 2),
        )
    else:
        headline = "Cards Against Humanity"
        if header_renderables and compact:
            headline = "Round View (expand terminal for full context)"
        header = Panel(
            Align.center(Text(headline, style="accent")),
            border_style="accent",
            box=box.DOUBLE,
            padding=(1, 2),
        )

    options_table = Table(show_header=False, box=box.SIMPLE_HEAVY)
    options_table.add_column(justify="left")
    for i, option in enumerate(options):
        marker = "▶ " if i == index else "  "
        style = "highlight" if i == index else "card_white"
        options_table.add_row(Text(f"{marker}{option}", style=style))

    menu_panel = Panel(
        options_table,
        title=prompt,
        border_style="accent_alt",
        box=box.ROUNDED,
        padding=(1, 2),
    )

    show_status = height >= 14
    status = Panel(
        Align.center(Text("Make a choice and commit to the chaos.", style="muted")),
        box=box.MINIMAL,
    )

    body = Columns([menu_panel], expand=True, equal=True)

    if show_status:
        return Group(header, body, status)
    return Group(header, body)


def select_from_list(prompt, options, header_renderables=None):
    if not options:
        raise ValueError("options must be non-empty")

    index = 0
    header_renderables = header_renderables or []
    layout = _build_menu_layout(prompt, options, index, header_renderables)

    while True:
        clear_screen()
        console.print(layout)
        key = read_key()
        if key in ("\x1b[A", "k", "K"):
            index = (index - 1) % len(options)
        elif key in ("\x1b[B", "j", "J"):
            index = (index + 1) % len(options)
        elif key in ("\r", "\n"):
            return index
        layout = _build_menu_layout(prompt, options, index, header_renderables)


async def prompt_async(prompt, **kwargs):
    return await asyncio.to_thread(Prompt.ask, prompt, **kwargs)


async def select_from_list_async(prompt, options, header_renderables=None):
    return await asyncio.to_thread(
        select_from_list, prompt, options, header_renderables
    )
