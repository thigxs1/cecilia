import pytest

from assistente.network.protocol import (
    CommandDispatch,
    CommandResult,
    Heartbeat,
    NodeRegister,
    ProtocolError,
    decode,
    encode,
)


def test_roundtrip_register():
    msg = NodeRegister(node_id="desktop", hostname="PC", capabilities=["prompt"])
    out = decode(encode(msg))
    assert out == msg


def test_roundtrip_dispatch_and_result():
    d = CommandDispatch(request_id="r1", command="prompt", args={"text": "oi"})
    assert decode(encode(d)) == d
    r = CommandResult(request_id="r1", ok=True, payload={"message": "ok"})
    assert decode(encode(r)) == r


def test_heartbeat():
    assert isinstance(decode(encode(Heartbeat(node_id="x"))), Heartbeat)


@pytest.mark.parametrize("raw", ["not json", "[]", '{"type":"WHAT"}', '{"type":"NODE_REGISTER"}'])
def test_invalid_messages_raise(raw):
    with pytest.raises(ProtocolError):
        decode(raw)


def test_node_id_sanitized():
    with pytest.raises(ProtocolError):
        decode(encode(NodeRegister(node_id="bad id!", hostname="h")))


def test_oversized_message_rejected():
    with pytest.raises(ProtocolError):
        decode("x" * 300_000)

