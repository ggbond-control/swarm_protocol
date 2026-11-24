"""Byte budgets for committed commands and batches."""

from .contracts import MAX_MESSAGE_BYTES, canonical

BATCH_BYTES = 1024 * 1024
# Leave room for the ROS and MQTT envelopes, read IDs and replication metadata.
ENTRY_BYTES = MAX_MESSAGE_BYTES - 64 * 1024


def validate_command_size(command):
    if len(canonical(command).encode()) > ENTRY_BYTES - 256:
        raise ValueError("共识命令超过单条复制大小限制")


def entry_batch(entry_at, first, last):
    entries = []
    remaining = BATCH_BYTES
    for index in range(first, min(last + 1, first + 32)):
        entry = entry_at(index)
        size = 1 + len(canonical(entry).encode())
        if entries and size > remaining:
            break
        entries.append(entry)
        remaining -= size
    return entries
