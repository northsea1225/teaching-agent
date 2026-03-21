from __future__ import annotations

import wave
from pathlib import Path


def get_audio_duration_seconds(path: Path) -> float | None:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        with wave.open(str(path), "rb") as wav_file:
            frame_rate = wav_file.getframerate() or 1
            frames = wav_file.getnframes()
            return round(frames / frame_rate, 3)

    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(path)
    except Exception:
        return None

    return round(len(audio) / 1000.0, 3)
