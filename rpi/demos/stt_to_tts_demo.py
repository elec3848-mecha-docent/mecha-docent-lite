from speech.stt import transcribe_from_microphone
from speech.tts import speak_text


def run_stt_to_tts_demo(
    voice_name: str,
    output_path: str | None,
    input_device: int | None = None,
    output_device: int | None = None,
) -> None:
    print("Listening for speech...")
    text = transcribe_from_microphone(input_device=input_device)

    if not text:
        print("No speech detected or transcription was empty.")
        return

    print(f"Transcribed: {text}")
    print("Speaking transcription...")
    audio_duration, synthesis_duration = speak_text(
        text=text,
        voice_name=voice_name,
        output_device=output_device,
        output_path=output_path,
    )
    print(f"Synthesis took {synthesis_duration:.2f} seconds")
    print(f"Audio duration: {audio_duration:.2f} seconds")
    print(f"Real-time factor: {synthesis_duration / audio_duration:.2f}x")
