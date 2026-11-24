"""Pure wire contracts. No dependency on the previous cooperation stack."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

VERSION = 1
TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
MAX_MESSAGE_BYTES = 8 * 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


def identifier(value, name="identifier"):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name}: invalid case-sensitive identifier")
    return value


def positive_int(value, name):
    if type(value) is not int or value <= 0 or value > 2**53 - 1:
        raise ValueError(f"{name}: expected positive safe integer")
    return value


def finite(value, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name}: expected finite number")
    return float(value)


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def decode(raw):
    if len(raw.encode() if isinstance(raw, str) else raw) > MAX_MESSAGE_BYTES:
        raise ValueError("message exceeds size limit")

    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate JSON key: " + key)
            out[key] = value
        return out

    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    if not isinstance(value, dict):
        raise ValueError("message must be an object")
    return value


def normalize_task(task):
    if not isinstance(task, dict):
        raise ValueError("task must be object")
    out = copy.deepcopy(task)
    identifier(out.get("id"), "task.id")
    loc = out.get("location")
    if not isinstance(loc, dict):
        raise ValueError("task.location required")
    identifier(loc.get("frame_id"), "location.frame_id")
    pos = loc.get("pos")
    if not isinstance(pos, list) or len(pos) != 3:
        raise ValueError("location.pos requires three coordinates")
    loc["pos"] = [finite(x, "location.pos") for x in pos]
    if "orientation" not in loc:
        yaw = math.radians(finite(loc.get("yaw", 0), "yaw"))
        loc["orientation"] = [0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2)]
    q = loc["orientation"]
    if not isinstance(q, list) or len(q) != 4:
        raise ValueError("orientation requires four values")
    q = [finite(x, "orientation") for x in q]
    norm = math.sqrt(sum(x * x for x in q))
    if norm < 1e-9:
        raise ValueError("zero quaternion")
    loc["orientation"] = q if abs(norm - 1.0) < 1e-12 else [x / norm for x in q]
    operations = out.get("tasks")
    if not isinstance(operations, list):
        raise ValueError("tasks[].tasks must be array (empty for navigation only)")
    requirements = {"device"}
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("operation must be object")
        identifier(operation.get("method"), "operation.method")
        req = operation.get("requirements", [])
        if not isinstance(req, list) or any(
            not isinstance(x, str) or not x.strip() or x != x.strip() for x in req
        ):
            raise ValueError("invalid operation requirements")
        requirements.update(req)
        if not isinstance(operation.get("params", {}), dict):
            raise ValueError("operation.params must be object")
    out["requirements"] = sorted(requirements)
    service = finite(out.get("service_seconds", 0), "service_seconds")
    if service < 0:
        raise ValueError("negative service_seconds")
    out["service_seconds"] = service
    return out


def validate_storage(value):
    from urllib.parse import urlsplit

    if not isinstance(value, dict) or not isinstance(value.get("stsCredentials"), dict):
        raise ValueError("storage and stsCredentials must be objects")
    out = copy.deepcopy(value)
    endpoint = urlsplit(out.get("endpoint", ""))
    if (
        endpoint.scheme not in {"http", "https"}
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.path not in {"", "/"}
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("invalid storage.endpoint")
    if endpoint.port == 0:
        raise ValueError("invalid storage port")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", out.get("bucket", "")):
        raise ValueError("invalid storage.bucket")
    prefix = out.get("objectKeyPrefix")
    if not isinstance(prefix, str):
        raise ValueError("storage.objectKeyPrefix required")
    prefix = prefix.strip("/")
    if (
        not prefix
        or any(x in {"", ".", ".."} for x in prefix.split("/"))
        or any(ord(x) < 32 for x in prefix)
    ):
        raise ValueError("invalid objectKeyPrefix")
    out["objectKeyPrefix"] = prefix
    cred = out["stsCredentials"]
    for field in ("accessKey", "secretKey"):
        if not isinstance(cred.get(field), str) or not cred[field].strip():
            raise ValueError("storage credentials required")
    if not isinstance(cred.get("sessionToken", ""), str):
        raise ValueError("sessionToken must be string")
    return out


def normalize_mission(value, mission_id):
    if not isinstance(value, dict):
        raise ValueError("mission must be object")
    out = copy.deepcopy(value)
    out["mission_id"] = identifier(mission_id, "mission_id")
    positive_int(out.get("round_epoch"), "round_epoch")
    ids = out.get("robot_ids")
    if not isinstance(ids, list) or not ids or len(ids) > 32:
        raise ValueError("robot_ids requires 1..32 actual participants")
    for robot in ids:
        identifier(robot, "robot_id")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate robot_ids")
    out["robot_ids"] = sorted(ids)
    path = out.get("map_package")
    if not isinstance(path, str) or "\x00" in path or not Path(path).is_absolute():
        raise ValueError("map_package must be an absolute device-local path")
    tasks = out.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("tasks must be array")
    out["tasks"] = [normalize_task(t) for t in tasks]
    if len({t["id"] for t in out["tasks"]}) != len(tasks):
        raise ValueError("duplicate task ids")
    if "storage" in out:
        out["storage"] = validate_storage(out["storage"])
    if "initial_voter_ids" in out:
        raise ValueError("use robot_ids only; initial_voter_ids is not supported")
    canonical(out)
    return out


def public_mission(mission):
    return {k: copy.deepcopy(v) for k, v in mission.items() if k != "storage"}


def envelope(cluster, robot, boot, destination, kind, data, epoch=0):
    return {
        "protocol_version": VERSION,
        "cluster_id": identifier(cluster),
        "robot_id": identifier(robot),
        "boot_id": identifier(boot),
        "to": "*" if destination == "*" else identifier(destination),
        "kind": identifier(kind),
        "round_epoch": epoch,
        "data": data,
    }


def validate_envelope(value, cluster, robot):
    if (
        value.get("protocol_version") != VERSION
        or value.get("cluster_id") != cluster
        or value.get("to") not in {"*", robot}
        or not isinstance(value.get("data"), dict)
    ):
        raise ValueError("protocol/cluster/destination mismatch")
    for field in ("robot_id", "boot_id", "kind"):
        identifier(value.get(field), field)
    epoch = value.get("round_epoch")
    if type(epoch) is not int or epoch < 0:
        raise ValueError("invalid round_epoch")
    return value
