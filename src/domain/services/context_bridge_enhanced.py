"""增强型上下文桥接器 (SecureContextBridge) - 阶段 5

业务定义：
- 安全的工作流间上下文传递
- 显式桥接请求机制
- 访问控制和授权
- 传递记录和审计日志

设计原则：
- 隔离优先：默认不同工作流上下文相互隔离
- 显式授权：桥接需要明确请求和授权
- 可追溯：所有传递都有日志记录
- 选择性传递：只传递请求的特定数据

核心功能：
- register_workflow: 注册工作流上下文
- transfer_with_request: 显式桥接请求
- get_transfer_logs: 获取传递日志
- set_access_policy: 设置访问策略
"""

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.services.context_bridge import WorkflowContext

logger = logging.getLogger(__name__)


class AccessDeniedError(Exception):
    """访问被拒绝异常"""

    pass


class AuthorizationDeniedError(Exception):
    """授权被拒绝异常"""

    pass


@dataclass
class BridgeRequest:
    """桥接请求

    属性：
    - source_workflow_id: 源工作流ID
    - target_workflow_id: 目标工作流ID
    - requested_keys: 请求的数据键列表
    - requester: 请求者标识
    - timestamp: 请求时间
    """

    source_workflow_id: str
    target_workflow_id: str
    requested_keys: list[str]
    requester: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BridgeResult:
    """桥接结果

    属性：
    - success: 是否成功
    - transferred_data: 传递的数据
    - error: 错误信息（如果失败）
    - timestamp: 完成时间
    """

    success: bool = False
    transferred_data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AccessPolicy:
    """访问策略

    属性：
    - workflow_id: 工作流ID
    - allowed_requesters: 允许的请求者列表（空列表表示允许所有）
    - restricted_keys: 受限的数据键列表
    """

    workflow_id: str
    allowed_requesters: list[str] = field(default_factory=list)
    restricted_keys: list[str] = field(default_factory=list)


@dataclass
class TransferLog:
    """传递日志

    记录每次桥接传递的详细信息。
    """

    source: str
    target: str
    keys: list[str]
    requester: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None


class SecureContextBridge:
    """安全上下文桥接器

    职责：
    1. 管理工作流上下文注册
    2. 处理显式桥接请求
    3. 执行访问控制
    4. 记录传递日志

    使用示例：
        bridge = SecureContextBridge()
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)

        request = BridgeRequest(
            source_workflow_id="wf_a",
            target_workflow_id="wf_b",
            requested_keys=["result_node"],
            requester="wf_b_coordinator"
        )

        result = await bridge.transfer_with_request(request)
    """

    def __init__(self):
        """初始化桥接器"""
        self._workflows: dict[str, WorkflowContext] = {}
        self._policies: dict[str, AccessPolicy] = {}
        self._transfer_logs: list[TransferLog] = []

    def register_workflow(self, workflow_context: WorkflowContext) -> None:
        """注册工作流上下文

        参数：
            workflow_context: 工作流上下文
        """
        workflow_id = workflow_context.workflow_id
        self._workflows[workflow_id] = workflow_context

        # 默认策略：允许所有请求者
        if workflow_id not in self._policies:
            self._policies[workflow_id] = AccessPolicy(workflow_id=workflow_id)

        logger.info(f"工作流已注册: {workflow_id}")

    def set_access_policy(
        self,
        workflow_id: str,
        allowed_requesters: list[str] | None = None,
        restricted_keys: list[str] | None = None,
    ) -> None:
        """设置访问策略

        参数：
            workflow_id: 工作流ID
            allowed_requesters: 允许的请求者列表
            restricted_keys: 受限的数据键列表
        """
        policy = self._policies.get(workflow_id, AccessPolicy(workflow_id=workflow_id))

        if allowed_requesters is not None:
            policy.allowed_requesters = allowed_requesters
        if restricted_keys is not None:
            policy.restricted_keys = restricted_keys

        self._policies[workflow_id] = policy

    async def transfer_with_request(self, request: BridgeRequest) -> BridgeResult:
        """处理桥接请求

        参数：
            request: 桥接请求

        返回：
            桥接结果
        """
        source_id = request.source_workflow_id
        target_id = request.target_workflow_id

        # 检查工作流是否存在
        if source_id not in self._workflows:
            return self._log_and_return_error(request, f"源工作流不存在: {source_id}")

        if target_id not in self._workflows:
            return self._log_and_return_error(request, f"目标工作流不存在: {target_id}")

        source_ctx = self._workflows[source_id]
        target_ctx = self._workflows[target_id]

        # 检查访问权限
        policy = self._policies.get(source_id)
        if policy and policy.allowed_requesters:
            if request.requester not in policy.allowed_requesters:
                error_msg = f"授权被拒绝: {request.requester} 无权访问 {source_id}"
                self._record_log(request, success=False, error=error_msg)
                raise AuthorizationDeniedError(error_msg)

        # 收集请求的数据
        transferred_data: dict[str, Any] = {}

        for key in request.requested_keys:
            # 检查是否是受限键
            if policy and key in policy.restricted_keys:
                logger.warning(f"跳过受限键: {key}")
                continue

            # 从 node_data 获取
            if key in source_ctx.node_data:
                transferred_data[key] = copy.deepcopy(source_ctx.node_data[key])
            # 从 variables 获取
            elif key in source_ctx.variables:
                transferred_data[key] = copy.deepcopy(source_ctx.variables[key])

        # 注入到目标上下文
        bridge_key = f"__bridge_{source_id}__"
        target_ctx.variables[bridge_key] = transferred_data

        # 记录日志
        self._record_log(request, success=True)

        logger.info(f"桥接成功: {source_id} -> {target_id}, 键: {request.requested_keys}")

        return BridgeResult(
            success=True,
            transferred_data=transferred_data,
        )

    def get_from_workflow(
        self,
        source_workflow_id: str,
        target_workflow_id: str,
        key: str,
    ) -> Any:
        """直接从工作流获取数据（需要已桥接）

        如果没有桥接，抛出 AccessDeniedError。

        参数：
            source_workflow_id: 源工作流ID
            target_workflow_id: 目标工作流ID
            key: 数据键

        返回：
            数据值

        异常：
            AccessDeniedError: 未授权访问
        """
        target_ctx = self._workflows.get(target_workflow_id)
        if not target_ctx:
            raise AccessDeniedError(f"目标工作流不存在: {target_workflow_id}")

        bridge_key = f"__bridge_{source_workflow_id}__"
        bridged_data = target_ctx.variables.get(bridge_key)

        if not bridged_data or key not in bridged_data:
            raise AccessDeniedError(
                f"未授权访问: {target_workflow_id} 未从 {source_workflow_id} 桥接 {key}"
            )

        return bridged_data[key]

    def get_transfer_logs(self) -> list[dict[str, Any]]:
        """获取所有传递日志

        返回：
            日志列表
        """
        return [
            {
                "source": log.source,
                "target": log.target,
                "keys": log.keys,
                "requester": log.requester,
                "timestamp": log.timestamp.isoformat(),
                "success": log.success,
                "error": log.error,
            }
            for log in self._transfer_logs
        ]

    def get_transfer_history(
        self,
        workflow_id: str,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """获取特定工作流的传递历史

        参数：
            workflow_id: 工作流ID
            direction: "incoming"（传入）, "outgoing"（传出）, "both"（全部）

        返回：
            日志列表
        """
        result = []

        for log in self._transfer_logs:
            if direction in ("outgoing", "both") and log.source == workflow_id:
                result.append(
                    {
                        "source": log.source,
                        "target": log.target,
                        "keys": log.keys,
                        "timestamp": log.timestamp.isoformat(),
                        "direction": "outgoing",
                    }
                )
            if direction in ("incoming", "both") and log.target == workflow_id:
                result.append(
                    {
                        "source": log.source,
                        "target": log.target,
                        "keys": log.keys,
                        "timestamp": log.timestamp.isoformat(),
                        "direction": "incoming",
                    }
                )

        return result

    def _record_log(
        self,
        request: BridgeRequest,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """记录传递日志"""
        log = TransferLog(
            source=request.source_workflow_id,
            target=request.target_workflow_id,
            keys=request.requested_keys,
            requester=request.requester,
            success=success,
            error=error,
        )
        self._transfer_logs.append(log)

    def _log_and_return_error(
        self,
        request: BridgeRequest,
        error_msg: str,
    ) -> BridgeResult:
        """记录错误日志并返回错误结果"""
        self._record_log(request, success=False, error=error_msg)
        logger.error(error_msg)
        return BridgeResult(success=False, error=error_msg)


# 导出
__all__ = [
    "AccessDeniedError",
    "AuthorizationDeniedError",
    "BridgeRequest",
    "BridgeResult",
    "AccessPolicy",
    "TransferLog",
    "SecureContextBridge",
]
