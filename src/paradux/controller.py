"""Game controllers: input handling, move validation, and the terminal game loop."""

import queue
import sys
import threading
from dataclasses import dataclass

from paradux.interfaces import (
    INPUT_POLL_INTERVAL,
    Colour,
    GameView,
    MenuState,
    WinState,
    are_adjacent,
    strip_json_extension,
)
from paradux.model import BoardState, GameState, Move, Position
from paradux.save_load_manager import SaveLoadManager
from paradux.view import TerminalView


def parse_position(text: str) -> Position:
    """Parse a position typed as 'row,column', such as '0,1'. Raises ValueError otherwise."""
    row, col = text.split(",")
    return int(row), int(col)


def order_pieces(board: BoardState, first: Position, second: Position) -> tuple[Position, Position]:
    """Return (the current player's piece, the opponent's piece).

    The two pieces must be different colours, so exactly one belongs to the current player.
    """
    if board.board_spaces.get(first) == board.player_turn.colour:
        return first, second
    return second, first


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
        """Play the move if it is legal, and return whether it was played."""
        board = self.game_state.get_board()
        if board is None or not move.is_move_legal(board.last_move):
            return False

        board.apply_move(move)

        outcome = board.check_win(preferred_colour=board.player_turn.colour)
        if outcome != WinState.NONE:
            self._notify_views("on_game_over", board, outcome)
            return True

        board.switch_turn()
        self._notify_views("on_board_update", board)
        return True

    def try_move(
        self, first: Position, second: Position, target: Position | None = None
    ) -> tuple[bool, str]:
        """Move two adjacent pieces of different colours, one of them the current player's.

        With a `target`, the current player's piece moves there and the other piece moves the
        same way. Without one, the two pieces swap places. Returns (True, "") when the move is
        made, or (False, reason) when it is not allowed.
        """
        board = self.game_state.get_board()
        if board is None:
            return False, "No active game"

        colours = (
            board.board_spaces.get(first, Colour.EMPTY),
            board.board_spaces.get(second, Colour.EMPTY),
        )
        if Colour.EMPTY in colours:
            return False, "Both positions must have pieces"
        if colours[0] == colours[1]:
            return False, "Pieces must be different colours"
        if not are_adjacent(first, second):
            return False, "Pieces must be adjacent"

        my_piece, opp_piece = order_pieces(board, first, second)
        move = board.build_move(my_piece, opp_piece, target)
        if move is None or not move.is_move_legal():
            return False, "Your piece cannot move there"
        # The rules are otherwise met, so a refusal here means the move undoes the last one
        if not self.apply_move(move):
            return False, "Cannot undo the opponent's previous move"
        return True, ""

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

    def list_saves(self) -> list[tuple[str, str]]:
        return self.save_manager.list_saves()

    def delete_save(self, filename: str) -> bool:
        return self.save_manager.delete_save(filename)


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
    """Runs the terminal game loop on a background thread.

    The GUI runs on the main thread and can change the game at any time, so the loop waits
    for input in short polls and checks between them for a new board, a move made in the GUI,
    or a change of menu.
    """

    def __init__(self, game_controller: GameController, terminal_view: TerminalView) -> None:
        self.game_controller = game_controller
        self.terminal_view = terminal_view
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
            menu_choice = value
            if menu_choice == "3":
                if self._prompt_load_game(stop_event):
                    self._run_game_loop(stop_event)
                continue
            if menu_choice == "4":
                self.terminal_view.display_rules()
                continue
            if menu_choice in {"1", "2", "5"}:
                return menu_choice
            self.terminal_view.display_error("Invalid menu option")
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
        self.board_state.last_seen_change = board.change_counter
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
            self._process_move_input(pieces_input)
        return True

    def _pause_to_menu(self) -> None:
        self.board_state.paused_board_id = self.board_state.active_board_id
        self.board_state.active_board_id = None
        self.board_state.allow_auto_resume = False

    def _process_move_input(self, pieces_input: str) -> None:
        """Make a move typed as '<piece> <piece> <target>' or '<piece> <piece> switch'."""
        try:
            first_text, second_text, target_text = pieces_input.split()
            first, second = parse_position(first_text), parse_position(second_text)
            target = None if target_text.lower() == "switch" else parse_position(target_text)
        except ValueError:
            self.terminal_view.display_error(
                "Expected input like '0,1 0,2 1,2' or '0,1 0,2 switch'"
            )
            return

        success, message = self.game_controller.try_move(first, second, target)
        if not success:
            self.terminal_view.display_error(message)

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

    def _wait_for_line(self, stop_event: threading.Event, opts: WaitOptions) -> tuple[str, str]:
        """Wait for a line of input, or for one of the game changes `opts` asks to watch.

        Returns ("input", the line without surrounding spaces), or
        ("menu" | "game_resumed" | "board" | "stop", "").
        """
        while not stop_event.is_set():
            if (
                opts.check_menu_exit
                and self.game_controller.game_state.get_menu_state() == MenuState.MAIN_MENU
            ):
                return ("menu", "")
            if (
                opts.check_game_resume
                and self.game_controller.game_state.get_menu_state() == MenuState.IN_GAME
            ):
                board = self.game_controller.get_board()
                if board is None or board.check_win() == WinState.NONE:
                    return ("game_resumed", "")
            if opts.allow_board_interrupt and self._detect_new_board(force=opts.force_board_check):
                return ("board", "")
            try:
                line = self.input_queue.get(timeout=INPUT_POLL_INTERVAL)
                return ("input", line.strip())
            except queue.Empty:
                continue
        return ("stop", "")

    def _detect_new_board(self, force: bool = False) -> bool:
        board = self.game_controller.get_board()
        if board is None:
            return False

        board_id = id(board)
        state = self.board_state
        if state.active_board_id is None or board_id != state.active_board_id:
            return self._activate_new_board(board_id, board.change_counter, force)

        if force and board.change_counter != state.last_seen_change:
            state.last_seen_change = board.change_counter
            return True

        return False

    def _activate_new_board(self, board_id: int, change_counter: int, force: bool) -> bool:
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
            self.terminal_view.display_save_cancelled()
            return False
        if status == "stop":
            return False
        try:
            filepath = self.game_controller.save_game(value or None)
            self.terminal_view.display_save_success(filepath)
        except ValueError as e:
            self.terminal_view.display_error(str(e))
        except OSError as e:
            self.terminal_view.display_error(f"Could not save the game: {e}")
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

            user_input = value

            if user_input.lower() == "cancel":
                return False

            if user_input.lower().startswith("delete "):
                self._handle_delete_save(user_input, saves)
                continue

            try:
                choice = int(user_input)
            except ValueError:
                self.terminal_view.display_error("Please enter a number or 'delete #'")
                continue
            if not 1 <= choice <= len(saves):
                self.terminal_view.display_error("Invalid selection")
                continue

            try:
                board = self.game_controller.load_game(saves[choice - 1][0])
            except FileNotFoundError:
                self.terminal_view.display_error("Save file not found")
                continue
            except ValueError as e:
                self.terminal_view.display_error(str(e))
                continue
            except OSError as e:
                self.terminal_view.display_error(f"Could not load the game: {e}")
                continue
            self._start_game(board)
            return True
        return False

    def _handle_delete_save(self, user_input: str, saves: list[tuple[str, str]]) -> None:
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
