"""Thread-safe Python client for the Arduino serial protocol.

:class:`SerialProtocolClient` wraps a ``pyserial`` connection and exposes
high-level methods for every command understood by the Arduino firmware
(see ``arduino/src/main.cpp``).

All commands are sent as newline-terminated ASCII strings at 115200 baud.
A re-entrant lock (``_io_lock``) makes it safe to call methods from
multiple threads simultaneously (e.g., a localization thread sending
odometry corrections while the main thread issues movement commands).

Blocking helpers
----------------
:meth:`~SerialProtocolClient.move_to_and_wait`
    Sends a ``goto`` command and polls for ``GOTO=IDLE`` in the Arduino’s
    reply stream.  Retries once if no activity is detected within the first
    5 seconds.
"""
import threading
import time
from collections.abc import Callable

import serial


class SerialProtocolClient:
    def __init__(self, port: str, baud: int, timeout_sec: float = 0.2) -> None:
        self.port = port
        self.baud = baud
        self._serial = serial.Serial(port=port, baudrate=baud, timeout=timeout_sec)
        self._io_lock = threading.Lock()
        # Opening serial often resets Arduino; allow boot logs to drain before first command.
        time.sleep(2.0)
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def send_command(self, command: str) -> None:
        with self._io_lock:
            self._serial.write((command.strip() + "\n").encode("utf-8"))
            self._serial.flush()

    def set_camera_angles(self, pan_deg: int, tilt_deg: int) -> None:
        pan = max(0, min(180, int(round(pan_deg))))
        tilt = max(0, min(180, int(round(tilt_deg))))
        self.send_command(f"servo_cam {pan} {tilt}")

    def set_laser_angles(self, pan_deg: int, tilt_deg: int) -> None:
        pan = max(0, min(180, int(round(pan_deg))))
        tilt = max(0, min(180, int(round(tilt_deg))))
        self.send_command(f"servo_laser {pan} {tilt}")

    def move_laser_midpoint(self, pan_offset_deg: int, tilt_offset_deg: int, speed_deg_per_sec: int) -> None:
        self.send_command(
            f"laser_dir {int(round(pan_offset_deg))} {int(round(tilt_offset_deg))} {int(round(speed_deg_per_sec))}"
        )

    def start_laser_circle(
        self,
        center_pan_deg: int,
        center_tilt_deg: int,
        radius_deg: int,
        rotations: int,
    ) -> None:
        safe_rotations = max(1, int(round(rotations)))
        self.send_command(
            "laser_circle "
            f"{int(round(center_pan_deg))} "
            f"{int(round(center_tilt_deg))} "
            f"{int(round(radius_deg))} "
            f"{safe_rotations}"
        )

    def cancel_laser_motion(self) -> None:
        self.send_command("laser_cancel")

    def laser_on(self) -> None:
        self.send_command("laser_on")

    def laser_off(self) -> None:
        self.send_command("laser_off")

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
    safe_print(
        "Enter commands exactly like serial monitor "
        "(e.g. 120 -30 45, stop, odom_reset, goto 100 0 157, goto_cancel, "
        "servo_cam 90 90, servo_laser 90 90, laser_dir 10 -5 90, laser_circle 10 -5 8 6, laser_cancel)."
    )
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
