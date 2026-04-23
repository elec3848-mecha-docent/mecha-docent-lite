import time
from typing import Any

import numpy as np
import sounddevice as sd
from supertonic import TTS
from tour.tour_config import AudioConfig

DEFAULT_AUDIO_CONFIG = AudioConfig()
DEFAULT_VOICE_NAME = "F4"
DEFAULT_SAMPLE_RATE = DEFAULT_AUDIO_CONFIG.sample_rate

def create_tts(auto_download: bool = True) -> TTS:
    return TTS(auto_download=auto_download)


def synthesize_text(
    text: str,
    voice_name: str = DEFAULT_VOICE_NAME,
    tts: TTS | None = None,
) -> tuple[Any, float, float]:
    tts = tts or create_tts()
    style = tts.get_voice_style(voice_name=voice_name)

    # Split text into sentences or smaller chunks if it's very long to avoid middle cutoffs
    # or ensure the engine finishes completely. 
    # For now, we trust supertonic's synthesize but ensure it returns full waveform.
    
    start_time = time.time()
    wav, duration = tts.synthesize(text, voice_style=style)
    synthesis_duration = time.time() - start_time

    return wav, float(duration[0]), synthesis_duration


def play_audio(wav: Any, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    # Pad with silence to prevent cutoff at start and end
    # 0.2 seconds of silence
    padding_duration = 0.2
    padding_samples = int(sample_rate * padding_duration)
    
    # Check if wav is 2D and needs padding differently or just concatenate
    if wav.ndim == 1:
        silence = np.zeros(padding_samples, dtype=wav.dtype)
        padded_wav = np.concatenate([silence, wav, silence])
    else:
        # Assuming wav is (channels, samples) based on wav.T usage
        silence_padded = np.zeros((wav.shape[0], padding_samples), dtype=wav.dtype)
        padded_wav = np.concatenate([silence_padded, wav, silence_padded], axis=1)

    # Use a larger buffer size (blocksize) to prevent mid-speech dropouts/stuttering on RPi
    # This addresses hardware/OS scheduling jitter.
    sd.play(
        padded_wav.T,
        samplerate=sample_rate,
        device=DEFAULT_AUDIO_CONFIG.output_device,
        blocking=True
    )


def save_audio(wav: Any, output_path: str, tts: TTS | None = None) -> None:
    tts = tts or create_tts()
    tts.save_audio(wav, output_path)


def speak_text(
    text: str,
    voice_name: str = DEFAULT_VOICE_NAME,
    output_device: int | None = DEFAULT_AUDIO_CONFIG.output_device,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    output_path: str | None = "output.wav",
    tts: TTS | None = None,
) -> tuple[float, float]:
    if output_device is not None:
        sd.default.device = (None, output_device)

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