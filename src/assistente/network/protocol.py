"""Protocolo JSON trocado entre o Hub e os nós da Cecília."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Union

MAX_MESSAGE_BYTES = 256_000
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ProtocolError(ValueError):
    """Mensagem inválida ou malformada."""


@dataclass
class NodeRegister:
    node_id: str
    hostname: str
    capabilities: list[str] = field(default_factory=list)
    type: str = "NODE_REGISTER"


@dataclass
class Heartbeat:
    node_id: str
    type: str = "HEARTBEAT"


@dataclass
class CommandDispatch:
    request_id: str
    command: str
    args: dict[str, Any] = field(default_factory=dict)
    type: str = "DISPATCH_COMMAND"


@dataclass
class CommandResult:
    request_id: str
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)
    type: str = "COMMAND_RESULT"


@dataclass
class BroadcastAlert:
    text: str
    type: str = "BROADCAST_ALERT"


Message = Union[NodeRegister, Heartbeat, CommandDispatch, CommandResult, BroadcastAlert]

_TYPES: dict[str, type] = {
    "NODE_REGISTER": NodeRegister,
    "HEARTBEAT": Heartbeat,
    "DISPATCH_COMMAND": CommandDispatch,
    "COMMAND_RESULT": CommandResult,
    "BROADCAST_ALERT": BroadcastAlert,
}


def valid_node_id(node_id: str) -> bool:
    return isinstance(node_id, str) and bool(_NODE_ID_RE.match(node_id))


def encode(msg: Message) -> str:
    return json.dumps(asdict(msg), ensure_ascii=False)


def decode(raw: str | bytes) -> Message:
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("mensagem grande demais")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        raise ProtocolError(f"JSON inválido: {e}") from e
    if not isinstance(data, dict):
        raise ProtocolError("mensagem deve ser um objeto JSON")
    cls = _TYPES.get(data.get("type"))
    if cls is None:
        raise ProtocolError(f"tipo desconhecido: {data.get('type')!r}")
    try:
        msg = cls(**data)
    except TypeError as e:
        raise ProtocolError(f"campos inválidos: {e}") from e
    node_id = getattr(msg, "node_id", None)
    if node_id is not None and not valid_node_id(node_id):
        raise ProtocolError(f"node_id inválido: {node_id!r}")
    if isinstance(msg, CommandDispatch) and not isinstance(msg.args, dict):
        raise ProtocolError("args deve ser objeto")
    if isinstance(msg, CommandResult) and not isinstance(msg.payload, dict):
        raise ProtocolError("payload deve ser objeto")
    return msg
