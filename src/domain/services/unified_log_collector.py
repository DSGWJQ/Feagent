"""统一日志收集器

提供统一的日志收集、查询和聚合功能：
- 多级别日志（DEBUG, INFO, WARNING, ERROR）
- 按来源、级别、时间范围过滤
- 日志聚合统计
- JSON 导出

用法：
    collector = UnifiedLogCollector()

    # 记录日志
    collector.info("CoordinatorAgent", "决策验证通过", {"decision_id": "d001"})
    collector.error("WorkflowAgent", "节点执行失败", {"node_id": "n001"})

    # 查询日志
    errors = collector.filter_by_level("ERROR")
    recent = collector.get_recent(10)

    # 聚合统计
    stats = collector.aggregate_by_source()

    # 导出
    json_str = collector.export_json()
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class LogEntry:
    """日志条目"""

    level: str
    source: str
    message: str
    context: dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


class UnifiedLogCollector:
    """统一日志收集器

    收集、存储和查询来自各个 Agent 的日志。
    """

    # 日志级别优先级
    LEVEL_PRIORITY = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3,
        "CRITICAL": 4,
    }

    def __init__(self, max_entries: int = 10000) -> None:
        """初始化日志收集器

        参数：
            max_entries: 最大保留条目数（默认 10000）
        """
        self.logs: list[LogEntry] = []
        self.max_entries = max_entries

    def log(
        self,
        level: str,
        source: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """记录日志

        参数：
            level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
            source: 日志来源
            message: 日志消息
            context: 上下文信息（可选）
        """
        entry = LogEntry(
            level=level.upper(),
            source=source,
            message=message,
            context=context or {},
            timestamp=datetime.now(),
        )

        self.logs.append(entry)

        # 超出限制时删除最旧的日志
        if len(self.logs) > self.max_entries:
            self.logs = self.logs[-self.max_entries :]

    def debug(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 DEBUG 级别日志"""
        self.log("DEBUG", source, message, context)

    def info(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 INFO 级别日志"""
        self.log("INFO", source, message, context)

    def warning(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 WARNING 级别日志"""
        self.log("WARNING", source, message, context)

    def error(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 ERROR 级别日志"""
        self.log("ERROR", source, message, context)

    def critical(self, source: str, message: str, context: dict[str, Any] | None = None) -> None:
        """记录 CRITICAL 级别日志"""
        self.log("CRITICAL", source, message, context)

    def filter_by_level(self, level: str) -> list[dict[str, Any]]:
        """按级别过滤日志

        参数：
            level: 日志级别

        返回：
            匹配的日志列表
        """
        level_upper = level.upper()
        return [entry.to_dict() for entry in self.logs if entry.level == level_upper]

    def filter_by_source(self, source: str) -> list[dict[str, Any]]:
        """按来源过滤日志

        参数：
            source: 日志来源

        返回：
            匹配的日志列表
        """
        return [entry.to_dict() for entry in self.logs if entry.source == source]

    def filter_by_time_range(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """按时间范围过滤日志

        参数：
            since: 开始时间（可选）
            until: 结束时间（可选）

        返回：
            匹配的日志列表
        """
        results = []

        for entry in self.logs:
            if since is not None and entry.timestamp < since:
                continue
            if until is not None and entry.timestamp > until:
                continue
            results.append(entry.to_dict())

        return results

    def get_recent(self, count: int) -> list[dict[str, Any]]:
        """获取最近 N 条日志

        参数：
            count: 条目数

        返回：
            最近的日志列表
        """
        return [entry.to_dict() for entry in self.logs[-count:]]

    def aggregate_by_source(self) -> dict[str, int]:
        """按来源聚合统计

        返回：
            {来源: 条目数} 的字典
        """
        stats: dict[str, int] = {}

        for entry in self.logs:
            stats[entry.source] = stats.get(entry.source, 0) + 1

        return stats

    def aggregate_by_level(self) -> dict[str, int]:
        """按级别聚合统计

        返回：
            {级别: 条目数} 的字典
        """
        stats: dict[str, int] = {}

        for entry in self.logs:
            stats[entry.level] = stats.get(entry.level, 0) + 1

        return stats

    def export_json(self, indent: int = 2) -> str:
        """导出为 JSON 字符串

        参数：
            indent: 缩进空格数

        返回：
            JSON 字符串
        """
        return json.dumps(
            [entry.to_dict() for entry in self.logs],
            indent=indent,
            ensure_ascii=False,
        )

    def clear(self) -> None:
        """清空所有日志"""
        self.logs.clear()

    def get_statistics(self) -> dict[str, Any]:
        """获取日志统计信息

        返回：
            统计信息字典
        """
        return {
            "total_entries": len(self.logs),
            "by_level": self.aggregate_by_level(),
            "by_source": self.aggregate_by_source(),
        }
