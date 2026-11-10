"""Cliente de nó da Cecília: conecta ao Hub, registra-se e executa comandos locais."""
from __future__ import annotations

import asyncio
import logging
import random
import socket
import threading
from typing import Any, Callable

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from .protocol import (
    MAX_MESSAGE_BYTES,
    BroadcastAlert,
    CommandDispatch,
    CommandResult,
    Heartbeat,
    NodeRegister,
    ProtocolError,
    decode,
    encode,
    valid_node_id,
)

log = logging.getLogger(__name__)

CommandHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


class CeciliaNodeClient:
    def __init__(
        self,
        url: str,
        secret: str,
        node_id: str,
        handler: CommandHandler,
        capabilities: list[str] | None = None,
        on_alert: Callable[[str], None] | None = None,
        heartbeat_interval: float = 15.0,
        command_timeout: float = 60.0,
        max_backoff: float = 60.0,
    ) -> None:
        if not valid_node_id(node_id):
            raise ValueError(f"node_id inválido: {node_id!r} (use letras, números, _ . -)")
        self.url = url
        self._secret = secret
        self.node_id = node_id
        self._handler = handler
        self.capabilities = capabilities or ["prompt"]
        self._on_alert = on_alert
        self._hb = heartbeat_interval
        self._cmd_timeout = command_timeout
        self._max_backoff = max_backoff
        self._stopping = False
        self._ws: ClientConnection | None = None
        self.connected = False

    async def run(self) -> None:
        backoff = 0.5
        while not self._stopping:
            try:
                async with connect(
                    self.url,
                    additional_headers={"Authorization": f"Bearer {self._secret}"},
                    max_size=MAX_MESSAGE_BYTES,
                    open_timeout=10,
                ) as ws:
                    self._ws = ws
                    await ws.send(encode(NodeRegister(self.node_id, socket.gethostname(), self.capabilities)))
                    self.connected = True
                    backoff = 0.5
                    log.info("Conectado ao Hub %s como '%s'", self.url, self.node_id)
                    await self._session(ws)
            except InvalidStatus as e:
                log.error("Hub recusou conexão (HTTP %s) — verifique CECILIA_HUB_SECRET", e.response.status_code)
            except (OSError, ConnectionClosed, asyncio.TimeoutError) as e:
                log.warning("Conexão com Hub perdida: %s", e)
            finally:
                self.connected = False
                self._ws = None
            if self._stopping:
                break
            await asyncio.sleep(backoff * (0.8 + random.random() * 0.4))
            backoff = min(backoff * 2, self._max_backoff)

    async def stop(self) -> None:
        self._stopping = True
        if self._ws is not None:
            await self._ws.close()

    async def _session(self, ws: ClientConnection) -> None:
        hb = asyncio.create_task(self._heartbeat(ws))
        tasks: set[asyncio.Task] = set()
        try:
            async for raw in ws:
                try:
                    msg = decode(raw)
                except ProtocolError as e:
                    log.warning("Mensagem inválida do Hub: %s", e)
                    continue
                if isinstance(msg, CommandDispatch):
                    t = asyncio.create_task(self._execute(ws, msg))
                    tasks.add(t)
                    t.add_done_callback(tasks.discard)
                elif isinstance(msg, BroadcastAlert) and self._on_alert:
                    try:
                        self._on_alert(msg.text)
                    except Exception:
                        log.exception("Erro no callback de alerta")
        finally:
            hb.cancel()

    async def _heartbeat(self, ws: ClientConnection) -> None:
        while True:
            await asyncio.sleep(self._hb)
            await ws.send(encode(Heartbeat(self.node_id)))

    async def _execute(self, ws: ClientConnection, msg: CommandDispatch) -> None:
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(self._handler, msg.command, msg.args), self._cmd_timeout
            )
            result = CommandResult(msg.request_id, True, payload if isinstance(payload, dict) else {"message": str(payload)})
        except asyncio.TimeoutError:
            result = CommandResult(msg.request_id, False, {"error": f"Timeout após {self._cmd_timeout}s"})
        except Exception as e:  # noqa: BLE001 — erro devolvido ao Hub
            result = CommandResult(msg.request_id, False, {"error": f"{type(e).__name__}: {e}"})
        try:
            await ws.send(encode(result))
        except ConnectionClosed:
            log.warning("Resultado %s perdido (conexão fechada)", msg.request_id)


class ThreadedNodeClient:
    """Roda o CeciliaNodeClient numa thread daemon (para o app Qt)."""

    def __init__(self, client: CeciliaNodeClient) -> None:
        self.client = client
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="cecilia-node")

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.client.run())

    def stop(self) -> None:
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.client.stop(), self._loop)

