"""Serial bridge for newline-delimited JSON communication with Arduino."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import serial


@dataclass
class TargetAckResult:
    ok: bool
    command_id: int
    reason: str = ""


class SerialBridge:
    """Non-blocking JSONL bridge for target commands and pose corrections."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        ack_timeout_s: float = 1.0,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._ack_timeout_s = ack_timeout_s
        self._serial: Optional[serial.Serial] = None
        self._next_id = 1
        self._pending_acks: Dict[int, TargetAckResult] = {}
        self._last_status: Optional[Dict[str, Any]] = None

    @property
    def last_status(self) -> Optional[Dict[str, Any]]:
        return self._last_status

    def open(self) -> None:
        if self._serial is not None and self._serial.is_open:
            return

        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=0.0,
            write_timeout=0.25,
        )
        # Wait for Arduino reset and boot message
        time.sleep(2.0)
        self._serial.reset_input_buffer()

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def send_pose_correction(self, x: float, y: float, yaw: float, confidence: float) -> None:
        self._send_message(
            {
                "type": "pose_correction",
                "x": float(x),
                "y": float(y),
                "yaw": float(yaw),
                "confidence": float(confidence),
            }
        )

    def send_cancel_target(self) -> None:
        self._send_message({"type": "cancel_target"})

    def send_target_and_wait_ack(
        self,
        x: float,
        y: float,
        yaw: float,
        timeout_s: Optional[float] = None,
    ) -> TargetAckResult:
        command_id = self._next_id
        self._next_id += 1

        self._send_message(
            {
                "type": "target",
                "id": command_id,
                "x": float(x),
                "y": float(y),
                "yaw": float(yaw),
            }
        )

        timeout = self._ack_timeout_s if timeout_s is None else timeout_s
        deadline = time.time() + timeout

        while time.time() < deadline:
            self.poll()
            pending = self._pending_acks.pop(command_id, None)
            if pending is not None:
                return pending
            time.sleep(0.01)

        return TargetAckResult(ok=False, command_id=command_id, reason="ack_timeout")

    def ping(self) -> None:
        self._send_message({"type": "ping"})

    def poll(self) -> None:
        if self._serial is None:
            raise RuntimeError("Serial bridge is not open")

        while True:
            raw = self._serial.readline()
            if not raw:
                break

            decoded = raw.decode("utf-8", errors="replace").strip()
            if not decoded:
                continue

            try:
                message = json.loads(decoded)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")
            if msg_type == "ack":
                cmd_id = int(message.get("id", -1))
                self._pending_acks[cmd_id] = TargetAckResult(ok=True, command_id=cmd_id)
            elif msg_type == "nack":
                cmd_id = int(message.get("id", -1))
                reason = str(message.get("reason", "nack"))
                self._pending_acks[cmd_id] = TargetAckResult(
                    ok=False,
                    command_id=cmd_id,
                    reason=reason,
                )
            elif msg_type == "status":
                self._last_status = message

    def _send_message(self, payload: Dict[str, Any]) -> None:
        if self._serial is None:
            raise RuntimeError("Serial bridge is not open")

        line = json.dumps(payload, separators=(",", ":")) + "\n"
        self._serial.write(line.encode("utf-8"))
