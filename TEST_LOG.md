# swarm_protocol 测试记录

## 2026-11-16

本包的单元测试位于 `test/`，跨包流程和故障验证统一归档于
[Swarm TEST_LOG](../swarm_mission_coordinator/TEST_LOG.md)，避免维护多份相互冲突的计数。
测试仅使用本地隔离环境，不连接开发板或生产 MQTT／MinIO。
