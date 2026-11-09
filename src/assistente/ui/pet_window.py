"""Módulo 1 — Janela flutuante do Pet com mecânica estilo Shimeji.

* Janela frameless, transparente, sempre no topo, fora da barra de tarefas.
* Física: gravidade, pouso com "squash", quique e arremesso ao soltar.
* Drag and drop com o botão esquerdo; ao soltar, a gravidade volta a agir.
* Máquina de estados (loop ~60 FPS via QTimer):
  FALLING -> IDLE <-> WALKING, e DRAGGED a qualquer momento.
* Colisão contra a união das áreas úteis de todos os monitores.
"""
from __future__ import annotations

import math
import random
from collections import deque
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QMovie, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QMenu, QWidget

from assistente.config import Settings
from assistente.media.controller import MediaController
from assistente.ui import desktop
from assistente.ui.media_bar import MediaBar
from assistente.ui.speech_bubble import SpeechBubble

TICK_MS = 16
MAX_FALL = 30.0
AIR_FRICTION = 0.98
MAX_THROW = 25.0


class State(Enum):
    FALLING = auto()
    IDLE = auto()
    WALKING = auto()
    DRAGGED = auto()


class PetWindow(QWidget):
    quit_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(settings.pet_size, settings.pet_size)
        self.setCursor(Qt.OpenHandCursor)

        self._label = QLabel(self)
        self._label.setGeometry(self.rect())
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._has_sprite = self._load_sprite(settings.sprite_path)
        self._media = MediaController()
        self._bubble = SpeechBubble()
        self._media_bar = MediaBar(self._media)
        self._media_bar.action_triggered.connect(lambda msg: self.say(msg, duration_ms=2000))

        # --- estado físico (float para movimento suave)
        self._x = self._y = 0.0
        self._vx = self._vy = 0.0
        self._state = State.FALLING
        self._state_ticks = 0           # ticks restantes no estado autônomo atual
        self._dir = 1                   # -1 esquerda, 1 direita

        # --- animação
        self._blink = 0                 # ticks restantes de olho fechado
        self._squash = 0.0              # 0..1 deformação ao pousar
        self._walk_phase = 0.0

        # --- drag
        self._drag_offset = QPointF()
        self._drag_hist: deque[tuple[int, QPointF]] = deque(maxlen=5)
        self._clock = QElapsedTimer()
        self._clock.start()

        self._timer = QTimer(self, interval=TICK_MS, timeout=self._tick)
        self._timer.setTimerType(Qt.PreciseTimer)

    # ================================================================ ciclo
    def start(self) -> None:
        """Surge no topo da tela onde está o cursor e cai."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self._x = area.center().x() - self.width() / 2
        self._y = area.top()
        self._set_state(State.FALLING)
        self._apply_pos()
        self.show()
        self._timer.start()

    def _set_state(self, state: State) -> None:
        self._state = state
        if state is State.IDLE:
            self._state_ticks = random.randint(90, 300)        # ~1.5 a 5 s
        elif state is State.WALKING:
            self._state_ticks = random.randint(120, 400)
            self._dir = random.choice((-1, 1))
        elif state is State.FALLING:
            self._state_ticks = 0
        self.setCursor(Qt.ClosedHandCursor if state is State.DRAGGED else Qt.OpenHandCursor)

    def _tick(self) -> None:
        areas = desktop.available_areas()   # barato; reflete troca de monitores em tempo real
        if self._state is State.FALLING:
            self._step_falling(areas)
        elif self._state is State.IDLE:
            self._step_idle(areas)
        elif self._state is State.WALKING:
            self._step_walking(areas)
        self._animate()
        if self._state is not State.DRAGGED:
            self._apply_pos()

    # ================================================================ estados
    def _step_falling(self, areas) -> None:
        w, h = self.width(), self.height()
        s = self.settings
        self._vy = min(self._vy + s.gravity, MAX_FALL)
        self._vx *= AIR_FRICTION

        # colisão horizontal (paredes entre/fora dos monitores)
        nx = self._x + self._vx
        edge = nx if self._vx < 0 else nx + w - 1
        if abs(self._vx) > 0.01 and not desktop.contains(areas, edge, self._y + h / 2):
            self._vx = -self._vx * 0.5
            nx = self._x
        self._x = nx

        # teto
        ny = self._y + self._vy
        if self._vy < 0 and not desktop.contains(areas, self._x + w / 2, ny):
            self._vy, ny = 0.0, self._y

        fy = desktop.floor_y(areas, self._x + w / 2, self._y + h, h)
        if fy is None:                                   # caiu num "buraco" entre telas
            self._x, self._y = desktop.clamp_into_desktop(areas, self._x, self._y, w, h)
            return
        if ny >= fy:
            ny = fy
            if self._vy > 6:                             # quique
                self._squash = min(1.0, self._vy / MAX_FALL + 0.3)
                self._vy = -self._vy * 0.35
                self._vx *= 0.6
            else:
                self._vx = self._vy = 0.0
                self._squash = max(self._squash, 0.4)
                self._set_state(State.IDLE)
        self._y = ny

    def _step_idle(self, areas) -> None:
        if self._lost_floor(areas):
            return
        self._state_ticks -= 1
        if self._state_ticks <= 0:
            self._set_state(State.WALKING if random.random() < 0.6 else State.IDLE)

    def _step_walking(self, areas) -> None:
        if self._lost_floor(areas):
            return
        w, h = self.width(), self.height()
        nx = self._x + self._dir * self.settings.walk_speed
        fy = desktop.floor_y(areas, nx + w / 2, self._y + h, h)
        edge = nx if self._dir < 0 else nx + w - 1

        if fy is None or fy < self._y - 2 or not desktop.contains(areas, edge, self._y + h - 1):
            self._dir = -self._dir                       # parede / borda do desktop
        elif fy > self._y + 2:                           # beirada: cai para o piso mais baixo
            self._x = nx
            self._vx = self._dir * self.settings.walk_speed
            self._set_state(State.FALLING)
        else:
            self._x, self._y = nx, fy

        self._state_ticks -= 1
        if self._state_ticks <= 0:
            self._set_state(State.IDLE)

    def _lost_floor(self, areas) -> bool:
        """Se a geometria mudou (monitor removido, taskbar movida), volta a cair."""
        w, h = self.width(), self.height()
        fy = desktop.floor_y(areas, self._x + w / 2, self._y + h, h)
        if fy is None or abs(fy - self._y) > 1:
            self._x, self._y = desktop.clamp_into_desktop(areas, self._x, self._y, w, h)
            self._set_state(State.FALLING)
            return True
        return False

    # ================================================================ animação
    def _animate(self) -> None:
        if self._blink > 0:
            self._blink -= 1
        elif random.random() < 1 / 180:                   # pisca a cada ~3 s em média
            self._blink = 8
        self._squash *= 0.85
        self._walk_phase = self._walk_phase + 0.25 if self._state is State.WALKING else 0.0
        if not self._has_sprite:
            self.update()

    def say(self, message: str, duration_ms: int = 4000) -> None:
        """Faz o pet 'falar' uma mensagem em um balão de fala."""
        self._bubble.say(message, duration_ms=duration_ms)
        self._bubble.update_anchor(round(self._x), round(self._y), self.width())

    def toggle_media_bar(self) -> None:
        """Abre/fecha o painel flutuante de controle de som e música."""
        self._media_bar.toggle_open(round(self._x), round(self._y), self.width(), self.height())

    def _apply_pos(self) -> None:
        rx, ry = round(self._x), round(self._y)
        self.move(rx, ry)
        self._bubble.update_anchor(rx, ry, self.width())
        self._media_bar.update_position(rx, ry, self.width(), self.height())

    # ================================================================ sprite / desenho
    def _load_sprite(self, path: Path | None) -> bool:
        if not path or not path.exists():
            return False
        if path.suffix.lower() == ".gif":
            movie = QMovie(str(path))
            movie.setScaledSize(self.size())
            self._label.setMovie(movie)
            movie.start()
        else:
            self._label.setPixmap(
                QPixmap(str(path)).scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return True

    def paintEvent(self, _event) -> None:
        if self._has_sprite:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        sq = self._squash
        stretch = 0.12 if self._state is State.DRAGGED else 0.0
        bw = w * 0.8 * (1 + sq * 0.25 - stretch)
        bh = h * 0.7 * (1 - sq * 0.25 + stretch)
        bob = abs(math.sin(self._walk_phase)) * 4
        body = QRectF((w - bw) / 2, h - bh - bob - 1, bw, bh)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(59, 130, 246, 240))
        p.drawEllipse(body)

        look = self._dir * w * 0.04 if self._state is State.WALKING else 0.0
        ey = body.top() + bh * 0.4
        r = w * 0.09
        for fx in (0.35, 0.65):
            c = QPointF(body.left() + bw * fx + look, ey)
            if self._blink > 0:
                p.setPen(QPen(QColor(15, 23, 42), max(2.0, w * 0.025), Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
                p.setPen(Qt.NoPen)
            else:
                p.setBrush(QColor("white"))
                p.drawEllipse(c, r, r * (1.15 if self._state is State.DRAGGED else 1))
                p.setBrush(QColor(15, 23, 42))
                p.drawEllipse(QPointF(c.x() + look * 0.5, c.y() + r * 0.15), r * 0.5, r * 0.5)

    # ================================================================ mouse
    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        self._set_state(State.DRAGGED)
        self._vx = self._vy = 0.0
        g = e.globalPosition()
        self._drag_offset = g - QPointF(self._x, self._y)
        self._drag_hist.clear()
        self._drag_hist.append((self._clock.elapsed(), g))

    def mouseMoveEvent(self, e) -> None:
        if self._state is not State.DRAGGED:
            return
        g = e.globalPosition()
        pos = g - self._drag_offset
        self._x, self._y = pos.x(), pos.y()
        self._apply_pos()
        self._drag_hist.append((self._clock.elapsed(), g))

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.LeftButton or self._state is not State.DRAGGED:
            return
        # velocidade de arremesso (px/tick) a partir das últimas amostras do mouse
        if len(self._drag_hist) >= 2:
            (t0, p0), (t1, p1) = self._drag_hist[0], self._drag_hist[-1]
            dt = max(1, t1 - t0) / TICK_MS
            if self._clock.elapsed() - t1 < 80:            # só arremessa se ainda estava em movimento
                self._vx = max(-MAX_THROW, min(MAX_THROW, (p1.x() - p0.x()) / dt))
                self._vy = max(-MAX_THROW, min(MAX_THROW, (p1.y() - p0.y()) / dt))
        areas = desktop.available_areas()
        self._x, self._y = desktop.clamp_into_desktop(areas, self._x, self._y, self.width(), self.height())
        self._set_state(State.FALLING)

    def wheelEvent(self, e) -> None:
        """Controla o volume do sistema ao rolar a roda do mouse sobre o pet."""
        delta = e.angleDelta().y()
        if delta > 0:
            self._media.change_volume(+5)
        elif delta < 0:
            self._media.change_volume(-5)
        e.accept()

    def mouseDoubleClickEvent(self, e) -> None:
        """Duplo clique no pet abre/fecha a barra visual de mídia e volume."""
        if e.button() == Qt.LeftButton:
            self.toggle_media_bar()
            e.accept()

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        menu.addAction("🎛️ Painel de Mídia", self.toggle_media_bar)
        media_menu = menu.addMenu("🎵 Mídia Rápida")
        media_menu.addAction("Play / Pause", self._media.play_pause)
        media_menu.addAction("Próxima Faixa (Next)", self._media.next_track)
        media_menu.addAction("Faixa Anterior (Prev)", self._media.previous_track)
        media_menu.addSeparator()
        vol_info = f"Volume: {self._media.get_volume()}%" + (" (Mudo)" if self._media.is_muted() else "")
        info_action = media_menu.addAction(vol_info)
        info_action.setEnabled(False)
        media_menu.addAction("Mutar / Desmutar", self._media.toggle_mute)
        menu.addSeparator()
        menu.addAction("Sair", self.quit_requested.emit)
        menu.exec(e.globalPos())
