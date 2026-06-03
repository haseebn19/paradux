"""Terminal-based view layer: board rendering and text output."""

from typing import Any

from paradux.interfaces import BOARD_ROWS, Colour, GameView, MenuState, WinState

# ANSI colour codes for terminal rendering
_ANSI_RED = "\033[31m"
_ANSI_BLUE = "\033[34m"
_ANSI_RESET = "\033[0m"

_MIDPOINT_ROW = BOARD_ROWS // 2


class BoardRenderer:
    """Renders the hex board as a coloured string for terminal display."""

    def tostring_board_spaces(self, board: Any) -> str:
        rows = self._organize_rows(board)
        if not rows:
            return ""

        sorted_rows, max_row_len, max_token_len = self._process_rows(rows)
        indent_unit = max(1, (max_token_len + 1) // 2)
        rendered_rows, top_line, bottom_line = self._render_rows(
            sorted_rows, max_row_len, max_token_len, indent_unit
        )
        return "\n".join([top_line, *rendered_rows, bottom_line])

    def _organize_rows(self, board: Any) -> dict[int, list[tuple[tuple[int, int], Colour]]]:
        rows: dict[int, list[tuple[tuple[int, int], Colour]]] = {}
        for coordinates, colour in board.board_spaces.items():
            rows.setdefault(coordinates[0], []).append((coordinates, colour))
        return rows

    def _process_rows(self, rows: dict[int, list[tuple[tuple[int, int], Colour]]]):
        sorted_rows = []
        max_row_len = 0
        max_token_len = 0
        for row_id in sorted(rows.keys()):
            entries = sorted(rows[row_id], key=lambda entry: entry[0][1])
            sorted_rows.append((row_id, entries))
            max_row_len = max(max_row_len, len(entries))
            max_token_len = max(
                max_token_len,
                max((len(self._token_plain(coord)) for coord, _ in entries), default=0),
            )
        return sorted_rows, max_row_len, max_token_len

    def _render_rows(
        self, sorted_rows: list, max_row_len: int, max_token_len: int, indent_unit: int
    ) -> tuple[list[str], str, str]:
        rendered_rows: list[str] = []
        top_line: str = ""
        bottom_line: str = ""
        for index, (_, entries) in enumerate(sorted_rows):
            row_data = self._render_single_row(
                entries, max_row_len, max_token_len, indent_unit, index, len(sorted_rows)
            )
            rendered_rows.append(row_data["rendered_row"])
            if index == 0:
                top_line = row_data["top_line"]
            if index == len(sorted_rows) - 1:
                bottom_line = row_data["bottom_line"]
        return rendered_rows, top_line, bottom_line

    def _render_single_row(
        self,
        entries: list,
        max_row_len: int,
        max_token_len: int,
        indent_unit: int,
        index: int,
        total_rows: int,
    ) -> dict:
        row_coloured = self._build_coloured_row(entries, max_token_len)
        indent = " " * ((max_row_len - len(entries)) * indent_unit)
        border_left, border_right = self._get_borders(index, total_rows)
        rendered_row = f"{indent}{border_left}{row_coloured}{border_right}"
        top_line = self._build_top_line(index, entries, max_token_len, indent)
        bottom_line = self._build_bottom_line(index, entries, max_token_len, indent, total_rows)
        return {"rendered_row": rendered_row, "top_line": top_line, "bottom_line": bottom_line}

    def _build_coloured_row(self, entries: list, max_token_len: int) -> str:
        colour_tokens = [
            self._token_colour(coord, colour, max_token_len) for coord, colour in entries
        ]
        return " ".join(colour_tokens)

    def _build_top_line(self, index: int, entries: list, max_token_len: int, indent: str) -> str:
        if index != 0:
            return ""
        plain_tokens = [self._token_plain(coord).ljust(max_token_len) for coord, _ in entries]
        row_plain = " ".join(plain_tokens)
        top_width = len(row_plain) + 2
        return f"{indent} " + "_" * (top_width - 2)

    def _build_bottom_line(
        self, index: int, entries: list, max_token_len: int, indent: str, total_rows: int
    ) -> str:
        if index != total_rows - 1:
            return ""
        plain_tokens = [self._token_plain(coord).ljust(max_token_len) for coord, _ in entries]
        row_plain = " ".join(plain_tokens)
        bottom_width = len(row_plain) + 2
        return f"{indent} " + "\u203e" * (bottom_width - 2)

    def _get_borders(self, index: int, _total_rows: int) -> tuple[str, str]:
        if index < _MIDPOINT_ROW:
            return "/", "\\"
        if index == _MIDPOINT_ROW:
            return "|", "|"
        return "\\", "/"

    def _token_plain(self, coord: tuple[int, int]) -> str:
        return f"({coord[0]},{coord[1]})"

    def _token_colour(self, coord: tuple[int, int], colour: Colour, width: int) -> str:
        symbol_map = {
            Colour.RED: _ANSI_RED,
            Colour.BLUE: _ANSI_BLUE,
            Colour.EMPTY: "",
        }
        colour_code = symbol_map.get(colour, "")
        token = f"({coord[0]},{coord[1]})".ljust(width)
        reset = _ANSI_RESET if colour_code else ""
        return f"{colour_code}{token}{reset}"


class TerminalView(GameView):
    """Terminal display layer acting as a strict MVP View."""

    def __init__(self) -> None:
        self.board_renderer = BoardRenderer()
        self.board_state: Any = None
        self.game_over_flag = False
        self.winner: WinState | None = None

    def on_board_update(self, board_state: Any) -> None:
        self.board_state = board_state
        self._display_board()

    def on_game_over(self, board_state: Any, winner: WinState) -> None:
        self.board_state = board_state
        self.game_over_flag = True
        self.winner = winner
        self._display_board()
        if winner == WinState.RED:
            print("Game over, Red wins!!")
        elif winner == WinState.BLUE:
            print("Game over, Blue wins!!")
        elif winner == WinState.TIE:
            print("Game over, it's a tie!")

    def on_game_start(self, board_state: Any) -> None:
        self.board_state = board_state
        self.game_over_flag = False
        self.winner = None
        print("\n--- Game Started ---")
        self._display_board()

    def on_menu_state_changed(self, menu_state: MenuState) -> None:
        pass

    def on_game_loaded(self, _board_state: Any, save_name: str) -> None:
        print(f"\nGame loaded: {save_name}")

    def on_selection_reset(self) -> None:
        pass

    def on_game_quit(self) -> None:
        pass

    def _display_board(self) -> None:
        if self.board_state:
            board_str = self.board_renderer.tostring_board_spaces(self.board_state)
            turn_colour = self.board_state.player_turn.colour.value
            print(f"\n{board_str}\n")
            if not self.game_over_flag:
                print(
                    f"{turn_colour}'s turn - Select two adjacent pieces, then where to move your piece."
                )

    def display_welcome(self) -> None:
        print("Welcome to PARADUX")

    def display_goodbye(self) -> None:
        print("Goodbye!")

    def display_main_menu(self) -> None:
        print("\nMain Menu")
        print("1 = New Game")
        print("2 = Continue Current Game")
        print("3 = Load Game")
        print("4 = Rules")
        print("5 = Quit Game")

    def display_prompt(self) -> None:
        print("> ", end="", flush=True)

    def display_rules(self) -> None:
        print("> The goal of the game is to get 4 pieces of your colour in a row.")
        print(
            "> Select two adjacent pieces (different colors), then choose where YOUR piece moves."
        )
        print("> The opponent's piece will follow in the same direction.")

    def display_error(self, message: str) -> None:
        print(f"Error: {message}")

    def display_move_prompt(self, turn_colour: str) -> None:
        msg = (
            f"Type: <piece1> <piece2> <target> for your {turn_colour} piece "
            f"(ex. 0,1 0,2 1,2 or 0,1 0,2 switch) | 'save' | 'menu'"
        )
        print(msg)

    def display_save_prompt(self) -> None:
        print("Enter save name (or press Enter for default): ", end="", flush=True)

    def display_save_success(self, filepath: str) -> None:
        print(f"Game saved to: {filepath}")

    def display_save_timeout(self) -> None:
        print("Error: Save timed out")

    def display_no_saves(self) -> None:
        print("No saved games found")

    def display_saves_list(self, saves: list) -> None:
        print("\nSaved Games:")
        for i, (filename, timestamp) in enumerate(saves, 1):
            display_name = filename[:-5] if filename.endswith(".json") else filename
            print(f"  {i}. {display_name} ({timestamp})")
        print("Type: <number> to load | 'delete #' | 'cancel'")

    def display_deleted(self, display_name: str) -> None:
        print(f"Deleted: {display_name}")
