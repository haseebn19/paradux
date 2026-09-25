import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_LOGGING_RULES"] = "*=false"

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QDialog

from paradux.controller import GameController
from paradux.gui_view import GUIWindow
from paradux.interfaces import Colour
from paradux.model import GameState


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def controller():
    return GameController(GameState())


@pytest.fixture
def window(controller):
    win = GUIWindow(controller)
    controller.add_view(win)
    yield win
    win.close()


@pytest.fixture
def game(qapp, window, controller):
    """Start a game where Red moves first."""
    with patch("paradux.model.random.choice", return_value=Colour.RED):
        controller.start_new_game()
    qapp.processEvents()
    assert window.stacked_widget.currentIndex() == 1
    return controller


def test_window_opens_on_the_main_menu(window):
    assert window.windowTitle() == "PARADUX"
    assert window.stacked_widget.currentIndex() == 0


def test_clicking_two_pieces_and_a_target_makes_a_move(qapp, window, game):
    window._on_cell_clicked(0, 1)  # Red piece
    assert window.board_widget.own_selection == [(0, 1)]
    assert window.board_widget.hint_cells == [(0, 0), (0, 2)]

    window._on_cell_clicked(0, 0)  # Adjacent blue piece
    assert window.board_widget.opponent_selection == [(0, 0)]
    assert window.selection.valid_move_targets == [(1, 2)]
    assert window.switch_btn.isVisibleTo(window)

    window._on_cell_clicked(1, 2)
    qapp.processEvents()

    board = game.get_board()
    assert board.board_spaces[(1, 2)] == Colour.RED
    assert board.board_spaces[(1, 1)] == Colour.BLUE
    assert window.selection.selection_step == 0
    assert window.turn_label.text() == "Blue's turn"


@pytest.mark.usefixtures("game")
def test_selecting_an_opponent_piece_first_outlines_it_as_the_opponents(window):
    window._on_cell_clicked(0, 0)  # Blue piece while Red is to move
    assert window.board_widget.own_selection == []
    assert window.board_widget.opponent_selection == [(0, 0)]


@pytest.mark.usefixtures("game")
def test_clicking_an_empty_space_shows_an_error(window):
    window._on_cell_clicked(3, 3)
    assert window.instruction_label.text() == "Error: Click on a piece, not an empty space"
    assert window.selection.selection_step == 0


def test_switch_button_swaps_the_selected_pieces(qapp, window, game):
    window._on_cell_clicked(0, 1)
    window._on_cell_clicked(0, 0)
    window.switch_btn.click()
    qapp.processEvents()

    assert game.get_board().board_spaces[(0, 0)] == Colour.RED


@pytest.mark.usefixtures("game")
def test_escape_resets_the_selection(window):
    window._on_cell_clicked(0, 1)
    assert window.selection.selection_step == 1

    window.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))

    assert window.selection.selection_step == 0
    assert window.board_widget.hint_cells == []
    assert window.board_widget.own_selection == []


@pytest.mark.usefixtures("game")
def test_menu_button_returns_to_the_main_menu_and_continue_comes_back(qapp, window):
    assert window.stacked_widget.currentIndex() == 1

    window.menu_btn.click()
    qapp.processEvents()
    assert window.stacked_widget.currentIndex() == 0

    window._on_menu_continue()
    qapp.processEvents()
    assert window.stacked_widget.currentIndex() == 1


def test_a_move_typed_in_the_terminal_clears_the_selection(qapp, window, game):
    window._on_cell_clicked(0, 1)
    game.try_move((0, 1), (0, 0), (1, 2))
    qapp.processEvents()

    assert window.selection.selection_step == 0
    assert window.board_widget.board_spaces[(1, 2)] == Colour.RED


def test_loading_a_damaged_save_shows_the_reason(window):
    window.game_controller = MagicMock()
    window.game_controller.load_game.side_effect = ValueError(
        "damaged.json is not a valid save file"
    )
    dialog = MagicMock()
    dialog.exec_.return_value = QDialog.Accepted
    dialog.get_selected_file.return_value = "damaged.json"

    with (
        patch("paradux.gui_view.LoadGameDialog", return_value=dialog),
        patch("paradux.gui_view.QMessageBox.warning") as warning,
    ):
        window._on_load_game()

    warning.assert_called_once_with(window, "Load Failed", "damaged.json is not a valid save file")


def test_quit_button_closes_the_application(qapp, window, game):
    quit_slot = MagicMock()
    window.signals.quit_application.connect(quit_slot)

    window._on_menu_quit()
    qapp.processEvents()

    quit_slot.assert_called_once()
    assert game.get_board() is None
