import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

DEFAULT_MODEL_SIZE = "tiny"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_BLOCK_DURATION_SEC = 0.1
DEFAULT_SILENCE_AFTER_SPEECH_SEC = 2
DEFAULT_MAX_RECORDING_SEC = 30
DEFAULT_VOICE_THRESHOLD = 0.01


def create_model(model_size: str = DEFAULT_MODEL_SIZE) -> WhisperModel:
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def record_until_silence(
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    block_duration_sec: float = DEFAULT_BLOCK_DURATION_SEC,
    silence_after_speech_sec: float = DEFAULT_SILENCE_AFTER_SPEECH_SEC,
    max_recording_sec: float = DEFAULT_MAX_RECORDING_SEC,
    voice_threshold: float = DEFAULT_VOICE_THRESHOLD,
) -> np.ndarray:
    block_size = int(sample_rate * block_duration_sec)
    recorded_blocks: list[np.ndarray] = []
    started_speaking = False
    silent_for_sec = 0.0
    total_sec = 0.0

    print("Speak into your microphone. Recording will stop after silence.")

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=block_size,
    ) as stream:
        while total_sec < max_recording_sec:
            block, _ = stream.read(block_size)
            level = float(np.sqrt(np.mean(np.square(block))))

            recorded_blocks.append(block.copy())

            if level > voice_threshold:
                started_speaking = True
                silent_for_sec = 0.0
            elif started_speaking:
                silent_for_sec += block_duration_sec

            if started_speaking and silent_for_sec >= silence_after_speech_sec:
                break

            total_sec += block_duration_sec

    if not started_speaking or not recorded_blocks:
        return np.array([], dtype=np.float32)

    return np.concatenate(recorded_blocks, axis=0).flatten().astype(np.float32)


def transcribe_audio(
    audio: np.ndarray,
    model: WhisperModel | None = None,
    language: str = "en",
    beam_size: int = 5,
) -> str:
    if audio.size == 0:
        return ""

    model = model or create_model()
    segments, _ = model.transcribe(
        audio,
        beam_size=beam_size,
        language=language,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


def transcribe_from_microphone(
    model: WhisperModel | None = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    block_duration_sec: float = DEFAULT_BLOCK_DURATION_SEC,
    silence_after_speech_sec: float = DEFAULT_SILENCE_AFTER_SPEECH_SEC,
    max_recording_sec: float = DEFAULT_MAX_RECORDING_SEC,
    voice_threshold: float = DEFAULT_VOICE_THRESHOLD,
    language: str = "en",
    beam_size: int = 5,
) -> str:
    audio = record_until_silence(
        sample_rate=sample_rate,
        block_duration_sec=block_duration_sec,
        silence_after_speech_sec=silence_after_speech_sec,
        max_recording_sec=max_recording_sec,
        voice_threshold=voice_threshold,
    )
    return transcribe_audio(audio, model=model, language=language, beam_size=beam_size)


def main() -> None:
    text = transcribe_from_microphone()
    print(text if text else "No speech detected or no transcription produced.")


if __name__ == "__main__":
    main()