"""Entry point for the Paradux game: ``python -m paradux``."""

import os
import sys
import threading

from PyQt5.QtWidgets import QApplication

from paradux.controller import GameController, TerminalLoopController
from paradux.gui_view import GUIWindow
from paradux.interfaces import THREAD_JOIN_TIMEOUT
from paradux.model import GameState
from paradux.view import TerminalView

# Start in headless mode when running on Linux without a display
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_LOGGING_RULES"] = "*=false"
    print("DISPLAY environment variable not found. PyQt GUI will run in offscreen mode.")


def main() -> None:
    app = QApplication(sys.argv)
    game_state = GameState()
    game_controller = GameController(game_state)

    terminal_view = TerminalView()
    gui_window = GUIWindow()
    gui_window.set_controller(game_controller)

    game_controller.add_view(terminal_view)
    game_controller.add_view(gui_window)
    gui_window.show()

    stop_event = threading.Event()
    terminal_loop_controller = TerminalLoopController(game_controller, terminal_view)
    terminal_thread = threading.Thread(
        target=terminal_loop_controller.run,
        args=(stop_event,),
        daemon=True,
    )
    terminal_thread.start()

    exit_code = app.exec_()
    stop_event.set()

    terminal_thread.join(timeout=THREAD_JOIN_TIMEOUT)
    sys.stdout.flush()
    sys.stderr.flush()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
