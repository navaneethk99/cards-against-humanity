import argparse
import asyncio
import json
import os
import random
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import websockets

import sys

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


@dataclass
class Player:
    name: str
    ws: websockets.WebSocketServerProtocol
    hand: list[str] = field(default_factory=list)
    score: int = 0


@dataclass
class Room:
    code: str
    players: list[Player] = field(default_factory=list)
    host: Player | None = None
    czar: Player | None = None
    black_card: str | None = None
    submissions: list[tuple[Player, str]] = field(default_factory=list)
    phase: str = "lobby"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


rooms: dict[str, Room] = {}


def deal_cards(player, num=5):
    if len(player.hand) == 0:
        player.hand = random.sample(white_cards, num)


async def send(ws, payload):
    await ws.send(json.dumps(payload))


async def broadcast(room, payload, exclude=None):
    for player in list(room.players):
        if exclude is not None and player == exclude:
            continue
        await send(player.ws, payload)


async def start_round(room):
    room.black_card = random.choice(black_cards)
    room.czar = random.choice(room.players)
    room.submissions = []
    room.phase = "collecting"

    for player in room.players:
        deal_cards(player)

    await broadcast(
        room,
        {
            "type": "round_start",
            "black_card": room.black_card,
            "czar": room.czar.name,
        },
    )

    for player in room.players:
        if player == room.czar:
            await send(
                player.ws,
                {"type": "wait", "message": "Waiting for submissions..."},
            )
        else:
            await send(
                player.ws,
                {"type": "request_submit", "hand": player.hand},
            )


async def handle_submit(room, player, index):
    if room.phase != "collecting" or player == room.czar:
        return
    if not (0 <= index < len(player.hand)):
        await send(player.ws, {"type": "error", "message": "Invalid card choice."})
        return

    card = player.hand.pop(index)
    room.submissions.append((player, card))
    await send(player.ws, {"type": "wait", "message": "Submission received."})

    if len(room.submissions) == len(room.players) - 1:
        room.phase = "judging"
        shuffled = list(room.submissions)
        random.shuffle(shuffled)
        room.submissions = shuffled
        await send(
            room.czar.ws,
            {"type": "judge_request", "cards": [card for _, card in shuffled]},
        )
        await broadcast(
            room,
            {"type": "wait", "message": "Czar is choosing a winner..."},
            exclude=room.czar,
        )


async def handle_judge(room, player, index):
    if room.phase != "judging" or player != room.czar:
        return
    if not (0 <= index < len(room.submissions)):
        await send(player.ws, {"type": "error", "message": "Invalid winner choice."})
        return

    winner, winning_card = room.submissions[index]
    winner.score += 1
    room.phase = "post_round"

    scores = {p.name: p.score for p in room.players}
    await broadcast(
        room,
        {
            "type": "round_result",
            "winner": winner.name,
            "winning_card": winning_card,
            "scores": scores,
        },
    )

    if room.host:
        await send(room.host.ws, {"type": "continue_request"})


async def handle_continue(room, player, again):
    if player != room.host:
        return
    if not again:
        room.phase = "lobby"
        await broadcast(room, {"type": "game_over", "message": "Game ended."})
        return
    await start_round(room)


async def handle_disconnect(room, player):
    if player in room.players:
        room.players.remove(player)
    if room.host == player:
        room.host = room.players[0] if room.players else None
    if room.czar == player:
        room.czar = None
    if room.phase in ("collecting", "judging"):
        room.phase = "lobby"
        await broadcast(
            room,
            {"type": "game_over", "message": "Player left. Round reset."},
        )

    if not room.players:
        rooms.pop(room.code, None)
    else:
        await broadcast(
            room,
            {
                "type": "players",
                "players": [p.name for p in room.players],
                "host": room.host.name if room.host else None,
            },
        )


async def handler(ws):
    room = None
    player = None
    try:
        raw = await ws.recv()
        message = json.loads(raw)
        if message.get("type") != "join":
            await send(ws, {"type": "error", "message": "Join required."})
            return

        room_code = message.get("room", "").strip().upper()
        name = message.get("name", "").strip()
        create = bool(message.get("create"))

        if not room_code or not name:
            await send(ws, {"type": "error", "message": "Missing room or name."})
            return

        if create:
            if room_code in rooms:
                await send(ws, {"type": "error", "message": "Room exists."})
                return
            room = Room(code=room_code)
            rooms[room_code] = room
        else:
            room = rooms.get(room_code)
            if room is None:
                await send(ws, {"type": "error", "message": "Room not found."})
                return

        if any(p.name == name for p in room.players):
            await send(ws, {"type": "error", "message": "Name already taken."})
            return

        player = Player(name=name, ws=ws)
        room.players.append(player)
        if room.host is None:
            room.host = player

        await send(
            ws,
            {
                "type": "joined",
                "room": room.code,
                "players": [p.name for p in room.players],
                "host": room.host.name if room.host else None,
                "you": player.name,
            },
        )
        await broadcast(
            room,
            {
                "type": "players",
                "players": [p.name for p in room.players],
                "host": room.host.name if room.host else None,
            },
            exclude=player,
        )

        async for raw in ws:
            message = json.loads(raw)
            msg_type = message.get("type")
            async with room.lock:
                if msg_type == "start":
                    if len(room.players) < 2:
                        await send(
                            ws,
                            {
                                "type": "error",
                                "message": "Need at least 2 players to start.",
                            },
                        )
                    elif room.phase in ("lobby", "post_round"):
                        await start_round(room)
                elif msg_type == "submit":
                    await handle_submit(room, player, int(message.get("index", -1)))
                elif msg_type == "judge":
                    await handle_judge(room, player, int(message.get("index", -1)))
                elif msg_type == "continue":
                    await handle_continue(room, player, bool(message.get("again")))
    except websockets.ConnectionClosed:
        if room and player:
            async with room.lock:
                await handle_disconnect(room, player)


async def main_async(host, port):
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


def main():
    parser = argparse.ArgumentParser(description="Cards Against Humanity server")
    parser.add_argument("--host", default="0.0.0.0")
    default_port = int(os.getenv("PORT", "8765"))
    parser.add_argument("--port", default=default_port, type=int)
    args = parser.parse_args()

    display_host = args.host
    if display_host in ("0.0.0.0", "::"):
        display_host = "YOUR_PUBLIC_IP"
        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=2) as resp:
                ip = resp.read().decode("utf-8").strip()
                if ip:
                    display_host = ip
        except (urllib.error.URLError, socket.timeout):
            pass
    print(
        "Server is running successfully. Your friends can join using "
        f"ws://{display_host}:{args.port}"
    )

    asyncio.run(main_async(args.host, args.port))


if __name__ == "__main__":
    main()
