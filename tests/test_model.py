from unittest.mock import patch

import pytest

from paradux.interfaces import Colour, MenuState, WinState
from paradux.model import BoardState, GameState, Move, Space


def empty_board(red=(), blue=()) -> BoardState:
    """A board with only the given red and blue pieces."""
    board = BoardState()
    for position in board.board_spaces:
        board.board_spaces[position] = Colour.EMPTY
    for position in red:
        board.board_spaces[position] = Colour.RED
    for position in blue:
        board.board_spaces[position] = Colour.BLUE
    return board


def test_space_is_empty():
    assert Space((0, 0), Colour.EMPTY).is_empty
    assert not Space((0, 0), Colour.RED).is_empty


class TestMoveRules:
    RED = Space((2, 2), Colour.RED)
    BLUE = Space((2, 3), Colour.BLUE)

    def shift(self, red_end, blue_end, red_colour=Colour.EMPTY, blue_colour=Colour.EMPTY):
        return Move(
            [self.RED, Space(red_end, red_colour)], [self.BLUE, Space(blue_end, blue_colour)]
        )

    def test_both_pieces_step_the_same_way_into_empty_spaces(self):
        assert self.shift((3, 2), (3, 3)).is_move_legal()

    def test_a_piece_can_step_into_the_space_the_other_is_leaving(self):
        assert self.shift((2, 3), (2, 4), red_colour=Colour.BLUE).is_move_legal()

    def test_the_pieces_can_swap(self):
        assert self.shift((2, 3), (2, 2), Colour.BLUE, Colour.RED).is_move_legal()

    def test_pieces_cannot_move_in_different_directions(self):
        assert not self.shift((3, 2), (2, 4)).is_move_legal()

    def test_pieces_cannot_move_onto_other_pieces(self):
        assert not self.shift((3, 2), (3, 3), blue_colour=Colour.RED).is_move_legal()

    def test_pieces_must_be_different_colours_and_adjacent(self):
        same = Move(
            [self.RED, Space((3, 2), Colour.EMPTY)],
            [Space((2, 3), Colour.RED), Space((3, 3), Colour.EMPTY)],
        )
        apart = Move(
            [self.RED, Space((3, 2), Colour.EMPTY)],
            [Space((5, 5), Colour.BLUE), Space((6, 5), Colour.EMPTY)],
        )
        assert not same.is_move_legal()
        assert not apart.is_move_legal()

    def test_a_move_cannot_undo_the_last_move(self):
        last_move = self.shift((3, 2), (3, 3))
        undo = Move(
            [Space((3, 2), Colour.RED), Space((2, 2), Colour.EMPTY)],
            [Space((3, 3), Colour.BLUE), Space((2, 3), Colour.EMPTY)],
        )
        assert undo.is_move_legal()
        assert not undo.is_move_legal(last_move)


class TestBoardState:
    def test_starting_position(self):
        board = BoardState()
        assert len(board.board_spaces) == 37
        assert set(board.red_spaces) == set(BoardState.STARTING_TOKENS[Colour.RED])
        assert set(board.blue_spaces) == set(BoardState.STARTING_TOKENS[Colour.BLUE])
        assert board.board_spaces.get((3, 3)) == Colour.EMPTY

    def test_switch_turn(self):
        board = BoardState()
        board.player_turn.colour = Colour.BLUE
        assert board.switch_turn() == Colour.RED
        assert board.switch_turn() == Colour.BLUE

    def test_shift_targets(self):
        # Moving down-left would put Blue on Red's piece at (1, 0), so only down-right is free
        assert BoardState().shift_targets((0, 1), (0, 0)) == [(1, 2)]

    def test_shift_targets_leave_out_undoing_the_last_move(self):
        board = empty_board(red=[(3, 2)], blue=[(3, 3)])
        move = board.build_move((3, 2), (3, 3), (4, 3))
        board.apply_move(move)
        assert (3, 2) not in board.shift_targets((4, 3), (4, 4))

    def test_build_move_returns_none_off_the_board(self):
        assert BoardState().build_move((0, 1), (0, 0), (-1, 0)) is None

    def test_apply_move_moves_both_pieces(self):
        board = empty_board(red=[(3, 2)], blue=[(3, 3)])
        move = board.build_move((3, 2), (3, 3), (3, 3))

        board.apply_move(move)

        assert board.red_spaces == [(3, 3)]
        assert board.blue_spaces == [(3, 4)]
        assert board.last_move is move
        assert board.change_counter == 1

    def test_apply_swap(self):
        board = empty_board(red=[(3, 2)], blue=[(3, 3)])
        board.apply_move(board.build_move((3, 2), (3, 3)))
        assert board.red_spaces == [(3, 3)]
        assert board.blue_spaces == [(3, 2)]


class TestWinDetection:
    @pytest.mark.parametrize(
        "line",
        [
            [(0, 0), (0, 1), (0, 2), (0, 3)],
            [(1, 1), (2, 1), (3, 1), (4, 1)],
            [(0, 0), (1, 1), (2, 2), (3, 3)],
        ],
    )
    def test_four_in_a_row_along_each_axis_wins(self, line):
        assert empty_board(red=line).check_win() == WinState.RED
        assert empty_board(blue=line).check_win() == WinState.BLUE

    def test_four_not_in_a_row_does_not_win(self):
        board = empty_board(red=[(0, 3), (1, 2), (2, 1), (3, 0)])
        assert board.check_win() == WinState.NONE
        assert BoardState().check_win() == WinState.NONE

    def test_the_player_who_moved_wins_when_both_complete_a_line(self):
        board = empty_board(
            red=[(0, 0), (0, 1), (0, 2), (0, 3)], blue=[(1, 0), (1, 1), (1, 2), (1, 3)]
        )
        assert board.check_win(preferred_colour=Colour.RED) == WinState.RED
        assert board.check_win(preferred_colour=Colour.BLUE) == WinState.BLUE


class TestGameState:
    def test_new_game_picks_a_random_first_player(self):
        game_state = GameState()
        with patch("paradux.model.random.choice", return_value=Colour.RED):
            board = game_state.start_new_game()
        assert board.player_turn.colour == Colour.RED
        assert game_state.can_continue
        assert game_state.get_menu_state() == MenuState.IN_GAME

    def test_menu_and_continue(self):
        game_state = GameState()
        assert game_state.get_menu_state() == MenuState.MAIN_MENU
        board = game_state.start_new_game()

        game_state.return_to_main_menu()
        assert game_state.get_menu_state() == MenuState.MAIN_MENU
        assert game_state.continue_game() is board
        assert game_state.get_menu_state() == MenuState.IN_GAME

    def test_cannot_continue_without_a_game_or_after_quitting(self):
        game_state = GameState()
        with pytest.raises(ValueError):
            game_state.continue_game()

        game_state.start_new_game()
        game_state.quit()
        assert not game_state.can_continue
        with pytest.raises(ValueError):
            game_state.continue_game()

    def test_cannot_continue_a_finished_game(self):
        game_state = GameState()
        board = game_state.start_new_game()
        for position in [(0, 0), (0, 1), (0, 2), (0, 3)]:
            board.board_spaces[position] = Colour.RED
        game_state.return_to_main_menu()
        with pytest.raises(ValueError):
            game_state.continue_game()

    def test_load_game(self):
        game_state = GameState()
        loaded = BoardState()
        assert game_state.load_game(loaded) is loaded
        assert game_state.can_continue
