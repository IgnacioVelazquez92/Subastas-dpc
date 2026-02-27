# app/utils/audio.py
"""
Utilidad de reproduccion de sonido.

Usa winsound en Windows (stdlib, sin dependencias extra).
En macOS/Linux usa subprocess + afplay / paplay como fallback.
Si no hay archivo MP3/WAV, genera un doble-beep de emergencia con winsound.Beep().

Carpeta esperada de sonidos: assets/sounds/
Archivo de alerta de outbid:  assets/sounds/outbid_alert.mp3
"""

from __future__ import annotations

import ctypes
import sys
import threading
from pathlib import Path

# Ruta base del proyecto (dos niveles arriba de este archivo)
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
SOUNDS_DIR = _BASE_DIR / "assets" / "sounds"
OUTBID_SOUND_MP3 = SOUNDS_DIR / "outbid_alert.mp3"
OUTBID_SOUND_WAV = SOUNDS_DIR / "outbid_alert.wav"


def _play_wav_windows(path: Path) -> None:
    """Reproduce WAV de forma asincrona en Windows (sin bloquear la UI)."""
    import winsound

    winsound.PlaySound(
        str(path),
        winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
    )


def _play_mp3_windows_blocking(path: Path, repeat: int = 1) -> None:
    """
    Reproduce MP3 en Windows usando MCI (winmm), de forma secuencial.
    Esta funcion bloquea el hilo actual, por eso debe correrse en background.
    """

    def _mci(cmd: str) -> None:
        result = ctypes.windll.winmm.mciSendStringW(cmd, None, 0, 0)
        if result != 0:
            raise RuntimeError(f"mciSendStringW error={result}")

    for idx in range(max(1, int(repeat))):
        alias = f"outbid_{threading.get_ident()}_{idx}"
        try:
            _mci(f'open "{path}" type mpegvideo alias {alias}')
            _mci(f"play {alias} from 0 wait")
        finally:
            try:
                _mci(f"close {alias}")
            except Exception:
                pass


def _play_mp3_windows_with_fallback(path: Path, repeat: int = 1) -> None:
    """
    Reproduce MP3 en background y, si falla MCI/codec, intenta WAV canonico.
    Ultimo recurso: beep de emergencia.
    """
    try:
        _play_mp3_windows_blocking(path, repeat=repeat)
    except Exception:
        if OUTBID_SOUND_WAV.exists():
            try:
                _play_wav_windows(OUTBID_SOUND_WAV)
                return
            except Exception:
                pass
        _beep_fallback()


def _play_wav_posix(path: Path) -> None:
    """Intenta reproducir WAV en macOS (afplay) o Linux (paplay/aplay)."""
    import subprocess

    if sys.platform == "darwin":
        subprocess.Popen(["afplay", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        for player in ("paplay", "aplay", "ffplay"):
            try:
                subprocess.Popen(
                    [player, str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except FileNotFoundError:
                continue


def _beep_fallback() -> None:
    """Doble-beep de emergencia usando winsound.Beep (solo Windows). No bloquea."""
    if sys.platform != "win32":
        return
    import winsound

    def _do() -> None:
        winsound.Beep(880, 180)
        winsound.Beep(1100, 220)

    threading.Thread(target=_do, daemon=True).start()


def play_outbid_alert() -> None:
    """
    Reproduce la alerta de OUTBID (oferta propia superada).

    Prioridad:
    1. assets/sounds/outbid_alert.mp3 (3 repeticiones secuenciales)
    2. assets/sounds/outbid_alert.wav
    3. cualquier otro .wav en assets/sounds/
    4. doble-beep con winsound.Beep() en Windows
    """
    try:
        sound = _find_outbid_sound()
        # En Windows priorizar WAV asincrono: es mas estable y no bloquea UI.
        if OUTBID_SOUND_WAV.exists() and sys.platform == "win32":
            _play_wav_windows(OUTBID_SOUND_WAV)
            return

        if sound and sound.suffix.lower() == ".mp3" and sys.platform == "win32":
            threading.Thread(
                target=_play_mp3_windows_with_fallback,
                args=(sound, 3),
                daemon=True,
            ).start()
            return

        if sound:
            _play_wav(sound)
        else:
            _beep_fallback()
    except Exception:
        # Nunca romper la UI por fallos de audio
        _beep_fallback()


def play_wav_file(filename: str) -> None:
    """
    Reproduce cualquier WAV por nombre de archivo ubicado en assets/sounds/.
    Si no existe, hace fallback al beep.
    """
    path = SOUNDS_DIR / filename
    if path.exists():
        try:
            _play_wav(path)
            return
        except Exception:
            pass
    _beep_fallback()


def _find_outbid_sound() -> Path | None:
    """Busca sonido de alerta; primero MP3 canonico, luego WAV canonico, luego cualquier WAV."""
    if OUTBID_SOUND_MP3.exists():
        return OUTBID_SOUND_MP3
    if OUTBID_SOUND_WAV.exists():
        return OUTBID_SOUND_WAV
    if SOUNDS_DIR.exists():
        wavs = sorted(SOUNDS_DIR.glob("*.wav"))
        if wavs:
            return wavs[0]
    return None


def _play_wav(path: Path) -> None:
    if sys.platform == "win32":
        _play_wav_windows(path)
    else:
        _play_wav_posix(path)


def ensure_default_sound() -> None:
    """
    Genera un archivo WAV de alerta por defecto si no existe ningun sonido en assets/sounds/.
    Util para que el sistema funcione sin que el usuario deba copiar un archivo.
    El tono generado es un acorde de alerta de doble pitido (880 Hz + 1100 Hz).
    """
    if OUTBID_SOUND_MP3.exists() or OUTBID_SOUND_WAV.exists():
        return
    try:
        SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
        _generate_default_wav(OUTBID_SOUND_WAV)
    except Exception:
        pass


def _generate_default_wav(out_path: Path) -> None:
    """Genera un WAV simple de doble-beep con la biblioteca stdlib `wave`."""
    import math
    import struct
    import wave

    sample_rate = 22050
    duration_ms = 400     # ms por tono
    gap_ms = 80           # silencio entre tonos
    amplitude = 18000     # 0-32767

    def _tone(freq: float, dur_ms: int) -> list[int]:
        n = int(sample_rate * dur_ms / 1000)
        return [int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)]

    def _silence(dur_ms: int) -> list[int]:
        return [0] * int(sample_rate * dur_ms / 1000)

    samples: list[int] = (
        _tone(880, duration_ms)
        + _silence(gap_ms)
        + _tone(1100, duration_ms)
    )

    with wave.open(str(out_path), "w") as wf:
        wf.setnchannels(1)        # mono
        wf.setsampwidth(2)        # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
