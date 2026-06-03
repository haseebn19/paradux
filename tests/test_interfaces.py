from paradux.interfaces import Colour, MenuState, WinState


def test_member_count():
    assert len(Colour) == 3


def test_red_value():
    assert Colour.RED.value == "Red"


def test_blue_value():
    assert Colour.BLUE.value == "Blue"


def test_empty_value():
    assert Colour.EMPTY.value == "Empty"


def test_winstate_member_count():
    assert len(WinState) == 4


def test_none_value():
    assert WinState.NONE.value == 0


def test_winstate_red_value():
    assert WinState.RED.value == 1


def test_winstate_blue_value():
    assert WinState.BLUE.value == 2


def test_tie_value():
    assert WinState.TIE.value == 3


def test_menustate_member_count():
    assert len(MenuState) == 3


def test_main_menu_value():
    assert MenuState.MAIN_MENU.value == "main"


def test_pause_menu_value():
    assert MenuState.PAUSE_MENU.value == "pause"


def test_in_game_value():
    assert MenuState.IN_GAME.value == "game"
