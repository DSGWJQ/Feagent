"""节点版本管理器 (Node Version Manager) - 阶段4

业务定义：
- 管理节点的版本历史
- 支持版本比较和回滚
- 提供版本审计追踪

核心功能：
- record_version: 记录节点版本
- get_version_history: 获取版本历史
- list_versions: 列出所有版本
- get_version: 获取指定版本
- rollback: 回滚到指定版本
- compare_versions: 比较两个版本差异
"""

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.services.node_registry import Node


@dataclass
class NodeVersionRecord:
    """节点版本记录

    存储节点在特定版本的完整状态。

    属性：
    - node_id: 节点ID
    - version: 版本号
    - config: 配置快照
    - node_type: 节点类型
    - scope: 作用域
    - promotion_status: 升级状态
    - created_at: 创建时间
    - rollback_from: 回滚来源版本（如果是回滚操作）
    """

    node_id: str
    version: int
    config: dict[str, Any]
    node_type: str
    scope: str
    promotion_status: str
    created_at: datetime = field(default_factory=datetime.now)
    rollback_from: int | None = None


class NodeVersionManager:
    """节点版本管理器

    职责：
    1. 记录节点版本变更
    2. 提供版本查询接口
    3. 支持版本回滚
    4. 提供版本比较功能

    使用示例：
        manager = NodeVersionManager()

        # 记录版本
        manager.record_version(node)

        # 获取历史
        history = manager.get_version_history(node.id)

        # 回滚
        rolled_back = manager.rollback(node.id, target_version=1)
    """

    def __init__(self):
        """初始化版本管理器"""
        # node_id -> list of version records
        self._versions: dict[str, list[NodeVersionRecord]] = {}

    def record_version(
        self,
        node: Node,
        rollback_from: int | None = None,
    ) -> NodeVersionRecord:
        """记录节点版本

        每次调用会保存节点当前状态的快照。

        参数：
            node: 节点实例
            rollback_from: 如果是回滚操作，指定来源版本

        返回：
            版本记录
        """
        record = NodeVersionRecord(
            node_id=node.id,
            version=node.version,
            config=copy.deepcopy(node.config),
            node_type=node.type.value,
            scope=node.scope.value,
            promotion_status=node.promotion_status.value,
            rollback_from=rollback_from,
        )

        if node.id not in self._versions:
            self._versions[node.id] = []

        self._versions[node.id].append(record)
        return record

    def get_version_history(self, node_id: str) -> list[dict[str, Any]]:
        """获取节点版本历史

        参数：
            node_id: 节点ID

        返回：
            版本历史列表（按版本号升序）
        """
        records = self._versions.get(node_id, [])

        return [self._record_to_dict(record) for record in records]

    def list_versions(self, node_id: str) -> list[dict[str, Any]]:
        """列出节点所有版本（与 get_version_history 相同）

        参数：
            node_id: 节点ID

        返回：
            版本列表
        """
        return self.get_version_history(node_id)

    def get_version(self, node_id: str, version: int) -> dict[str, Any]:
        """获取指定版本的节点配置

        参数：
            node_id: 节点ID
            version: 版本号

        返回：
            版本详情

        异常：
            ValueError: 版本不存在
        """
        records = self._versions.get(node_id, [])

        for record in records:
            if record.version == version:
                return self._record_to_dict(record)

        raise ValueError(f"版本不存在: {node_id} v{version}")

    def rollback(self, node_id: str, target_version: int) -> dict[str, Any]:
        """回滚到指定版本

        回滚会创建一个新版本，内容与目标版本相同。

        参数：
            node_id: 节点ID
            target_version: 目标版本号

        返回：
            回滚后的版本详情

        异常：
            ValueError: 版本不存在
        """
        records = self._versions.get(node_id, [])

        # 查找目标版本
        target_record = None
        for record in records:
            if record.version == target_version:
                target_record = record
                break

        if not target_record:
            raise ValueError(f"版本不存在: {node_id} v{target_version}")

        # 计算新版本号
        current_max_version = max(r.version for r in records)
        new_version = current_max_version + 1

        # 创建回滚版本
        rollback_record = NodeVersionRecord(
            node_id=node_id,
            version=new_version,
            config=copy.deepcopy(target_record.config),
            node_type=target_record.node_type,
            scope=target_record.scope,
            promotion_status=target_record.promotion_status,
            rollback_from=target_version,  # 标记回滚来源
        )

        self._versions[node_id].append(rollback_record)

        return self._record_to_dict(rollback_record)

    def compare_versions(
        self,
        node_id: str,
        version1: int,
        version2: int,
    ) -> dict[str, Any]:
        """比较两个版本的差异

        参数：
            node_id: 节点ID
            version1: 版本1
            version2: 版本2

        返回：
            差异报告：
            {
                "changed": {field: {"old": v1_value, "new": v2_value}},
                "added": {field: value},  # v1没有，v2有
                "removed": {field: value},  # v1有，v2没有
            }

        异常：
            ValueError: 版本不存在
        """
        v1 = self.get_version(node_id, version1)
        v2 = self.get_version(node_id, version2)

        config1 = v1["config"]
        config2 = v2["config"]

        changed = {}
        added = {}
        removed = {}

        # 找出改变和删除的字段
        for key, value1 in config1.items():
            if key not in config2:
                removed[key] = value1
            elif config2[key] != value1:
                changed[key] = {"old": value1, "new": config2[key]}

        # 找出新增的字段
        for key, value2 in config2.items():
            if key not in config1:
                added[key] = value2

        return {
            "changed": changed,
            "added": added,
            "removed": removed,
            "version1": version1,
            "version2": version2,
        }

    def get_latest_version(self, node_id: str) -> dict[str, Any] | None:
        """获取节点最新版本

        参数：
            node_id: 节点ID

        返回：
            最新版本详情，如果没有则返回 None
        """
        records = self._versions.get(node_id, [])

        if not records:
            return None

        latest = max(records, key=lambda r: r.version)
        return self._record_to_dict(latest)

    def delete_node_history(self, node_id: str) -> bool:
        """删除节点的所有版本历史

        参数：
            node_id: 节点ID

        返回：
            是否删除成功
        """
        if node_id in self._versions:
            del self._versions[node_id]
            return True
        return False

    def _record_to_dict(self, record: NodeVersionRecord) -> dict[str, Any]:
        """将版本记录转换为字典

        参数：
            record: 版本记录

        返回：
            字典格式
        """
        result = {
            "node_id": record.node_id,
            "version": record.version,
            "config": copy.deepcopy(record.config),
            "node_type": record.node_type,
            "scope": record.scope,
            "promotion_status": record.promotion_status,
            "created_at": record.created_at.isoformat(),
        }

        if record.rollback_from is not None:
            result["rollback_from"] = record.rollback_from

        return result


# 导出
__all__ = [
    "NodeVersionRecord",
    "NodeVersionManager",
]
