import argparse

from stt import transcribe_from_microphone
from tour_fsm import run_tour_guide_demo
from tts import speak_text


def demo_tts_only(text: str, voice_name: str, output_path: str | None) -> None:
    audio_duration, synthesis_duration = speak_text(
        text=text,
        voice_name=voice_name,
        output_path=output_path,
    )
    print(f"Synthesis took {synthesis_duration:.2f} seconds")
    print(f"Audio duration: {audio_duration:.2f} seconds")
    print(f"Real-time factor: {synthesis_duration / audio_duration:.2f}x")


def demo_stt_to_tts(voice_name: str, output_path: str | None) -> None:
    print("Listening for speech...")
    text = transcribe_from_microphone()

    if not text:
        print("No speech detected or transcription was empty.")
        return

    print(f"Transcribed: {text}")
    print("Speaking transcription...")
    audio_duration, synthesis_duration = speak_text(
        text=text,
        voice_name=voice_name,
        output_path=output_path,
    )
    print(f"Synthesis took {synthesis_duration:.2f} seconds")
    print(f"Audio duration: {audio_duration:.2f} seconds")
    print(f"Real-time factor: {synthesis_duration / audio_duration:.2f}x")


def demo_tour_guide(
    voice_name: str,
    output_path: str | None,
    content_path: str | None,
) -> None:
    run_tour_guide_demo(
        voice_name=voice_name,
        output_path=output_path,
        content_path=content_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="STT/TTS demo runner")
    parser.add_argument(
        "--demo",
        choices=["tts", "stt-to-tts", "tour"],
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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output_path = args.output if args.output else None

    if args.demo == "tts":
        demo_tts_only(text=args.text, voice_name=args.voice, output_path=output_path)
        return

    if args.demo == "stt-to-tts":
        demo_stt_to_tts(voice_name=args.voice, output_path=output_path)
        return

    content_path = args.content_json if args.content_json else None
    demo_tour_guide(
        voice_name=args.voice,
        output_path=output_path,
        content_path=content_path,
    )


if __name__ == "__main__":
    main()