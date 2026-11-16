# Swarm 协议基础库

新协同系列的公共库，无 ROS 节点。提供版本化 JSON、任务和存储配置校验、确定性摘要、原子持久化与进程锁；不保存任务状态，不执行选举或导航。

输入采用严格 JSON：拒绝重复键、非有限数值、非法 ID 和超过 8 MiB 的消息。设备 ID 区分大小写。任务配置通过 `public_mission` 去除存储凭据后才能进入复制日志。

持久文件使用校验和、原子替换与 fsync；private 文件权限为 0600。进程锁只防止同一路径被本机多个进程共同写入，不代替跨设备共识。

全套构建、入口和部署边界见 [协调器 README](../swarm_mission_coordinator/README.md)，消息约定见 [PROTOCOL](../swarm_mission_coordinator/PROTOCOL.md)，测试见 [TEST_LOG](TEST_LOG.md)。
