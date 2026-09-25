import re
from unittest.mock import patch

import pytest

from paradux.interfaces import RULES, Colour, WinState
from paradux.model import BoardState
from paradux.view import TerminalView, render_board

ANSI_CODE = re.compile(r"\033\[\d+m")

EMPTY_BOARD_LINES = [
    "          _______________________",
    "         /(0,0) (0,1) (0,2) (0,3)\\",
    "      /(1,0) (1,1) (1,2) (1,3) (1,4)\\",
    "   /(2,0) (2,1) (2,2) (2,3) (2,4) (2,5)\\",
    "|(3,0) (3,1) (3,2) (3,3) (3,4) (3,5) (3,6)|",
    "   \\(4,1) (4,2) (4,3) (4,4) (4,5) (4,6)/",
    "      \\(5,2) (5,3) (5,4) (5,5) (5,6)/",
    "         \\(6,3) (6,4) (6,5) (6,6)/",
    "          ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾",
]


@pytest.fixture
def view():
    return TerminalView()


def printed(mock_print) -> str:
    return "\n".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)


def test_board_is_drawn_as_a_hexagon_of_positions():
    assert (
        ANSI_CODE.sub("", render_board(BoardState().board_spaces)).split("\n") == EMPTY_BOARD_LINES
    )


def test_pieces_are_coloured():
    board = BoardState()
    rendered = render_board(board.board_spaces)
    assert "\033[31m(0,1)\033[0m" in rendered
    assert "\033[34m(0,0)\033[0m" in rendered
    assert " (3,3) " in rendered


@patch("builtins.print")
def test_game_start_shows_the_board_and_whose_turn_it_is(mock_print, view):
    board = BoardState()
    board.player_turn.colour = Colour.RED

    view.on_game_start(board)

    output = printed(mock_print)
    assert "--- Game Started ---" in output
    assert "(6,6)" in output
    assert "Red's turn" in output


@patch("builtins.print")
def test_game_over_announces_the_winner_without_a_turn_prompt(mock_print, view):
    view.on_game_over(BoardState(), WinState.BLUE)
    output = printed(mock_print)
    assert output.endswith("Game over, Blue wins!")
    assert "'s turn" not in output


@patch("builtins.print")
def test_messages(mock_print, view):
    view.on_game_loaded(BoardState(), "evening.json")
    view.display_rules()
    view.display_error("Pieces must be adjacent")
    view.display_saves_list([("evening.json", "2026-01-01 18:00:00")])

    output = printed(mock_print)
    assert "Game loaded: evening" in output
    assert all(f"> {paragraph}" in output for paragraph in RULES)
    assert "Error: Pieces must be adjacent" in output
    assert "1. evening (2026-01-01 18:00:00)" in output
