import threading
import time
from collections.abc import Callable

import serial


class SerialProtocolClient:
    def __init__(self, port: str, baud: int, timeout_sec: float = 0.2) -> None:
        self.port = port
        self.baud = baud
        self._serial = serial.Serial(port=port, baudrate=baud, timeout=timeout_sec)
        # Opening serial often resets Arduino; allow boot logs to drain before first command.
        time.sleep(2.0)
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def send_command(self, command: str) -> None:
        self._serial.write((command.strip() + "\n").encode("utf-8"))
        self._serial.flush()

    def stop(self) -> None:
        self.send_command("stop")

    def reset_odometry(self) -> None:
        self.send_command("odom_reset")

    def cancel_move_to(self) -> None:
        self.send_command("goto_cancel")

    def move_to(self, x_m: float, y_m: float, yaw_rad: float) -> None:
        # Drop any stale status lines so completion checks match the latest goto command.
        self._serial.reset_input_buffer()
        target_x = int(round(x_m * 100.0))
        target_y = int(round(y_m * 100.0))
        target_yaw_deg = int(round(yaw_rad * 57.2958))
        print(f"[serial] -> goto {target_x} {target_y} {target_yaw_deg}")
        self.send_command(f"goto {target_x} {target_y} {target_yaw_deg}")

    def wait_for_move_to_idle(self, timeout_sec: float = 60.0) -> tuple[bool, bool]:
        deadline = time.monotonic() + timeout_sec
        saw_goto_ack = False
        saw_goto_active = False

        while time.monotonic() < deadline:
            try:
                raw = self._serial.readline()
            except serial.SerialException as exc:
                raise RuntimeError(f"Serial read failed while waiting for move completion: {exc}") from exc

            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue

            print(f"[arduino] {line}")

            if line.startswith("GOTO x="):
                saw_goto_ack = True

            if "GOTO=ACTIVE" in line:
                saw_goto_active = True

            # Only accept IDLE after we know this goto command was accepted/active.
            if "GOTO=IDLE" in line and (saw_goto_ack or saw_goto_active):
                return True, True

        return False, (saw_goto_ack or saw_goto_active)

    def move_to_and_wait(self, x_m: float, y_m: float, yaw_rad: float, timeout_sec: float = 60.0) -> bool:
        for attempt in range(2):
            self.move_to(x_m=x_m, y_m=y_m, yaw_rad=yaw_rad)
            reached, saw_activity = self.wait_for_move_to_idle(timeout_sec=timeout_sec)
            if reached:
                return True
            if saw_activity:
                return False

            # If we never saw any goto acknowledgment/activity, retry once.
            print("[serial] No GOTO activity observed; retrying goto once")

        return False

    def close(self) -> None:
        if self._serial.is_open:
            self._serial.close()


def create_serial_protocol_client(port: str, baud: int, timeout_sec: float = 0.2) -> SerialProtocolClient:
    return SerialProtocolClient(port=port, baud=baud, timeout_sec=timeout_sec)


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
