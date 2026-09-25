"""Terminal-based view layer: board rendering and text output."""

from paradux.interfaces import (
    BOARD_ROWS,
    RULES,
    Colour,
    GameView,
    MenuState,
    WinState,
    strip_json_extension,
)
from paradux.model import BoardState, Position

_ANSI_CODES = {Colour.RED: "\033[31m", Colour.BLUE: "\033[34m"}
_ANSI_RESET = "\033[0m"

# Each position prints as "(row,col)", five characters, so shorter rows are indented by
# three spaces per missing position to line up as a hexagon.
_TOKEN_WIDTH = 5
_INDENT_PER_MISSING_TOKEN = 3


def render_board(board_spaces: dict[Position, Colour]) -> str:
    """Draw the board as rows of coloured "(row,col)" positions inside a hexagon outline."""
    rows = [
        sorted(position for position in board_spaces if position[0] == row)
        for row in range(BOARD_ROWS)
    ]
    widest = max(len(row) for row in rows)
    middle = BOARD_ROWS // 2

    lines = []
    for index, row in enumerate(rows):
        indent = " " * ((widest - len(row)) * _INDENT_PER_MISSING_TOKEN)
        left, right = (
            ("/", "\\") if index < middle else ("|", "|") if index == middle else ("\\", "/")
        )
        tokens = []
        for position in row:
            code = _ANSI_CODES.get(board_spaces[position])
            token = f"({position[0]},{position[1]})"
            tokens.append(f"{code}{token}{_ANSI_RESET}" if code else token)
        lines.append(f"{indent}{left}{' '.join(tokens)}{right}")

    def edge(row: list[Position], character: str) -> str:
        indent = " " * ((widest - len(row)) * _INDENT_PER_MISSING_TOKEN)
        return indent + " " + character * (len(row) * (_TOKEN_WIDTH + 1) - 1)

    return "\n".join([edge(rows[0], "_"), *lines, edge(rows[-1], "\u203e")])


class TerminalView(GameView):
    """Terminal display layer acting as a strict MVP View."""

    def __init__(self) -> None:
        self.board_state: BoardState | None = None
        self.game_over_flag = False

    def on_board_update(self, board_state: BoardState) -> None:
        self.board_state = board_state
        self._display_board()

    def on_game_over(self, board_state: BoardState, winner: WinState) -> None:
        self.board_state = board_state
        self.game_over_flag = True
        self._display_board()
        if winner == WinState.RED:
            print("Game over, Red wins!")
        elif winner == WinState.BLUE:
            print("Game over, Blue wins!")

    def on_game_start(self, board_state: BoardState) -> None:
        self.board_state = board_state
        self.game_over_flag = False
        print("\n--- Game Started ---")
        self._display_board()

    def on_menu_state_changed(self, menu_state: MenuState) -> None:
        pass

    def on_game_loaded(self, _board_state: BoardState, save_name: str) -> None:
        print(f"\nGame loaded: {strip_json_extension(save_name)}")

    def on_game_quit(self) -> None:
        pass

    def _display_board(self) -> None:
        if self.board_state is not None:
            board_str = render_board(self.board_state.board_spaces)
            turn_colour = self.board_state.player_turn.colour.value
            print(f"\n{board_str}\n")
            if not self.game_over_flag:
                print(
                    f"{turn_colour}'s turn. Select two adjacent pieces, then where to move your piece."
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
        for paragraph in RULES:
            print(f"> {paragraph}")

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

    def display_save_cancelled(self) -> None:
        print("\nSave cancelled, returned to the menu")

    def display_no_saves(self) -> None:
        print("No saved games found")

    def display_saves_list(self, saves: list[tuple[str, str]]) -> None:
        print("\nSaved Games:")
        for i, (filename, timestamp) in enumerate(saves, 1):
            print(f"  {i}. {strip_json_extension(filename)} ({timestamp})")
        print("Type: <number> to load | 'delete #' | 'cancel'")

    def display_deleted(self, display_name: str) -> None:
        print(f"Deleted: {display_name}")
