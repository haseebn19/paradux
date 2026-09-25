"""Game domain models: Space, Move, BoardState, Player, and GameState."""

import random
from typing import ClassVar

from paradux.interfaces import (
    BOARD_ROW_RANGES,
    HEX_DIRECTIONS,
    LINE_DIRECTIONS,
    WIN_LINE_LENGTH,
    Colour,
    MenuState,
    WinState,
    are_adjacent,
)

Position = tuple[int, int]


def _step(start: Position, end: Position) -> Position:
    return end[0] - start[0], end[1] - start[1]


class Space:
    """A single cell on the hex board, identified by coordinates and colour."""

    def __init__(self, coordinates: tuple[int, int], colour: Colour) -> None:
        self.coordinates: tuple[int, int] = coordinates
        self.colour: Colour = colour

    @property
    def is_empty(self) -> bool:
        """Return True when this space has no piece on it."""
        return self.colour == Colour.EMPTY


class Player:
    """Tracks a player's assigned colour."""

    def __init__(self, colour: Colour) -> None:
        self.colour: Colour = colour


class Move:
    """A turn: the (start, end) spaces of the moving player's piece, then of the other piece.

    Each space records the colour on it before the move.
    """

    def __init__(self, player_move: list[Space], opponent_move: list[Space]) -> None:
        self.player_move: list[Space] = player_move
        self.opponent_move: list[Space] = opponent_move

    def is_move_legal(self, last_move: "Move | None" = None) -> bool:
        """Check the move against the rules.

        The two pieces must be adjacent and of different colours. They either swap places, or
        both step one space in the same direction, each into an empty space or the space the
        other piece is leaving. A move cannot undo `last_move`, the opponent's last move.
        """
        start_one, end_one = self.player_move
        start_two, end_two = self.opponent_move

        if {start_one.colour, start_two.colour} != {Colour.RED, Colour.BLUE}:
            return False
        if not are_adjacent(start_one.coordinates, start_two.coordinates):
            return False

        is_swap = (
            end_one.coordinates == start_two.coordinates
            and end_two.coordinates == start_one.coordinates
        )
        if not is_swap:
            step = _step(start_one.coordinates, end_one.coordinates)
            if (
                step not in HEX_DIRECTIONS
                or _step(start_two.coordinates, end_two.coordinates) != step
            ):
                return False
            for end, other_start in ((end_one, start_two), (end_two, start_one)):
                if not end.is_empty and end.coordinates != other_start.coordinates:
                    return False

        return last_move is None or not self._undoes(last_move)

    def _undoes(self, last_move: "Move") -> bool:
        """Return True if this move puts the pieces of `last_move` back where they started."""

        def ends(move: "Move", index: int) -> set[Position]:
            return {move.player_move[index].coordinates, move.opponent_move[index].coordinates}

        return ends(self, 0) == ends(last_move, 1) and ends(self, 1) == ends(last_move, 0)


class BoardState:
    """Game board: tracks piece positions and turn order."""

    STARTING_TOKENS: ClassVar[dict[Colour, list[tuple[int, int]]]] = {
        Colour.RED: [
            (0, 1),
            (0, 3),
            (1, 0),
            (2, 5),
            (3, 0),
            (4, 3),
            (4, 6),
            (5, 2),
            (6, 4),
            (6, 6),
        ],
        Colour.BLUE: [
            (0, 0),
            (0, 2),
            (1, 4),
            (2, 0),
            (2, 3),
            (3, 6),
            (4, 1),
            (5, 6),
            (6, 3),
            (6, 5),
        ],
    }

    def __init__(self) -> None:
        self.board_spaces: dict[Position, Colour] = {
            (row, col): Colour.EMPTY
            for row, (col_start, col_end) in BOARD_ROW_RANGES.items()
            for col in range(col_start, col_end)
        }
        for colour, positions in self.STARTING_TOKENS.items():
            for position in positions:
                self.board_spaces[position] = colour
        self.player_turn: Player = Player(Colour.BLUE)
        self.last_move: Move | None = None
        self.change_counter: int = 0

    @property
    def red_spaces(self) -> list[Position]:
        return [pos for pos, colour in self.board_spaces.items() if colour == Colour.RED]

    @property
    def blue_spaces(self) -> list[Position]:
        return [pos for pos, colour in self.board_spaces.items() if colour == Colour.BLUE]

    def switch_turn(self) -> Colour:
        current = self.player_turn.colour
        self.player_turn.colour = Colour.RED if current == Colour.BLUE else Colour.BLUE
        return self.player_turn.colour

    # -- Moves --

    def build_move(
        self, my_piece: Position, opp_piece: Position, my_target: Position | None = None
    ) -> Move | None:
        """Build the move of the current player's piece to `my_target`, with the other piece
        moving the same way, or a swap when `my_target` is None.

        Returns None when a piece would leave the board. The move is not checked against the rules.
        """
        if my_target is None:
            my_target, opp_target = opp_piece, my_piece
        else:
            step = _step(my_piece, my_target)
            opp_target = (opp_piece[0] + step[0], opp_piece[1] + step[1])
        if my_target not in self.board_spaces or opp_target not in self.board_spaces:
            return None

        def space(position: Position) -> Space:
            return Space(position, self.board_spaces[position])

        return Move([space(my_piece), space(my_target)], [space(opp_piece), space(opp_target)])

    def shift_targets(self, my_piece: Position, opp_piece: Position) -> list[Position]:
        """Return where the current player's piece can step to, with the other piece following."""
        targets = []
        for dr, dc in HEX_DIRECTIONS:
            target = (my_piece[0] + dr, my_piece[1] + dc)
            move = self.build_move(my_piece, opp_piece, target)
            if move is not None and move.is_move_legal(self.last_move):
                targets.append(target)
        return targets

    def apply_move(self, move: Move) -> None:
        """Move both pieces. The move must already be legal."""
        (start_one, end_one), (start_two, end_two) = move.player_move, move.opponent_move
        self.board_spaces[start_one.coordinates] = Colour.EMPTY
        self.board_spaces[start_two.coordinates] = Colour.EMPTY
        self.board_spaces[end_one.coordinates] = start_one.colour
        self.board_spaces[end_two.coordinates] = start_two.colour
        self.last_move = move
        self.change_counter += 1

    # -- Win detection --

    def check_win(self, preferred_colour: Colour | None = None) -> WinState:
        """Return the winner, if any.

        `preferred_colour` is the player who just moved: if a move completes a line for both
        colours, that player wins.
        """
        red_wins = self._has_winning_line(self.red_spaces)
        blue_wins = self._has_winning_line(self.blue_spaces)

        if red_wins and blue_wins:
            return WinState.BLUE if preferred_colour == Colour.BLUE else WinState.RED
        if red_wins:
            return WinState.RED
        if blue_wins:
            return WinState.BLUE
        return WinState.NONE

    def _has_winning_line(self, spaces: list[Position]) -> bool:
        """Return True if the spaces include WIN_LINE_LENGTH in a row along any axis."""
        occupied = set(spaces)
        return any(
            all((row + i * dr, col + i * dc) in occupied for i in range(WIN_LINE_LENGTH))
            for row, col in occupied
            for dr, dc in LINE_DIRECTIONS
        )


class GameState:
    """Top-level state machine: manages game lifecycle (new, continue, pause, quit)."""

    def __init__(self) -> None:
        self.can_continue: bool = False
        self._board_state: BoardState | None = None
        self._menu_state: MenuState = MenuState.MAIN_MENU

    def get_board(self) -> BoardState | None:
        return self._board_state

    def start_new_game(self) -> BoardState:
        self._board_state = BoardState()
        self._set_starting_player(self._board_state)
        self.can_continue = True
        self._menu_state = MenuState.IN_GAME
        return self._board_state

    def continue_game(self) -> BoardState:
        if self.can_continue and self._board_state is not None:
            if self._board_state.check_win() != WinState.NONE:
                raise ValueError("Game is already over. Start a new game.")
            self._menu_state = MenuState.IN_GAME
            return self._board_state
        raise ValueError("No game available to continue.")

    def load_game(self, loaded_board: BoardState) -> BoardState:
        self._board_state = loaded_board
        self.can_continue = True
        self._menu_state = MenuState.IN_GAME
        return self._board_state

    def quit(self) -> None:
        self._board_state = None
        self.can_continue = False
        self._menu_state = MenuState.MAIN_MENU

    def return_to_main_menu(self) -> None:
        """Leave the current game, which stays available to continue."""
        if self._board_state is not None:
            self.can_continue = True
        self._menu_state = MenuState.MAIN_MENU

    def get_menu_state(self) -> MenuState:
        return self._menu_state

    def _set_starting_player(self, board: BoardState) -> None:
        starting_colour = random.choice([Colour.BLUE, Colour.RED])
        board.player_turn.colour = starting_colour
