"""Servidor MCP local "assistente-os" — Mídia e Volume do Windows.

Execução: PYTHONPATH=src python -m mcp_servers.os_server  (transporte stdio)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from assistente.media.controller import MediaController

mcp = FastMCP("assistente-os")
media = MediaController()


@mcp.tool()
def media_play_pause() -> str:
    """Alterna Play/Pause do player de mídia ativo no Windows."""
    media.play_pause()
    return "Comando Play/Pause enviado com sucesso."


@mcp.tool()
def media_next() -> str:
    """Avança para a próxima faixa de áudio/mídia."""
    media.next_track()
    return "Comando Próxima Faixa enviado com sucesso."


@mcp.tool()
def media_previous() -> str:
    """Retorna para a faixa anterior."""
    media.previous_track()
    return "Comando Faixa Anterior enviado com sucesso."


@mcp.tool()
def media_stop() -> str:
    """Para a reprodução de mídia."""
    media.stop()
    return "Comando Parar enviado com sucesso."


@mcp.tool()
def get_volume() -> dict:
    """Obtém o volume mestre atual (0 a 100) e o estado de mudo."""
    return {"volume": media.get_volume(), "muted": media.is_muted()}


@mcp.tool()
def set_volume(percent: int) -> dict:
    """Define o volume mestre do sistema (0 a 100)."""
    val = media.set_volume(percent)
    return {"volume": val, "status": "sucesso"}


@mcp.tool()
def change_volume(delta: int) -> dict:
    """Aumenta ou diminui o volume relativo em passos (ex: +5, -10)."""
    val = media.change_volume(delta)
    return {"volume": val, "status": "sucesso"}


@mcp.tool()
def toggle_mute() -> dict:
    """Alterna o estado de mudo do sistema."""
    muted = media.toggle_mute()
    return {"muted": muted}


if __name__ == "__main__":
    mcp.run()
