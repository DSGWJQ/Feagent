"""UnifiedLogCollector 集成模块

提供统一日志收集、多源聚合与查询的集成接口。
从 CoordinatorAgent 提取（Phase 34.10）。

职责：
- 包装 UnifiedLogCollector 的所有日志记录方法
- 提供统一的查询、过滤、统计接口
- 支持多源日志合并（log_collector + message_log + container_logs）
- 按时间排序合并后的日志

设计模式：
- 委托模式：所有方法委托到 UnifiedLogCollector
- 懒加载：log_collector 可选注入，默认懒加载创建
- Gateway模式：通过 accessor 访问外部日志源（message_log, container_logs）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class UnifiedLogIntegration:
    """UnifiedLogCollector 集成包装器

    提供统一日志收集与多源聚合功能。

    用法：
        # 基础用法（仅 UnifiedLogCollector）
        integration = UnifiedLogIntegration()
        integration.log_info("CoordinatorAgent", "决策验证通过", {"decision_id": "d001"})
        recent = integration.get_recent_logs(10)

        # 多源日志合并
        integration = UnifiedLogIntegration(
            log_collector=log_collector,
            message_log_accessor=message_accessor,
            container_log_accessor=container_accessor,
        )
        merged = integration.get_merged_logs()  # 合并三源日志并按时间排序
    """

    def __init__(
        self,
        log_collector: Any | None = None,
        message_log_accessor: Any | None = None,
        container_log_accessor: Any | None = None,
    ) -> None:
        """初始化 UnifiedLogIntegration

        参数：
            log_collector: UnifiedLogCollector 实例（可选，默认懒加载）
            message_log_accessor: 提供 get_messages() 方法的访问器（可选）
            container_log_accessor: 提供 get_container_logs() 方法的访问器（可选）

        注意：
            - log_collector 为 None 时，首次访问 self.log_collector 将懒加载创建
            - message_log_accessor 和 container_log_accessor 为可选，仅影响 get_merged_logs()
        """
        self._log_collector = log_collector
        self.message_log_accessor = message_log_accessor
        self.container_log_accessor = container_log_accessor

    @property
    def log_collector(self) -> Any:
        """获取 UnifiedLogCollector 实例（懒加载）

        返回：
            UnifiedLogCollector 实例
        """
        if self._log_collector is None:
            from src.domain.services.unified_log_collector import UnifiedLogCollector

            self._log_collector = UnifiedLogCollector()
        return self._log_collector

    # ==================== 日志记录方法包装 ====================

    def log_debug(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 DEBUG 级别日志

        参数：
            source: 日志来源（如 "CoordinatorAgent"）
            message: 日志消息
            context: 上下文信息（可选）
        """
        self.log_collector.debug(source, message, context)

    def log_info(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 INFO 级别日志

        参数：
            source: 日志来源
            message: 日志消息
            context: 上下文信息（可选）
        """
        self.log_collector.info(source, message, context)

    def log_warning(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 WARNING 级别日志

        参数：
            source: 日志来源
            message: 日志消息
            context: 上下文信息（可选）
        """
        self.log_collector.warning(source, message, context)

    def log_error(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 ERROR 级别日志

        参数：
            source: 日志来源
            message: 日志消息
            context: 上下文信息（可选）
        """
        self.log_collector.error(source, message, context)

    def log_critical(
        self, source: str, message: str, context: dict[str, Any] | None = None
    ) -> None:
        """记录 CRITICAL 级别日志

        参数：
            source: 日志来源
            message: 日志消息
            context: 上下文信息（可选）
        """
        self.log_collector.critical(source, message, context)

    # ==================== 查询与过滤 ====================

    def get_recent_logs(self, count: int) -> list[dict[str, Any]]:
        """获取最近 N 条日志

        参数：
            count: 返回的日志条目数

        返回：
            最近的日志列表（按时间从旧到新）
        """
        return self.log_collector.get_recent(count)

    def filter_logs_by_level(self, level: str) -> list[dict[str, Any]]:
        """按级别过滤日志

        参数：
            level: 日志级别（如 "ERROR"）

        返回：
            匹配的日志列表
        """
        return self.log_collector.filter_by_level(level)

    def filter_logs_by_source(self, source: str) -> list[dict[str, Any]]:
        """按来源过滤日志

        参数：
            source: 日志来源（如 "CoordinatorAgent"）

        返回：
            匹配的日志列表
        """
        return self.log_collector.filter_by_source(source)

    def filter_logs_by_time_range(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """按时间范围过滤日志

        参数：
            since: 开始时间（可选，None 表示无限制）
            until: 结束时间（可选，None 表示无限制）

        返回：
            时间范围内的日志列表
        """
        return self.log_collector.filter_by_time_range(since=since, until=until)

    # ==================== 统计与聚合 ====================

    def get_log_statistics(self) -> dict[str, Any]:
        """获取日志统计信息

        返回：
            统计信息字典，包含：
            - total_entries: 总日志条目数
            - by_level: 按级别统计 {"INFO": 60, "ERROR": 10, ...}
            - by_source: 按来源统计 {"CoordinatorAgent": 50, ...}
        """
        return self.log_collector.get_statistics()

    def aggregate_logs_by_source(self) -> dict[str, int]:
        """按来源聚合日志数量

        返回：
            来源统计字典 {"CoordinatorAgent": 50, "WorkflowAgent": 30, ...}
        """
        return self.log_collector.aggregate_by_source()

    def aggregate_logs_by_level(self) -> dict[str, int]:
        """按级别聚合日志数量

        返回：
            级别统计字典 {"INFO": 60, "WARNING": 20, "ERROR": 10, ...}
        """
        return self.log_collector.aggregate_by_level()

    # ==================== 多源日志合并 ====================

    def get_merged_logs(self) -> list[dict[str, Any]]:
        """合并多源日志并按时间排序

        合并以下日志源：
        1. UnifiedLogCollector 的日志
        2. message_log（如果 message_log_accessor 不为 None）
        3. container_logs（如果 container_log_accessor 不为 None）

        返回：
            统一格式的日志列表，按时间从旧到新排序
            每条日志包含：
            - level: 日志级别
            - source: 日志来源
            - message: 日志消息
            - timestamp: 时间戳（ISO格式）
            - context: 上下文信息字典

        注意：
            - 日志格式已统一，不同源的日志会标记不同的 source
            - message_log 来源标记为 "MessageLog"
            - container_logs 来源标记为 "Container:{container_id}"
        """
        all_logs: list[dict[str, Any]] = []

        # 1. UnifiedLogCollector 的日志
        all_logs.extend([entry.to_dict() for entry in self.log_collector.logs])

        # 2. message_log 日志（如果有 accessor）
        if self.message_log_accessor is not None:
            messages = self.message_log_accessor.get_messages()
            # 转换为统一格式
            for msg in messages:
                # 从多个可能的字段构建消息内容
                message_content = (
                    msg.get("content")
                    or msg.get("user_input")
                    or msg.get("response")
                    or msg.get("intent")
                    or str(msg)  # 兜底：转换整个对象
                )
                all_logs.append(
                    {
                        "level": msg.get("level", "INFO"),
                        "source": "MessageLog",
                        "message": message_content,
                        "timestamp": self._normalize_timestamp(msg.get("timestamp", "")),
                        "context": {},
                    }
                )

        # 3. container_logs 日志（如果有 accessor）
        if self.container_log_accessor is not None:
            # 复制字典以避免并发修改风险
            container_logs_dict = dict(self.container_log_accessor.get_container_logs())
            for container_id, logs in container_logs_dict.items():
                # 为每个容器的日志添加 container_id 上下文
                for log in logs:
                    all_logs.append(
                        {
                            "level": log.get("level", "DEBUG"),
                            "source": f"Container:{container_id}",
                            "message": log.get("message", ""),
                            "timestamp": self._normalize_timestamp(log.get("timestamp", "")),
                            "context": {"container_id": container_id},
                        }
                    )

        # 按时间戳排序（从旧到新）
        all_logs.sort(key=lambda x: self._normalize_timestamp(x.get("timestamp")))

        return all_logs

    # ==================== 辅助方法 ====================

    def clear_logs(self) -> None:
        """清空 UnifiedLogCollector 中的所有日志

        注意：
            仅清空 log_collector 的日志，不影响 message_log 或 container_logs
        """
        self.log_collector.clear()

    def export_logs_json(self, indent: int = 2) -> str:
        """导出日志为 JSON 字符串

        参数：
            indent: JSON 缩进空格数（默认 2）

        返回：
            JSON 格式的日志字符串

        注意：
            仅导出 log_collector 的日志，不包含 message_log 或 container_logs
            如需导出合并日志，请先调用 get_merged_logs() 再自行序列化
        """
        return self.log_collector.export_json(indent=indent)

    @staticmethod
    def _normalize_timestamp(value: Any) -> str:
        """将时间戳统一为可排序的字符串

        参数：
            value: 时间戳（可能是 datetime 对象或字符串）

        返回：
            ISO格式的时间字符串（用于排序）

        注意：
            - datetime 对象转换为 ISO 格式字符串
            - 字符串直接返回
            - None 或其他类型返回空字符串（排序时会排在最前）
        """
        if isinstance(value, datetime):
            return value.isoformat()
        return value or ""
