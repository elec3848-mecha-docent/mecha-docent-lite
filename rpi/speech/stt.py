import numpy as np
import sounddevice as sd
import webrtcvad
from scipy.signal import resample_poly
from math import gcd
from faster_whisper import WhisperModel

WHISPER_SAMPLE_RATE = 16000

DEFAULT_MODEL_SIZE = "tiny"
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_BLOCK_DURATION_SEC = 0.03  # WebRTC VAD supports 10, 20, or 30 ms frames
DEFAULT_SILENCE_AFTER_SPEECH_SEC = 2
DEFAULT_MAX_RECORDING_SEC = 30
DEFAULT_VAD_AGGRESSIVENESS = 3  # 0 (least) to 3 (most aggressive)

def create_model(model_size: str = DEFAULT_MODEL_SIZE) -> WhisperModel:
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def record_until_silence(
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    block_duration_sec: float = DEFAULT_BLOCK_DURATION_SEC,
    silence_after_speech_sec: float = DEFAULT_SILENCE_AFTER_SPEECH_SEC,
    max_recording_sec: float = DEFAULT_MAX_RECORDING_SEC,
    vad_aggressiveness: int = DEFAULT_VAD_AGGRESSIVENESS,
) -> np.ndarray:
    block_size = int(sample_rate * block_duration_sec)
    recorded_blocks: list[np.ndarray] = []
    started_speaking = False
    silent_for_sec = 0.0
    total_sec = 0.0

    vad = webrtcvad.Vad(vad_aggressiveness)

    print("Speak into your microphone. Recording will stop after silence.")

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=block_size,
    ) as stream:
        while total_sec < max_recording_sec:
            block, _ = stream.read(block_size)
            recorded_blocks.append(block.copy())

            # Convert float32 [-1, 1] to int16 PCM bytes for WebRTC VAD
            pcm = (block.flatten() * 32767).astype(np.int16).tobytes()
            is_speech = vad.is_speech(pcm, sample_rate)

            if is_speech:
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
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> str:
    if audio.size == 0:
        return ""

    if sample_rate != WHISPER_SAMPLE_RATE:
        g = gcd(WHISPER_SAMPLE_RATE, sample_rate)
        audio = resample_poly(audio, WHISPER_SAMPLE_RATE // g, sample_rate // g).astype(np.float32)

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
    input_device: int | None = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    block_duration_sec: float = DEFAULT_BLOCK_DURATION_SEC,
    silence_after_speech_sec: float = DEFAULT_SILENCE_AFTER_SPEECH_SEC,
    max_recording_sec: float = DEFAULT_MAX_RECORDING_SEC,
    vad_aggressiveness: int = DEFAULT_VAD_AGGRESSIVENESS,
    language: str = "en",
    beam_size: int = 5,
) -> str:
    if input_device is not None:
        sd.default.device = (input_device, None)

    audio = record_until_silence(
        sample_rate=sample_rate,
        block_duration_sec=block_duration_sec,
        silence_after_speech_sec=silence_after_speech_sec,
        max_recording_sec=max_recording_sec,
        vad_aggressiveness=vad_aggressiveness,
    )
    return transcribe_audio(audio, model=model, language=language, beam_size=beam_size, sample_rate=sample_rate)


def main() -> None:
    text = transcribe_from_microphone()
    print(text if text else "No speech detected or no transcription produced.")


if __name__ == "__main__":
    main()