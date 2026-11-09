"""Ponto de entrada do Jarvis / Assistente Pessoal Desktop."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from assistente.ai.brain import AssistantBrain
from assistente.config import Settings
from assistente.media.controller import MediaController
from assistente.tasks.scheduler import TaskScheduler
from assistente.telegram.bot import TelegramBridge
from assistente.ui.pet_window import PetWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = Settings()

    # 1. UI do Pet
    pet = PetWindow(settings)
    pet.quit_requested.connect(app.quit)

    # 2. Agendador de Lembretes & Alarmes
    def on_reminder(item):
        pet.say(f"⏰ Lembrete: {item.title}", duration_ms=6000)

    scheduler = TaskScheduler(on_trigger=on_reminder)

    # 3. Cérebro IA (Gemini + ferramentas do sistema)
    media = pet._media
    brain = AssistantBrain(settings=settings, media=media, scheduler=scheduler)

    # 4. Ponte Telegram (Comandos remotos mobile)
    def on_telegram_ping(text: str):
        pet.say(text, duration_ms=3000)

    telegram_bridge = TelegramBridge(
        settings=settings,
        brain=brain,
        on_notify_desktop=on_telegram_ping,
    )
    telegram_bridge.start()

    # 5. Inicia o Pet na tela
    pet.start()
    pet.say("Jarvis pronto!", duration_ms=2500)

    exit_code = app.exec()
    scheduler.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
