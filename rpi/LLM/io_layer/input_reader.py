from __future__ import annotations

import concurrent.futures
import platform
import select
import sys


EXIT_COMMANDS = {"/exit", "exit", "quit", "/quit"}


def is_exit_command(text: str | None) -> bool:
    if not text:
        return False
    return text.strip().lower() in EXIT_COMMANDS


def input_with_timeout(prompt_text: str, timeout_seconds: int) -> str | None:
    print(prompt_text, end=" ", flush=True)

    if platform.system() == "Windows":
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(sys.stdin.readline)
            try:
                line = future.result(timeout=timeout_seconds)
                return line.strip() or None
            except concurrent.futures.TimeoutError:
                return None

    ready, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
    if not ready:
        return None
    line = sys.stdin.readline()
    return line.strip() or None
