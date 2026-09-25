"""Shared enums, constants, and the GameView protocol interface for the Paradux game."""

from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from paradux.model import BoardState

# -- Board geometry constants --

BOARD_ROWS = 7
"""Number of rows on the hexagonal board."""

WIN_LINE_LENGTH = 4
"""Number of tokens in a row needed to win."""

HEX_DIRECTIONS = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, 0), (1, 1)]
"""(row, column) steps to the six neighbours of a cell on the hexagonal grid."""

LINE_DIRECTIONS = [(0, 1), (1, 0), (1, 1)]
"""The three axes a winning line can run along, one direction per axis."""

BOARD_ROW_RANGES: dict[int, tuple[int, int]] = {
    0: (0, 4),
    1: (0, 5),
    2: (0, 6),
    3: (0, 7),
    4: (1, 7),
    5: (2, 7),
    6: (3, 7),
}
"""Maps each row index to its (col_start, col_end) range on the hex board."""

RULES = (
    f"The goal of the game is to get {WIN_LINE_LENGTH} pieces of your colour in a row.",
    "Select two adjacent pieces of different colours, then choose where YOUR piece moves. "
    "The other piece moves in the same direction.",
    "You can also switch the two pieces, but you cannot undo your opponent's last move.",
)
"""The rules, one paragraph each, as both views show them."""

INPUT_POLL_INTERVAL = 0.1
"""Seconds between input queue polls in the terminal loop."""

THREAD_JOIN_TIMEOUT = 0.5
"""Seconds to wait for the terminal thread to finish on exit."""


class Colour(Enum):
    """Piece colours and the empty-space marker."""

    RED = "Red"
    BLUE = "Blue"
    EMPTY = "Empty"


class WinState(Enum):
    """Possible game outcomes."""

    NONE = 0
    RED = 1
    BLUE = 2


class MenuState(Enum):
    """UI navigation states."""

    MAIN_MENU = "main"
    IN_GAME = "game"


class GameView(Protocol):
    """Interface that views implement to receive game-state updates from the Presenter."""

    def on_board_update(self, board_state: "BoardState") -> None: ...

    def on_game_over(self, board_state: "BoardState", winner: WinState) -> None: ...

    def on_game_start(self, board_state: "BoardState") -> None: ...

    def on_game_quit(self) -> None: ...

    def on_menu_state_changed(self, menu_state: MenuState) -> None: ...

    def on_game_loaded(self, board_state: "BoardState", save_name: str) -> None: ...


def are_adjacent(pos1: tuple[int, int], pos2: tuple[int, int]) -> bool:
    """Return True if two hex-grid positions are adjacent."""
    return (pos2[0] - pos1[0], pos2[1] - pos1[1]) in HEX_DIRECTIONS


def strip_json_extension(filename: str) -> str:
    """Remove a trailing '.json' extension for display purposes."""
    return filename.removesuffix(".json")
