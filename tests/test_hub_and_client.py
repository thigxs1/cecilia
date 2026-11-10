import asyncio

import pytest
import websockets

from assistente.network.client import CeciliaNodeClient
from assistente.network.protocol import NodeRegister, encode
from assistente.network.server import CeciliaHub, NodeNotFound

SECRET = "s3cret-token"


@pytest.fixture
async def hub():
    h = CeciliaHub(secret=SECRET, host="127.0.0.1", port=0)
    await h.start()
    yield h
    await h.stop()


def url(h):
    return f"ws://127.0.0.1:{h.port}/ws"


async def wait_for(cond, timeout=3.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("timeout esperando condição")
        await asyncio.sleep(0.02)


async def test_rejects_missing_or_bad_token(hub):
    for headers in ({}, {"Authorization": "Bearer errado"}):
        with pytest.raises(websockets.exceptions.InvalidStatus) as ei:
            async with websockets.connect(url(hub), additional_headers=headers):
                pass
        assert ei.value.response.status_code == 401
    assert hub.nodes() == {}


async def test_register_and_list(hub):
    async with websockets.connect(url(hub), additional_headers={"Authorization": f"Bearer {SECRET}"}) as ws:
        await ws.send(encode(NodeRegister(node_id="notebook", hostname="NB", capabilities=["prompt"])))
        await wait_for(lambda: "notebook" in hub.nodes())
        assert hub.nodes()["notebook"].hostname == "NB"
    await wait_for(lambda: "notebook" not in hub.nodes())


async def test_first_message_must_be_register(hub):
    async with websockets.connect(url(hub), additional_headers={"Authorization": f"Bearer {SECRET}"}) as ws:
        await ws.send("lixo")
        with pytest.raises(websockets.exceptions.ConnectionClosed):
            await asyncio.wait_for(ws.recv(), 2)


async def test_dispatch_to_unknown_node(hub):
    with pytest.raises(NodeNotFound):
        await hub.dispatch("fantasma", "prompt", {"text": "oi"})


async def test_end_to_end_with_client(hub):
    calls = []

    def handler(command, args):
        calls.append((command, args))
        return {"message": f"eco: {args['text']}"}

    client = CeciliaNodeClient(url(hub), SECRET, "desktop", handler, capabilities=["prompt"])
    task = asyncio.create_task(client.run())
    try:
        await wait_for(lambda: "desktop" in hub.nodes())
        res = await hub.dispatch("desktop", "prompt", {"text": "oi"}, timeout=3)
        assert res.ok and res.payload["message"] == "eco: oi"
        assert calls == [("prompt", {"text": "oi"})]
    finally:
        await client.stop()
        task.cancel()


async def test_handler_exception_returns_error(hub):
    def handler(command, args):
        raise RuntimeError("boom")

    client = CeciliaNodeClient(url(hub), SECRET, "nb", handler)
    task = asyncio.create_task(client.run())
    try:
        await wait_for(lambda: "nb" in hub.nodes())
        res = await hub.dispatch("nb", "prompt", {}, timeout=3)
        assert not res.ok and "boom" in res.payload["error"]
    finally:
        await client.stop()
        task.cancel()


async def test_handler_timeout_does_not_hang(hub):
    import time

    def handler(command, args):
        time.sleep(2)
        return {}

    client = CeciliaNodeClient(url(hub), SECRET, "slow", handler, command_timeout=0.3)
    task = asyncio.create_task(client.run())
    try:
        await wait_for(lambda: "slow" in hub.nodes())
        res = await hub.dispatch("slow", "prompt", {}, timeout=3)
        assert not res.ok and "timeout" in res.payload["error"].lower()
    finally:
        await client.stop()
        task.cancel()


async def test_client_reconnects_after_hub_restart():
    h = CeciliaHub(secret=SECRET, host="127.0.0.1", port=0)
    await h.start()
    port = h.port
    client = CeciliaNodeClient(f"ws://127.0.0.1:{port}/ws", SECRET, "pc", lambda c, a: {}, max_backoff=0.3)
    task = asyncio.create_task(client.run())
    try:
        await wait_for(lambda: "pc" in h.nodes())
        await h.stop()
        h2 = CeciliaHub(secret=SECRET, host="127.0.0.1", port=port)
        await h2.start()
        await wait_for(lambda: "pc" in h2.nodes(), timeout=5)
        await h2.stop()
    finally:
        await client.stop()
        task.cancel()


async def test_broadcast_reaches_clients(hub):
    got = []
    client = CeciliaNodeClient(url(hub), SECRET, "a", lambda c, a: {}, on_alert=got.append)
    task = asyncio.create_task(client.run())
    try:
        await wait_for(lambda: "a" in hub.nodes())
        await hub.broadcast("alarme!")
        await wait_for(lambda: got == ["alarme!"])
    finally:
        await client.stop()
        task.cancel()

