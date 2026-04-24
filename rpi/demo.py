import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raspberry Pi demo runner")
    parser.add_argument(
        "--demo",
        choices=[
            "audio",
            "tts",
            "stt-to-tts",
            "tour",
            "serial-protocol",
            "screen",
            "apriltag",
            "llm",
        ],
        default="tour",
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
        default="",
        help="Output WAV file path. Defaults to not saving.",
    )
    parser.add_argument(
        "--content-json",
        default="",
        help="Path to tour JSON content file when running --demo tour.",
    )
    parser.add_argument(
        "--painting-positions-json",
        default="",
        help="Path to painting position JSON file when running --demo tour.",
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
    parser.add_argument(
        "--face-tracking",
        action="store_true",
        default=True,
        help="Enable camera-based face tracking for the screen demo (default: True).",
    )
    parser.add_argument(
        "--no-face-tracking",
        action="store_false",
        dest="face_tracking",
        help="Disable camera-based face tracking for the screen demo.",
    )
    parser.add_argument(
        "--camera-width",
        type=int,
        default=1280,
        help="Camera width for --demo apriltag.",
    )
    parser.add_argument(
        "--camera-height",
        type=int,
        default=720,
        help="Camera height for --demo apriltag.",
    )
    parser.add_argument(
        "--calibration",
        default="",
        help="Camera calibration YAML path for --demo apriltag.",
    )
    parser.add_argument(
        "--tag-map",
        default="",
        help="Tag map JSON path for --demo apriltag.",
    )
    parser.add_argument(
        "--window-name",
        default="Live Localization",
        help="OpenCV window title for --demo apriltag.",
    )
    parser.add_argument(
        "--llm-model",
        default="models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        help="Path to GGUF model file for --demo llm.",
    )
    parser.add_argument(
        "--llm-exhibits",
        default="exhibits.json",
        help="Path to exhibits JSON for --demo llm.",
    )
    parser.add_argument(
        "--llm-output-path",
        default="output.json",
        help="Output packet JSON path for --demo llm.",
    )
    parser.add_argument(
        "--llm-profile-path",
        default="profile_current.json",
        help="Visitor profile output path for --demo llm.",
    )
    parser.add_argument(
        "--llm-silence-timeout",
        type=int,
        default=20,
        help="Silence timeout (seconds) for --demo llm.",
    )
    parser.add_argument(
        "--llm-chat-format",
        default=None,
        help="Optional explicit chat format for --demo llm.",
    )
    parser.add_argument(
        "--llm-n-ctx",
        type=int,
        default=2048,
        help="Context window size for --demo llm.",
    )
    parser.add_argument(
        "--llm-n-threads",
        type=int,
        default=None,
        help="Thread count for --demo llm (default: min(4, cpu_count)).",
    )
    parser.add_argument(
        "--llm-n-batch",
        type=int,
        default=128,
        help="Batch size for --demo llm.",
    )
    parser.add_argument(
        "--llm-max-tokens",
        type=int,
        default=300,
        help="Max generation tokens for --demo llm.",
    )
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=0.35,
        help="Sampling temperature for --demo llm.",
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

    if args.demo == "screen":
        from demos.screen_demo import run_screen_demo

        run_screen_demo(face_tracking=args.face_tracking)
        return

    if args.demo == "apriltag":
        from demos.apriltag_demo import run_apriltag_demo

        run_apriltag_demo(
            camera_width=args.camera_width,
            camera_height=args.camera_height,
            calibration_path=args.calibration or None,
            tag_map_path=args.tag_map or None,
            window_name=args.window_name,
        )
        return

    if args.demo == "llm":
        from demos.llm_demo import run_llm_demo

        run_llm_demo(
            model_path=args.llm_model,
            exhibits_path=args.llm_exhibits,
            output_path=args.llm_output_path,
            profile_path=args.llm_profile_path,
            silence_timeout=args.llm_silence_timeout,
            chat_format=args.llm_chat_format,
            n_ctx=args.llm_n_ctx,
            n_threads=args.llm_n_threads,
            n_batch=args.llm_n_batch,
            max_tokens=args.llm_max_tokens,
            temperature=args.llm_temperature,
        )
        return

    from demos.tour_demo import run_tour_demo

    content_path = args.content_json if args.content_json else None
    run_tour_demo(
        voice_name=args.voice,
        output_path=output_path,
        content_path=content_path,
        serial_port=args.port,
        serial_baud=args.baud,
        painting_positions_path=args.painting_positions_json if args.painting_positions_json else None,
    )


if __name__ == "__main__":
    main()