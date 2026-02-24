import random

from .ui import build_submissions_table, console, render_black_card_panel, render_czar_panel


class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.score = 0


class Deck:
    def __init__(self, cards):
        self.cards = list(cards)
        random.shuffle(self.cards)

    def draw(self, num=1):
        if num <= 0:
            return []
        draw_count = min(num, len(self.cards))
        return [self.cards.pop() for _ in range(draw_count)]

    def draw_one(self):
        drawn = self.draw(1)
        return drawn[0] if drawn else None


def deal_cards(players, deck, num=5):
    for player in players:
        player.hand = deck.draw(num)


def play_round(players, white_deck, black_deck, select_from_list):
    console.rule("[bold red]New Round[/bold red]")

    black_card = black_deck.draw_one()
    if black_card is None:
        console.print("[bold red]No more black cards. Game ended.[/bold red]")
        return False
    czar = random.choice(players)

    black_panel = render_black_card_panel(black_card)
    czar_panel = render_czar_panel(czar.name)
    console.print(black_panel)
    console.print(czar_panel)

    submissions = {}

    for player in players:
        if player == czar:
            continue

        choice_index = select_from_list(
            f"{player.name}, choose a card",
            player.hand,
            header_renderables=[black_panel, czar_panel],
        )
        chosen_card = player.hand.pop(choice_index)
        submissions[player] = chosen_card
        replacement = white_deck.draw_one()
        if replacement is not None:
            player.hand.append(replacement)

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
    return True
