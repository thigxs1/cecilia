"""Integração: TelegramBridge (modo hub) -> ThreadedHub -> CeciliaNodeClient -> brain remoto."""
import asyncio
import types

from assistente.network.client import CeciliaNodeClient, ThreadedNodeClient
from assistente.network.routing import make_node_handler
from assistente.network.server import CeciliaHub, ThreadedHub
from assistente.telegram.bot import TelegramBridge

SECRET = "x" * 32


class FakeBrain:
    def __init__(self, name):
        self.name = name

    def process_command(self, text):
        return {"message": f"{self.name}:{text}"}


def make_update(text, chat_id=42):
    replies = []

    async def reply_text(msg, **kw):
        replies.append(msg)

    upd = types.SimpleNamespace(
        effective_chat=types.SimpleNamespace(id=chat_id),
        message=types.SimpleNamespace(text=text, reply_text=reply_text),
    )
    return upd, replies


def settings():
    return types.SimpleNamespace(telegram_allowed_chat_id="42", node_id="hubpc", telegram_bot_token="")


async def wait_for(cond, timeout=5.0):
    for _ in range(int(timeout / 0.05)):
        if cond():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("timeout")


async def test_telegram_routes_to_remote_node_and_local():
    hub = ThreadedHub(CeciliaHub(SECRET, "127.0.0.1", 0))
    hub.start()
    node = ThreadedNodeClient(CeciliaNodeClient(
        f"ws://127.0.0.1:{hub.hub.port}/ws", SECRET, "notebook", make_node_handler(FakeBrain("NB"))
    ))
    node.start()
    try:
        await wait_for(lambda: "notebook" in hub.nodes())
        bridge = TelegramBridge(settings(), FakeBrain("HUB"), hub=hub)

        upd, replies = make_update("@notebook pause")
        await bridge._on_message(upd, None)
        assert replies == ["[notebook] NB:pause"]

        upd, replies = make_update("pause")
        await bridge._on_message(upd, None)
        assert replies == ["HUB:pause"]

        upd, replies = make_update("@fantasma oi")
        await bridge._on_message(upd, None)
        assert "offline" in replies[0] and "notebook" in replies[0]
    finally:
        node.stop()
        hub.stop()


async def test_unauthorized_chat_blocked():
    bridge = TelegramBridge(settings(), FakeBrain("HUB"))
    upd, replies = make_update("@notebook pause", chat_id=999)
    await bridge._on_message(upd, None)
    assert "não autorizado" in replies[0]

