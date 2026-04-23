"""demos/screen_demo.py — Eye-animation demo."""

import threading
import time

from screen.display import Screen
from screen.eyes import Eyes


def _loop(eyes: Eyes) -> None:
    eyes.init()
    time.sleep(1.0)  # let the window settle

    while True:
        time.sleep(2.5)
        eyes.blink()
        time.sleep(0.15)

        eyes.look("left", duration=0.25)
        time.sleep(0.8)

        eyes.look("right", duration=0.3)
        time.sleep(0.8)

        eyes.look("centre", duration=0.2)
        time.sleep(0.5)

        eyes.blink(0.07)
        time.sleep(0.12)
        eyes.blink(0.07)
        time.sleep(0.5)

        eyes.squint(0.2)
        time.sleep(1.0)

        eyes.open(0.2)
        time.sleep(1.5)


def run_screen_demo() -> None:
    screen = Screen()
    eyes = Eyes(screen)
    threading.Thread(target=_loop, args=(eyes,), daemon=True).start()
    screen.run()
