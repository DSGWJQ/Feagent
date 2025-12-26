"""AppendRunEventUseCase - 追加 Run 事件并驱动生命周期

业务场景:
    - 工作流执行过程中，将执行事件追加到 Run 记录
    - 事件驱动 Run 状态流转 (created → running → completed/failed)

职责:
    1. 获取 Run (确保存在)
    2. 追加 RunEvent (持久化)
    3. 根据事件驱动 Run 状态流转 (使用 CAS 保证并发安全)
    4. 管理事务边界 (commit/rollback)

状态流转规则:
    - 任意事件到来时: created → running (CAS 保证只有一个成功)
    - workflow_complete 事件: running → completed (CAS 防止终态覆盖)
    - workflow_error 事件: running → failed (CAS 防止终态覆盖)

并发安全:
    使用 update_status_if_current (CAS) 替代 count_by_run_id：
    - 避免 TOCTOU 竞态：多个并发事务同时看到 count=0
    - 防止状态覆盖：completed 状态不会被覆盖回 running
    - 原子条件更新：UPDATE ... WHERE status = expected
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.application.ports.transaction_manager import TransactionManager
from src.domain.entities.run_event import RunEvent
from src.domain.ports.run_event_repository import RunEventRepository
from src.domain.ports.run_repository import RunRepository
from src.domain.value_objects.run_status import RunStatus


@dataclass
class AppendRunEventInput:
    """追加 RunEvent 的输入参数

    Attributes:
        run_id: Run ID (必填)
        event_type: 事件类型 (如 node_start, workflow_complete)
        channel: 事件通道 (如 execution, planning)
        payload: 事件负载 (JSON 可序列化 dict)
    """

    run_id: str
    event_type: str
    channel: str
    payload: dict[str, Any] | None = None


class AppendRunEventUseCase:
    """追加 RunEvent 用例 (含生命周期驱动，并发安全)

    并发安全机制:
        - 使用 CAS (Compare-And-Swap) 条件更新
        - 每个事件都尝试触发 created → running
        - 终止事件使用 CAS 防止状态回退

    事务边界:
        - 成功: commit
        - 失败: rollback (best-effort)

    依赖:
        - RunRepository: 查询/条件更新 Run
        - RunEventRepository: 追加事件
        - TransactionManager: 事务控制
    """

    # 终止事件类型映射
    TERMINAL_EVENT_COMPLETED = "workflow_complete"
    TERMINAL_EVENT_FAILED = "workflow_error"

    def __init__(
        self,
        run_repository: RunRepository,
        run_event_repository: RunEventRepository,
        transaction_manager: TransactionManager,
    ) -> None:
        """初始化用例

        Args:
            run_repository: Run 仓储
            run_event_repository: RunEvent 仓储
            transaction_manager: 事务管理器
        """
        self.run_repository = run_repository
        self.run_event_repository = run_event_repository
        self.transaction_manager = transaction_manager

    def execute(self, input_data: AppendRunEventInput) -> RunEvent:
        """执行用例: 追加事件并 (可选) 更新 Run 状态

        并发安全:
            - 使用 CAS 条件更新，不依赖 count_by_run_id
            - 多个并发事件只有一个能成功触发状态流转
            - 终态不会被覆盖回中间态

        Args:
            input_data: 追加事件的输入参数

        Returns:
            持久化后的 RunEvent (包含自增 ID)

        Raises:
            NotFoundError: 当 Run 不存在时
        """
        try:
            # 1. 验证 Run 存在性（仅做存在性检查，不用于状态判断）
            self.run_repository.get_by_id(input_data.run_id)

            # 2. 尝试触发 created → running (CAS 保证只有一个成功)
            #    即使失败也不影响后续流程（说明已被其他事务触发）
            self.run_repository.update_status_if_current(
                input_data.run_id,
                current_status=RunStatus.CREATED,
                target_status=RunStatus.RUNNING,
            )

            # 3. 处理终止事件 (CAS 防止状态覆盖)
            #    注意：不需要再次尝试 created → running，上面已经尝试过了
            if input_data.event_type == self.TERMINAL_EVENT_COMPLETED:
                # 尝试 complete（仅当当前为 running 才会成功）
                self.run_repository.update_status_if_current(
                    input_data.run_id,
                    current_status=RunStatus.RUNNING,
                    target_status=RunStatus.COMPLETED,
                    finished_at=datetime.now(UTC),
                )
            elif input_data.event_type == self.TERMINAL_EVENT_FAILED:
                self.run_repository.update_status_if_current(
                    input_data.run_id,
                    current_status=RunStatus.RUNNING,
                    target_status=RunStatus.FAILED,
                    finished_at=datetime.now(UTC),
                )

            # 4. 创建 RunEvent 实体
            event = RunEvent.create(
                run_id=input_data.run_id,
                event_type=input_data.event_type,
                channel=input_data.channel,
                payload=input_data.payload,
            )

            # 5. 持久化事件 (获取自增 ID)
            persisted_event = self.run_event_repository.append(event)

            # 6. 提交事务
            self.transaction_manager.commit()

            return persisted_event

        except Exception:
            # 尽力回滚 (best-effort rollback)
            try:
                self.transaction_manager.rollback()
            except Exception:
                pass  # 忽略回滚失败，优先抛出原始异常
            raise
