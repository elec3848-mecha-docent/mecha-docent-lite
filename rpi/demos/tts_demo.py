from speech.tts import speak_text


def run_tts_demo(text: str, voice_name: str, output_path: str | None) -> None:
    audio_duration, synthesis_duration = speak_text(
        text=text,
        voice_name=voice_name,
        output_path=output_path,
    )
    print(f"Synthesis took {synthesis_duration:.2f} seconds")
    print(f"Audio duration: {audio_duration:.2f} seconds")
    print(f"Real-time factor: {synthesis_duration / audio_duration:.2f}x")
