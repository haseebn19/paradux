import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_LOGGING_RULES"] = "*=false"

from PyQt5.QtWidgets import QApplication

from paradux.controller import GameController
from paradux.gui_view import BoardWidget, GUISignals, GUIWindow
from paradux.interfaces import MenuState
from paradux.model import BoardState, GameState


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def signals():
    return GUISignals()


@pytest.fixture
def window():
    win = GUIWindow()
    yield win
    win.close()


@pytest.fixture
def widget():
    w = BoardWidget()
    yield w
    w.close()


def test_signals_exist(signals):
    assert hasattr(signals, "board_updated")
    assert hasattr(signals, "game_over")
    assert hasattr(signals, "game_started")
    assert hasattr(signals, "selection_reset")
    assert hasattr(signals, "quit_application")
    assert hasattr(signals, "menu_state_changed")
    assert hasattr(signals, "game_loaded")


def test_window_creation(window):
    assert window is not None


def test_window_title(window):
    assert window.windowTitle() == "PARADUX"


def test_set_controller(window):
    game_state = GameState()
    controller = GameController(game_state)
    window.set_controller(controller)
    assert window.game_controller == controller


def test_initial_state(window):
    assert window.game_controller is None
    assert window.board_state is None


def test_widget_creation(widget):
    assert widget is not None


def test_widget_initial_state(widget):
    assert widget.board_spaces == {}
    assert widget.selected_cells == []


def test_set_board(widget):
    board = BoardState()
    widget.set_board(board.board_spaces)
    assert widget.board_spaces == board.board_spaces


def test_clear_selection(widget):
    widget.selected_cells = [(0, 0), (0, 1)]
    widget.hint_cells = [(1, 0)]
    widget.clear_selection()
    assert widget.selected_cells == []
    assert widget.hint_cells == []


def test_set_selection(widget):
    cells = [(0, 0), (1, 1)]
    widget.set_selection(cells)
    assert widget.selected_cells == cells


def test_set_hints(widget):
    hints = [(2, 2), (3, 3)]
    widget.set_hints(hints)
    assert widget.hint_cells == hints


def test_on_board_update_emits_signal(window):
    board = BoardState()
    mock_slot = MagicMock()
    window.signals.board_updated.connect(mock_slot)
    window.on_board_update(board)
    mock_slot.assert_called_once()


def test_on_game_start_emits_signal(window):
    board = BoardState()
    mock_slot = MagicMock()
    window.signals.game_started.connect(mock_slot)
    window.on_game_start(board)
    mock_slot.assert_called_once()


def test_on_menu_state_changed_emits_signal(window):
    mock_slot = MagicMock()
    window.signals.menu_state_changed.connect(mock_slot)
    window.on_menu_state_changed(MenuState.MAIN_MENU)
    mock_slot.assert_called_once()


def test_on_game_quit_emits_signal(window):
    mock_slot = MagicMock()
    window.signals.quit_application.connect(mock_slot)
    window.on_game_quit()
    mock_slot.assert_called_once()


def test_on_selection_reset_emits_signal(window):
    mock_slot = MagicMock()
    window.signals.selection_reset.connect(mock_slot)
    window.on_selection_reset()
    mock_slot.assert_called_once()


def test_on_game_loaded_emits_signal(window):
    board = BoardState()
    mock_slot = MagicMock()
    window.signals.game_loaded.connect(mock_slot)
    window.on_game_loaded(board, "test_save")
    mock_slot.assert_called_once()


def test_set_board_triggers_update(widget):
    board = BoardState()
    with patch.object(widget, "update") as mock_update:
        widget.set_board(board.board_spaces)
        mock_update.assert_called_once()


def test_clear_selection_triggers_update(widget):
    widget.selected_cells = [(0, 0)]
    with patch.object(widget, "update") as mock_update:
        widget.clear_selection()
        mock_update.assert_called_once()


def test_set_selection_triggers_update(widget):
    with patch.object(widget, "update") as mock_update:
        widget.set_selection([(0, 0)])
        mock_update.assert_called_once()


def test_set_hints_triggers_update(widget):
    with patch.object(widget, "update") as mock_update:
        widget.set_hints([(1, 1)])
        mock_update.assert_called_once()
