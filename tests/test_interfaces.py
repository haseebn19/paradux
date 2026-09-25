from paradux.interfaces import Colour, MenuState, WinState


def test_colours_are_saved_by_name():
    assert [colour.value for colour in Colour] == ["Red", "Blue", "Empty"]


def test_win_states():
    assert [state.value for state in WinState] == [0, 1, 2]
    assert [state.name for state in WinState] == ["NONE", "RED", "BLUE"]


def test_menu_states():
    assert [state.value for state in MenuState] == ["main", "game"]
