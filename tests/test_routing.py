import pytest

from assistente.network.routing import make_node_handler, parse_target


@pytest.mark.parametrize(
    "text,expected",
    [
        ("@notebook pause a música", ("notebook", "pause a música")),
        ("  @desktop-01   volume 30", ("desktop-01", "volume 30")),
        ("pause", (None, "pause")),
        ("email@exemplo.com", (None, "email@exemplo.com")),
        ("@notebook", ("notebook", "")),
    ],
)
def test_parse_target(text, expected):
    assert parse_target(text) == expected


class FakeBrain:
    def __init__(self):
        self.seen = []

    def process_command(self, text):
        self.seen.append(text)
        return {"action": "reply", "message": f"ok:{text}"}


def test_node_handler_prompt_and_notify():
    brain, notes = FakeBrain(), []
    h = make_node_handler(brain, notes.append)
    assert h("prompt", {"text": "status"})["message"] == "ok:status"
    assert brain.seen == ["status"] and notes


def test_node_handler_ping_and_unknown():
    h = make_node_handler(FakeBrain())
    assert h("ping", {})["message"] == "pong"
    with pytest.raises(ValueError):
        h("rm -rf", {})
    with pytest.raises(ValueError):
        h("prompt", {"text": 123})

