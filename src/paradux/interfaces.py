"""Shared enums, constants, and the GameView protocol interface for the Paradux game."""

from enum import Enum
from typing import Any, Protocol

# -- Board geometry constants --

BOARD_ROWS = 7
"""Number of rows on the hexagonal board."""

WIN_LINE_LENGTH = 4
"""Number of tokens in a row needed to win."""

TOKENS_PER_PLAYER = 10
"""Number of tokens each player starts with."""

HEX_DIRECTIONS = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, 0), (1, 1)]
"""Valid movement directions on the hexagonal grid."""

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
    TIE = 3


class MenuState(Enum):
    """UI navigation states."""

    MAIN_MENU = "main"
    PAUSE_MENU = "pause"
    IN_GAME = "game"


class GameView(Protocol):
    """Interface that views implement to receive game-state updates from the Presenter."""

    def on_board_update(self, board_state: Any) -> None: ...

    def on_game_over(self, board_state: Any, winner: WinState) -> None: ...

    def on_game_start(self, board_state: Any) -> None: ...

    def on_game_quit(self) -> None: ...

    def on_menu_state_changed(self, menu_state: MenuState) -> None: ...

    def on_game_loaded(self, board_state: Any, save_name: str) -> None: ...

    def on_selection_reset(self) -> None: ...


def are_adjacent(pos1: tuple[int, int], pos2: tuple[int, int]) -> bool:
    """Return True if two hex-grid positions are adjacent."""
    dr = pos2[0] - pos1[0]
    dc = pos2[1] - pos1[1]
    return (dr, dc) in HEX_DIRECTIONS or (-dr, -dc) in HEX_DIRECTIONS


def strip_json_extension(filename: str) -> str:
    """Remove a trailing '.json' extension for display purposes."""
    if filename.endswith(".json"):
        return filename[:-5]
    return filename
