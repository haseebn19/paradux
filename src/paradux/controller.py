"""Game controllers: input handling, move building, and the terminal game loop."""

import queue
import sys
import threading
from dataclasses import dataclass

from paradux.interfaces import (
    HEX_DIRECTIONS,
    INPUT_POLL_INTERVAL,
    Colour,
    GameView,
    MenuState,
    WinState,
    are_adjacent,
    strip_json_extension,
)
from paradux.model import BoardState, GameState, Move, Space
from paradux.save_load_manager import SaveLoadManager
from paradux.view import TerminalView


@dataclass
class MoveBuildParams:
    """Parameters needed to construct a Move from terminal input."""

    board: BoardState
    my_piece: tuple[int, int]
    opp_piece: tuple[int, int]
    target_command: str
    valid_targets: list[tuple[int, int]]


class InputController:
    """Parses raw coordinate strings into tuples."""

    def coord_from_str(self, coord_input: str) -> tuple[int, int]:
        try:
            x_str, y_str = coord_input.split(",")
            return int(x_str), int(y_str)
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Invalid coordinate format: {coord_input}") from exc


class MoveController:
    """Validates raw terminal move input format."""

    def check_valid_input(self, move: str) -> bool:
        stripped_move = move.strip()
        parts = stripped_move.split()
        if len(parts) != 2:
            return False
        for part in parts:
            coords = part.split(",")
            if len(coords) != 2:
                return False
            if not all(component.strip().isdigit() for component in coords):
                return False
        return True


def compute_valid_move_targets(
    board: BoardState,
    my_piece: tuple[int, int],
    opp_piece: tuple[int, int],
) -> list[tuple[int, int]]:
    """Return all valid target cells for the current player's piece.

    This is the single source of truth for move-target calculation,
    used by both the terminal controller and the GUI view.
    """
    valid: list[tuple[int, int]] = []
    for direction in HEX_DIRECTIONS:
        adj_pos = (my_piece[0] + direction[0], my_piece[1] + direction[1])
        if adj_pos not in board.board_spaces:
            continue

        dx = adj_pos[0] - my_piece[0]
        dy = adj_pos[1] - my_piece[1]
        opp_target = (opp_piece[0] + dx, opp_piece[1] + dy)
        if opp_target not in board.board_spaces:
            continue
        if not are_adjacent(opp_piece, opp_target):
            continue
        if not are_adjacent(adj_pos, opp_target):
            continue

        if adj_pos == opp_piece:
            if board.board_spaces.get(opp_target, Colour.EMPTY) == Colour.EMPTY:
                valid.append(adj_pos)
            continue

        if board.board_spaces.get(adj_pos, Colour.EMPTY) != Colour.EMPTY:
            continue
        opp_target_colour = board.board_spaces.get(opp_target, Colour.EMPTY)
        if opp_target_colour == Colour.EMPTY or opp_target == my_piece:
            valid.append(adj_pos)
    return valid


class GameController:
    """High-level controller bridging user actions to the game model."""

    def __init__(self, game_state: GameState) -> None:
        self.game_state = game_state
        self.save_manager = SaveLoadManager()
        self.views: list[GameView] = []

    def add_view(self, view: GameView) -> None:
        if view not in self.views:
            self.views.append(view)
        view.on_menu_state_changed(self.game_state.get_menu_state())

    def remove_view(self, view: GameView) -> None:
        if view in self.views:
            self.views.remove(view)

    def _notify_views(self, method_name: str, *args: object) -> None:
        for view in self.views:
            getattr(view, method_name)(*args)

    def start_new_game(self) -> BoardState:
        board = self.game_state.start_new_game()
        self._notify_views("on_menu_state_changed", self.game_state.get_menu_state())
        self._notify_views("on_game_start", board)
        return board

    def continue_game(self) -> BoardState:
        board = self.game_state.continue_game()
        self._notify_views("on_menu_state_changed", self.game_state.get_menu_state())
        self._notify_views("on_board_update", board)
        return board

    def quit_game(self) -> None:
        self.game_state.quit()
        self._notify_views("on_menu_state_changed", self.game_state.get_menu_state())
        self._notify_views("on_game_quit")

    def return_to_main_menu(self) -> None:
        self.game_state.return_to_main_menu()
        self._notify_views("on_menu_state_changed", self.game_state.get_menu_state())

    def apply_move(self, move: Move) -> bool:
        board = self.game_state.get_board()
        if board is None:
            return False

        if not move.is_move_legal(board.last_move):
            return False

        board.apply_move(move)

        outcome = board.check_win(preferred_colour=board.player_turn.colour)
        if outcome != WinState.NONE:
            self._notify_views("on_game_over", board, outcome)
            return True

        board.switch_turn()
        self._notify_views("on_board_update", board)
        return True

    def get_board(self) -> BoardState | None:
        return self.game_state.get_board()

    def save_game(self, save_name: str | None = None) -> str:
        board = self.game_state.get_board()
        if board is None:
            raise ValueError("No active game to save")
        if board.check_win() != WinState.NONE:
            raise ValueError("Cannot save a finished game")
        return self.save_manager.save_game(board, save_name)

    def load_game(self, filename: str) -> BoardState:
        loaded_board = self.save_manager.load_game(filename)
        board = self.game_state.load_game(loaded_board)
        self._notify_views("on_menu_state_changed", self.game_state.get_menu_state())
        self._notify_views("on_game_loaded", board, filename)
        self._notify_views("on_game_start", board)
        return board

    def list_saves(self) -> list:
        return self.save_manager.list_saves()

    def delete_save(self, filename: str) -> bool:
        return self.save_manager.delete_save(filename)

    def reset_selection(self) -> None:
        if self.game_state.get_board() is not None:
            self._notify_views("on_selection_reset")

    def try_gui_move(
        self,
        piece1_current: tuple[int, int],
        piece1_target: tuple[int, int],
        piece2_current: tuple[int, int],
        piece2_target: tuple[int, int],
    ) -> tuple[bool, str]:
        board = self.game_state.get_board()
        if board is None:
            return False, "No active game"

        try:
            current_one = Space(
                piece1_current, board.board_spaces.get(piece1_current, Colour.EMPTY)
            )
            current_two = Space(
                piece2_current, board.board_spaces.get(piece2_current, Colour.EMPTY)
            )

            is_swap = piece1_target == piece2_current and piece2_target == piece1_current
            if is_swap:
                target_one_colour = board.board_spaces.get(piece1_target, Colour.EMPTY)
                target_two_colour = board.board_spaces.get(piece2_target, Colour.EMPTY)
            else:
                target_one_colour = Colour.EMPTY
                target_two_colour = Colour.EMPTY

            target_one = Space(piece1_target, target_one_colour)
            target_two = Space(piece2_target, target_two_colour)
            move = Move([current_one, target_one], [current_two, target_two])

            if not move.is_move_legal(board.last_move):
                return self._check_undo_violation(
                    board, piece1_current, piece1_target, piece2_current, piece2_target
                )

            return self.apply_move(move), ""
        except (ValueError, KeyError, AttributeError) as e:
            return False, str(e)[:40]

    def _check_undo_violation(
        self,
        board: BoardState,
        piece1_current: tuple[int, int],
        piece1_target: tuple[int, int],
        piece2_current: tuple[int, int],
        piece2_target: tuple[int, int],
    ) -> tuple[bool, str]:
        if board.last_move is not None:
            last_start = {
                board.last_move.player_move[0].coordinates,
                board.last_move.opponent_move[0].coordinates,
            }
            last_end = {
                board.last_move.player_move[1].coordinates,
                board.last_move.opponent_move[1].coordinates,
            }
            current_positions = {piece1_current, piece2_current}
            new_targets = {piece1_target, piece2_target}
            if current_positions == last_end and new_targets == last_start:
                return False, "Cannot undo opponent's previous move"
        return False, "Illegal move - pieces must be adjacent"


@dataclass
class BoardTrackingState:
    """Tracks which board the terminal loop is currently attached to."""

    active_board_id: int | None = None
    paused_board_id: int | None = None
    allow_auto_resume: bool = True
    last_seen_change: int | None = None


@dataclass
class WaitOptions:
    """Flags controlling how _wait_for_line behaves."""

    allow_board_interrupt: bool = False
    force_board_check: bool = False
    check_menu_exit: bool = False
    check_game_resume: bool = False


class TerminalLoopController:
    """Runs the terminal game loop on a background thread."""

    def __init__(self, game_controller: GameController, terminal_view: TerminalView) -> None:
        self.game_controller = game_controller
        self.terminal_view = terminal_view
        self.input_controller = InputController()
        self.move_controller = MoveController()
        self.board_state = BoardTrackingState()
        self.input_queue: queue.Queue[str] = queue.Queue()
        self.reader_started = False

    def run(self, stop_event: threading.Event) -> None:
        self._ensure_input_reader(stop_event)
        self.terminal_view.display_welcome()
        while not stop_event.is_set():
            if self._detect_new_board():
                self._run_game_loop(stop_event)
                continue

            menu_choice = self._prompt_main_menu(stop_event)
            if menu_choice == "5":
                self.terminal_view.display_goodbye()
                self.game_controller.quit_game()
                stop_event.set()
                break
            if menu_choice == "1":
                board = self.game_controller.start_new_game()
                self._start_game(board)
                self._run_game_loop(stop_event)
                continue
            if menu_choice == "2":
                try:
                    board = self.game_controller.continue_game()
                    self._start_game(board)
                    self._run_game_loop(stop_event)
                except ValueError as e:
                    self.terminal_view.display_error(str(e))

    def _start_game(self, board: BoardState) -> None:
        self.board_state.active_board_id = id(board)
        self.board_state.allow_auto_resume = True
        self.board_state.paused_board_id = None

    def _prompt_main_menu(self, stop_event: threading.Event) -> str:
        while not stop_event.is_set():
            self.terminal_view.display_main_menu()
            self.terminal_view.display_prompt()
            status, value = self._wait_for_line(
                stop_event, WaitOptions(allow_board_interrupt=True, check_game_resume=True)
            )
            if status == "board":
                self._run_game_loop(stop_event)
                continue
            if status == "game_resumed":
                board = self.game_controller.get_board()
                if board is not None:
                    self._start_game(board)
                    self._run_game_loop(stop_event)
                continue
            if status == "stop":
                return "5"
            menu_choice = (value or "").strip()
            if menu_choice == "3":
                if self._prompt_load_game(stop_event):
                    self._run_game_loop(stop_event)
                continue
            if menu_choice == "4":
                self.terminal_view.display_rules()
                continue
            if menu_choice in {"1", "2", "5"}:
                return menu_choice
            self.terminal_view.display_error("Invalid Menu Option")
        return "5"

    def _run_game_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            board = self._get_valid_board()
            if board is None:
                return

            turn_colour = board.player_turn.colour.value
            self.terminal_view.display_move_prompt(turn_colour)
            self.terminal_view.display_prompt()
            status, pieces_input = self._wait_for_line(
                stop_event,
                WaitOptions(
                    allow_board_interrupt=True, force_board_check=True, check_menu_exit=True
                ),
            )
            if status == "board":
                continue
            if status == "menu":
                self._pause_to_menu()
                return
            if status == "stop":
                self.board_state.active_board_id = None
                return
            pieces_input = (pieces_input or "").strip()
            if stop_event.is_set():
                break

            if not self._handle_game_input(board, pieces_input, stop_event):
                return

            if not self.game_controller.get_board():
                return
        self.board_state.active_board_id = None

    def _get_valid_board(self) -> BoardState | None:
        board = self.game_controller.get_board()
        if board is None:
            self.board_state.active_board_id = None
            return None
        if (
            self.board_state.active_board_id is not None
            and id(board) != self.board_state.active_board_id
        ):
            return None
        self.board_state.last_seen_change = getattr(
            board, "change_counter", self.board_state.last_seen_change
        )
        if board.check_win() != WinState.NONE:
            return None
        return board

    def _handle_game_input(
        self, board: BoardState, pieces_input: str, stop_event: threading.Event
    ) -> bool:
        if pieces_input.lower() == "menu":
            self.game_controller.return_to_main_menu()
            self._pause_to_menu()
            return False
        if pieces_input.lower() == "save":
            if not self._save_game(board, stop_event):
                self._pause_to_menu()
                return False
        else:
            self._process_move_input(board, pieces_input)
        return True

    def _pause_to_menu(self) -> None:
        self.board_state.paused_board_id = self.board_state.active_board_id
        self.board_state.active_board_id = None
        self.board_state.allow_auto_resume = False

    def _process_move_input(self, board: BoardState, pieces_input: str) -> bool:
        parts = pieces_input.split()
        if not self._validate_input_format(parts):
            return False

        pair_input = " ".join(parts[:2])
        if not self._validate_pair_input(pair_input):
            return False

        piece1_pos, piece2_pos = self._parse_and_validate_coordinates(pair_input, board)
        if piece1_pos is None:
            return False

        my_piece, opp_piece = self._determine_turn(board, piece1_pos, piece2_pos)
        if my_piece is None:
            return False

        return self._execute_move(board, my_piece, opp_piece, parts[2].strip())

    def _validate_input_format(self, parts: list[str]) -> bool:
        if len(parts) != 3:
            self.terminal_view.display_error(
                "Expected input like '0,1 0,2 1,2' or '0,1 0,2 switch'"
            )
            return False
        return True

    def _validate_pair_input(self, pair_input: str) -> bool:
        if not self.move_controller.check_valid_input(pair_input):
            self.terminal_view.display_error("Expected the first two coordinates like 0,1 0,2")
            return False
        return True

    def _parse_and_validate_coordinates(
        self, pair_input: str, board: BoardState
    ) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
        try:
            piece1_pos, piece2_pos = self._parse_pair_coordinates(pair_input)
            if not self._pieces_are_valid(board, piece1_pos, piece2_pos):
                return None, None
            return piece1_pos, piece2_pos
        except ValueError as exc:
            self.terminal_view.display_error(str(exc))
            return None, None

    def _execute_move(
        self,
        board: BoardState,
        my_piece: tuple[int, int],
        opp_piece: tuple[int, int],
        target_command: str,
    ) -> bool:
        valid_targets = compute_valid_move_targets(board, my_piece, opp_piece)
        if target_command.lower() == "switch":
            target_command = "switch"
        params = MoveBuildParams(board, my_piece, opp_piece, target_command, valid_targets)
        move = self._build_move(params)
        if move is None:
            return False
        if not self.game_controller.apply_move(move):
            self.terminal_view.display_error("Illegal move")
            return False
        self._reset_gui_selection()
        return True

    def _parse_pair_coordinates(self, pieces_input: str) -> tuple[tuple[int, int], tuple[int, int]]:
        parts = pieces_input.split()
        piece1_pos = self.input_controller.coord_from_str(parts[0])
        piece2_pos = self.input_controller.coord_from_str(parts[1])
        return piece1_pos, piece2_pos

    def _pieces_are_valid(
        self, board: BoardState, pos1: tuple[int, int], pos2: tuple[int, int]
    ) -> bool:
        colour1 = board.board_spaces.get(pos1, Colour.EMPTY)
        colour2 = board.board_spaces.get(pos2, Colour.EMPTY)

        if Colour.EMPTY in (colour1, colour2):
            self.terminal_view.display_error("Both positions must have pieces")
            return False
        if colour1 == colour2:
            self.terminal_view.display_error("Pieces must be different colors")
            return False

        if not are_adjacent(pos1, pos2):
            self.terminal_view.display_error("Pieces must be adjacent")
            return False
        return True

    def _determine_turn(
        self, board: BoardState, pos1: tuple[int, int], pos2: tuple[int, int]
    ) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
        turn_colour = board.player_turn.colour
        colour1 = board.board_spaces.get(pos1, Colour.EMPTY)
        colour2 = board.board_spaces.get(pos2, Colour.EMPTY)

        if colour1 == turn_colour:
            return pos1, pos2
        if colour2 == turn_colour:
            return pos2, pos1
        self.terminal_view.display_error("You must move your own colour")
        return None, None

    def _build_move(self, params: MoveBuildParams) -> Move | None:
        try:
            if params.target_command == "switch":
                return self._build_swap_move(params)
            return self._build_shift_move(params)
        except ValueError as exc:
            self.terminal_view.display_error(str(exc))
            return None

    def _build_swap_move(self, params: MoveBuildParams) -> Move | None:
        my_target = params.opp_piece
        opp_target = params.my_piece
        return self._create_move_from_targets(params, my_target, opp_target, is_swap=True)

    def _build_shift_move(self, params: MoveBuildParams) -> Move | None:
        if not params.valid_targets:
            self.terminal_view.display_error("No valid target cells for those pieces")
            return None

        my_target = self.input_controller.coord_from_str(params.target_command)
        if my_target not in params.valid_targets:
            self.terminal_view.display_error("Target must be one of the valid coordinates")
            return None

        dx = my_target[0] - params.my_piece[0]
        dy = my_target[1] - params.my_piece[1]
        if (dx, dy) not in HEX_DIRECTIONS:
            self.terminal_view.display_error("Target must be adjacent to your piece")
            return None

        if my_target == params.opp_piece:
            opp_target = params.my_piece
        else:
            opp_target = (params.opp_piece[0] + dx, params.opp_piece[1] + dy)
            if opp_target not in params.board.board_spaces:
                self.terminal_view.display_error("Opponent piece would move off the board")
                return None

        return self._create_move_from_targets(params, my_target, opp_target, is_swap=False)

    def _create_move_from_targets(
        self,
        params: MoveBuildParams,
        my_target: tuple[int, int],
        opp_target: tuple[int, int],
        is_swap: bool,
    ) -> Move:
        current_one = Space(
            params.my_piece, params.board.board_spaces.get(params.my_piece, Colour.EMPTY)
        )
        current_two = Space(
            params.opp_piece, params.board.board_spaces.get(params.opp_piece, Colour.EMPTY)
        )
        target_one_colour = (
            params.board.board_spaces.get(my_target, Colour.EMPTY) if is_swap else Colour.EMPTY
        )
        target_two_colour = (
            params.board.board_spaces.get(opp_target, Colour.EMPTY) if is_swap else Colour.EMPTY
        )
        target_one = Space(my_target, target_one_colour)
        target_two = Space(opp_target, target_two_colour)
        return Move([current_one, target_one], [current_two, target_two])

    def _reset_gui_selection(self) -> None:
        self.game_controller.reset_selection()

    def _ensure_input_reader(self, stop_event: threading.Event) -> None:
        if self.reader_started:
            return

        def _reader() -> None:
            while not stop_event.is_set():
                line = sys.stdin.readline()
                if line == "":
                    break
                self.input_queue.put(line.rstrip("\n"))

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        self.reader_started = True

    def _wait_for_line(
        self, stop_event: threading.Event, opts: WaitOptions | None = None
    ) -> tuple[str, str | None]:
        if opts is None:
            opts = WaitOptions()
        while not stop_event.is_set():
            if (
                opts.check_menu_exit
                and self.game_controller.game_state.get_menu_state() == MenuState.MAIN_MENU
            ):
                return ("menu", None)
            if (
                opts.check_game_resume
                and self.game_controller.game_state.get_menu_state() == MenuState.IN_GAME
            ):
                board = self.game_controller.get_board()
                if board is None or board.check_win() == WinState.NONE:
                    return ("game_resumed", None)
            if opts.allow_board_interrupt and self._detect_new_board(force=opts.force_board_check):
                return ("board", None)
            try:
                line = self.input_queue.get(timeout=INPUT_POLL_INTERVAL)
                return ("input", line.strip())
            except queue.Empty:
                continue
        return ("stop", None)

    def _detect_new_board(self, force: bool = False) -> bool:
        board = self.game_controller.get_board()
        if board is None:
            return False

        board_id = id(board)
        change_counter = getattr(board, "change_counter", None)

        state = self.board_state
        if state.active_board_id is None:
            return self._activate_new_board(board_id, change_counter, force)

        if board_id != state.active_board_id:
            return self._activate_new_board(board_id, change_counter, force)

        if force and change_counter is not None and change_counter != state.last_seen_change:
            state.last_seen_change = change_counter
            return True

        return False

    def _activate_new_board(self, board_id: int, change_counter: int | None, force: bool) -> bool:
        state = self.board_state
        if not force and not state.allow_auto_resume and state.paused_board_id == board_id:
            return False
        state.active_board_id = board_id
        state.last_seen_change = change_counter
        if state.paused_board_id != board_id:
            state.paused_board_id = None
            state.allow_auto_resume = True
        return True

    def _save_game(self, board: BoardState, stop_event: threading.Event) -> bool:
        if board.check_win() != WinState.NONE:
            self.terminal_view.display_error("Cannot save a finished game")
            return True
        self.terminal_view.display_save_prompt()
        status, value = self._wait_for_line(stop_event, WaitOptions(check_menu_exit=True))
        if status == "menu":
            print("\nSave cancelled - returned to menu")
            return False
        if status == "stop":
            return False
        try:
            save_name = value.strip() if value and value.strip() else None
            filepath = self.game_controller.save_game(save_name)
            self.terminal_view.display_save_success(filepath)
        except ValueError as e:
            self.terminal_view.display_error(str(e))
        except OSError as e:
            self.terminal_view.display_error(f"saving game: {e}")
        return True

    def _prompt_load_game(self, stop_event: threading.Event) -> bool:
        while not stop_event.is_set():
            saves = self.game_controller.list_saves()
            if not saves:
                self.terminal_view.display_no_saves()
                return False

            self.terminal_view.display_saves_list(saves)
            self.terminal_view.display_prompt()

            status, value = self._wait_for_line(stop_event, WaitOptions(allow_board_interrupt=True))
            if status == "board":
                return True
            if status != "input":
                return False

            user_input = (value or "").strip()

            if user_input.lower() == "cancel":
                return False

            if user_input.lower().startswith("delete "):
                self._handle_delete_save(user_input, saves)
                continue

            try:
                choice = int(user_input)
                if choice < 1 or choice > len(saves):
                    self.terminal_view.display_error("Invalid selection")
                    continue

                filename = saves[choice - 1][0]
                self.game_controller.load_game(filename)
                self._start_game(self.game_controller.get_board())
                return True
            except ValueError:
                self.terminal_view.display_error("Please enter a number or 'delete #'")
                continue
            except FileNotFoundError:
                self.terminal_view.display_error("Save file not found")
                continue
            except OSError as e:
                self.terminal_view.display_error(f"loading game: {e}")
                continue
        return False

    def _handle_delete_save(self, user_input: str, saves: list) -> None:
        parts = user_input.split()
        if len(parts) != 2:
            self.terminal_view.display_error("Use 'delete #' where # is the save number")
            return
        try:
            delete_num = int(parts[1])
            if delete_num < 1 or delete_num > len(saves):
                self.terminal_view.display_error("Invalid save number")
                return
            filename = saves[delete_num - 1][0]
            display_name = strip_json_extension(filename)
            if self.game_controller.delete_save(filename):
                self.terminal_view.display_deleted(display_name)
            else:
                self.terminal_view.display_error("Failed to delete save")
        except ValueError:
            self.terminal_view.display_error("Use 'delete #' where # is a number")
