import asyncio
import json
import os
import random
import sys

import websockets
from websockets.exceptions import InvalidURI
from rich import box
from rich.panel import Panel
from rich.table import Table

from .ui import (
    build_submissions_table,
    clear_screen,
    console,
    prompt_async,
    render_czar_panel,
    select_from_list_async,
    spinner_until,
)

SERVER_URL = os.getenv("CAH_SERVER_URL", "ws://localhost:8765")


def normalize_server_url(value):
    value = value.strip()
    if value.startswith("https://"):
        return "wss://" + value[len("https://") :]
    if value.startswith("http://"):
        return "ws://" + value[len("http://") :]
    if value.startswith("ws://") or value.startswith("wss://"):
        return value
    return "ws://" + value


def generate_room_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(length))


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
    is_host = False
    lobby_active = True
    lobby_task = None
    remove_lobby_reader = None
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
            wait_task = None
            wait_event = None

            async for raw in ws:
                message = json.loads(raw)
                msg_type = message.get("type")

                if msg_type != "wait" and wait_task is not None:
                    wait_event.set()
                    await wait_task
                    wait_task = None
                    wait_event = None

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
                    if lobby_active and lobby_task is None:
                        loop = asyncio.get_running_loop()
                        queue = asyncio.Queue()

                        def on_stdin():
                            line = sys.stdin.readline()
                            if line:
                                queue.put_nowait(line.rstrip("\n"))

                        if hasattr(loop, "add_reader") and sys.stdin.isatty():
                            loop.add_reader(sys.stdin, on_stdin)
                            remove_lobby_reader = lambda: loop.remove_reader(sys.stdin)

                            async def lobby_input_loop():
                                while True:
                                    line = await queue.get()
                                    if not lobby_active:
                                        continue
                                    text = line.strip()
                                    if not text:
                                        continue
                                    if text.startswith("/start"):
                                        if is_host:
                                            await ws.send(
                                                json.dumps({"type": "start"})
                                            )
                                        else:
                                            console.print(
                                                "[dim]Only the host can start the game.[/dim]"
                                            )
                                    else:
                                        await ws.send(
                                            json.dumps(
                                                {"type": "chat", "message": text}
                                            )
                                        )

                            lobby_task = asyncio.create_task(lobby_input_loop())

                    if is_host:
                        console.print(
                            "[dim]You are the host. Type /start to begin.[/dim]"
                        )
                    console.print(
                        "[dim]Lobby chat: type a message and press Enter.[/dim]"
                    )

                elif msg_type == "players":
                    console.print(
                        f"[dim]Players:[/dim] {', '.join(message['players'])}"
                    )

                elif msg_type == "round_start":
                    lobby_active = False
                    if lobby_task is not None:
                        lobby_task.cancel()
                        lobby_task = None
                    if remove_lobby_reader is not None:
                        remove_lobby_reader()
                        remove_lobby_reader = None
                    black_panel = Panel(
                        message["black_card"], title="Black Card", style="bold white"
                    )
                    czar_panel = render_czar_panel(message["czar"])
                    clear_screen()
                    console.print(black_panel)
                    console.print(czar_panel)

                elif msg_type == "request_submit":
                    hand = message["hand"]
                    choice_index = await select_from_list_async(
                        f"{username}, choose a card",
                        hand,
                        header_renderables=[black_panel, czar_panel],
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
                    wait_message = message.get("message", "Waiting...")
                    if wait_task is not None:
                        wait_event.set()
                        await wait_task
                    wait_event = asyncio.Event()
                    wait_task = asyncio.create_task(
                        spinner_until(wait_message, wait_event, spinner_name="dots")
                    )

                elif msg_type == "chat":
                    sender = message.get("from", "Unknown")
                    text = message.get("message", "")
                    console.print(f"[cyan]{sender}:[/cyan] {text}")

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
                    if remove_lobby_reader is not None:
                        remove_lobby_reader()
                        remove_lobby_reader = None
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
