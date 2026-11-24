"""Bounded, best-effort diagnostic recording outside the control loop."""

from collections import OrderedDict
import errno
import os
from pathlib import Path
from queue import Full, Queue
import re
from threading import Thread
import time

from .contracts import canonical, digest

REDACTED_KEYS = {
    "storage", "stscredentials", "accesskey", "secretkey", "sessiontoken",
    "password", "mqtt_password", "authorization",
}
ROUTE = re.compile(r"^sw([0-9]+)-[0-9a-f]+-r([0-9]+)-")


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k.lower() not in REDACTED_KEYS}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class Audit:
    def __init__(self, root, robot, logger):
        self.root, self.robot, self.logger = Path(root), robot, logger
        self.queue = Queue(maxsize=128)
        self.thread = Thread(target=self._write, name="swarm-audit", daemon=True)
        self.last_warning = 0.0
        self.dropped = 0
        self.segment_bytes = 16 * 1024 * 1024
        self.thread.start()

    def _warn(self, message):
        now = time.monotonic()
        if now - self.last_warning >= 10:
            self.logger.warning(message)
            self.last_warning = now

    def record(self, kind, value, *, epoch=0, revision=0, **context):
        payload = value.get("data", value)
        payload = payload if isinstance(payload, dict) else value
        route = payload.get("route_name", "")
        match = ROUTE.match(route) if isinstance(route, str) else None
        if match:
            epoch, revision = map(int, match.groups())
        epoch = payload.get("round_epoch", epoch)
        revision = payload.get("plan_revision", payload.get("revision", revision))
        epoch = epoch if type(epoch) is int and 0 < epoch < 2**53 else 0
        revision = revision if type(revision) is int and 0 < revision < 2**53 else 0
        rec = {"time": time.time(), "robot_id": self.robot, "kind": kind,
               "round_epoch": epoch, "revision": revision, **context, "payload": value}
        try:
            self.queue.put_nowait(rec)
        except Full:
            self.dropped += 1
            self._warn("协同审计队列已满，累计丢弃 %d 条" % self.dropped)

    def _write(self):
        seen = OrderedDict()
        segments = {}
        while (row := self.queue.get()) is not None:
            try:
                row = redact(row)
                signature = {k: v for k, v in row.items() if k != "time"}
                if "timestamp" in signature["payload"]:
                    signature["payload"] = {
                        k: v for k, v in signature["payload"].items() if k != "timestamp"
                    }
                key = digest(signature)
                if key in seen:
                    seen.move_to_end(key)
                    continue
                directory = self.root / "audit" / f"round-{row['round_epoch']}"
                if row["revision"]:
                    directory /= f"r{row['revision']:03d}"
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                line = canonical(row) + "\n"
                segment = segments.get(directory, directory / "events.jsonl")
                if segment.exists() and segment.stat().st_size + len(line.encode()) > self.segment_bytes:
                    segment = directory / f"events-{time.time_ns()}.jsonl"
                segments[directory] = segment
                with open(segment, "a", encoding="utf-8",
                          opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
                    stream.write(line)
                seen[key] = None
                if len(seen) > 2048:
                    seen.popitem(last=False)
            except (OSError, ValueError, TypeError, RecursionError) as error:
                self.dropped += 1
                reason = "磁盘已满" if getattr(error, "errno", None) == errno.ENOSPC else type(error).__name__
                self._warn(f"协同审计写入失败：{reason}，累计丢弃 {self.dropped} 条")
            if self.dropped:
                try:
                    from .storage import atomic_json
                    atomic_json(self.root / "audit" / "status.json", {"dropped": self.dropped})
                except OSError:
                    pass

    def close(self):
        try:
            self.queue.put(None, timeout=1.0)
        except Full:
            self._warn("协同审计退出时未排空")
            return
        self.thread.join(timeout=2.0)
