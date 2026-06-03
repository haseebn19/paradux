from unittest.mock import patch

import pytest

from paradux.interfaces import Colour, MenuState, WinState
from paradux.model import BoardState
from paradux.view import BoardRenderer, TerminalView


@pytest.fixture
def renderer():
    return BoardRenderer()


@pytest.fixture
def board():
    return BoardState()


@pytest.fixture
def terminal_view():
    return TerminalView()


def test_tostring_board_spaces_empty_board(renderer, board):
    board.board_spaces = {}
    result = renderer.tostring_board_spaces(board)
    assert result == ""


def test_tostring_board_spaces_populated_board(renderer, board):
    board.board_spaces = {
        (0, 0): Colour.RED,
        (0, 1): Colour.BLUE,
        (1, 0): Colour.BLUE,
        (1, 1): Colour.RED,
    }
    result = renderer.tostring_board_spaces(board)
    assert "(0,0)" in result
    assert "(0,1)" in result


def test_tostring_includes_red_colour_code(renderer, board):
    result = renderer.tostring_board_spaces(board)
    assert "\033[31m" in result


def test_tostring_includes_blue_colour_code(renderer, board):
    result = renderer.tostring_board_spaces(board)
    assert "\033[34m" in result


def test_tostring_includes_coordinates(renderer, board):
    result = renderer.tostring_board_spaces(board)
    assert "(1,1)" in result


@patch("builtins.print")
def test_on_game_start_displays_board(_mock_print, terminal_view, board):
    terminal_view.on_game_start(board)
    assert terminal_view.board_state == board
    assert not terminal_view.game_over_flag


@patch("builtins.print")
def test_on_board_update_updates_state(_mock_print, terminal_view, board):
    terminal_view.on_board_update(board)
    assert terminal_view.board_state == board


@patch("builtins.print")
def test_on_game_over_sets_winner(_mock_print, terminal_view, board):
    terminal_view.on_game_over(board, WinState.RED)
    assert terminal_view.game_over_flag
    assert terminal_view.winner == WinState.RED


@patch("builtins.print")
def test_on_game_over_with_win_state(_mock_print, terminal_view, board):
    terminal_view.on_game_over(board, WinState.BLUE)
    assert terminal_view.game_over_flag
    assert terminal_view.winner == WinState.BLUE


def test_on_game_quit_no_error(terminal_view):
    terminal_view.on_game_quit()


@patch("builtins.print")
def test_on_game_loaded(mock_print, terminal_view, board):
    terminal_view.on_game_loaded(board, "test_save.json")
    mock_print.assert_called()
    call_args = str(mock_print.call_args)
    assert "test_save" in call_args


def test_on_menu_state_changed_no_error(terminal_view):
    terminal_view.on_menu_state_changed(MenuState.MAIN_MENU)


def test_on_selection_reset_no_error(terminal_view):
    terminal_view.on_selection_reset()


def test_initial_state(terminal_view):
    assert terminal_view.board_state is None
    assert not terminal_view.game_over_flag
    assert terminal_view.winner is None


@patch("builtins.print")
def test_on_game_start_prints_header(mock_print, terminal_view, board):
    terminal_view.on_game_start(board)
    calls = [str(c) for c in mock_print.call_args_list]
    header_found = any("Game Started" in c for c in calls)
    assert header_found


@patch("builtins.print")
def test_on_game_over_prints_winner(mock_print, terminal_view, board):
    terminal_view.on_game_over(board, WinState.RED)
    calls = [str(c) for c in mock_print.call_args_list]
    winner_found = any("winner" in c.lower() or "red" in c.lower() for c in calls)
    assert winner_found


@patch("builtins.print")
def test_on_game_over_tie(mock_print, terminal_view, board):
    terminal_view.on_game_over(board, WinState.TIE)
    calls = [str(c) for c in mock_print.call_args_list]
    tie_found = any("tie" in c.lower() for c in calls)
    assert tie_found


@patch("builtins.print")
def test_display_welcome(mock_print, terminal_view):
    terminal_view.display_welcome()
    mock_print.assert_called_with("Welcome to PARADUX")


@patch("builtins.print")
def test_display_goodbye(mock_print, terminal_view):
    terminal_view.display_goodbye()
    mock_print.assert_called_with("Goodbye!")


@patch("builtins.print")
def test_display_main_menu(mock_print, terminal_view):
    terminal_view.display_main_menu()
    calls = [str(c) for c in mock_print.call_args_list]
    assert any("Main Menu" in c for c in calls)
    assert any("New Game" in c for c in calls)
    assert any("Quit" in c for c in calls)


@patch("builtins.print")
def test_display_prompt(mock_print, terminal_view):
    terminal_view.display_prompt()
    mock_print.assert_called_with("> ", end="", flush=True)


@patch("builtins.print")
def test_display_rules(mock_print, terminal_view):
    terminal_view.display_rules()
    calls = [str(c) for c in mock_print.call_args_list]
    assert any("goal" in c.lower() for c in calls)


@patch("builtins.print")
def test_display_error(mock_print, terminal_view):
    terminal_view.display_error("Test error message")
    mock_print.assert_called_with("Error: Test error message")


@patch("builtins.print")
def test_display_move_prompt(mock_print, terminal_view):
    terminal_view.display_move_prompt("Red")
    calls = str(mock_print.call_args)
    assert "Red" in calls
    assert "piece1" in calls


@patch("builtins.print")
def test_display_save_prompt(mock_print, terminal_view):
    terminal_view.display_save_prompt()
    mock_print.assert_called_with(
        "Enter save name (or press Enter for default): ", end="", flush=True
    )


@patch("builtins.print")
def test_display_save_success(mock_print, terminal_view):
    terminal_view.display_save_success("/path/to/save.json")
    mock_print.assert_called_with("Game saved to: /path/to/save.json")


@patch("builtins.print")
def test_display_save_timeout(mock_print, terminal_view):
    terminal_view.display_save_timeout()
    mock_print.assert_called_with("Error: Save timed out")


@patch("builtins.print")
def test_display_no_saves(mock_print, terminal_view):
    terminal_view.display_no_saves()
    mock_print.assert_called_with("No saved games found")


@patch("builtins.print")
def test_display_saves_list(mock_print, terminal_view):
    saves = [("save1.json", "2024-01-01 12:00:00"), ("save2.json", "2024-01-02 12:00:00")]
    terminal_view.display_saves_list(saves)
    calls = [str(c) for c in mock_print.call_args_list]
    assert any("Saved Games" in c for c in calls)
    assert any("save1" in c for c in calls)
    assert any("save2" in c for c in calls)


@patch("builtins.print")
def test_display_deleted(mock_print, terminal_view):
    terminal_view.display_deleted("test_save")
    mock_print.assert_called_with("Deleted: test_save")


def test_token_colour_for_empty(renderer):
    result = renderer._token_colour((0, 0), Colour.EMPTY, 5)
    assert "(0,0)" in result
    assert "\033[31m" not in result
    assert "\033[34m" not in result


def test_get_borders_middle_row(renderer):
    # BOARD_ROWS is 7, so midpoint is 3.
    left, right = renderer._get_borders(3, 7)
    assert left == "|"
    assert right == "|"


def test_get_borders_bottom_rows(renderer):
    left, right = renderer._get_borders(5, 7)
    assert left == "\\"
    assert right == "/"
