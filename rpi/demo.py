import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raspberry Pi demo runner")
    parser.add_argument(
        "--demo",
        choices=["audio", "tts", "stt-to-tts", "tour", "serial-protocol"],
        default="stt-to-tts",
        help="Which demo to run.",
    )
    parser.add_argument(
        "--text",
        default="Hello from the TTS demo.",
        help="Text to synthesize when running --demo tts.",
    )
    parser.add_argument(
        "--voice",
        default="F4",
        help="Voice style name for TTS.",
    )
    parser.add_argument(
        "--output",
        default="output.wav",
        help="Output WAV file path. Use empty value to skip saving.",
    )
    parser.add_argument(
        "--content-json",
        default="",
        help="Path to tour JSON content file when running --demo tour.",
    )
    parser.add_argument(
        "--input-device",
        type=int,
        default=None,
        help="Optional input device index for microphone capture.",
    )
    parser.add_argument(
        "--output-device",
        type=int,
        default=None,
        help="Optional output device index for audio playback.",
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0",
        help="Serial port path for --demo serial-protocol.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baud rate for --demo serial-protocol.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output_path = args.output if args.output else None

    if args.demo == "audio":
        from demos.audio_demo import run_audio_demo

        run_audio_demo(input_device=args.input_device, output_device=args.output_device)
        return

    if args.demo == "tts":
        from demos.tts_demo import run_tts_demo

        run_tts_demo(text=args.text, voice_name=args.voice, output_path=output_path)
        return

    if args.demo == "stt-to-tts":
        from demos.stt_to_tts_demo import run_stt_to_tts_demo

        run_stt_to_tts_demo(
            voice_name=args.voice,
            output_path=output_path,
            input_device=args.input_device,
            output_device=args.output_device,
        )
        return

    if args.demo == "serial-protocol":
        from demos.serial_protocol_demo import run_serial_protocol_demo

        run_serial_protocol_demo(port=args.port, baud=args.baud)
        return

    from demos.tour_demo import run_tour_demo

    content_path = args.content_json if args.content_json else None
    run_tour_demo(
        voice_name=args.voice,
        output_path=output_path,
        content_path=content_path,
    )


if __name__ == "__main__":
    main()