"""Game domain models: Space, Move, BoardState, Player, and GameState."""

import random
from typing import ClassVar, Optional

from paradux.interfaces import (
    BOARD_ROW_RANGES,
    HEX_DIRECTIONS,
    WIN_LINE_LENGTH,
    Colour,
    MenuState,
    WinState,
)


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
    """A complete turn: two (current, target) space pairs, one per piece."""

    def __init__(self, player_move: list[Space], opponent_move: list[Space]) -> None:
        self.player_move: list[Space] = player_move
        self.opponent_move: list[Space] = opponent_move

    def is_move_legal(self, last_move: Optional["Move"] = None) -> bool:
        """Validate every aspect of this move, optionally checking for undo."""
        if not self._validate_move_structure():
            return False

        current_one, target_one = self.player_move
        current_two, target_two = self.opponent_move

        if not self._validate_colours(current_one, current_two):
            return False
        if not self._validate_adjacency(current_one, current_two, target_one, target_two):
            return False
        if last_move is not None and self._is_reverse_move(
            last_move, current_one, current_two, target_one, target_two
        ):
            return False

        return self._validate_targets(target_one, target_two, current_one, current_two)

    def _validate_move_structure(self) -> bool:
        return len(self.player_move) == 2 and len(self.opponent_move) == 2

    def _validate_colours(self, current_one: Space, current_two: Space) -> bool:
        colours = {current_one.colour, current_two.colour}
        return colours == {Colour.RED, Colour.BLUE}

    def _validate_adjacency(
        self,
        current_one: Space,
        current_two: Space,
        target_one: Space,
        target_two: Space,
    ) -> bool:
        def _are_hex_adjacent(space_a: Space, space_b: Space) -> bool:
            dr = space_b.coordinates[0] - space_a.coordinates[0]
            dc = space_b.coordinates[1] - space_a.coordinates[1]
            return (dr, dc) in HEX_DIRECTIONS

        return (
            _are_hex_adjacent(current_one, current_two)
            and _are_hex_adjacent(target_one, target_two)
            and _are_hex_adjacent(current_one, target_one)
            and _are_hex_adjacent(current_two, target_two)
        )

    def _is_reverse_move(
        self,
        last_move: "Move",
        current_one: Space,
        current_two: Space,
        target_one: Space,
        target_two: Space,
    ) -> bool:
        last_start_positions = {
            last_move.player_move[0].coordinates,
            last_move.opponent_move[0].coordinates,
        }
        last_end_positions = {
            last_move.player_move[1].coordinates,
            last_move.opponent_move[1].coordinates,
        }
        current_positions = {current_one.coordinates, current_two.coordinates}
        new_target_positions = {target_one.coordinates, target_two.coordinates}
        return (
            current_positions == last_end_positions and new_target_positions == last_start_positions
        )

    def _validate_targets(
        self,
        target_one: Space,
        target_two: Space,
        current_one: Space,
        current_two: Space,
    ) -> bool:
        if target_one.colour == Colour.EMPTY and target_two.colour == Colour.EMPTY:
            return True

        occupied_count = sum(
            1 for target in (target_one, target_two) if target.colour != Colour.EMPTY
        )
        if occupied_count != 2:
            return False

        for target, opposing_current in ((target_one, current_two), (target_two, current_one)):
            if target.colour != Colour.EMPTY and (
                target.coordinates != opposing_current.coordinates
                or target.colour != opposing_current.colour
            ):
                return False
        return True


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
        self.board_spaces: dict[tuple[int, int], Colour] = {}
        self.red_spaces: list[tuple[int, int]] = []
        self.blue_spaces: list[tuple[int, int]] = []
        self.player_turn: Player = Player(Colour.BLUE)
        self.last_move: Move | None = None
        self.change_counter: int = 0
        self._initialise_board()

    # -- Turn management --

    def switch_turn(self) -> Colour:
        current = self.player_turn.colour
        self.player_turn.colour = Colour.RED if current == Colour.BLUE else Colour.BLUE
        return self.player_turn.colour

    # -- Board setup --

    def _initialise_board(self) -> None:
        for row, (col_start, col_end) in BOARD_ROW_RANGES.items():
            for col in range(col_start, col_end):
                self.board_spaces[(row, col)] = Colour.EMPTY

        self.red_spaces.clear()
        self.blue_spaces.clear()

        for colour, coordinates in self.STARTING_TOKENS.items():
            for coord in coordinates:
                if coord in self.board_spaces:
                    self.board_spaces[coord] = colour
                    if colour == Colour.RED:
                        self.red_spaces.append(coord)
                    else:
                        self.blue_spaces.append(coord)

    # -- Move application --

    def clear_prev_tokens(self, red_piece: Space, blue_piece: Space) -> None:
        self.board_spaces[red_piece.coordinates] = Colour.EMPTY
        self.board_spaces[blue_piece.coordinates] = Colour.EMPTY

        while red_piece.coordinates in self.red_spaces:
            self.red_spaces.remove(red_piece.coordinates)

        while blue_piece.coordinates in self.blue_spaces:
            self.blue_spaces.remove(blue_piece.coordinates)

    def set_new_locations(self, red_piece: Space, blue_piece: Space) -> None:
        self.board_spaces[red_piece.coordinates] = Colour.RED
        self.board_spaces[blue_piece.coordinates] = Colour.BLUE

        if red_piece.coordinates not in self.red_spaces:
            self.red_spaces.append(red_piece.coordinates)

        if blue_piece.coordinates not in self.blue_spaces:
            self.blue_spaces.append(blue_piece.coordinates)

    def apply_move(self, move: Move) -> None:
        current_one, target_one = move.player_move
        current_two, target_two = move.opponent_move

        if current_one.colour == Colour.RED:
            red_current, blue_current = current_one, current_two
            red_target, blue_target = target_one, target_two
        else:
            red_current, blue_current = current_two, current_one
            red_target, blue_target = target_two, target_one

        self.clear_prev_tokens(red_current, blue_current)
        red_target.colour = Colour.RED
        blue_target.colour = Colour.BLUE
        self.set_new_locations(red_target, blue_target)
        self.last_move = move
        self.change_counter += 1

    # -- Win detection --

    def check_win(self, preferred_colour: Colour | None = None) -> WinState:
        elimination_winner = self._check_elimination_win()
        if elimination_winner != WinState.NONE:
            return elimination_winner

        sorted_red = sorted(self.red_spaces, key=lambda c: (c[0], c[1]))
        sorted_blue = sorted(self.blue_spaces, key=lambda c: (c[0], c[1]))
        red_wins = self._has_winning_line(sorted_red)
        blue_wins = self._has_winning_line(sorted_blue)

        return self._determine_winner(red_wins, blue_wins, preferred_colour)

    def _check_elimination_win(self) -> WinState:
        if len(self.red_spaces) == 0 and len(self.blue_spaces) > 0:
            return WinState.BLUE
        if len(self.blue_spaces) == 0 and len(self.red_spaces) > 0:
            return WinState.RED
        return WinState.NONE

    def _has_winning_line(self, spaces: list[tuple[int, int]]) -> bool:
        for i in range(len(spaces) - WIN_LINE_LENGTH + 1):
            x0, y0 = spaces[i]
            if all((x0 + j, y0 + j) in spaces for j in range(WIN_LINE_LENGTH)):
                return True
            if all((x0, y0 + j) in spaces for j in range(WIN_LINE_LENGTH)):
                return True
            if all((x0 + j, y0) in spaces for j in range(WIN_LINE_LENGTH)):
                return True
        return False

    def _determine_winner(
        self,
        red_wins: bool,
        blue_wins: bool,
        preferred_colour: Colour | None,
    ) -> WinState:
        if preferred_colour == Colour.RED and red_wins:
            return WinState.RED
        if preferred_colour == Colour.BLUE and blue_wins:
            return WinState.BLUE
        if red_wins and not blue_wins:
            return WinState.RED
        if blue_wins and not red_wins:
            return WinState.BLUE
        if red_wins and blue_wins:
            return WinState.RED if preferred_colour != Colour.BLUE else WinState.BLUE
        return WinState.NONE


class GameState:
    """Top-level state machine: manages game lifecycle (new, continue, pause, quit)."""

    def __init__(self) -> None:
        self.can_continue: bool = False
        self._board_state: BoardState | None = None
        self.is_paused: bool = False
        self._menu_state: MenuState = MenuState.MAIN_MENU

    def get_board(self) -> BoardState | None:
        return self._board_state

    def start_new_game(self) -> BoardState:
        self._board_state = BoardState()
        self._set_starting_player(self._board_state)
        self.can_continue = True
        self.is_paused = False
        self._set_menu_state(MenuState.IN_GAME)
        return self._board_state

    def continue_game(self) -> BoardState:
        if self.can_continue and self._board_state is not None:
            if self._board_state.check_win() != WinState.NONE:
                raise ValueError("Game is already over. Start a new game.")
            self.is_paused = False
            self._set_menu_state(MenuState.IN_GAME)
            return self._board_state
        raise ValueError("No game available to continue.")

    def load_game(self, loaded_board: BoardState) -> BoardState:
        self._board_state = loaded_board
        self.can_continue = True
        self.is_paused = False
        self._set_menu_state(MenuState.IN_GAME)
        return self._board_state

    def quit(self) -> None:
        self._board_state = None
        self.can_continue = False
        self.is_paused = False
        self._set_menu_state(MenuState.MAIN_MENU)

    def pause_game(self) -> None:
        if self._board_state is None:
            raise ValueError("No active game to pause.")
        self.is_paused = True
        self.can_continue = True
        self._set_menu_state(MenuState.PAUSE_MENU)

    def return_to_main_menu(self) -> None:
        if self._board_state is None:
            self._set_menu_state(MenuState.MAIN_MENU)
        else:
            self.is_paused = True
            self.can_continue = True
            self._set_menu_state(MenuState.MAIN_MENU)

    def restart_game(self) -> BoardState:
        if not self.is_paused:
            raise ValueError("Game must be paused before restarting.")
        self._board_state = BoardState()
        self._set_starting_player(self._board_state)
        self.is_paused = False
        self.can_continue = True
        return self._board_state

    def _set_menu_state(self, menu_state: MenuState) -> None:
        self._menu_state = menu_state

    def get_menu_state(self) -> MenuState:
        return self._menu_state

    def _set_starting_player(self, board: BoardState) -> None:
        starting_colour = random.choice([Colour.BLUE, Colour.RED])
        board.player_turn.colour = starting_colour
