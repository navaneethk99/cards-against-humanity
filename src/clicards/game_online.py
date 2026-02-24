import asyncio
import json
import os
import random

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
                    clear_screen()
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
