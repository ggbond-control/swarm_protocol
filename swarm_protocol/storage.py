"""Atomic, fsync-backed files with integrity checking and single-process ownership."""

import fcntl
import json
import os
import tempfile
from pathlib import Path

from .contracts import canonical, digest


def atomic_json(path, value, private=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600 if private else 0o644)
            stream.write(canonical(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        folder = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class DurableFile:
    def __init__(self, path):
        self.path = Path(path)

    def load(self, default=None):
        if not self.path.exists():
            return default
        wrapper = json.loads(self.path.read_text())
        if wrapper.get("sha256") != digest(wrapper.get("data")):
            raise RuntimeError(f"corrupt durable state: {self.path}")
        return wrapper["data"]

    def save(self, value):
        atomic_json(self.path, {"sha256": digest(value), "data": value})


class ProcessLock:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            raise RuntimeError(f"another process owns {path}") from None

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
