from robot_serial import run_serial_protocol_cli


def run_serial_protocol_demo(port: str, baud: int) -> None:
    run_serial_protocol_cli(port=port, baud=baud)
