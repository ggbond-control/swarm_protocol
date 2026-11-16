"""Small standard-String ROS boundary shared by new swarm nodes."""

from pathlib import Path

from .contracts import canonical, identifier


def publish(publisher, value):
    from std_msgs.msg import String

    publisher.publish(String(data=canonical(value)))


def runtime_path(node, component):
    node.declare_parameter("data_root", "")
    value = node.get_parameter("data_root").value
    robot = identifier(node.get_parameter("robot_id").value, "robot_id")
    root = (
        Path(value).expanduser()
        if value
        else Path.home() / ".ros" / "swarm" / robot / component
    )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def main_node(factory, args=None):
    import rclpy
    from rclpy.executors import ExternalShutdownException

    rclpy.init(args=args)
    node = factory()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
