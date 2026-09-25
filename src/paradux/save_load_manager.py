"""Save and load game state as JSON files."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paradux.interfaces import Colour
from paradux.model import BoardState, Move, Player, Space

# Characters Windows does not allow in file names. "/" and "\" would also leave the save folder.
INVALID_NAME_CHARACTERS = set('<>:"/\\|?*')


class SaveLoadManager:
    """Handles persisting and restoring BoardState to/from JSON save files."""

    def __init__(self, save_dir: str = "saves") -> None:
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save_game(self, board_state: BoardState, filename: str | None = None) -> str:
        """Save the board and return the file path.

        Raises ValueError if the name is blank or has characters a file name cannot use.
        """
        if filename is None:
            filename = f"save_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            filename = filename.strip()
            if not filename.strip(".") or any(
                char in INVALID_NAME_CHARACTERS or not char.isprintable() for char in filename
            ):
                raise ValueError('Save names cannot be blank or contain < > : " / \\ | ? *')

        if not filename.endswith(".json"):
            filename += ".json"

        filepath = self.save_dir / filename
        save_data = self._serialize_board_state(board_state)

        filepath.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
        return str(filepath)

    def load_game(self, filename: str) -> BoardState:
        """Load a saved board.

        Raises FileNotFoundError if the save does not exist, or ValueError if it cannot be read.
        """
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = self.save_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Save file not found: {filepath}")

        try:
            save_data = json.loads(filepath.read_text(encoding="utf-8"))
            return self._deserialize_board_state(save_data)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"{filepath.name} is not a valid save file") from exc

    def list_saves(self) -> list[tuple[str, str]]:
        if not self.save_dir.exists():
            return []

        saves = []
        for filepath in self.save_dir.iterdir():
            if filepath.suffix == ".json":
                timestamp = datetime.fromtimestamp(filepath.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                saves.append((filepath.name, timestamp))

        saves.sort(key=lambda x: x[1], reverse=True)
        return saves

    def delete_save(self, filename: str) -> bool:
        if not filename.endswith(".json"):
            filename += ".json"

        try:
            (self.save_dir / filename).unlink()
        except OSError:
            return False
        return True

    def _serialize_board_state(self, board_state: BoardState) -> dict[str, Any]:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "board_spaces": {
                f"{coord[0]},{coord[1]}": colour.value
                for coord, colour in board_state.board_spaces.items()
            },
            "player_turn": board_state.player_turn.colour.value,
            "change_counter": board_state.change_counter,
            "last_move": (
                self._serialize_move(board_state.last_move)
                if board_state.last_move is not None
                else None
            ),
        }

    def _serialize_move(self, move: Move) -> dict[str, Any]:
        return {
            "player_move": [
                {"coordinates": list(space.coordinates), "colour": space.colour.value}
                for space in move.player_move
            ],
            "opponent_move": [
                {"coordinates": list(space.coordinates), "colour": space.colour.value}
                for space in move.opponent_move
            ],
        }

    def _deserialize_board_state(self, save_data: dict[str, Any]) -> BoardState:
        board_state = BoardState()
        board_state.board_spaces = {
            tuple(map(int, position.split(","))): Colour(colour)
            for position, colour in save_data["board_spaces"].items()
        }
        board_state.player_turn = Player(Colour(save_data["player_turn"]))
        board_state.change_counter = save_data.get("change_counter", 0)

        if save_data.get("last_move") is not None:
            board_state.last_move = self._deserialize_move(save_data["last_move"])
        return board_state

    def _deserialize_move(self, move_data: dict[str, Any]) -> Move:
        player_move = [
            Space(tuple(s["coordinates"]), Colour(s["colour"])) for s in move_data["player_move"]
        ]
        opponent_move = [
            Space(tuple(s["coordinates"]), Colour(s["colour"])) for s in move_data["opponent_move"]
        ]
        return Move(player_move, opponent_move)
