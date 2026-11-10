"""Ponto de entrada do Jarvis / Assistente Pessoal Desktop.

Modos (CLI `--mode` ou env CECILIA_MODE):
  standalone  - comportamento original, tudo local.
  hub         - local + Telegram + Hub WebSocket aceitando outras máquinas.
  node        - local + conecta a um Hub remoto (sem Telegram próprio).
"""
from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from assistente.ai.brain import AssistantBrain
from assistente.config import Settings
from assistente.media.controller import MediaController
from assistente.tasks.scheduler import TaskScheduler
from assistente.telegram.bot import TelegramBridge
from assistente.ui.pet_window import PetWindow


def parse_args(argv: list[str], settings: Settings) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="assistente", description="Cecília - assistente pessoal")
    p.add_argument("--mode", choices=["standalone", "hub", "node"], default=settings.cecilia_mode)
    p.add_argument("--node-id", default=settings.node_id)
    p.add_argument("--hub-url", default=settings.hub_url)
    p.add_argument("--port", type=int, default=settings.hub_port)
    return p.parse_args(argv)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = Settings()
    args = parse_args(sys.argv[1:], settings)
    settings.cecilia_mode, settings.node_id, settings.hub_url, settings.hub_port = (
        args.mode, args.node_id, args.hub_url, args.port,
    )

    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)

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

    def notify(text: str):
        pet.say(text, duration_ms=3000)

    # 4. Rede multi-nós
    hub = node = None
    if settings.cecilia_mode == "hub":
        from assistente.network.server import CeciliaHub, ThreadedHub

        hub = ThreadedHub(CeciliaHub(settings.hub_secret, settings.hub_host, settings.hub_port))
        hub.start()
    elif settings.cecilia_mode == "node":
        from assistente.network.client import CeciliaNodeClient, ThreadedNodeClient
        from assistente.network.routing import make_node_handler

        if not settings.hub_url or not settings.hub_secret:
            print("Modo node requer CECILIA_HUB_URL e CECILIA_HUB_SECRET", file=sys.stderr)
            return 2
        node = ThreadedNodeClient(CeciliaNodeClient(
            settings.hub_url, settings.hub_secret, settings.node_id,
            make_node_handler(brain, notify), on_alert=notify,
        ))
        node.start()

    # 5. Ponte Telegram (somente standalone/hub — evita dois bots no mesmo token)
    if settings.cecilia_mode != "node":
        TelegramBridge(settings=settings, brain=brain, on_notify_desktop=notify, hub=hub).start()

    # 6. Inicia o Pet na tela
    pet.start()
    pet.say(f"Cecília pronta! ({settings.cecilia_mode}: {settings.node_id})", duration_ms=2500)

    exit_code = app.exec()
    if hub:
        hub.stop()
    if node:
        node.stop()
    scheduler.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
