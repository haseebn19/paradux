import threading
from unittest.mock import MagicMock, patch

import pytest

from paradux.controller import GameController, TerminalLoopController, parse_position
from paradux.interfaces import Colour, WinState
from paradux.model import BoardState, GameState, Move, Space
from paradux.view import TerminalView


@pytest.mark.parametrize(("text", "position"), [("1,2", (1, 2)), ("10,20", (10, 20))])
def test_parse_position(text, position):
    assert parse_position(text) == position


@pytest.mark.parametrize("text", ["invalid", "12", "a,b", "1,2,3"])
def test_parse_position_rejects_other_text(text):
    with pytest.raises(ValueError):
        parse_position(text)


@pytest.fixture
def board():
    return BoardState()


@pytest.fixture
def terminal_view():
    return TerminalView()


@pytest.fixture
def game_state():
    return GameState()


@pytest.fixture
def game_controller(game_state):
    return GameController(game_state)


@pytest.fixture
def terminal_loop_controller(terminal_view, game_controller):
    return TerminalLoopController(game_controller=game_controller, terminal_view=terminal_view)


def test_start_new_game(game_controller):
    assert game_controller.get_board() is None
    board = game_controller.start_new_game()
    assert game_controller.get_board() is board


def test_apply_move_no_board(game_controller):
    move = Move(
        [Space((0, 0), Colour.RED), Space((1, 1), Colour.EMPTY)],
        [Space((0, 1), Colour.BLUE), Space((1, 2), Colour.EMPTY)],
    )
    result = game_controller.apply_move(move)
    assert result is False


def test_save_game_raises_without_board(game_controller):
    with pytest.raises(ValueError):
        game_controller.save_game()


def test_save_game_finished_game_raises(game_controller):
    board = game_controller.start_new_game()
    for position in [(0, 0), (0, 1), (0, 2), (0, 3)]:
        board.board_spaces[position] = Colour.RED
    with pytest.raises(ValueError):
        game_controller.save_game("test")


def test_apply_move_illegal_move(game_controller):
    game_controller.start_new_game()
    move = Move(
        [Space((0, 0), Colour.RED), Space((5, 5), Colour.EMPTY)],
        [Space((0, 1), Colour.BLUE), Space((5, 6), Colour.EMPTY)],
    )
    assert game_controller.apply_move(move) is False


def test_detect_new_board_no_board(terminal_loop_controller):
    result = terminal_loop_controller._detect_new_board()
    assert result is False


def test_detect_new_board_with_board(terminal_loop_controller, game_controller):
    game_controller.start_new_game()
    terminal_loop_controller.board_state.active_board_id = None
    result = terminal_loop_controller._detect_new_board()
    assert result is True


def test_start_game_sets_board_id(terminal_loop_controller, game_controller):
    board = game_controller.start_new_game()
    terminal_loop_controller._start_game(board)
    assert terminal_loop_controller.board_state.active_board_id == id(board)
    assert terminal_loop_controller.board_state.allow_auto_resume is True


# -- Moves --
#
# On the starting board, Red has pieces at (0, 1) and (1, 0) and Blue at (0, 0) and (0, 2).
RED, BLUE = (0, 1), (0, 0)


@pytest.fixture
def red_to_move(game_controller):
    """Start a game where Red moves first and return its board."""
    with patch("paradux.model.random.choice", return_value=Colour.RED):
        return game_controller.start_new_game()


def place_pieces(board, red, blue):
    """Clear the board, then place one red and one blue piece."""
    for cell in board.board_spaces:
        board.board_spaces[cell] = Colour.EMPTY
    board.board_spaces[red] = Colour.RED
    board.board_spaces[blue] = Colour.BLUE


def test_try_move_without_a_game(game_controller):
    assert game_controller.try_move(RED, BLUE, (1, 2)) == (False, "No active game")


def test_try_move_shifts_both_pieces(game_controller, red_to_move):
    assert game_controller.try_move(RED, BLUE, (1, 2)) == (True, "")

    spaces = red_to_move.board_spaces
    assert spaces[(1, 2)] == Colour.RED
    assert spaces[(1, 1)] == Colour.BLUE
    assert spaces[RED] == spaces[BLUE] == Colour.EMPTY
    assert red_to_move.player_turn.colour == Colour.BLUE


def test_try_move_accepts_the_pieces_in_either_order(game_controller, red_to_move):
    assert game_controller.try_move(BLUE, RED, (1, 2)) == (True, "")
    assert red_to_move.board_spaces[(1, 2)] == Colour.RED


def test_try_move_rejects_a_target_the_other_piece_cannot_follow(game_controller, red_to_move):
    success, message = game_controller.try_move(RED, BLUE, (1, 1))

    assert success is False
    assert message == "Your piece cannot move there"
    assert red_to_move.board_spaces[(1, 0)] == Colour.RED


def test_try_move_pushes_into_the_other_piece(game_controller, red_to_move):
    place_pieces(red_to_move, red=(3, 2), blue=(3, 3))

    assert game_controller.try_move((3, 2), (3, 3), (3, 3)) == (True, "")

    assert red_to_move.board_spaces[(3, 3)] == Colour.RED
    assert red_to_move.board_spaces[(3, 4)] == Colour.BLUE
    assert red_to_move.board_spaces[(3, 2)] == Colour.EMPTY


def test_try_move_swaps_without_a_target(game_controller, red_to_move):
    assert game_controller.try_move(RED, BLUE) == (True, "")
    assert red_to_move.board_spaces[RED] == Colour.BLUE
    assert red_to_move.board_spaces[BLUE] == Colour.RED


@pytest.mark.usefixtures("red_to_move")
def test_try_move_cannot_undo_the_previous_move(game_controller):
    game_controller.try_move(RED, BLUE, (1, 2))

    # Blue moves the same two pieces straight back
    success, message = game_controller.try_move((1, 1), (1, 2), BLUE)

    assert success is False
    assert message == "Cannot undo the opponent's previous move"


@pytest.mark.parametrize(
    ("first", "second", "message"),
    [
        ((0, 1), (1, 1), "Both positions must have pieces"),
        ((0, 1), (1, 0), "Pieces must be different colours"),
        ((0, 1), (6, 3), "Pieces must be adjacent"),
    ],
)
@pytest.mark.usefixtures("red_to_move")
def test_try_move_rejects_invalid_pairs(game_controller, first, second, message):
    assert game_controller.try_move(first, second, (1, 2)) == (False, message)


def test_a_winning_move_ends_the_game(game_controller, red_to_move):
    # Red holds (3, 1) to (3, 3); moving (2, 0) down to (3, 0) completes the row, and the blue
    # piece at (1, 0) follows into (2, 0).
    place_pieces(red_to_move, red=(2, 0), blue=(1, 0))
    for cell in [(3, 1), (3, 2), (3, 3)]:
        red_to_move.board_spaces[cell] = Colour.RED
    view = MagicMock()
    game_controller.add_view(view)

    assert game_controller.try_move((2, 0), (1, 0), (3, 0)) == (True, "")

    view.on_game_over.assert_called_once_with(red_to_move, WinState.RED)


# -- Terminal input --


def test_terminal_load_reports_a_damaged_save(terminal_loop_controller, game_controller):
    replies = iter([("input", "1"), ("input", "cancel")])
    with (
        patch.object(game_controller, "list_saves", return_value=[("damaged.json", "today")]),
        patch.object(
            game_controller,
            "load_game",
            side_effect=ValueError("damaged.json is not a valid save file"),
        ),
        patch.object(
            terminal_loop_controller, "_wait_for_line", side_effect=lambda *_: next(replies)
        ),
        patch.object(TerminalView, "display_error") as mock_error,
    ):
        loaded = terminal_loop_controller._prompt_load_game(threading.Event())

    assert loaded is False
    mock_error.assert_called_once_with("damaged.json is not a valid save file")


@patch.object(TerminalView, "display_error")
def test_terminal_move_input(mock_error, terminal_loop_controller, red_to_move):
    terminal_loop_controller._process_move_input("0,1 0,0 1,2")
    mock_error.assert_not_called()
    assert red_to_move.board_spaces[(1, 2)] == Colour.RED


@patch.object(TerminalView, "display_error")
def test_terminal_switch_input(mock_error, terminal_loop_controller, red_to_move):
    terminal_loop_controller._process_move_input("0,1 0,0 SWITCH")
    mock_error.assert_not_called()
    assert red_to_move.board_spaces[RED] == Colour.BLUE


@pytest.mark.parametrize(
    ("command", "error"),
    [
        ("0,1 0,0", "Expected input like '0,1 0,2 1,2' or '0,1 0,2 switch'"),
        ("0,1 a,b 1,2", "Expected input like '0,1 0,2 1,2' or '0,1 0,2 switch'"),
        ("0,1 0,0 up", "Expected input like '0,1 0,2 1,2' or '0,1 0,2 switch'"),
        ("0,1 0,0 1,1", "Your piece cannot move there"),
    ],
)
@pytest.mark.usefixtures("red_to_move")
def test_terminal_reports_bad_moves(terminal_loop_controller, command, error):
    with patch.object(TerminalView, "display_error") as mock_error:
        terminal_loop_controller._process_move_input(command)
    mock_error.assert_called_once_with(error)
