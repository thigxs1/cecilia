"""Widget de balão de fala flutuante acoplado ao Pet."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SpeechBubble(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._text_label = QLabel(self)
        self._text_label.setWordWrap(True)
        self._text_label.setAlignment(Qt.AlignCenter)
        self._text_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._text_label.setStyleSheet("color: #0f172a; background: transparent; padding: 4px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 18)
        layout.addWidget(self._text_label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def say(self, message: str, duration_ms: int = 4000) -> None:
        self._text_label.setText(message)
        self.adjustSize()
        self._hide_timer.stop()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms)
        self.show()

    def update_anchor(self, pet_x: int, pet_y: int, pet_width: int) -> None:
        """Posiciona o balão centralizado acima da cabeça do pet."""
        if not self.isVisible():
            return
        w = max(140, self.sizeHint().width())
        h = max(45, self.sizeHint().height())
        self.resize(w, h)

        target_x = round(pet_x + (pet_width - w) / 2)
        target_y = round(pet_y - h + 6)
        self.move(target_x, target_y)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        bubble_rect_h = h - 10

        # Balão arredondado moderno
        path = QPainterPath()
        path.addRoundedRect(1, 1, w - 2, bubble_rect_h, 12, 12)

        # Ponta do balão apontando para o pet
        cx = w / 2
        path.moveTo(cx - 7, bubble_rect_h)
        path.lineTo(cx, h - 1)
        path.lineTo(cx + 7, bubble_rect_h)

        # Preenchimento branco suave com borda sutil
        p.setPen(QPen(QColor(148, 163, 184, 200), 1.5))
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawPath(path)

