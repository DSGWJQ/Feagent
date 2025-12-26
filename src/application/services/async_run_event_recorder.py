"""AsyncRunEventRecorder - 非阻塞事件落库服务

职责：
    将 SSE 事件以非阻塞方式写入 run_events 表，
    使用 asyncio.Queue + 后台 worker 实现不阻塞 SSE 输出。

设计原则：
    - 非阻塞：emit() 只做 put_nowait，不等待 DB 写入
    - Best-effort：队列满时丢弃，不影响 SSE 输出
    - 背压控制：队列有 maxsize 限制，防止内存无限增长
    - 生命周期管理：支持 startup/shutdown

使用示例：
    # FastAPI startup
    @app.on_event("startup")
    async def startup():
        app.state.event_recorder = AsyncRunEventRecorder(session_factory=SessionLocal)
        await app.state.event_recorder.start()

    # FastAPI shutdown
    @app.on_event("shutdown")
    async def shutdown():
        await app.state.event_recorder.stop()

    # SSE 生成器中使用
    app.state.event_recorder.enqueue(run_id="run_xxx", sse_event={...})
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class EventRecord:
    """事件记录"""

    run_id: str
    event_type: str
    channel: str
    payload: dict[str, Any]


class AsyncRunEventRecorder:
    """异步事件录制器（非阻塞）

    特点：
        - 使用 asyncio.Queue 实现异步队列
        - 后台 worker 串行处理队列中的事件
        - put_nowait 实现非阻塞入队
        - 队列满时丢弃（best-effort）
    """

    DEFAULT_QUEUE_SIZE = 1000
    DEFAULT_WORKER_COUNT = 1

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        queue_size: int = DEFAULT_QUEUE_SIZE,
        worker_count: int = DEFAULT_WORKER_COUNT,
        logger: logging.Logger | None = None,
    ) -> None:
        """初始化录制器

        Args:
            session_factory: Session 工厂函数
            queue_size: 队列大小（满时丢弃新事件）
            worker_count: worker 数量（通常 1 个即可）
            logger: 日志记录器
        """
        self._session_factory = session_factory
        self._queue_size = queue_size
        self._worker_count = worker_count
        self._logger = logger or logging.getLogger(__name__)

        self._queue: asyncio.Queue[EventRecord | None] = asyncio.Queue(maxsize=queue_size)
        self._workers: list[asyncio.Task[None]] = []
        self._running = False

        # 统计信息
        self._enqueued_count = 0
        self._dropped_count = 0
        self._processed_count = 0
        self._failed_count = 0

    async def start(self) -> None:
        """启动后台 worker

        应在 FastAPI startup 中调用。
        """
        if self._running:
            return

        self._running = True
        for i in range(self._worker_count):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)

        self._logger.info(
            "AsyncRunEventRecorder started with %d worker(s), queue_size=%d",
            self._worker_count,
            self._queue_size,
        )

    async def stop(self, timeout: float = 5.0) -> None:
        """停止后台 worker

        Args:
            timeout: 等待 worker 完成的超时时间（秒）

        应在 FastAPI shutdown 中调用。
        """
        if not self._running:
            return

        self._running = False

        # 发送停止信号
        for _ in self._workers:
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

        # 等待 worker 完成
        if self._workers:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=timeout,
                )
            except TimeoutError:
                self._logger.warning("AsyncRunEventRecorder stop timeout, cancelling workers")
                for task in self._workers:
                    task.cancel()

        self._workers.clear()
        self._logger.info(
            "AsyncRunEventRecorder stopped. Stats: enqueued=%d, dropped=%d, "
            "processed=%d, failed=%d",
            self._enqueued_count,
            self._dropped_count,
            self._processed_count,
            self._failed_count,
        )

    def enqueue(
        self,
        *,
        run_id: str | None,
        sse_event: Mapping[str, Any],
    ) -> bool:
        """非阻塞入队事件

        Args:
            run_id: Run ID（为 None 或空时跳过）
            sse_event: SSE 事件 dict

        Returns:
            True 表示成功入队；False 表示跳过或队列满
        """
        # run_id 缺失：跳过
        if not run_id:
            return False

        # 提取 type/channel
        event_type = sse_event.get("type")
        channel = sse_event.get("channel")

        # 缺少必填字段：跳过
        if not event_type or not channel:
            return False

        # 构造 payload（去掉 type/channel）
        payload = dict(sse_event)
        payload.pop("type", None)
        payload.pop("channel", None)

        # 兜底 JSON 化
        payload = self._safe_json_payload(payload)

        record = EventRecord(
            run_id=run_id,
            event_type=str(event_type),
            channel=str(channel),
            payload=payload,
        )

        try:
            self._queue.put_nowait(record)
            self._enqueued_count += 1
            return True
        except asyncio.QueueFull:
            self._dropped_count += 1
            self._logger.debug(
                "AsyncRunEventRecorder queue full, dropping event: run_id=%s, type=%s",
                run_id,
                event_type,
            )
            return False

    async def _worker(self, worker_id: int) -> None:
        """后台 worker

        从队列中取出事件并写入数据库。
        """
        self._logger.debug("Worker %d started", worker_id)

        while self._running or not self._queue.empty():
            try:
                record = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
            except TimeoutError:
                continue

            # 停止信号
            if record is None:
                break

            # 在线程池中执行同步 DB 写入
            try:
                await asyncio.to_thread(self._write_event, record)
                self._processed_count += 1
            except Exception as exc:
                self._failed_count += 1
                self._logger.debug(
                    "Worker %d failed to write event: run_id=%s, error=%s",
                    worker_id,
                    record.run_id,
                    exc,
                )
            finally:
                self._queue.task_done()

        self._logger.debug("Worker %d stopped", worker_id)

    def _write_event(self, record: EventRecord) -> None:
        """同步写入事件（在线程池中执行）"""
        session = self._session_factory()
        try:
            # 延迟导入：避免循环依赖
            from src.application.use_cases.append_run_event import (
                AppendRunEventInput,
                AppendRunEventUseCase,
            )
            from src.infrastructure.database.repositories.run_event_repository import (
                SQLAlchemyRunEventRepository,
            )
            from src.infrastructure.database.repositories.run_repository import (
                SQLAlchemyRunRepository,
            )
            from src.infrastructure.database.transaction_manager import (
                SQLAlchemyTransactionManager,
            )

            use_case = AppendRunEventUseCase(
                run_repository=SQLAlchemyRunRepository(session),
                run_event_repository=SQLAlchemyRunEventRepository(session),
                transaction_manager=SQLAlchemyTransactionManager(session),
            )

            use_case.execute(
                AppendRunEventInput(
                    run_id=record.run_id,
                    event_type=record.event_type,
                    channel=record.channel,
                    payload=record.payload,
                )
            )
        finally:
            session.close()

    def _safe_json_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """安全 JSON 化 payload"""
        try:
            json_str = json.dumps(payload, ensure_ascii=False, default=str)
            return json.loads(json_str)
        except Exception:
            return {"raw": str(payload)}

    @property
    def stats(self) -> dict[str, int]:
        """获取统计信息"""
        return {
            "enqueued": self._enqueued_count,
            "dropped": self._dropped_count,
            "processed": self._processed_count,
            "failed": self._failed_count,
            "pending": self._queue.qsize(),
        }


# 导出
__all__ = ["AsyncRunEventRecorder", "EventRecord"]
