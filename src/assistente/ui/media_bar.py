"""Widget de controle de mídia flutuante (Dock moderna com botões táteis e slider de volume)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from assistente.media.controller import MediaController


class MediaBar(QWidget):
    action_triggered = Signal(str)

    def __init__(self, media: MediaController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.media = media

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(230)

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setInterval(4500)
        self._auto_close_timer.timeout.connect(self.hide)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Botões de controle de mídia
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.12);
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(59, 130, 246, 0.6);
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: rgba(37, 99, 235, 0.8);
            }
        """

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_prev.setToolTip("Faixa Anterior")
        self.btn_prev.clicked.connect(self._on_prev)

        self.btn_play = QPushButton("⏯")
        self.btn_play.setStyleSheet(btn_style)
        self.btn_play.setToolTip("Play / Pause")
        self.btn_play.clicked.connect(self._on_play)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setStyleSheet(btn_style)
        self.btn_next.setToolTip("Próxima Faixa")
        self.btn_next.clicked.connect(self._on_next)

        btn_layout.addWidget(self.btn_prev)
        btn_layout.addWidget(self.btn_play)
        btn_layout.addWidget(self.btn_next)
        main_layout.addLayout(btn_layout)

        # Barra de Volume + Ícone
        vol_layout = QHBoxLayout()
        vol_layout.setSpacing(6)

        self.lbl_vol_icon = QLabel("🔊")
        self.lbl_vol_icon.setStyleSheet("color: #cbd5e1; font-size: 13px; background: transparent;")

        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(self.media.get_volume())
        self.slider_vol.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 5px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
        """)
        self.slider_vol.valueChanged.connect(self._on_volume_slider)

        self.lbl_vol_num = QLabel(f"{self.media.get_volume()}%")
        self.lbl_vol_num.setFixedWidth(34)
        self.lbl_vol_num.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; font-weight: bold;")

        vol_layout.addWidget(self.lbl_vol_icon)
        vol_layout.addWidget(self.slider_vol)
        vol_layout.addWidget(self.lbl_vol_num)
        main_layout.addLayout(vol_layout)

    def _on_play(self) -> None:
        self.media.play_pause()
        self.action_triggered.emit("⏯ Play/Pause")
        self._reset_timer()

    def _on_next(self) -> None:
        self.media.next_track()
        self.action_triggered.emit("⏭ Próxima")
        self._reset_timer()

    def _on_prev(self) -> None:
        self.media.previous_track()
        self.action_triggered.emit("⏮ Anterior")
        self._reset_timer()

    def _on_volume_slider(self, val: int) -> None:
        self.media.set_volume(val)
        self.lbl_vol_num.setText(f"{val}%")
        self.lbl_vol_icon.setText("🔇" if val == 0 else "🔉" if val < 50 else "🔊")
        self._reset_timer()

    def refresh_volume(self) -> None:
        vol = self.media.get_volume()
        self.slider_vol.blockSignals(True)
        self.slider_vol.setValue(vol)
        self.slider_vol.blockSignals(False)
        self.lbl_vol_num.setText(f"{vol}%")
        self.lbl_vol_icon.setText("🔇" if (vol == 0 or self.media.is_muted()) else "🔊")

    def toggle_open(self, pet_x: int, pet_y: int, pet_width: int, pet_height: int) -> None:
        if self.isVisible():
            self.hide()
            self._auto_close_timer.stop()
        else:
            self.refresh_volume()
            self.adjustSize()
            # Posiciona flutuando logo acima do pet
            w = self.width()
            h = self.height()
            target_x = round(pet_x + (pet_width - w) / 2)
            target_y = round(pet_y - h - 10)
            self.move(target_x, target_y)
            self.show()
            self._reset_timer()

    def update_position(self, pet_x: int, pet_y: int, pet_width: int, pet_height: int) -> None:
        if self.isVisible():
            target_x = round(pet_x + (pet_width - self.width()) / 2)
            target_y = round(pet_y - self.height() - 10)
            self.move(target_x, target_y)

    def _reset_timer(self) -> None:
        self._auto_close_timer.start()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Fundo estilo Dark Glassmorphism com borda moderna
        path = QPainterPath()
        path.addRoundedRect(1, 1, self.width() - 2, self.height() - 2, 14, 14)
        p.setPen(QColor(255, 255, 255, 35))
        p.setBrush(QColor(15, 23, 42, 235))  # Slate escuro translúcido
        p.drawPath(path)

