"""Save and load game state as JSON files."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paradux.interfaces import Colour
from paradux.model import BoardState, Move, Player, Space


class SaveLoadManager:
    """Handles persisting and restoring BoardState to/from JSON save files."""

    def __init__(self, save_dir: str = "saves") -> None:
        self.save_dir = Path(save_dir)
        self._ensure_save_directory()

    def _ensure_save_directory(self) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save_game(self, board_state: BoardState, filename: str | None = None) -> str:
        if filename is None:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"save_{timestamp}"

        if not filename.endswith(".json"):
            filename += ".json"

        filepath = self.save_dir / filename
        save_data = self._serialize_board_state(board_state)

        filepath.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
        return str(filepath)

    def load_game(self, filename: str) -> BoardState:
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = self.save_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Save file not found: {filepath}")

        save_data = json.loads(filepath.read_text(encoding="utf-8"))
        return self._deserialize_board_state(save_data)

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

        filepath = self.save_dir / filename

        try:
            if filepath.exists():
                filepath.unlink()
                return True
        except OSError:
            pass

        return False

    def _serialize_board_state(self, board_state: BoardState) -> dict[str, Any]:
        save_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "board_spaces": {
                f"{coord[0]},{coord[1]}": colour.value
                for coord, colour in board_state.board_spaces.items()
            },
            "red_spaces": [list(coord) for coord in board_state.red_spaces],
            "blue_spaces": [list(coord) for coord in board_state.blue_spaces],
            "player_turn": board_state.player_turn.colour.value,
            "change_counter": board_state.change_counter,
            "last_move": (
                self._serialize_move(board_state.last_move)
                if board_state.last_move is not None
                else None
            ),
        }
        return save_data

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

        board_state.board_spaces.clear()
        board_state.red_spaces.clear()
        board_state.blue_spaces.clear()

        for coord_str, colour_str in save_data["board_spaces"].items():
            x, y = map(int, coord_str.split(","))
            board_state.board_spaces[(x, y)] = Colour(colour_str)

        board_state.red_spaces = [tuple(coord) for coord in save_data["red_spaces"]]
        board_state.blue_spaces = [tuple(coord) for coord in save_data["blue_spaces"]]
        board_state.player_turn = Player(Colour(save_data["player_turn"]))
        board_state.change_counter = save_data.get("change_counter", 0)

        if save_data.get("last_move") is not None:
            board_state.last_move = self._deserialize_move(save_data["last_move"])
        else:
            board_state.last_move = None

        return board_state

    def _deserialize_move(self, move_data: dict[str, Any]) -> Move:
        player_move = [
            Space(tuple(s["coordinates"]), Colour(s["colour"])) for s in move_data["player_move"]
        ]
        opponent_move = [
            Space(tuple(s["coordinates"]), Colour(s["colour"])) for s in move_data["opponent_move"]
        ]
        return Move(player_move, opponent_move)
