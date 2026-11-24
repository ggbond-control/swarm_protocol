import os

import pytest
from swarm_protocol.contracts import (
    decode,
    normalize_mission,
    envelope,
    public_mission,
    validate_envelope,
    validate_storage,
)
from swarm_protocol.storage import DurableFile, ProcessLock


def test_private_integrity_and_exclusive_lock(tmp_path):
    state = DurableFile(tmp_path / "state.json")
    state.save({"term": 3})
    assert state.load() == {"term": 3}
    assert os.stat(state.path).st_mode & 0o777 == 0o600
    lock = ProcessLock(tmp_path / "lock")
    with pytest.raises(RuntimeError):
        ProcessLock(tmp_path / "lock")
    lock.close()
    lock2 = ProcessLock(tmp_path / "lock")
    lock2.close()


@pytest.mark.parametrize("raw", ["NaN", "[]", '{"a":NaN}', '{"x":1,"x":2}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):
        decode(raw)


def test_envelope_destination_protocol_and_case():
    value = envelope("test", "A", "boot", "a", "hello", {}, 1)
    assert validate_envelope(value, "test", "a") is value
    with pytest.raises(ValueError):
        validate_envelope(value, "test", "A")


def test_storage_prefix_and_redaction():
    storage = {
        "endpoint": "http://localhost:9000",
        "bucket": "device-platform",
        "objectKeyPrefix": "/tmp/test/",
        "stsCredentials": {
            "accessKey": "example-access",
            "secretKey": "example-secret",
            "sessionToken": "",
            "expire": 300,
        },
    }
    assert validate_storage(storage)["objectKeyPrefix"] == "tmp/test"
    assert "storage" not in public_mission({"storage": storage, "tasks": []})
    assert validate_storage(storage)["stsCredentials"]["expire"] == 300


def test_default_runtime_is_per_robot_and_explicit_path_is_unchanged(
    tmp_path, monkeypatch
):
    from pathlib import Path
    from types import SimpleNamespace

    from swarm_protocol.ros import runtime_path

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def node(robot, root=""):
        return SimpleNamespace(
            declare_parameter=lambda *args: None,
            get_parameter=lambda key: SimpleNamespace(
                value=root if key == "data_root" else robot
            ),
        )

    assert runtime_path(node("A"), "agent") == tmp_path / ".ros/swarm/A/runtime/agent"
    assert runtime_path(node("B"), "agent") == tmp_path / ".ros/swarm/B/runtime/agent"
    assert (
        runtime_path(node("A", str(tmp_path / "custom")), "agent")
        == tmp_path / "custom"
    )
    with pytest.raises(ValueError):
        runtime_path(node("../unsafe"), "agent")


@pytest.mark.parametrize(
    "field,value",
    [
        ("robot_ids", []),
        ("robot_ids", ["A", "A"]),
        ("robot_ids", [" A"]),
        ("robot_ids", ["a b"]),
        ("round_epoch", 0),
        ("round_epoch", True),
        ("map_package", "company2"),
        ("map_package", "relative/map"),
        ("map_package", ".."),
        ("tasks", None),
    ],
)
def test_invalid_input_rejected(field, value):
    m = {"robot_ids": ["A"], "round_epoch": 1, "map_package": "/maps", "tasks": []}
    m[field] = value
    with pytest.raises(ValueError):
        normalize_mission(m, "demo")


def test_robot_ids_are_case_sensitive():
    assert normalize_mission(
        {
            "round_epoch": 1,
            "robot_ids": ["A", "a"],
            "map_package": "/maps",
            "tasks": [],
        },
        "m",
    )["robot_ids"] == ["A", "a"]
