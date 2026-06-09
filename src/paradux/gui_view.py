"""PyQt5 GUI view layer: board widget, selection state, and main window."""

import contextlib
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from paradux.controller import compute_valid_move_targets
from paradux.interfaces import (
    BOARD_ROW_RANGES,
    BOARD_ROWS,
    Colour,
    MenuState,
    WinState,
    are_adjacent,
)

# -- Colour constants for the GUI --

BOARD_CELL_BG = QColor(100, 150, 200)
BOARD_CELL_BORDER = QColor(70, 120, 180)

RED_PIECE_FILL = QColor(220, 50, 50)
RED_PIECE_BORDER = QColor(180, 30, 30)
RED_LABEL_CSS = "rgb(220, 50, 50)"

BLUE_PIECE_FILL = QColor(50, 100, 220)
BLUE_PIECE_BORDER = QColor(30, 70, 180)
BLUE_LABEL_CSS = "rgb(50, 100, 220)"

HINT_FILL = QColor(0, 255, 200, 60)
HINT_BORDER = QColor(0, 200, 150)
HINT_BORDER_WIDTH = 3

SELECTION_COLOUR_OWN = QColor(255, 255, 0)
SELECTION_COLOUR_OPP = QColor(0, 255, 0)
SELECTION_BORDER_WIDTH = 4

NEUTRAL_LABEL_CSS = "rgb(100, 100, 100)"
ERROR_LABEL_CSS = "rgb(200, 50, 50)"

WINDOW_BG_CSS = "background-color: rgb(200, 200, 200);"

BUTTON_BG = "rgb(70, 120, 180)"
BUTTON_HOVER = "rgb(100, 150, 200)"
BUTTON_PRESSED = "rgb(50, 100, 160)"

SWITCH_BG = "rgb(50, 180, 100)"
SWITCH_HOVER = "rgb(70, 200, 120)"
SWITCH_PRESSED = "rgb(40, 150, 80)"

# -- Board geometry constants --

_MIN_CELL_SIZE = 20
_CELL_INSET = 3
_CELL_BORDER_INSET = 5
_CLICK_INSET = 4
_ROW_SPACING_FACTOR = 0.85
_WIDTH_DIVISOR = 8
_HEIGHT_DIVISOR = 6.1


class GUISignals(QObject):
    """Thread-safe Qt signals for forwarding Presenter updates to the GUI thread."""

    board_updated = pyqtSignal(object)
    game_over = pyqtSignal(object, object)
    game_started = pyqtSignal(object)
    selection_reset = pyqtSignal()
    quit_application = pyqtSignal()
    menu_state_changed = pyqtSignal(object)
    game_loaded = pyqtSignal(object, str)


class BoardWidget(QWidget):
    """Hexagonal game board widget with click detection and rendering."""

    cell_clicked = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.board_spaces: dict = {}
        self.selected_cells: list[tuple[int, int]] = []
        self.hint_cells: list[tuple[int, int]] = []
        self.setMinimumSize(300, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    @property
    def cell_size(self) -> int:
        max_cell_by_width = self.width() // _WIDTH_DIVISOR
        max_cell_by_height = int(self.height() / _HEIGHT_DIVISOR)
        return max(min(max_cell_by_width, max_cell_by_height), _MIN_CELL_SIZE)

    def set_board(self, board_spaces: dict) -> None:
        self.board_spaces = board_spaces
        self.update()

    def set_selection(self, cells: list[tuple[int, int]]) -> None:
        self.selected_cells = cells
        self.update()

    def set_hints(self, cells: list[tuple[int, int]]) -> None:
        self.hint_cells = cells
        self.update()

    def clear_selection(self) -> None:
        self.selected_cells = []
        self.hint_cells = []
        self.update()

    def _get_cell_center(self, row: int, col: int) -> tuple[int, int]:
        col_start, col_end = BOARD_ROW_RANGES.get(row, (0, 0))
        col_count = col_end - col_start

        center_x = self.width() // 2
        center_y = self.height() // 2
        row_spacing = self.cell_size * _ROW_SPACING_FACTOR
        y = center_y - ((BOARD_ROWS // 2) * row_spacing) + row * row_spacing

        x_offset = center_x - (col_count * self.cell_size // 2)
        x = x_offset + (col - col_start) * self.cell_size + (self.cell_size // 2)

        return int(x), int(y)

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        self._draw_cells(painter)
        self._draw_hints(painter)
        self._draw_selections(painter)

    def _draw_cells(self, painter: QPainter) -> None:
        for row in range(BOARD_ROWS):
            col_start, col_end = BOARD_ROW_RANGES[row]
            for col in range(col_start, col_end):
                x, y = self._get_cell_center(row, col)
                radius = self.cell_size // 2 - _CELL_BORDER_INSET

                painter.setBrush(BOARD_CELL_BG)
                painter.setPen(QPen(BOARD_CELL_BORDER, 1))
                painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

                colour = self.board_spaces.get((row, col), Colour.EMPTY)
                if colour == Colour.RED:
                    self._draw_piece(painter, x, y, radius, RED_PIECE_FILL, RED_PIECE_BORDER)
                elif colour == Colour.BLUE:
                    self._draw_piece(painter, x, y, radius, BLUE_PIECE_FILL, BLUE_PIECE_BORDER)

    def _draw_piece(
        self, painter: QPainter, x: int, y: int, radius: int, fill: QColor, border: QColor
    ) -> None:
        inner_radius = radius - _CELL_INSET
        painter.setBrush(fill)
        painter.setPen(QPen(border, 1))
        painter.drawEllipse(x - inner_radius, y - inner_radius, inner_radius * 2, inner_radius * 2)

    def _draw_hints(self, painter: QPainter) -> None:
        for row, col in self.hint_cells:
            x, y = self._get_cell_center(row, col)
            radius = self.cell_size // 2 - _CELL_INSET
            painter.setBrush(HINT_FILL)
            pen = QPen(HINT_BORDER, HINT_BORDER_WIDTH, Qt.DashLine)
            painter.setPen(pen)
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

    def _draw_selections(self, painter: QPainter) -> None:
        selection_colours = [
            SELECTION_COLOUR_OWN,
            SELECTION_COLOUR_OWN,
            SELECTION_COLOUR_OPP,
            SELECTION_COLOUR_OPP,
        ]
        for i, (row, col) in enumerate(self.selected_cells):
            x, y = self._get_cell_center(row, col)
            radius = self.cell_size // 2 - _CELL_BORDER_INSET
            painter.setBrush(Qt.NoBrush)
            painter.setPen(
                QPen(selection_colours[i % len(selection_colours)], SELECTION_BORDER_WIDTH)
            )
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.LeftButton:
            pos = self._get_board_position(event.x(), event.y())
            if pos:
                self.cell_clicked.emit(pos[0], pos[1])

    def _get_board_position(self, mouse_x: int, mouse_y: int) -> tuple[int, int] | None:
        for row in range(BOARD_ROWS):
            col_start, col_end = BOARD_ROW_RANGES[row]
            for col in range(col_start, col_end):
                x, y = self._get_cell_center(row, col)
                dist = ((mouse_x - x) ** 2 + (mouse_y - y) ** 2) ** 0.5
                if dist <= self.cell_size // 2 - _CLICK_INSET:
                    return (row, col)
        return None


@dataclass
class SelectionState:
    """Tracks the multi-step piece selection for a GUI move."""

    piece1_current: tuple[int, int] | None = None
    piece1_target: tuple[int, int] | None = None
    piece2_current: tuple[int, int] | None = None
    piece2_target: tuple[int, int] | None = None
    selection_step: int = 0
    valid_adjacent_cells: list[tuple[int, int]] = field(default_factory=list)
    valid_move_targets: list[tuple[int, int]] = field(default_factory=list)


class LoadGameDialog(QDialog):
    """Modal dialog for selecting a saved game to load or delete."""

    def __init__(self, game_controller: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.game_controller = game_controller
        self._setup_ui()
        self._load_save_list()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Load Game")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        title = QLabel("Select a saved game to load:")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()

        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.accept)
        self.load_btn.setEnabled(False)
        btn_layout.addWidget(self.load_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

    def _load_save_list(self) -> None:
        self.list_widget.clear()
        saves = self.game_controller.list_saves()

        if not saves:
            item = QListWidgetItem("No saved games found")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.list_widget.addItem(item)
        else:
            for filename, timestamp in saves:
                display_text = f"{filename[:-5]}  ({timestamp})"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, filename)
                self.list_widget.addItem(item)

    def _on_selection_changed(self) -> None:
        has_selection = bool(self.list_widget.selectedItems())
        self.load_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole):
            self.accept()

    def _on_delete(self) -> None:
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        filename = selected_items[0].data(Qt.UserRole)
        if not filename:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{filename[:-5]}'?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            if self.game_controller.delete_save(filename):
                self._load_save_list()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete save file.")

    def get_selected_file(self) -> str | None:
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            return selected_items[0].data(Qt.UserRole)
        return None


class GUIWindow(QMainWindow):
    """Main application window: menu screens, game board, and move handling."""

    def __init__(self, game_controller: Any = None) -> None:
        super().__init__()
        self.game_controller = game_controller
        self.board_state: Any = None
        self.selection = SelectionState()
        self._headless = os.environ.get("QT_QPA_PLATFORM") == "offscreen"

        self.main_layout: QVBoxLayout | None = None
        self.menu_widget: QWidget | None = None
        self.menu_title: QLabel | None = None
        self.menu_btn_layout: QVBoxLayout | None = None
        self.menu_btn1: QPushButton | None = None
        self.menu_btn2: QPushButton | None = None
        self.menu_btn3: QPushButton | None = None
        self.menu_btn4: QPushButton | None = None
        self.menu_btn5: QPushButton | None = None
        self.game_widget: QWidget | None = None
        self.turn_label: QLabel | None = None
        self.board_widget: BoardWidget | None = None
        self.instruction_label: QLabel | None = None
        self.save_game_btn: QPushButton | None = None
        self.menu_btn: QPushButton | None = None
        self.switch_btn: QPushButton | None = None
        self.reset_btn: QPushButton | None = None
        self.stacked_widget: QStackedWidget | None = None
        self._scale = 1.0

        self.signals = GUISignals()
        self.signals.board_updated.connect(self._handle_board_update)
        self.signals.game_over.connect(self._handle_game_over)
        self.signals.game_started.connect(self._handle_game_start)
        self.signals.selection_reset.connect(self._reset_selection)
        self.signals.quit_application.connect(QApplication.instance().quit)
        self.signals.menu_state_changed.connect(self._handle_menu_state_changed)
        self.signals.game_loaded.connect(self._handle_game_loaded_signal)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("PARADUX")
        self._set_window_size()
        self.setStyleSheet(WINDOW_BG_CSS)
        icon_path = Path(__file__).parent / "assets" / "logo.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _set_window_size(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.availableGeometry()
            width = min(int(screen_size.width() * 0.7), 800)
            height = min(int(screen_size.height() * 0.9), 700)
            width = max(width, 450)
            height = max(height, 400)
            self._scale = min(height / 700, 1.0)
        else:
            width, height = 550, 480
            self._scale = 0.7
        self.setFixedSize(width, height)
        self._build_ui()

    def _scaled(self, value: int) -> int:
        return max(1, int(value * self._scale))

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setSpacing(self._scaled(10))

        title = QLabel("PARADUX")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color: black; font-size: {self._scaled(36)}px; "
            f"font-weight: bold; padding: {self._scaled(10)}px;"
        )
        self.main_layout.addWidget(title)

        self._build_menu_ui()
        self._build_game_ui()

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.menu_widget)
        self.stacked_widget.addWidget(self.game_widget)
        self.main_layout.addWidget(self.stacked_widget)

        self._show_menu_ui()

    def _build_menu_ui(self) -> None:
        self.menu_widget = QWidget()
        menu_layout = QVBoxLayout(self.menu_widget)
        menu_layout.setSpacing(self._scaled(15))

        self.menu_title = QLabel("Main Menu")
        self.menu_title.setAlignment(Qt.AlignCenter)
        self.menu_title.setStyleSheet(
            f"color: black; font-size: {self._scaled(24)}px; "
            f"font-weight: bold; padding: {self._scaled(15)}px;"
        )
        menu_layout.addWidget(self.menu_title)

        self.menu_btn_layout = QVBoxLayout()
        self.menu_btn_layout.setSpacing(self._scaled(10))

        menu_items = [
            ("1 = New Game", self._on_menu_new_game),
            ("2 = Continue Current Game", self._on_menu_continue),
            ("3 = Load Game", self._on_load_game),
            ("4 = Rules", self._on_show_rules),
            ("5 = Quit Game", self._on_menu_quit),
        ]
        self.menu_btn1, self.menu_btn2, self.menu_btn3, self.menu_btn4, self.menu_btn5 = (
            self._create_menu_button(text, handler) for text, handler in menu_items
        )

        menu_layout.addLayout(self.menu_btn_layout)
        menu_layout.addStretch()

    def _create_menu_button(self, text: str, handler: Any) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(self._menu_button_style())
        btn.clicked.connect(handler)
        self.menu_btn_layout.addWidget(btn)
        return btn

    def _build_game_ui(self) -> None:
        self.game_widget = QWidget()
        game_layout = QVBoxLayout(self.game_widget)
        game_layout.setSpacing(self._scaled(5))

        self.turn_label = QLabel("Waiting for game...")
        self.turn_label.setAlignment(Qt.AlignCenter)
        self._set_turn_label_style(NEUTRAL_LABEL_CSS)
        game_layout.addWidget(self.turn_label)

        self.board_widget = BoardWidget()
        self.board_widget.cell_clicked.connect(self._on_cell_clicked)
        game_layout.addWidget(self.board_widget, 1)

        self.instruction_label = QLabel("ESC = Reset Selection")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self._set_instruction_style(NEUTRAL_LABEL_CSS)
        game_layout.addWidget(self.instruction_label)

        btn_layout = QHBoxLayout()

        self.save_game_btn = QPushButton("Save Game")
        self.save_game_btn.setStyleSheet(self._button_style())
        self.save_game_btn.clicked.connect(self._on_save_game)
        btn_layout.addWidget(self.save_game_btn)

        self.menu_btn = QPushButton("Menu")
        self.menu_btn.setStyleSheet(self._button_style())
        self.menu_btn.clicked.connect(self._on_show_pause_menu)
        btn_layout.addWidget(self.menu_btn)

        self.switch_btn = QPushButton("Switch Pieces")
        self.switch_btn.setStyleSheet(self._switch_button_style())
        self.switch_btn.clicked.connect(self._on_switch)
        self.switch_btn.setVisible(False)
        btn_layout.addWidget(self.switch_btn)

        self.reset_btn = QPushButton("Reset Selection")
        self.reset_btn.setStyleSheet(self._button_style())
        self.reset_btn.clicked.connect(self._reset_selection)
        btn_layout.addWidget(self.reset_btn)

        game_layout.addLayout(btn_layout)

    def _button_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: white;
                border: 2px solid white;
                padding: {self._scaled(8)}px {self._scaled(16)}px;
                font-size: {self._scaled(14)}px;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {BUTTON_PRESSED};
            }}
        """

    def _switch_button_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {SWITCH_BG};
                color: white;
                border: 2px solid white;
                padding: {self._scaled(8)}px {self._scaled(16)}px;
                font-size: {self._scaled(14)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {SWITCH_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {SWITCH_PRESSED};
            }}
        """

    def _menu_button_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: white;
                border: 2px solid white;
                padding: {self._scaled(12)}px {self._scaled(24)}px;
                font-size: {self._scaled(16)}px;
                min-width: {self._scaled(200)}px;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {BUTTON_PRESSED};
            }}
        """

    # -- Styling helpers --

    def _set_turn_label_style(self, colour_css: str) -> None:
        self.turn_label.setStyleSheet(
            f"color: {colour_css}; font-size: {self._scaled(18)}px; padding: {self._scaled(3)}px;"
        )

    def _set_instruction_style(self, colour_css: str, bold: bool = False) -> None:
        weight = "font-weight: bold;" if bold else ""
        self.instruction_label.setStyleSheet(
            f"color: {colour_css}; font-size: {self._scaled(14)}px; {weight}"
        )

    def _colour_css_for_turn(self, turn_value: str) -> str:
        return RED_LABEL_CSS if turn_value == "Red" else BLUE_LABEL_CSS

    # -- Signal relay helpers --

    def _try_emit(self, emit_func: Any) -> None:
        with contextlib.suppress(RuntimeError):
            emit_func()

    # -- GameView interface --

    def on_board_update(self, board_state: Any) -> None:
        self._try_emit(lambda: self.signals.board_updated.emit(board_state))

    def on_game_over(self, board_state: Any, winner: WinState) -> None:
        self._try_emit(lambda: self.signals.game_over.emit(board_state, winner))

    def on_game_start(self, board_state: Any) -> None:
        self._try_emit(lambda: self.signals.game_started.emit(board_state))

    def on_game_quit(self) -> None:
        self._try_emit(self.signals.quit_application.emit)

    def on_menu_state_changed(self, menu_state: MenuState) -> None:
        self._try_emit(lambda: self.signals.menu_state_changed.emit(menu_state))

    def on_game_loaded(self, board_state: Any, save_name: str) -> None:
        self._try_emit(lambda: self.signals.game_loaded.emit(board_state, save_name))

    def on_selection_reset(self) -> None:
        self._try_emit(self.signals.selection_reset.emit)

    # -- Signal handlers --

    def _handle_board_update(self, board_state: Any) -> None:
        self.board_state = board_state
        self.board_widget.set_board(board_state.board_spaces)
        self.board_widget.set_hints([])
        self.selection.valid_adjacent_cells = []
        self.selection.valid_move_targets = []
        turn_colour = board_state.player_turn.colour.value
        self.turn_label.setText(f"{turn_colour}'s turn")
        self._set_turn_label_style(self._colour_css_for_turn(turn_colour))

    def _handle_game_over(self, board_state: Any, winner: WinState) -> None:
        self.board_widget.set_board(board_state.board_spaces)
        winner_text = (
            "Red" if winner == WinState.RED else "Blue" if winner == WinState.BLUE else "Tie"
        )
        self.turn_label.setText(f"Game Over - {winner_text} wins!")

        if winner == WinState.RED:
            css = RED_LABEL_CSS
        elif winner == WinState.BLUE:
            css = BLUE_LABEL_CSS
        else:
            css = NEUTRAL_LABEL_CSS
        self._set_turn_label_style(css)

        board_id_before = id(board_state)
        if not self._headless:
            QMessageBox.information(self, "Game Over", f"{winner_text} wins!")

        if self.game_controller:
            current_board = self.game_controller.get_board()
            if current_board is None or id(current_board) == board_id_before:
                self.game_controller.game_state.return_to_main_menu()

    def _handle_game_start(self, board_state: Any) -> None:
        self.board_state = board_state
        self.board_widget.set_board(board_state.board_spaces)
        self._reset_selection()
        turn_colour = board_state.player_turn.colour.value
        self.turn_label.setText(f"{turn_colour}'s Turn")
        self._set_turn_label_style(self._colour_css_for_turn(turn_colour))

    def _handle_game_loaded_signal(self, _board_state: Any, save_name: str) -> None:
        if not self._headless:
            QTimer.singleShot(
                100,
                lambda: QMessageBox.information(self, "Game Loaded", f"Game loaded: {save_name}"),
            )

    # -- Cell selection logic --

    def _get_valid_adjacent_pieces(self, pos: tuple[int, int]) -> list[tuple[int, int]]:
        if self.board_state is None:
            return []
        my_colour = self.board_state.board_spaces.get(pos, Colour.EMPTY)
        valid = []
        for dr, dc in ((d[0], d[1]) for d in [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, 0), (1, 1)]):
            new_pos = (pos[0] + dr, pos[1] + dc)
            if self.board_state and new_pos in self.board_state.board_spaces:
                adj_colour = self.board_state.board_spaces.get(new_pos, Colour.EMPTY)
                if adj_colour not in (Colour.EMPTY, my_colour):
                    valid.append(new_pos)
        return valid

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if self.board_state is None:
            return

        piece_colour = self.board_state.board_spaces.get((row, col), Colour.EMPTY)

        if self.selection.selection_step == 0:
            self._handle_step0_selection(row, col, piece_colour)
        elif self.selection.selection_step == 1:
            self._handle_step1_selection(row, col, piece_colour)
        elif self.selection.selection_step == 2:
            self._handle_step2_selection(row, col)

    def _handle_step0_selection(self, row: int, col: int, piece_colour: Colour) -> None:
        if piece_colour != Colour.EMPTY:
            self.selection.piece1_current = (row, col)
            self.selection.selection_step = 1
            self._update_selection_display()
            self.selection.valid_adjacent_cells = self._get_valid_adjacent_pieces((row, col))
            self.selection.valid_move_targets = []
            self.board_widget.set_hints(self.selection.valid_adjacent_cells)
            self.instruction_label.setText("Click a highlighted adjacent piece")
            self._set_instruction_style(NEUTRAL_LABEL_CSS)
        else:
            self._show_error("Click on a piece, not an empty space")

    def _handle_step1_selection(self, row: int, col: int, piece_colour: Colour) -> None:
        if piece_colour == Colour.EMPTY:
            self._show_error("Click on a piece, not an empty space")
            return
        if (row, col) not in self.selection.valid_adjacent_cells:
            self._show_error("Select a highlighted adjacent piece")
            return

        first_colour = self.board_state.board_spaces.get(
            self.selection.piece1_current, Colour.EMPTY
        )
        if piece_colour == first_colour:
            self._show_error("Must select a piece of different color")
            return
        if not are_adjacent(self.selection.piece1_current, (row, col)):
            self._show_error("Pieces must be adjacent to each other")
            return

        self.selection.piece2_current = (row, col)
        self.selection.selection_step = 2
        self._update_selection_display()
        self.switch_btn.setVisible(True)

        my_piece, opp_piece = self._determine_pieces()
        hints = compute_valid_move_targets(self.board_state, my_piece, opp_piece)
        self.selection.valid_move_targets = hints
        self.board_widget.set_hints(hints)
        turn_colour = self.board_state.player_turn.colour
        self.instruction_label.setText(
            f"Click position for {turn_colour.value}, or click 'Switch Pieces'"
        )
        self._set_instruction_style(NEUTRAL_LABEL_CSS)

    def _handle_step2_selection(self, row: int, col: int) -> None:
        if (row, col) not in self.selection.valid_move_targets:
            self._show_error("Select a highlighted target or click Switch")
            return
        self._attempt_move_with_direction((row, col))

    def _determine_pieces(self) -> tuple[tuple[int, int], tuple[int, int]]:
        turn_colour = self.board_state.player_turn.colour
        piece1_colour = self.board_state.board_spaces.get(
            self.selection.piece1_current, Colour.EMPTY
        )
        if piece1_colour == turn_colour:
            return self.selection.piece1_current, self.selection.piece2_current
        return self.selection.piece2_current, self.selection.piece1_current

    def _update_selection_display(self) -> None:
        cells = []
        for attr in ("piece1_current", "piece1_target", "piece2_current", "piece2_target"):
            val = getattr(self.selection, attr)
            if val is not None:
                cells.append(val)
        self.board_widget.set_selection(cells)

    def _reset_selection(self, show_default_msg: bool = True) -> None:
        self.selection = SelectionState()
        self.board_widget.clear_selection()
        self.switch_btn.setVisible(False)
        if show_default_msg:
            self.instruction_label.setText("Select two adjacent pieces to move")
            self._set_instruction_style(NEUTRAL_LABEL_CSS)

    def _show_error(self, message: str) -> None:
        self.instruction_label.setText(f"Error: {message}")
        self._set_instruction_style(ERROR_LABEL_CSS, bold=True)

    def _attempt_move_with_direction(self, player_target: tuple[int, int]) -> None:
        if self.board_state is None or self.game_controller is None:
            self._reset_selection()
            return

        turn_colour = self.board_state.player_turn.colour
        piece1_colour = self.board_state.board_spaces.get(
            self.selection.piece1_current, Colour.EMPTY
        )

        if piece1_colour == turn_colour:
            my_piece = self.selection.piece1_current
            opponent_piece = self.selection.piece2_current
        else:
            my_piece = self.selection.piece2_current
            opponent_piece = self.selection.piece1_current

        if not are_adjacent(my_piece, player_target):
            self._show_error("Target must be adjacent to your piece")
            self._reset_selection(show_default_msg=False)
            return

        dx = player_target[0] - my_piece[0]
        dy = player_target[1] - my_piece[1]
        opponent_target = (opponent_piece[0] + dx, opponent_piece[1] + dy)

        if opponent_target not in self.board_state.board_spaces:
            self._show_error("Opponent piece would move off the board")
            self._reset_selection(show_default_msg=False)
            return

        self.selection.piece1_target = (
            player_target if piece1_colour == turn_colour else opponent_target
        )
        self.selection.piece2_target = (
            opponent_target if piece1_colour == turn_colour else player_target
        )

        self._attempt_move()

    def _attempt_move(self) -> None:
        if self.game_controller is None:
            self._reset_selection()
            return

        success, error_msg = self.game_controller.try_gui_move(
            self.selection.piece1_current,
            self.selection.piece1_target,
            self.selection.piece2_current,
            self.selection.piece2_target,
        )

        if success:
            self._reset_selection()
        else:
            if error_msg:
                self._show_error(error_msg)
            self._reset_selection(show_default_msg=False)

    def _on_switch(self) -> None:
        if self.board_state is None or self.game_controller is None:
            return
        if self.selection.piece1_current is None or self.selection.piece2_current is None:
            return

        self.selection.piece1_target = self.selection.piece2_current
        self.selection.piece2_target = self.selection.piece1_current
        self._attempt_move()

    def _handle_menu_state_changed(self, menu_state: MenuState) -> None:
        if menu_state == MenuState.MAIN_MENU:
            self._show_main_menu()
        elif menu_state == MenuState.IN_GAME:
            self._show_game_ui()

    def _show_menu_ui(self) -> None:
        self.stacked_widget.setCurrentIndex(0)

    def _show_game_ui(self) -> None:
        self.stacked_widget.setCurrentIndex(1)

    def _show_main_menu(self) -> None:
        self.menu_title.setText("Main Menu")
        self.menu_btn1.setVisible(True)
        self.menu_btn2.setVisible(True)
        self.menu_btn3.setVisible(True)
        self.menu_btn4.setVisible(True)
        self._show_menu_ui()

    def _on_menu_new_game(self) -> None:
        if self.game_controller:
            self.game_controller.start_new_game()

    def _on_menu_continue(self) -> None:
        if self.game_controller:
            try:
                self.game_controller.game_state.continue_game()
            except ValueError:
                QMessageBox.warning(self, "Error", "No game available to continue")

    def _on_menu_quit(self) -> None:
        if self.game_controller:
            self.game_controller.game_state.quit()

    def _on_show_pause_menu(self) -> None:
        if self.game_controller:
            self.game_controller.game_state.return_to_main_menu()

    def _on_show_rules(self) -> None:
        rules_text = (
            "The goal of the game is to get 4 pieces of your colour in a row.\n\n"
            "Select two adjacent pieces (different colors), then choose where YOUR piece moves.\n"
            "The opponent's piece will follow in the same direction."
        )
        QMessageBox.information(self, "Rules", rules_text)

    def set_controller(self, controller: Any) -> None:
        self.game_controller = controller

    def _on_save_game(self) -> None:
        if self.game_controller is None:
            QMessageBox.warning(self, "Error", "No game controller available.")
            return

        board_id_before = id(self.board_state) if self.board_state else None

        save_name, ok = QInputDialog.getText(
            self,
            "Save Game",
            "Enter a name for this save:",
            text=f"save_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
        )

        if ok and save_name:
            current_board = self.game_controller.get_board()
            if current_board is None or id(current_board) != board_id_before:
                QMessageBox.warning(
                    self,
                    "Save Cancelled",
                    "The game changed while the dialog was open. Save cancelled.",
                )
                return

            try:
                self.game_controller.save_game(save_name)
                QMessageBox.information(self, "Save Successful", "Game saved successfully!")
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))
            except OSError as e:
                QMessageBox.critical(self, "Save Failed", f"Failed to save game: {e!s}")

    def _on_load_game(self) -> None:
        if self.game_controller is None:
            QMessageBox.warning(self, "Error", "No game controller available.")
            return

        board_before = self.game_controller.get_board()
        board_id_before = id(board_before) if board_before else None
        menu_state_before = self.game_controller.game_state.get_menu_state()

        dialog = LoadGameDialog(self.game_controller, self)

        if dialog.exec_() == QDialog.Accepted:
            board_after = self.game_controller.get_board()
            board_id_after = id(board_after) if board_after else None
            menu_state_after = self.game_controller.game_state.get_menu_state()
            if board_id_before != board_id_after or menu_state_before != menu_state_after:
                QMessageBox.warning(
                    self,
                    "Load Cancelled",
                    "Game state changed while the dialog was open. Load cancelled.",
                )
                return

            filename = dialog.get_selected_file()
            if filename:
                try:
                    self.game_controller.load_game(filename)
                except FileNotFoundError:
                    QMessageBox.warning(self, "Load Failed", "Save file not found.")
                except OSError as e:
                    QMessageBox.critical(self, "Load Failed", f"Failed to load game: {e!s}")
