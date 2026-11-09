"""Módulo 2 — Controle de mídia e volume do sistema (Windows).

* Mídia: envia as teclas virtuais de mídia (VK_MEDIA_*) via ``SendInput``.
  Funciona com qualquer player que respeite as teclas de mídia
  (Spotify, YouTube no navegador, Groove, VLC...), mesmo em segundo plano.
* Volume: Core Audio via ``pycaw`` (dispositivo de saída padrão).
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

_IS_WIN = sys.platform == "win32"

VK_VOLUME_MUTE = 0xAD
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _MOUSEINPUT(ctypes.Structure):  # só para dimensionar a union corretamente
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _press(vk: int) -> None:
    if not _IS_WIN:
        raise OSError("Controle de mídia implementado apenas para Windows.")
    down = _INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=_KEYBDINPUT(vk, 0, KEYEVENTF_EXTENDEDKEY, 0, 0)))
    up = _INPUT(INPUT_KEYBOARD, _INPUTUNION(
        ki=_KEYBDINPUT(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0, 0)))
    arr = (_INPUT * 2)(down, up)
    ctypes.windll.user32.SendInput(2, arr, ctypes.sizeof(_INPUT))


class MediaController:
    """API de alto nível usada pela UI e pelo servidor MCP."""

    # ------------------------------------------------------------ mídia
    def play_pause(self) -> None: _press(VK_MEDIA_PLAY_PAUSE)
    def next_track(self) -> None: _press(VK_MEDIA_NEXT_TRACK)
    def previous_track(self) -> None: _press(VK_MEDIA_PREV_TRACK)
    def stop(self) -> None: _press(VK_MEDIA_STOP)

    # ------------------------------------------------------------ volume
    @staticmethod
    def _endpoint():
        """Obtém IAudioEndpointVolume (compatível com pycaw antigo e novo)."""
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        speakers = AudioUtilities.GetSpeakers()
        ep = getattr(speakers, "EndpointVolume", None)
        if ep is not None:
            return ep
        from comtypes import CLSCTX_ALL
        from ctypes import POINTER, cast
        iface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(iface, POINTER(IAudioEndpointVolume))

    def get_volume(self) -> int:
        """Volume mestre em 0..100."""
        return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)

    def set_volume(self, percent: int) -> int:
        percent = max(0, min(100, int(percent)))
        self._endpoint().SetMasterVolumeLevelScalar(percent / 100, None)
        return percent

    def change_volume(self, delta: int) -> int:
        return self.set_volume(self.get_volume() + delta)

    def is_muted(self) -> bool:
        return bool(self._endpoint().GetMute())

    def set_mute(self, muted: bool) -> None:
        self._endpoint().SetMute(int(muted), None)

    def toggle_mute(self) -> bool:
        new = not self.is_muted()
        self.set_mute(new)
        return new

