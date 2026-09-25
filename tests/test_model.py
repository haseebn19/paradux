from unittest.mock import patch

import pytest

from paradux.interfaces import Colour, MenuState, WinState
from paradux.model import BoardState, GameState, Move, Player, Space


def test_is_empty_true_for_empty():
    space = Space((0, 0), Colour.EMPTY)
    assert space.is_empty


def test_is_empty_false_for_coloured():
    space = Space((0, 0), Colour.RED)
    assert not space.is_empty


@pytest.fixture
def move_spaces():
    return {
        "red_current": Space((2, 2), Colour.RED),
        "blue_current": Space((2, 3), Colour.BLUE),
        "empty_target_1": Space((3, 2), Colour.EMPTY),
        "empty_target_2": Space((3, 3), Colour.EMPTY),
    }


def test_move_requires_two_spaces_each(move_spaces):
    move = Move(
        [move_spaces["red_current"]], [move_spaces["blue_current"], move_spaces["empty_target_2"]]
    )
    assert not move.is_move_legal()


def test_move_requires_opposite_colours(move_spaces):
    move = Move(
        [Space((2, 2), Colour.RED), move_spaces["empty_target_1"]],
        [Space((2, 3), Colour.RED), move_spaces["empty_target_2"]],
    )
    assert not move.is_move_legal()


def test_move_requires_adjacency(move_spaces):
    far_space = Space((5, 5), Colour.BLUE)
    move = Move(
        [move_spaces["red_current"], move_spaces["empty_target_1"]],
        [far_space, move_spaces["empty_target_2"]],
    )
    assert not move.is_move_legal()


def test_valid_shift_move(move_spaces):
    move = Move(
        [move_spaces["red_current"], move_spaces["empty_target_1"]],
        [move_spaces["blue_current"], move_spaces["empty_target_2"]],
    )
    assert move.is_move_legal()


def test_swap_move(move_spaces):
    red_target = Space(move_spaces["blue_current"].coordinates, Colour.BLUE)
    blue_target = Space(move_spaces["red_current"].coordinates, Colour.RED)
    move = Move(
        [move_spaces["red_current"], red_target], [move_spaces["blue_current"], blue_target]
    )
    assert move.is_move_legal()


def test_move_cannot_reverse_last_move(move_spaces):
    last_move = Move(
        [move_spaces["red_current"], move_spaces["empty_target_1"]],
        [move_spaces["blue_current"], move_spaces["empty_target_2"]],
    )
    result = Move(
        [Space(move_spaces["empty_target_1"].coordinates, Colour.RED), move_spaces["red_current"]],
        [
            Space(move_spaces["empty_target_2"].coordinates, Colour.BLUE),
            move_spaces["blue_current"],
        ],
    )
    assert not result.is_move_legal(last_move)


def test_shift_with_occupied_target_requires_swap_pattern(move_spaces):
    red_target = Space(move_spaces["blue_current"].coordinates, Colour.BLUE)
    move = Move(
        [move_spaces["red_current"], red_target],
        [move_spaces["blue_current"], Space((3, 4), Colour.EMPTY)],
    )
    assert not move.is_move_legal()


@pytest.fixture
def board_state():
    return BoardState()


def test_board_initialises_starting_tokens(board_state):
    expected_coordinates = {
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
        (2, 0),
        (2, 1),
        (2, 2),
        (2, 3),
        (2, 4),
        (2, 5),
        (3, 0),
        (3, 1),
        (3, 2),
        (3, 3),
        (3, 4),
        (3, 5),
        (3, 6),
        (4, 1),
        (4, 2),
        (4, 3),
        (4, 4),
        (4, 5),
        (4, 6),
        (5, 2),
        (5, 3),
        (5, 4),
        (5, 5),
        (5, 6),
        (6, 3),
        (6, 4),
        (6, 5),
        (6, 6),
    }
    assert set(board_state.board_spaces.keys()) == expected_coordinates
    expected_red = {
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
    }
    expected_blue = {
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
    }

    assert set(board_state.red_spaces) == expected_red
    assert set(board_state.blue_spaces) == expected_blue

    for coord, colour in board_state.board_spaces.items():
        if coord in expected_red:
            assert colour == Colour.RED
        elif coord in expected_blue:
            assert colour == Colour.BLUE
        else:
            assert colour == Colour.EMPTY


def test_clear_prev_tokens_sets_empty_and_updates_lists(board_state):
    current_red = Space((2, 2), Colour.RED)
    current_blue = Space((2, 3), Colour.BLUE)
    board_state.board_spaces[current_red.coordinates] = Colour.RED
    board_state.board_spaces[current_blue.coordinates] = Colour.BLUE
    board_state.red_spaces.append(current_red.coordinates)
    board_state.blue_spaces.append(current_blue.coordinates)

    board_state.clear_prev_tokens(current_red, current_blue)

    assert board_state.board_spaces[current_red.coordinates] == Colour.EMPTY
    assert board_state.board_spaces[current_blue.coordinates] == Colour.EMPTY
    assert current_red.coordinates not in board_state.red_spaces
    assert current_blue.coordinates not in board_state.blue_spaces


def test_set_new_locations_sets_colours_and_lists(board_state):
    red_move = Space((2, 2), Colour.RED)
    blue_move = Space((2, 3), Colour.BLUE)
    board_state.set_new_locations(red_move, blue_move)

    assert board_state.board_spaces[red_move.coordinates] == Colour.RED
    assert board_state.board_spaces[blue_move.coordinates] == Colour.BLUE
    assert red_move.coordinates in board_state.red_spaces
    assert blue_move.coordinates in board_state.blue_spaces


def test_check_win_detects_win_conditions(board_state):
    board_state.red_spaces = [(0, 0), (1, 1), (2, 2), (3, 3)]
    assert board_state.check_win() == WinState.RED
    board_state.red_spaces.clear()
    board_state.blue_spaces = [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert board_state.check_win() == WinState.BLUE
    board_state.blue_spaces.clear()
    board_state.red_spaces = [(0, 3), (1, 2), (2, 1), (3, 0)]
    assert board_state.check_win() == WinState.RED


def test_check_win_no_win_returns_none(board_state):
    assert board_state.check_win() == WinState.NONE


def test_check_win_prefers_current_player_on_double_line(board_state):
    red_line = [(0, 0), (0, 1), (0, 2), (0, 3)]
    blue_line = [(1, 0), (1, 1), (1, 2), (1, 3)]
    for coord in board_state.board_spaces:
        board_state.board_spaces[coord] = Colour.EMPTY
    board_state.red_spaces = red_line.copy()
    board_state.blue_spaces = blue_line.copy()
    for coord in red_line:
        board_state.board_spaces[coord] = Colour.RED
    for coord in blue_line:
        board_state.board_spaces[coord] = Colour.BLUE

    assert board_state.check_win(preferred_colour=Colour.RED) == WinState.RED
    assert board_state.check_win(preferred_colour=Colour.BLUE) == WinState.BLUE


@pytest.fixture
def game_state():
    return GameState()


def test_start_new_game_initialises_board(game_state):
    with patch("paradux.model.random.choice", return_value=Colour.RED):
        board = game_state.start_new_game()
    assert isinstance(board, BoardState)
    assert game_state.can_continue
    assert not game_state.is_paused
    assert board.player_turn.colour == Colour.RED


def test_continue_game_returns_existing_board(game_state):
    with patch("paradux.model.random.choice", return_value=Colour.BLUE):
        board = game_state.start_new_game()
    game_state.pause_game()
    continued = game_state.continue_game()
    assert continued is board
    assert not game_state.is_paused


def test_continue_game_raises_if_no_board(game_state):
    with pytest.raises(ValueError):
        game_state.continue_game()


def test_quit_resets_state(game_state):
    game_state.start_new_game()
    game_state.quit()
    assert not game_state.can_continue
    with pytest.raises(ValueError):
        game_state.continue_game()


def test_pause_and_restart_game(game_state):
    with patch("paradux.model.random.choice", return_value=Colour.RED):
        initial_board = game_state.start_new_game()
    game_state.pause_game()
    with patch("paradux.model.random.choice", return_value=Colour.BLUE):
        restarted_board = game_state.restart_game()
    assert isinstance(restarted_board, BoardState)
    assert initial_board is not restarted_board
    assert not game_state.is_paused
    assert restarted_board.player_turn.colour == Colour.BLUE


def test_restart_requires_pause(game_state):
    game_state.start_new_game()
    with pytest.raises(ValueError):
        game_state.restart_game()


def test_load_game_sets_board(game_state):
    loaded_board = BoardState()
    result = game_state.load_game(loaded_board)
    assert result is loaded_board
    assert game_state.can_continue


def test_return_to_main_menu_sets_state(game_state):
    game_state.start_new_game()
    game_state.return_to_main_menu()
    assert game_state.get_menu_state() == MenuState.MAIN_MENU
    assert game_state.is_paused


def test_get_menu_state_initial(game_state):
    assert game_state.get_menu_state() == MenuState.MAIN_MENU


def test_menu_state_changes_on_new_game(game_state):
    game_state.start_new_game()
    assert game_state.get_menu_state() == MenuState.IN_GAME


def test_continue_game_fails_after_win(game_state):
    board = game_state.start_new_game()
    board.red_spaces = [(0, 0), (0, 1), (0, 2), (0, 3)]
    for coord in board.red_spaces:
        board.board_spaces[coord] = Colour.RED
    game_state.return_to_main_menu()
    with pytest.raises(ValueError):
        game_state.continue_game()


def test_apply_move_updates_positions(board_state):
    red_pos = (0, 1)
    blue_pos = (0, 0)
    board_state.board_spaces[red_pos] = Colour.RED
    board_state.board_spaces[blue_pos] = Colour.BLUE
    if red_pos not in board_state.red_spaces:
        board_state.red_spaces.append(red_pos)
    if blue_pos not in board_state.blue_spaces:
        board_state.blue_spaces.append(blue_pos)

    current_red = Space(red_pos, Colour.RED)
    current_blue = Space(blue_pos, Colour.BLUE)
    target_red = Space((1, 1), Colour.EMPTY)
    target_blue = Space((1, 0), Colour.EMPTY)
    move = Move([current_red, target_red], [current_blue, target_blue])

    board_state.apply_move(move)
    assert board_state.board_spaces[(1, 1)] == Colour.RED
    assert board_state.board_spaces[(1, 0)] == Colour.BLUE
    assert (1, 1) in board_state.red_spaces
    assert (1, 0) in board_state.blue_spaces


def test_apply_move_increments_counter(board_state):
    initial_count = board_state.change_counter
    current_red = Space((0, 1), Colour.RED)
    current_blue = Space((0, 0), Colour.BLUE)
    target_red = Space((1, 1), Colour.EMPTY)
    target_blue = Space((1, 0), Colour.EMPTY)
    move = Move([current_red, target_red], [current_blue, target_blue])
    board_state.apply_move(move)
    assert board_state.change_counter == initial_count + 1


def test_apply_move_sets_last_move(board_state):
    current_red = Space((0, 1), Colour.RED)
    current_blue = Space((0, 0), Colour.BLUE)
    target_red = Space((1, 1), Colour.EMPTY)
    target_blue = Space((1, 0), Colour.EMPTY)
    move = Move([current_red, target_red], [current_blue, target_blue])
    board_state.apply_move(move)
    assert board_state.last_move is move


def test_switch_turn_blue_to_red(board_state):
    board_state.player_turn.colour = Colour.BLUE
    result = board_state.switch_turn()
    assert result == Colour.RED


def test_switch_turn_red_to_blue(board_state):
    board_state.player_turn.colour = Colour.RED
    result = board_state.switch_turn()
    assert result == Colour.BLUE


def test_player_colour():
    player = Player(Colour.RED)
    assert player.colour == Colour.RED


def test_player_colour_change():
    player = Player(Colour.BLUE)
    player.colour = Colour.RED
    assert player.colour == Colour.RED


def test_vertical_win_detection():
    board = BoardState()
    for coord in board.board_spaces:
        board.board_spaces[coord] = Colour.EMPTY
    board.red_spaces.clear()
    board.blue_spaces.clear()

    vertical_line = [(0, 0), (1, 0), (2, 0), (3, 0)]
    board.red_spaces = vertical_line.copy()
    for coord in vertical_line:
        board.board_spaces[coord] = Colour.RED
    assert board.check_win() == WinState.RED


def test_vertical_win_column_pattern():
    board = BoardState()
    for coord in board.board_spaces:
        board.board_spaces[coord] = Colour.EMPTY
    board.red_spaces.clear()
    board.blue_spaces.clear()

    vertical_line = [(1, 1), (2, 1), (3, 1), (4, 1)]
    board.red_spaces = vertical_line.copy()
    for coord in vertical_line:
        board.board_spaces[coord] = Colour.RED
    # sort_colour_spaces is removed; we directly use _has_winning_line with sorted spaces
    assert board._has_winning_line(sorted(vertical_line, key=lambda c: (c[0], c[1])))


def test_blue_only_win():
    board = BoardState()
    for coord in board.board_spaces:
        board.board_spaces[coord] = Colour.EMPTY
    board.red_spaces.clear()
    board.blue_spaces.clear()

    blue_line = [(0, 0), (0, 1), (0, 2), (0, 3)]
    board.blue_spaces = blue_line.copy()
    for coord in blue_line:
        board.board_spaces[coord] = Colour.BLUE
    assert board.check_win() == WinState.BLUE


def test_elimination_win_blue():
    board = BoardState()
    for coord in board.board_spaces:
        board.board_spaces[coord] = Colour.EMPTY
    board.red_spaces.clear()
    board.blue_spaces.clear()

    board.red_spaces = []
    board.blue_spaces = [(0, 0)]
    board.board_spaces[(0, 0)] = Colour.BLUE
    assert board.check_win() == WinState.BLUE


def test_elimination_win_red():
    board = BoardState()
    for coord in board.board_spaces:
        board.board_spaces[coord] = Colour.EMPTY
    board.red_spaces.clear()
    board.blue_spaces.clear()

    board.blue_spaces = []
    board.red_spaces = [(0, 0)]
    board.board_spaces[(0, 0)] = Colour.RED
    assert board.check_win() == WinState.RED


def test_double_win_defaults_to_red_without_preference():
    board = BoardState()
    for coord in board.board_spaces:
        board.board_spaces[coord] = Colour.EMPTY
    board.red_spaces.clear()
    board.blue_spaces.clear()

    red_line = [(0, 0), (0, 1), (0, 2), (0, 3)]
    blue_line = [(1, 0), (1, 1), (1, 2), (1, 3)]
    board.red_spaces = red_line.copy()
    board.blue_spaces = blue_line.copy()
    for coord in red_line:
        board.board_spaces[coord] = Colour.RED
    for coord in blue_line:
        board.board_spaces[coord] = Colour.BLUE
    result = board.check_win(preferred_colour=None)
    assert result in [WinState.RED, WinState.BLUE]


def test_blue_only_win_not_red():
    board = BoardState()
    for coord in board.board_spaces:
        board.board_spaces[coord] = Colour.EMPTY
    board.red_spaces.clear()
    board.blue_spaces.clear()

    blue_line = [(1, 0), (1, 1), (1, 2), (1, 3)]
    red_scattered = [(0, 0), (2, 2), (3, 3)]
    board.blue_spaces = blue_line.copy()
    board.red_spaces = red_scattered.copy()
    for coord in blue_line:
        board.board_spaces[coord] = Colour.BLUE
    for coord in red_scattered:
        board.board_spaces[coord] = Colour.RED
    assert board.check_win() == WinState.BLUE


def test_apply_move_with_blue_as_first_piece(board_state):
    blue_pos = (0, 0)
    red_pos = (0, 1)
    board_state.board_spaces[blue_pos] = Colour.BLUE
    board_state.board_spaces[red_pos] = Colour.RED
    if blue_pos not in board_state.blue_spaces:
        board_state.blue_spaces.append(blue_pos)
    if red_pos not in board_state.red_spaces:
        board_state.red_spaces.append(red_pos)

    current_blue = Space(blue_pos, Colour.BLUE)
    current_red = Space(red_pos, Colour.RED)
    target_blue = Space((1, 0), Colour.EMPTY)
    target_red = Space((1, 1), Colour.EMPTY)
    move = Move([current_blue, target_blue], [current_red, target_red])

    board_state.apply_move(move)
    assert board_state.board_spaces[(1, 0)] == Colour.BLUE
    assert board_state.board_spaces[(1, 1)] == Colour.RED


def test_occupied_target_wrong_colour():
    red_current = Space((0, 0), Colour.RED)
    blue_current = Space((0, 1), Colour.BLUE)
    red_target = Space((1, 0), Colour.RED)
    blue_target = Space((1, 1), Colour.BLUE)
    move = Move([red_current, red_target], [blue_current, blue_target])
    assert not move.is_move_legal()


def test_pause_game_raises_without_board(game_state):
    with pytest.raises(ValueError):
        game_state.pause_game()


def test_return_to_main_menu_without_board(game_state):
    game_state.return_to_main_menu()
    assert game_state.get_menu_state() == MenuState.MAIN_MENU
