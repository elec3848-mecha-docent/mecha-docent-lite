import time
from typing import Any

import sounddevice as sd
from supertonic import TTS

DEFAULT_VOICE_NAME = "F4"
DEFAULT_SAMPLE_RATE = 48000


def create_tts(auto_download: bool = True) -> TTS:
    return TTS(auto_download=auto_download)


def synthesize_text(
    text: str,
    voice_name: str = DEFAULT_VOICE_NAME,
    tts: TTS | None = None,
) -> tuple[Any, float, float]:
    tts = tts or create_tts()
    style = tts.get_voice_style(voice_name=voice_name)

    start_time = time.time()
    wav, duration = tts.synthesize(text, voice_style=style)
    synthesis_duration = time.time() - start_time

    return wav, float(duration[0]), synthesis_duration


def play_audio(wav: Any, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    sd.play(wav.T, samplerate=sample_rate)
    sd.wait()


def save_audio(wav: Any, output_path: str, tts: TTS | None = None) -> None:
    tts = tts or create_tts()
    tts.save_audio(wav, output_path)


def speak_text(
    text: str,
    voice_name: str = DEFAULT_VOICE_NAME,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    output_path: str | None = "output.wav",
    tts: TTS | None = None,
) -> tuple[float, float]:
    tts = tts or create_tts()
    wav, audio_duration, synthesis_duration = synthesize_text(
        text=text,
        voice_name=voice_name,
        tts=tts,
    )

    play_audio(wav, sample_rate=sample_rate)

    if output_path:
        save_audio(wav, output_path=output_path, tts=tts)

    return audio_duration, synthesis_duration


def main() -> None:
    text = (
        "Hi there! My name is Meadow. I am a text-to-speech model developed by OpenAI. "
        "I can convert written text into natural-sounding speech. How can I assist you today?"
    )
    audio_duration, synthesis_duration = speak_text(text)
    print(f"Synthesis took {synthesis_duration:.2f} seconds")
    print(f"Audio duration: {audio_duration:.2f} seconds")
    print(f"Real-time factor: {synthesis_duration / audio_duration:.2f}x")


if __name__ == "__main__":
    main()