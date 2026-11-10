"""Hub WebSocket central da Cecília.

Nós se conectam com `Authorization: Bearer <CECILIA_HUB_SECRET>` e se registram
(NODE_REGISTER). O Hub despacha comandos (DISPATCH_COMMAND) e aguarda o
COMMAND_RESULT correlacionado por `request_id`.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

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
)

log = logging.getLogger(__name__)
REGISTER_TIMEOUT = 10.0


class NodeNotFound(LookupError):
    pass


@dataclass
class NodeInfo:
    node_id: str
    hostname: str
    capabilities: list[str]
    remote: str
    connected_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    ws: ServerConnection | None = field(default=None, repr=False)


class CeciliaHub:
    def __init__(self, secret: str, host: str = "0.0.0.0", port: int = 8765) -> None:
        if not secret:
            raise ValueError("CECILIA_HUB_SECRET é obrigatório para expor o Hub")
        self._secret = secret.encode()
        self.host = host
        self._port = port
        self._server: Server | None = None
        self._nodes: dict[str, NodeInfo] = {}
        self._pending: dict[str, asyncio.Future[CommandResult]] = {}

    # ---------- ciclo de vida ----------
    @property
    def port(self) -> int:
        if self._server is None:
            return self._port
        return self._server.sockets[0].getsockname()[1]

    async def start(self) -> None:
        self._server = await serve(
            self._handle,
            self.host,
            self._port,
            process_request=self._authenticate,
            max_size=MAX_MESSAGE_BYTES,
            ping_interval=20,
            ping_timeout=20,
        )
        log.info("Hub Cecília ouvindo em %s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(ConnectionError("Hub encerrado"))
        self._pending.clear()
        self._nodes.clear()

    # ---------- API pública ----------
    def nodes(self) -> dict[str, NodeInfo]:
        return dict(self._nodes)

    async def dispatch(
        self, node_id: str, command: str, args: dict[str, Any] | None = None, timeout: float = 30.0
    ) -> CommandResult:
        node = self._nodes.get(node_id)
        if node is None or node.ws is None:
            raise NodeNotFound(f"Nó '{node_id}' não está conectado")
        req = CommandDispatch(request_id=uuid.uuid4().hex, command=command, args=args or {})
        fut: asyncio.Future[CommandResult] = asyncio.get_running_loop().create_future()
        self._pending[req.request_id] = fut
        try:
            await node.ws.send(encode(req))
            return await asyncio.wait_for(fut, timeout)
        except ConnectionClosed as e:
            raise NodeNotFound(f"Nó '{node_id}' desconectou") from e
        finally:
            self._pending.pop(req.request_id, None)

    async def broadcast(self, text: str) -> None:
        raw = encode(BroadcastAlert(text=text))
        for node in list(self._nodes.values()):
            try:
                await node.ws.send(raw)
            except ConnectionClosed:
                pass

    # ---------- internos ----------
    def _authenticate(self, connection: ServerConnection, request):
        header = request.headers.get("Authorization", "")
        token = header[7:].encode() if header.startswith("Bearer ") else b""
        if not hmac.compare_digest(token, self._secret):
            log.warning("Conexão recusada (token inválido) de %s", connection.remote_address)
            return connection.respond(HTTPStatus.UNAUTHORIZED, "Unauthorized\n")
        return None

    async def _handle(self, ws: ServerConnection) -> None:
        try:
            first = decode(await asyncio.wait_for(ws.recv(), REGISTER_TIMEOUT))
        except (ProtocolError, asyncio.TimeoutError, ConnectionClosed) as e:
            await ws.close(4002, f"registro esperado: {e}"[:120])
            return
        if not isinstance(first, NodeRegister):
            await ws.close(4002, "primeira mensagem deve ser NODE_REGISTER")
            return

        old = self._nodes.get(first.node_id)
        if old and old.ws is not None:
            await old.ws.close(4009, "substituído por nova conexão")
        info = NodeInfo(
            node_id=first.node_id,
            hostname=first.hostname,
            capabilities=list(first.capabilities),
            remote=str(ws.remote_address),
            ws=ws,
        )
        self._nodes[first.node_id] = info
        log.info("Nó conectado: %s (%s)", info.node_id, info.remote)

        try:
            async for raw in ws:
                try:
                    msg = decode(raw)
                except ProtocolError as e:
                    log.warning("Mensagem inválida de %s: %s", info.node_id, e)
                    continue
                info.last_seen = time.time()
                if isinstance(msg, CommandResult):
                    fut = self._pending.get(msg.request_id)
                    if fut and not fut.done():
                        fut.set_result(msg)
                elif isinstance(msg, Heartbeat):
                    pass
        except ConnectionClosed:
            pass
        finally:
            if self._nodes.get(info.node_id) is info:
                del self._nodes[info.node_id]
            log.info("Nó desconectado: %s", info.node_id)


class ThreadedHub:
    """Executa o CeciliaHub em uma thread com loop próprio (para apps Qt/síncronos)."""

    def __init__(self, hub: CeciliaHub) -> None:
        self.hub = hub
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="cecilia-hub")

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(5)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.hub.start())
        self._ready.set()
        self._loop.run_forever()

    def stop(self) -> None:
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.hub.stop(), self._loop).result(5)
            self._loop.call_soon_threadsafe(self._loop.stop)

    def nodes(self) -> dict[str, NodeInfo]:
        return self.hub.nodes()

    def dispatch_sync(self, node_id: str, command: str, args: dict[str, Any], timeout: float = 30.0) -> CommandResult:
        fut = asyncio.run_coroutine_threadsafe(self.hub.dispatch(node_id, command, args, timeout), self._loop)
        return fut.result(timeout + 2)

    async def dispatch(self, node_id: str, command: str, args: dict[str, Any], timeout: float = 30.0) -> CommandResult:
        """Versão awaitable chamada de OUTRO loop (ex.: Telegram)."""
        fut = asyncio.run_coroutine_threadsafe(self.hub.dispatch(node_id, command, args, timeout), self._loop)
        return await asyncio.wrap_future(fut)

    def broadcast_sync(self, text: str) -> None:
        asyncio.run_coroutine_threadsafe(self.hub.broadcast(text), self._loop)

