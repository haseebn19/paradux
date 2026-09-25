from unittest.mock import MagicMock, patch

import pytest

from paradux.controller import (
    BoardTrackingState,
    GameController,
    InputController,
    MoveBuildParams,
    MoveController,
    TerminalLoopController,
    WaitOptions,
)
from paradux.interfaces import Colour
from paradux.model import BoardState, GameState, Move, Space
from paradux.view import TerminalView


@pytest.fixture
def input_controller():
    return InputController()


def test_coord_from_str_valid(input_controller):
    result = input_controller.coord_from_str("1,2")
    assert result == (1, 2)


def test_coord_from_str_large_numbers(input_controller):
    result = input_controller.coord_from_str("10,20")
    assert result == (10, 20)


def test_coord_from_str_invalid_format(input_controller):
    with pytest.raises(ValueError):
        input_controller.coord_from_str("invalid")


def test_coord_from_str_missing_comma(input_controller):
    with pytest.raises(ValueError):
        input_controller.coord_from_str("12")


def test_coord_from_str_non_numeric(input_controller):
    with pytest.raises(ValueError):
        input_controller.coord_from_str("a,b")


@pytest.fixture
def move_controller():
    return MoveController()


def test_check_valid_input_valid_format(move_controller):
    valid_moves = ["0,0 1,1", "10,5 9,4", " 0,1 2,3 "]
    for move in valid_moves:
        result = move_controller.check_valid_input(move)
        assert result is True


def test_check_valid_input_invalid_format(move_controller):
    invalid_moves = ["", "0,0", "0,0 1", "0,a 1,1", "0,0 1,1 2,2", "0 1,1"]
    for move in invalid_moves:
        result = move_controller.check_valid_input(move)
        assert result is False


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


def test_build_move_with_coordinate_target(terminal_loop_controller, board):
    my_piece = (0, 0)
    opp_piece = (0, 1)
    from paradux.controller import compute_valid_move_targets

    valid_targets = compute_valid_move_targets(board, my_piece, opp_piece)
    params = MoveBuildParams(board, my_piece, opp_piece, "1,1", valid_targets)
    move = terminal_loop_controller._build_move(params)
    assert move is not None
    assert move.player_move[1].coordinates == (1, 1)
    assert move.opponent_move[1].coordinates == (1, 2)


def test_build_move_switch_command(terminal_loop_controller, board):
    my_piece = (0, 0)
    opp_piece = (0, 1)
    from paradux.controller import compute_valid_move_targets

    valid_targets = compute_valid_move_targets(board, my_piece, opp_piece)
    params = MoveBuildParams(board, my_piece, opp_piece, "switch", valid_targets)
    move = terminal_loop_controller._build_move(params)
    assert move is not None
    assert move.player_move[1].coordinates == opp_piece
    assert move.opponent_move[1].coordinates == my_piece


@patch("builtins.print")
def test_build_move_rejects_invalid_target(_mock_print, terminal_loop_controller, board):
    my_piece = (0, 0)
    opp_piece = (0, 1)
    from paradux.controller import compute_valid_move_targets

    valid_targets = compute_valid_move_targets(board, my_piece, opp_piece)
    params = MoveBuildParams(board, my_piece, opp_piece, "0,0", valid_targets)
    move = terminal_loop_controller._build_move(params)
    assert move is None


def test_reset_gui_selection_called():
    mock_controller = MagicMock()
    term_view = TerminalView()
    controller = TerminalLoopController(game_controller=mock_controller, terminal_view=term_view)
    controller._reset_gui_selection()
    mock_controller.reset_selection.assert_called_once()


def test_start_new_game_returns_board(game_controller):
    board = game_controller.start_new_game()
    assert isinstance(board, BoardState)


def test_get_board_returns_none_initially(game_controller):
    assert game_controller.get_board() is None


def test_get_board_returns_board_after_start(game_controller):
    game_controller.start_new_game()
    assert game_controller.get_board() is not None


@patch("paradux.model.random.choice", return_value=Colour.RED)
@patch("builtins.print")
def test_apply_move_valid(_mock_print, _mock_choice, game_controller):
    game_controller.start_new_game()
    red_pos = (0, 1)
    blue_pos = (0, 0)
    current_one = Space(red_pos, Colour.RED)
    current_two = Space(blue_pos, Colour.BLUE)
    target_one = Space((1, 1), Colour.EMPTY)
    target_two = Space((1, 0), Colour.EMPTY)
    move = Move([current_one, target_one], [current_two, target_two])
    result = game_controller.apply_move(move)
    assert result is True


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


def test_reset_selection_no_error_without_board(game_controller):
    game_controller.reset_selection()


def test_reset_selection_notifies_views(game_controller):
    game_controller.start_new_game()
    view = MagicMock()
    game_controller.add_view(view)
    game_controller.reset_selection()
    view.on_selection_reset.assert_called_once()


def test_try_gui_move_no_board(game_controller):
    success, msg = game_controller.try_gui_move((0, 0), (1, 0), (0, 1), (1, 1))
    assert success is False
    assert msg == "No active game"


@patch("paradux.model.random.choice", return_value=Colour.RED)
def test_try_gui_move_valid_shift(_mock_choice, game_controller):
    game_controller.start_new_game()
    red_pos = (0, 1)
    blue_pos = (0, 0)
    red_target = (1, 1)
    blue_target = (1, 0)
    success, msg = game_controller.try_gui_move(red_pos, red_target, blue_pos, blue_target)
    assert success is True
    assert msg == ""


@patch("paradux.model.random.choice", return_value=Colour.RED)
def test_try_gui_move_swap(_mock_choice, game_controller):
    game_controller.start_new_game()
    red_pos = (0, 1)
    blue_pos = (0, 0)
    success, msg = game_controller.try_gui_move(red_pos, blue_pos, blue_pos, red_pos)
    assert success is True
    assert msg == ""


def test_list_saves(game_controller):
    saves = game_controller.list_saves()
    assert isinstance(saves, list)


def test_save_game_finished_game_raises(game_controller):
    board = game_controller.start_new_game()
    board.red_spaces = [(0, 0), (0, 1), (0, 2), (0, 3)]
    for coord in board.red_spaces:
        board.board_spaces[coord] = Colour.RED
    with pytest.raises(ValueError):
        game_controller.save_game("test")


def test_apply_move_illegal_move(game_controller):
    game_controller.start_new_game()
    move = Move(
        [Space((0, 0), Colour.RED), Space((5, 5), Colour.EMPTY)],
        [Space((0, 1), Colour.BLUE), Space((5, 6), Colour.EMPTY)],
    )
    result = game_controller.apply_move(move)
    assert result is False


def test_compute_valid_move_targets(board):
    my_piece = (0, 0)
    opp_piece = (0, 1)
    from paradux.controller import compute_valid_move_targets

    targets = compute_valid_move_targets(board, my_piece, opp_piece)
    assert isinstance(targets, list)


@patch.object(TerminalView, "display_error")
def test_build_move_invalid_target_format(mock_error, terminal_loop_controller, board):
    my_piece = (0, 0)
    opp_piece = (0, 1)
    from paradux.controller import compute_valid_move_targets

    valid_targets = compute_valid_move_targets(board, my_piece, opp_piece)
    params = MoveBuildParams(board, my_piece, opp_piece, "invalid", valid_targets)
    move = terminal_loop_controller._build_move(params)
    assert move is None
    mock_error.assert_called_once()


@patch("paradux.model.random.choice", return_value=Colour.RED)
def test_try_gui_move_undo_violation(_mock_choice, game_controller):
    game_controller.start_new_game()
    red_pos = (0, 1)
    blue_pos = (0, 0)
    red_target = (1, 1)
    blue_target = (1, 0)

    success, _ = game_controller.try_gui_move(red_pos, red_target, blue_pos, blue_target)
    assert success is True

    undo_success, msg = game_controller.try_gui_move(red_target, red_pos, blue_target, blue_pos)
    assert undo_success is False
    assert "undo" in msg.lower()


def test_try_gui_move_illegal_move_message(game_controller):
    game_controller.start_new_game()
    success, msg = game_controller.try_gui_move((0, 0), (5, 5), (0, 1), (5, 6))
    assert success is False
    assert "Illegal" in msg


def test_check_undo_violation_no_last_move(game_controller):
    board = game_controller.start_new_game()
    board.last_move = None
    success, msg = game_controller._check_undo_violation(board, (0, 0), (1, 0), (0, 1), (1, 1))
    assert success is False
    assert "Illegal" in msg


def test_board_tracking_state_defaults():
    state = BoardTrackingState()
    assert state.active_board_id is None
    assert state.paused_board_id is None
    assert state.allow_auto_resume is True
    assert state.last_seen_change is None


def test_wait_options_defaults():
    opts = WaitOptions()
    assert opts.allow_board_interrupt is False
    assert opts.force_board_check is False
    assert opts.check_menu_exit is False
    assert opts.check_game_resume is False


def test_move_build_params(board):
    params = MoveBuildParams(board, (0, 0), (0, 1), "1,1", [(1, 1)])
    assert params.my_piece == (0, 0)
    assert params.opp_piece == (0, 1)
    assert params.target_command == "1,1"


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
