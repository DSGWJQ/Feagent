"""UnifiedLogIntegration E2E Integration Test

快速验证 Phase 34.10 集成的正确性：
- CoordinatorAgent 初始化 UnifiedLogIntegration
- 三源日志（log_collector, message_log, container_logs）能正确合并
- get_merged_logs() 公开接口可用
"""

from datetime import datetime

from src.domain.agents.coordinator_agent import CoordinatorAgent
from src.domain.services.event_bus import EventBus


def test_coordinator_get_merged_logs_basic():
    """测试 CoordinatorAgent.get_merged_logs() 基础功能"""
    # 创建 CoordinatorAgent 实例
    event_bus = EventBus()
    coordinator = CoordinatorAgent(event_bus=event_bus)

    # 1. 添加 log_collector 日志
    coordinator.log_collector.info("TestSource", "Log from UnifiedLogCollector", {"test": "data"})

    # 2. 添加 message_log 日志
    coordinator.message_log.append(
        {
            "timestamp": datetime(2025, 1, 1, 10, 0, 0).isoformat(),
            "level": "INFO",
            "content": "Message from message_log",
        }
    )

    # 3. 添加 container_logs 日志
    coordinator._container_monitor.container_logs["container_001"] = [
        {
            "timestamp": datetime(2025, 1, 1, 10, 0, 30).isoformat(),
            "level": "DEBUG",
            "message": "Container log from container_001",
        }
    ]

    # 4. 调用 get_merged_logs() 并验证
    merged_logs = coordinator.get_merged_logs()

    # 验证日志数量（至少有3条）
    assert len(merged_logs) >= 3, f"Expected at least 3 logs, got {len(merged_logs)}"

    # 验证日志来源标识
    sources = [log.get("source") for log in merged_logs]
    assert "TestSource" in sources, "Missing log from UnifiedLogCollector"
    assert "MessageLog" in sources, "Missing log from message_log"
    assert "Container:container_001" in sources, "Missing log from container_logs"

    # 验证日志格式统一（每条日志都有必需字段）
    for log in merged_logs:
        assert "level" in log, f"Missing 'level' in log: {log}"
        assert "source" in log, f"Missing 'source' in log: {log}"
        assert "message" in log or "content" in log, f"Missing message/content in log: {log}"
        assert "timestamp" in log, f"Missing 'timestamp' in log: {log}"

    # 验证按时间排序（时间戳应升序）
    timestamps = [log.get("timestamp") for log in merged_logs if log.get("timestamp")]
    assert timestamps == sorted(timestamps), "Logs are not sorted by timestamp"

    print("[PASS] All assertions passed!")
    print(f"   Total merged logs: {len(merged_logs)}")
    print(f"   Sources found: {set(sources)}")

    return True


if __name__ == "__main__":
    print("Running UnifiedLogIntegration E2E Integration Test...")
    print("-" * 60)

    success = test_coordinator_get_merged_logs_basic()

    if success:
        print("-" * 60)
        print("[SUCCESS] Test PASSED: UnifiedLogIntegration integration is correct!")
    else:
        print("-" * 60)
        print("[FAILED] Test FAILED: Please check implementation")
        exit(1)
