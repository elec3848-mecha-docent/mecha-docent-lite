"""Record audio until silence, then play it back."""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000
BLOCK_DURATION_SEC = 0.03  # 30 ms frames required by WebRTC VAD
VAD_AGGRESSIVENESS = 3
SILENCE_AFTER_SPEECH_SEC = 2
MAX_RECORDING_SEC = 10

sd.default.device = (1, 1)


def record() -> np.ndarray:
    import webrtcvad

    block_size = int(SAMPLE_RATE * BLOCK_DURATION_SEC)
    blocks: list[np.ndarray] = []
    started = False
    silent_for = 0.0
    total = 0.0

    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

    print("Recording... speak now. Stops after silence.")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=block_size) as stream:
        while total < MAX_RECORDING_SEC:
            block, _ = stream.read(block_size)
            blocks.append(block.copy())

            pcm = (block.flatten() * 32767).astype(np.int16).tobytes()
            is_speech = vad.is_speech(pcm, SAMPLE_RATE)

            if is_speech:
                started = True
                silent_for = 0.0
            elif started:
                silent_for += BLOCK_DURATION_SEC

            if started and silent_for >= SILENCE_AFTER_SPEECH_SEC:
                break

            total += BLOCK_DURATION_SEC

    if not started or not blocks:
        print("No speech detected.")
        return np.array([], dtype=np.float32)

    print(f"Recorded {total:.1f}s of audio.")
    return np.concatenate(blocks, axis=0).flatten().astype(np.float32)


def playback(audio: np.ndarray) -> None:
    if audio.size == 0:
        print("Nothing to play.")
        return
    print("Playing back...")
    sd.play(audio, samplerate=SAMPLE_RATE)
    sd.wait()
    print("Done.")


if __name__ == "__main__":
    audio = record()
    playback(audio)
