"""Roteamento de comandos entre Telegram/Hub e nós."""
from __future__ import annotations

import re
import socket
from typing import Any, Callable

from .client import CommandHandler

_TARGET_RE = re.compile(r"^\s*@([A-Za-z0-9_.-]{1,64})(?:\s+(.*))?$", re.DOTALL)
ALLOWED_COMMANDS = ("prompt", "ping")


def parse_target(text: str) -> tuple[str | None, str]:
    """'@notebook pause' -> ('notebook', 'pause'); sem prefixo -> (None, texto)."""
    m = _TARGET_RE.match(text)
    if not m:
        return None, text.strip()
    return m.group(1), (m.group(2) or "").strip()


def make_node_handler(brain: Any, notify: Callable[[str], None] | None = None) -> CommandHandler:
    """Cria o handler que um nó usa para executar comandos vindos do Hub.

    Apenas comandos da lista branca são aceitos — o texto livre passa pelo
    cérebro, que só pode acionar as ferramentas declaradas.
    """

    def handler(command: str, args: dict[str, Any]) -> dict[str, Any]:
        if command == "ping":
            return {"message": "pong", "hostname": socket.gethostname()}
        if command == "prompt":
            text = args.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("'text' deve ser string não vazia")
            if notify:
                notify(f"🌐 Remoto: {text[:28]}")
            return brain.process_command(text[:4000])
        raise ValueError(f"Comando não permitido: {command!r}")

    return handler

