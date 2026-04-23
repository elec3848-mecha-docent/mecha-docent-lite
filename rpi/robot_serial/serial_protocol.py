import threading
from collections.abc import Callable

import serial


def _reader_loop(ser: serial.Serial, stop_event: threading.Event, print_fn: Callable[[str], None]) -> None:
    while not stop_event.is_set():
        try:
            raw = ser.readline()
        except serial.SerialException as exc:
            print_fn(f"[rx-error] {exc}")
            break

        if not raw:
            continue

        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line:
            print_fn(f"[arduino] {line}")


def run_serial_protocol_cli(port: str, baud: int) -> None:
    print(f"Connecting to {port} @ {baud}...")
    ser = serial.Serial(port=port, baudrate=baud, timeout=0.2)
    stop_event = threading.Event()
    lock = threading.Lock()

    def safe_print(message: str) -> None:
        with lock:
            print(message)

    reader = threading.Thread(
        target=_reader_loop,
        args=(ser, stop_event, safe_print),
        daemon=True,
    )
    reader.start()

    safe_print("Serial protocol demo ready.")
    safe_print("Enter commands exactly like serial monitor (e.g. 120 -30 45, stop, odom_reset, goto 100 0 157, goto_cancel).")
    safe_print("Type 'quit' or 'exit' to leave.")

    try:
        while True:
            try:
                command = input("> ").strip()
            except EOFError:
                break

            if not command:
                continue

            if command.lower() in {"quit", "exit"}:
                break

            try:
                ser.write((command + "\n").encode("utf-8"))
                ser.flush()
            except serial.SerialException as exc:
                safe_print(f"[tx-error] {exc}")
                break
    except KeyboardInterrupt:
        safe_print("Interrupted by user.")
    finally:
        stop_event.set()
        if ser.is_open:
            ser.close()
        reader.join(timeout=1.0)
        safe_print("Serial protocol demo closed.")
