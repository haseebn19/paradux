import json
from pathlib import Path

import pytest

from paradux.interfaces import Colour
from paradux.model import BoardState, Move, Space
from paradux.save_load_manager import SaveLoadManager


@pytest.fixture
def temp_save_dir(tmp_path):
    return tmp_path / "saves"


@pytest.fixture
def manager(temp_save_dir):
    return SaveLoadManager(save_dir=str(temp_save_dir))


@pytest.fixture
def board():
    return BoardState()


def test_ensure_save_directory_creates_dir(temp_save_dir):
    new_dir = temp_save_dir / "new_saves"
    SaveLoadManager(save_dir=str(new_dir))
    assert new_dir.exists()
    assert new_dir.is_dir()


def test_save_game_creates_file(manager, board):
    filepath = manager.save_game(board, "test_save")
    assert Path(filepath).exists()
    assert filepath.endswith(".json")


def test_save_game_auto_generates_filename(manager, board):
    filepath = manager.save_game(board)
    assert Path(filepath).exists()
    assert "save_" in Path(filepath).name


def test_save_game_creates_valid_json(manager, board, temp_save_dir):
    manager.save_game(board, "test_json")
    filepath = temp_save_dir / "test_json.json"
    with Path(filepath).open(encoding="utf-8") as f:
        data = json.load(f)
    assert "board_spaces" in data
    assert "red_spaces" in data
    assert "blue_spaces" in data
    assert "player_turn" in data


def test_load_game_restores_board_spaces(manager, board):
    manager.save_game(board, "test_load")
    loaded = manager.load_game("test_load")
    assert len(loaded.board_spaces) == len(board.board_spaces)


def test_load_game_restores_piece_positions(manager, board):
    manager.save_game(board, "test_pieces")
    loaded = manager.load_game("test_pieces")
    assert set(loaded.red_spaces) == set(board.red_spaces)
    assert set(loaded.blue_spaces) == set(board.blue_spaces)


def test_load_game_restores_player_turn(manager, board):
    board.player_turn.colour = Colour.RED
    manager.save_game(board, "test_turn")
    loaded = manager.load_game("test_turn")
    assert loaded.player_turn.colour == Colour.RED


def test_load_game_restores_change_counter(manager, board):
    board.change_counter = 5
    manager.save_game(board, "test_counter")
    loaded = manager.load_game("test_counter")
    assert loaded.change_counter == 5


def test_load_game_restores_last_move(manager, board):
    move = Move(
        [Space((0, 0), Colour.RED), Space((1, 1), Colour.EMPTY)],
        [Space((0, 1), Colour.BLUE), Space((1, 2), Colour.EMPTY)],
    )
    board.last_move = move
    manager.save_game(board, "test_move")
    loaded = manager.load_game("test_move")
    assert loaded.last_move is not None
    assert loaded.last_move.player_move[0].coordinates == move.player_move[0].coordinates


def test_load_game_handles_no_last_move(manager, board):
    board.last_move = None
    manager.save_game(board, "test_no_move")
    loaded = manager.load_game("test_no_move")
    assert loaded.last_move is None


def test_load_game_file_not_found(manager):
    with pytest.raises(FileNotFoundError):
        manager.load_game("nonexistent")


def test_load_game_appends_json_extension(manager, board):
    manager.save_game(board, "test_ext")
    loaded = manager.load_game("test_ext")
    assert loaded is not None


def test_list_saves_returns_empty_for_no_saves(temp_save_dir):
    empty_dir = temp_save_dir / "empty"
    manager = SaveLoadManager(save_dir=str(empty_dir))
    saves = manager.list_saves()
    assert saves == []


def test_list_saves_returns_saved_files(manager, board):
    manager.save_game(board, "save1")
    manager.save_game(board, "save2")
    saves = manager.list_saves()
    filenames = [s[0] for s in saves]
    assert "save1.json" in filenames
    assert "save2.json" in filenames


def test_list_saves_includes_timestamps(manager, board):
    manager.save_game(board, "timed_save")
    saves = manager.list_saves()
    assert len(saves) == 1
    assert len(saves[0]) == 2
    assert isinstance(saves[0][1], str)


def test_delete_save_removes_file(manager, board, temp_save_dir):
    manager.save_game(board, "to_delete")
    filepath = temp_save_dir / "to_delete.json"
    assert filepath.exists()
    result = manager.delete_save("to_delete")
    assert result is True
    assert not filepath.exists()


def test_delete_save_returns_false_for_nonexistent(manager):
    result = manager.delete_save("nonexistent")
    assert result is False


def test_serialize_deserialize_roundtrip(manager, board):
    board.player_turn.colour = Colour.BLUE
    board.change_counter = 10
    manager.save_game(board, "roundtrip")
    loaded = manager.load_game("roundtrip")
    assert loaded.player_turn.colour == board.player_turn.colour
    assert loaded.change_counter == board.change_counter
    assert len(loaded.red_spaces) == len(board.red_spaces)
    assert len(loaded.blue_spaces) == len(board.blue_spaces)


def test_list_saves_nonexistent_directory(temp_save_dir):
    nonexistent_dir = temp_save_dir / "does_not_exist"
    if nonexistent_dir.exists():
        nonexistent_dir.rmdir()
    # create object without running init to test edge case
    manager = SaveLoadManager.__new__(SaveLoadManager)
    manager.save_dir = nonexistent_dir
    saves = manager.list_saves()
    assert saves == []


def test_delete_save_with_json_extension(manager, board):
    manager.save_game(board, "with_ext")
    result = manager.delete_save("with_ext.json")
    assert result is True


def test_save_game_with_json_extension_in_name(manager, board):
    filepath = manager.save_game(board, "already_has.json")
    assert filepath.endswith(".json")
    assert not filepath.endswith(".json.json")


def test_delete_save_io_error(manager, board, temp_save_dir, monkeypatch):
    manager.save_game(board, "to_delete_err")
    filepath = temp_save_dir / "to_delete_err.json"
    assert filepath.exists()

    def mock_unlink(*_args, **_kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "unlink", mock_unlink)
    result = manager.delete_save("to_delete_err")
    assert result is False
