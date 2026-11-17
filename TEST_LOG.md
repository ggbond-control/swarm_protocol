# swarm_protocol 测试记录

## 2026-11-17

新增统一主题默认值：固定新 swarm 平台／心跳／内部主题，默认值不含日期或版本。
协议消息的版本校验保持不变。跨包单元、ROS 集成及双开发板空任务验证结果统一见
[Swarm TEST_LOG](../swarm_mission_coordinator/TEST_LOG.md#2026-11-17)。

## 2026-11-16

本包的单元测试位于 `test/`，跨包流程和故障验证统一归档于
[Swarm TEST_LOG](../swarm_mission_coordinator/TEST_LOG.md)，避免维护多份相互冲突的计数。
测试仅使用本地隔离环境，不连接开发板或生产 MQTT／MinIO。
