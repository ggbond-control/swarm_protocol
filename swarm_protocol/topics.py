"""Stable deployment names, independent of software and wire protocol versions."""

DEFAULT_CLUSTER_ID = "inspection-swarm"
DEFAULT_PEER_PREFIX = "fh/swarm/peer"
DEFAULT_PLATFORM_PREFIX = "fh/swarm/dispatch"


def heartbeat_topic(robot_id):
    return "fh/swarm/device/" + robot_id + "/heartbeat"
