"""Voice/audio to text (SpeechRecognition)."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def voice_to_text(audio_path: str | Path, language: str = "fr-FR") -> str | None:
    path = Path(audio_path)
    if not path.exists():
        logger.warning("Audio file not found: %s", path)
        return None
    try:
        import speech_recognition as sr
    except ImportError:
        logger.error("SpeechRecognition not installed. pip install SpeechRecognition pydub")
        return None

    wav_path = path
    if path.suffix.lower() in (".ogg", ".oga", ".opus", ".m4a", ".mp3"):
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(str(path), format=path.suffix.lstrip(".").lower())
            wav_path = path.with_suffix(".wav")
            seg.export(str(wav_path), format="wav")
        except Exception as e:
            logger.warning("Could not convert %s to wav: %s", path, e)
            return None

    try:
        r = sr.Recognizer()
        with sr.AudioFile(str(wav_path)) as source:
            r.adjust_for_ambient_noise(source, duration=0.3)
            audio = r.record(source)
        try:
            text = r.recognize_google(audio, language=language)
            return (text or "").strip() or None
        except sr.UnknownValueError:
            logger.info("Speech not understood for %s", path)
            return None
        except sr.RequestError as e:
            logger.warning("Speech recognition request failed: %s", e)
            return None
    except Exception as e:
        logger.warning("Voice-to-text failed for %s: %s", path, e)
        return None
    finally:
        if wav_path != path and Path(wav_path).exists():
            try:
                Path(wav_path).unlink(missing_ok=True)
            except OSError:
                pass
