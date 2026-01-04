"""ToolEngine - 工具引擎 - 阶段 2

业务定义：
- 启动时扫描工具目录并加载工具配置
- 维护工具索引，支持按名称/标签/分类查找
- 支持热更新（检测文件变化或手动触发重载）
- 提供事件订阅机制，通知工具变更

设计原则：
- 线程安全：使用锁保护并发访问
- 事件驱动：工具变更时发布事件
- 可扩展：支持自定义工具加载器
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.domain.entities.tool import Tool
from src.domain.services.tool_config_loader import ToolConfigLoader
from src.domain.services.tool_parameter_validator import (
    ToolParameterValidator,
    ToolValidationError,
    ValidationResult,
)
from src.domain.value_objects.tool_category import ToolCategory

if TYPE_CHECKING:
    from src.domain.services.tool_executor import (
        ToolExecutionContext,
        ToolExecutionResult,
    )
    from src.domain.services.tool_knowledge_store import (
        ToolCallRecord,
        ToolCallSummary,
        ToolKnowledgeStore,
    )

logger = logging.getLogger(__name__)

# =============================================================================
# 异常定义
# =============================================================================


class ToolNotFoundError(Exception):
    """工具未找到异常"""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"工具未找到: {tool_name}")


# =============================================================================
# 事件系统
# =============================================================================


class ToolEngineEventType(str, Enum):
    """工具引擎事件类型"""

    TOOL_LOADED = "tool_loaded"  # 工具加载完成
    TOOL_ADDED = "tool_added"  # 工具添加
    TOOL_UPDATED = "tool_updated"  # 工具更新
    TOOL_REMOVED = "tool_removed"  # 工具移除
    RELOAD_STARTED = "reload_started"  # 重载开始
    RELOAD_COMPLETED = "reload_completed"  # 重载完成
    LOAD_ERROR = "load_error"  # 加载错误
    VALIDATION_ERROR = "validation_error"  # 参数验证错误
    EXECUTION_STARTED = "execution_started"  # 执行开始
    EXECUTION_COMPLETED = "execution_completed"  # 执行完成
    EXECUTION_FAILED = "execution_failed"  # 执行失败


@dataclass
class ToolEngineEvent:
    """工具引擎事件"""

    event_type: ToolEngineEventType
    tool_name: str | None = None
    tool: Tool | None = None
    error: str | None = None
    validation_errors: list | None = None  # 验证错误列表
    execution_result: Any | None = None  # 执行结果
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# =============================================================================
# 配置
# =============================================================================


@dataclass
class ToolEngineConfig:
    """工具引擎配置

    属性说明：
    - tools_directory: 工具配置目录
    - auto_reload: 是否支持自动重载
    - reload_interval: 自动重载间隔（秒）
    - watch_for_changes: 是否监听文件变化（使用 watchdog）
    - strict_validation: 是否启用严格参数验证（检测多余参数）
    """

    tools_directory: str = "tools"
    auto_reload: bool = True
    reload_interval: float = 5.0
    watch_for_changes: bool = False
    strict_validation: bool = False


# =============================================================================
# 工具索引
# =============================================================================


class ToolIndex:
    """工具索引

    维护工具的多种索引，支持快速查找：
    - 按名称索引
    - 按标签索引
    - 按分类索引
    """

    def __init__(self):
        self._by_name: dict[str, Tool] = {}
        self._by_tag: dict[str, set[str]] = defaultdict(set)  # tag -> set of tool names
        self._by_category: dict[ToolCategory, set[str]] = defaultdict(set)
        self._lock = threading.RLock()

    def add(self, tool: Tool) -> None:
        """添加工具到索引"""
        with self._lock:
            self._by_name[tool.name] = tool
            # 更新标签索引
            for tag in tool.tags:
                self._by_tag[tag].add(tool.name)
            # 更新分类索引
            self._by_category[tool.category].add(tool.name)

    def get(self, name: str) -> Tool | None:
        """按名称获取工具"""
        with self._lock:
            return self._by_name.get(name)

    def remove(self, name: str) -> Tool | None:
        """从索引移除工具"""
        with self._lock:
            tool = self._by_name.pop(name, None)
            if tool:
                # 移除标签索引
                for tag in tool.tags:
                    self._by_tag[tag].discard(name)
                    if not self._by_tag[tag]:
                        del self._by_tag[tag]
                # 移除分类索引
                self._by_category[tool.category].discard(name)
                if not self._by_category[tool.category]:
                    del self._by_category[tool.category]
            return tool

    def update(self, tool: Tool) -> None:
        """更新工具（先移除再添加）"""
        with self._lock:
            self.remove(tool.name)
            self.add(tool)

    def find_by_tag(self, tag: str) -> list[Tool]:
        """按单个标签查找"""
        with self._lock:
            names = self._by_tag.get(tag, set())
            return [self._by_name[name] for name in names if name in self._by_name]

    def find_by_tags(self, tags: list[str]) -> list[Tool]:
        """按多个标签查找（AND 逻辑）"""
        with self._lock:
            if not tags:
                return []
            # 获取所有标签对应的工具名集合的交集
            result_names = None
            for tag in tags:
                tag_names = self._by_tag.get(tag, set())
                if result_names is None:
                    result_names = tag_names.copy()
                else:
                    result_names &= tag_names
            if result_names is None:
                return []
            return [self._by_name[name] for name in result_names if name in self._by_name]

    def find_by_any_tag(self, tags: list[str]) -> list[Tool]:
        """按任意标签查找（OR 逻辑）"""
        with self._lock:
            result_names: set[str] = set()
            for tag in tags:
                result_names |= self._by_tag.get(tag, set())
            return [self._by_name[name] for name in result_names if name in self._by_name]

    def find_by_category(self, category: ToolCategory) -> list[Tool]:
        """按分类查找"""
        with self._lock:
            names = self._by_category.get(category, set())
            return [self._by_name[name] for name in names if name in self._by_name]

    def list_all(self) -> list[Tool]:
        """列出所有工具"""
        with self._lock:
            return list(self._by_name.values())

    def list_names(self) -> list[str]:
        """列出所有工具名称"""
        with self._lock:
            return list(self._by_name.keys())

    def clear(self) -> None:
        """清空索引"""
        with self._lock:
            self._by_name.clear()
            self._by_tag.clear()
            self._by_category.clear()

    def __contains__(self, name: str) -> bool:
        """检查工具是否存在"""
        with self._lock:
            return name in self._by_name

    @property
    def count(self) -> int:
        """工具数量"""
        with self._lock:
            return len(self._by_name)


# =============================================================================
# 工具引擎
# =============================================================================


class ToolEngine:
    """工具引擎

    核心功能：
    1. 启动时扫描工具目录并加载
    2. 维护工具索引
    3. 支持按名称/标签/分类查找
    4. 支持热更新（reload）
    5. 事件订阅机制
    """

    def __init__(self, config: ToolEngineConfig | None = None):
        """初始化工具引擎

        参数：
            config: 引擎配置（可选，使用默认配置）
        """
        self._config = config or ToolEngineConfig()
        self._index = ToolIndex()
        self._loader = ToolConfigLoader()
        self._validator = ToolParameterValidator(strict_mode=self._config.strict_validation)
        self._is_loaded = False
        self._load_errors: list[tuple[str, str]] = []
        self._last_reload_at: datetime | None = None
        self._tool_file_map: dict[str, str] = {}  # tool_name -> file_path
        self._file_tool_map: dict[str, str] = {}  # file_path -> tool_name
        self._subscribers: list[Callable[[ToolEngineEvent], None]] = []
        self._lock = threading.RLock()

        # 执行器和知识库记录器
        self._executors: dict[str, Any] = {}  # handler_name -> executor
        self._knowledge_recorder: Any | None = None
        self._knowledge_store: ToolKnowledgeStore | None = None

    @property
    def config(self) -> ToolEngineConfig:
        """获取配置"""
        return self._config

    @property
    def is_loaded(self) -> bool:
        """是否已加载"""
        return self._is_loaded

    @property
    def tool_count(self) -> int:
        """工具数量"""
        return self._index.count

    @property
    def load_errors(self) -> list[tuple[str, str]]:
        """加载错误列表"""
        return self._load_errors.copy()

    # =========================================================================
    # 加载与重载
    # =========================================================================

    async def load(self) -> None:
        """加载工具目录

        扫描配置目录，加载所有有效的工具配置
        """
        with self._lock:
            self._index.clear()
            self._load_errors.clear()
            self._tool_file_map.clear()
            self._file_tool_map.clear()

            tools_dir = Path(self._config.tools_directory)
            if not tools_dir.exists():
                self._is_loaded = True
                self._last_reload_at = datetime.now(UTC)
                return

            configs, errors = self._loader.load_from_directory_with_errors(str(tools_dir))

            self._load_errors = errors

            for config in configs:
                try:
                    tool = self._loader.to_tool_entity(config)
                    self._index.add(tool)

                    # 记录文件映射
                    file_path = self._find_tool_file(tools_dir, config.name)
                    if file_path:
                        self._tool_file_map[tool.name] = file_path
                        self._file_tool_map[file_path] = tool.name

                    self._emit_event(
                        ToolEngineEvent(
                            event_type=ToolEngineEventType.TOOL_LOADED,
                            tool_name=tool.name,
                            tool=tool,
                        )
                    )
                except Exception as e:
                    self._load_errors.append((config.name, str(e)))
                    self._emit_event(
                        ToolEngineEvent(
                            event_type=ToolEngineEventType.LOAD_ERROR,
                            tool_name=config.name,
                            error=str(e),
                        )
                    )

            self._is_loaded = True
            self._last_reload_at = datetime.now(UTC)

    async def reload(self) -> dict[str, list[str]]:
        """重载工具目录

        检测变更（新增/修改/删除）并更新索引

        返回：
            变更信息字典：{"added": [...], "modified": [...], "removed": [...]}
        """
        changes: dict[str, list[str]] = {
            "added": [],
            "modified": [],
            "removed": [],
        }

        with self._lock:
            self._emit_event(ToolEngineEvent(event_type=ToolEngineEventType.RELOAD_STARTED))

            tools_dir = Path(self._config.tools_directory)
            if not tools_dir.exists():
                # 目录不存在，移除所有工具
                for name in self._index.list_names():
                    self._index.remove(name)
                    changes["removed"].append(name)
                    self._emit_event(
                        ToolEngineEvent(
                            event_type=ToolEngineEventType.TOOL_REMOVED,
                            tool_name=name,
                        )
                    )
                self._last_reload_at = datetime.now(UTC)
                return changes

            # 加载当前目录中的所有工具
            configs, errors = self._loader.load_from_directory_with_errors(str(tools_dir))
            self._load_errors = errors

            # 构建当前配置映射
            current_configs: dict[str, Any] = {}
            for config in configs:
                current_configs[config.name] = config

            # 检测新增和修改
            for name, config in current_configs.items():
                existing_tool = self._index.get(name)
                try:
                    new_tool = self._loader.to_tool_entity(config)

                    if existing_tool is None:
                        # 新增
                        self._index.add(new_tool)
                        changes["added"].append(name)
                        self._emit_event(
                            ToolEngineEvent(
                                event_type=ToolEngineEventType.TOOL_ADDED,
                                tool_name=name,
                                tool=new_tool,
                            )
                        )
                    else:
                        # 检查是否修改（比较版本或描述）
                        if (
                            existing_tool.version != new_tool.version
                            or existing_tool.description != new_tool.description
                        ):
                            self._index.update(new_tool)
                            changes["modified"].append(name)
                            self._emit_event(
                                ToolEngineEvent(
                                    event_type=ToolEngineEventType.TOOL_UPDATED,
                                    tool_name=name,
                                    tool=new_tool,
                                )
                            )

                    # 更新文件映射
                    file_path = self._find_tool_file(tools_dir, name)
                    if file_path:
                        self._tool_file_map[name] = file_path
                        self._file_tool_map[file_path] = name

                except Exception as e:
                    self._load_errors.append((name, str(e)))

            # 检测删除
            current_names = set(current_configs.keys())
            existing_names = set(self._index.list_names())
            removed_names = existing_names - current_names

            for name in removed_names:
                self._index.remove(name)
                changes["removed"].append(name)
                # 清理文件映射
                if name in self._tool_file_map:
                    file_path = self._tool_file_map.pop(name)
                    self._file_tool_map.pop(file_path, None)
                self._emit_event(
                    ToolEngineEvent(
                        event_type=ToolEngineEventType.TOOL_REMOVED,
                        tool_name=name,
                    )
                )

            self._last_reload_at = datetime.now(UTC)

            self._emit_event(ToolEngineEvent(event_type=ToolEngineEventType.RELOAD_COMPLETED))

        return changes

    # =========================================================================
    # 工具查找
    # =========================================================================

    def get(self, name: str) -> Tool | None:
        """按名称获取工具

        参数：
            name: 工具名称

        返回：
            Tool 实例或 None
        """
        return self._index.get(name)

    def get_or_raise(self, name: str) -> Tool:
        """按名称获取工具，不存在则抛出异常

        参数：
            name: 工具名称

        返回：
            Tool 实例

        抛出：
            ToolNotFoundError: 工具不存在时
        """
        tool = self._index.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        return tool

    def find_by_tag(self, tag: str) -> list[Tool]:
        """按单个标签查找工具

        参数：
            tag: 标签

        返回：
            匹配的工具列表
        """
        return self._index.find_by_tag(tag)

    def find_by_tags(self, tags: list[str]) -> list[Tool]:
        """按多个标签查找工具（AND 逻辑）

        参数：
            tags: 标签列表

        返回：
            同时具有所有标签的工具列表
        """
        return self._index.find_by_tags(tags)

    def find_by_any_tag(self, tags: list[str]) -> list[Tool]:
        """按任意标签查找工具（OR 逻辑）

        参数：
            tags: 标签列表

        返回：
            具有任一标签的工具列表
        """
        return self._index.find_by_any_tag(tags)

    def find_by_category(self, category: ToolCategory) -> list[Tool]:
        """按分类查找工具

        参数：
            category: 工具分类

        返回：
            该分类下的工具列表
        """
        return self._index.find_by_category(category)

    def list_all(self) -> list[Tool]:
        """列出所有工具

        返回：
            所有工具列表
        """
        return self._index.list_all()

    def list_names(self) -> list[str]:
        """列出所有工具名称

        返回：
            工具名称列表
        """
        return self._index.list_names()

    def search(self, keyword: str) -> list[Tool]:
        """搜索工具（名称/描述模糊匹配）

        参数：
            keyword: 搜索关键词

        返回：
            匹配的工具列表
        """
        keyword_lower = keyword.lower()
        results = []
        for tool in self._index.list_all():
            if keyword_lower in tool.name.lower() or keyword_lower in tool.description.lower():
                results.append(tool)
        return results

    # =========================================================================
    # 工具注册
    # =========================================================================

    def register(self, tool: Tool) -> None:
        """手动注册工具

        参数：
            tool: Tool 实例
        """
        with self._lock:
            self._index.add(tool)
            self._emit_event(
                ToolEngineEvent(
                    event_type=ToolEngineEventType.TOOL_ADDED,
                    tool_name=tool.name,
                    tool=tool,
                )
            )

    def unregister(self, name: str) -> Tool | None:
        """注销工具

        参数：
            name: 工具名称

        返回：
            被移除的工具或 None
        """
        with self._lock:
            tool = self._index.remove(name)
            if tool:
                # 清理文件映射
                if name in self._tool_file_map:
                    file_path = self._tool_file_map.pop(name)
                    self._file_tool_map.pop(file_path, None)
                self._emit_event(
                    ToolEngineEvent(
                        event_type=ToolEngineEventType.TOOL_REMOVED,
                        tool_name=name,
                        tool=tool,
                    )
                )
            return tool

    # =========================================================================
    # 事件订阅
    # =========================================================================

    def subscribe(self, callback: Callable[[ToolEngineEvent], None]) -> None:
        """订阅事件

        参数：
            callback: 事件回调函数
        """
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ToolEngineEvent], None]) -> None:
        """取消订阅

        参数：
            callback: 事件回调函数
        """
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    # =========================================================================
    # 统计信息
    # =========================================================================

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息

        返回：
            统计信息字典
        """
        with self._lock:
            by_category: dict[str, int] = defaultdict(int)
            for tool in self._index.list_all():
                by_category[tool.category.value] += 1

            return {
                "total_tools": self._index.count,
                "by_category": dict(by_category),
                "load_errors": len(self._load_errors),
                "last_reload_at": (
                    self._last_reload_at.isoformat() if self._last_reload_at else None
                ),
                "is_loaded": self._is_loaded,
            }

    # =========================================================================
    # 参数验证
    # =========================================================================

    def validate_params(self, tool_name: str, params: dict[str, Any]) -> ValidationResult:
        """验证工具调用参数

        参数：
            tool_name: 工具名称
            params: 调用参数

        返回：
            ValidationResult 验证结果

        抛出：
            ToolNotFoundError: 工具不存在时
        """
        tool = self.get_or_raise(tool_name)
        result = self._validator.validate(tool, params)

        # 验证失败时发送事件
        if not result.is_valid:
            self._emit_event(
                ToolEngineEvent(
                    event_type=ToolEngineEventType.VALIDATION_ERROR,
                    tool_name=tool_name,
                    tool=tool,
                    error=f"参数验证失败: {len(result.errors)} 个错误",
                    validation_errors=[e.to_dict() for e in result.errors],
                )
            )

        return result

    def validate_params_or_raise(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """验证工具调用参数，失败时抛出异常

        参数：
            tool_name: 工具名称
            params: 调用参数

        返回：
            验证后的参数（包含默认值）

        抛出：
            ToolNotFoundError: 工具不存在时
            ToolValidationError: 参数验证失败时
        """
        tool = self.get_or_raise(tool_name)
        result = self._validator.validate(tool, params)

        if not result.is_valid:
            # 发送事件
            self._emit_event(
                ToolEngineEvent(
                    event_type=ToolEngineEventType.VALIDATION_ERROR,
                    tool_name=tool_name,
                    tool=tool,
                    error=f"参数验证失败: {len(result.errors)} 个错误",
                    validation_errors=[e.to_dict() for e in result.errors],
                )
            )
            raise ToolValidationError(tool_name=tool_name, errors=result.errors)

        return result.validated_params

    # =========================================================================
    # 执行器管理
    # =========================================================================

    def register_executor(self, handler_name: str, executor: Any) -> None:
        """注册工具执行器

        参数：
            handler_name: 处理器名称（与工具配置中的 entry.handler 对应）
            executor: 执行器实例
        """
        with self._lock:
            self._executors[handler_name] = executor
            logger.debug(f"Registered executor: {handler_name}")

    def unregister_executor(self, handler_name: str) -> None:
        """注销工具执行器

        参数：
            handler_name: 处理器名称
        """
        with self._lock:
            self._executors.pop(handler_name, None)

    def get_executor(self, handler_name: str) -> Any | None:
        """获取执行器

        参数：
            handler_name: 处理器名称

        返回：
            执行器实例或 None
        """
        return self._executors.get(handler_name)

    def set_knowledge_recorder(self, recorder: Any) -> None:
        """设置知识库记录器

        参数：
            recorder: KnowledgeRecorder 实例
        """
        self._knowledge_recorder = recorder

    def set_knowledge_store(self, store: "ToolKnowledgeStore") -> None:
        """设置知识库存储

        参数：
            store: ToolKnowledgeStore 实例
        """
        self._knowledge_store = store

    @property
    def knowledge_store(self) -> "ToolKnowledgeStore | None":
        """获取知识库存储"""
        return self._knowledge_store

    # =========================================================================
    # 工具执行
    # =========================================================================

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        context: "ToolExecutionContext",
    ) -> "ToolExecutionResult":
        """执行工具

        参数：
            tool_name: 工具名称
            params: 调用参数
            context: 执行上下文

        返回：
            ToolExecutionResult 执行结果
        """
        from src.domain.services.tool_executor import ToolExecutionResult

        start_time = time.time()

        # 1. 检查工具是否存在
        tool = self.get(tool_name)
        if not tool:
            return ToolExecutionResult.failure(
                tool_name=tool_name,
                error=f"工具未找到: {tool_name}",
                error_type="tool_not_found",
            )

        # 2. 验证参数
        validation_result = self.validate_params(tool_name, params)
        if not validation_result.is_valid:
            return ToolExecutionResult.validation_failure(
                tool_name=tool_name,
                validation_errors=[
                    {"parameter": e.parameter_name, "error": e.message}
                    for e in validation_result.errors
                ],
            )

        # 3. 获取执行器
        handler_name = self._get_handler_name(tool)
        executor = self.get_executor(handler_name)
        if not executor:
            return ToolExecutionResult.failure(
                tool_name=tool_name,
                error=f"执行器未找到: {handler_name}",
                error_type="executor_not_found",
            )

        # 4. 发送执行开始事件
        self._emit_event(
            ToolEngineEvent(
                event_type=ToolEngineEventType.EXECUTION_STARTED,
                tool_name=tool_name,
                tool=tool,
            )
        )

        # 5. 执行工具
        try:
            result = await self._execute_with_timeout(
                executor=executor,
                tool=tool,
                params=validation_result.validated_params,
                context=context,
                timeout=context.timeout,
            )

            execution_time = time.time() - start_time
            exec_result = ToolExecutionResult.success(
                tool_name=tool_name,
                output=result,
                execution_time=execution_time,
            )

            # 发送执行完成事件
            self._emit_event(
                ToolEngineEvent(
                    event_type=ToolEngineEventType.EXECUTION_COMPLETED,
                    tool_name=tool_name,
                    tool=tool,
                    execution_result=exec_result,
                )
            )

            # 记录到知识库
            await self._record_execution(exec_result, context, validation_result.validated_params)

            return exec_result

        except TimeoutError:
            execution_time = time.time() - start_time
            exec_result = ToolExecutionResult.failure(
                tool_name=tool_name,
                error=f"执行超时 ({context.timeout}s)",
                error_type="timeout",
                execution_time=execution_time,
            )

            self._emit_event(
                ToolEngineEvent(
                    event_type=ToolEngineEventType.EXECUTION_FAILED,
                    tool_name=tool_name,
                    tool=tool,
                    error=exec_result.error,
                    execution_result=exec_result,
                )
            )

            await self._record_execution(exec_result, context, validation_result.validated_params)
            return exec_result

        except Exception as e:
            execution_time = time.time() - start_time
            exec_result = ToolExecutionResult.failure(
                tool_name=tool_name,
                error=str(e),
                error_type="execution_error",
                execution_time=execution_time,
            )

            self._emit_event(
                ToolEngineEvent(
                    event_type=ToolEngineEventType.EXECUTION_FAILED,
                    tool_name=tool_name,
                    tool=tool,
                    error=str(e),
                    execution_result=exec_result,
                )
            )

            await self._record_execution(exec_result, context, validation_result.validated_params)
            return exec_result

    async def _execute_with_timeout(
        self,
        executor: Any,
        tool: Tool,
        params: dict[str, Any],
        context: "ToolExecutionContext",
        timeout: float,
    ) -> dict[str, Any]:
        """带超时的执行

        参数：
            executor: 执行器
            tool: 工具定义
            params: 验证后的参数
            context: 执行上下文
            timeout: 超时时间

        返回：
            执行结果

        抛出：
            asyncio.TimeoutError: 超时时
        """
        return await asyncio.wait_for(
            executor.execute(tool, params, context),
            timeout=timeout,
        )

    def _get_handler_name(self, tool: Tool) -> str:
        """获取工具的处理器名称

        参数：
            tool: 工具定义

        返回：
            处理器名称
        """
        # 从工具的 implementation_config 获取 handler
        # 默认使用工具名称作为 handler
        if tool.implementation_config:
            return tool.implementation_config.get("handler", tool.name)
        return tool.name

    async def _record_execution(
        self,
        result: "ToolExecutionResult",
        context: "ToolExecutionContext",
        params: dict[str, Any] | None = None,
    ) -> None:
        """记录执行结果到知识库

        参数：
            result: 执行结果
            context: 执行上下文
            params: 调用参数
        """
        # 使用新的知识库存储
        if self._knowledge_store:
            try:
                from src.domain.services.tool_knowledge_store import ToolCallRecord

                metadata: dict[str, Any] = {}
                if context.trace_id:
                    metadata["trace_id"] = context.trace_id
                    metadata["tool_call_id"] = context.trace_id
                run_id = None
                if isinstance(context.variables, dict):
                    run_id = context.variables.get("run_id")
                if isinstance(run_id, str) and run_id.strip():
                    metadata["run_id"] = run_id.strip()

                record = ToolCallRecord.from_execution_result(
                    result=result,
                    params=params or {},
                    caller_id=context.caller_id,
                    caller_type=context.caller_type,
                    conversation_id=context.conversation_id,
                    workflow_id=context.workflow_id,
                    metadata=metadata or None,
                )
                await self._knowledge_store.save(record)
            except Exception as e:
                logger.error(f"Failed to save to knowledge store: {e}")

        # 兼容旧的知识库记录器
        if self._knowledge_recorder:
            try:
                record_data = {
                    "tool_name": result.tool_name,
                    "success": result.is_success,
                    "output": result.output if result.is_success else None,
                    "error": result.error,
                    "error_type": result.error_type,
                    "execution_time": result.execution_time,
                    "caller_id": context.caller_id,
                    "conversation_id": context.conversation_id,
                    "workflow_id": context.workflow_id,
                    "executed_at": result.executed_at.isoformat() if result.executed_at else None,
                }
                await self._knowledge_recorder.record(record_data)
            except Exception as e:
                logger.error(f"Failed to record execution: {e}")

    # =========================================================================
    # 私有方法
    # =========================================================================

    def _emit_event(self, event: ToolEngineEvent) -> None:
        """发布事件"""
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                pass  # 忽略回调错误

    def _find_tool_file(self, tools_dir: Path, tool_name: str) -> str | None:
        """查找工具文件路径"""
        for ext in [".yaml", ".yml"]:
            file_path = tools_dir / f"{tool_name}{ext}"
            if file_path.exists():
                return str(file_path)
        # 如果文件名与工具名不匹配，扫描目录
        for file_path in tools_dir.glob("*.yaml"):
            if file_path.stem == tool_name:
                return str(file_path)
        for file_path in tools_dir.glob("*.yml"):
            if file_path.stem == tool_name:
                return str(file_path)
        return None

    # =========================================================================
    # 知识库查询接口
    # =========================================================================

    async def query_call_records(
        self,
        conversation_id: str | None = None,
        tool_name: str | None = None,
        caller_id: str | None = None,
        limit: int = 100,
    ) -> list["ToolCallRecord"]:
        """查询调用记录

        参数：
            conversation_id: 会话 ID（可选）
            tool_name: 工具名称（可选）
            caller_id: 调用者 ID（可选）
            limit: 返回数量限制

        返回：
            调用记录列表
        """
        if not self._knowledge_store:
            return []

        return await self._knowledge_store.query(
            conversation_id=conversation_id,
            tool_name=tool_name,
            caller_id=caller_id,
            limit=limit,
        )

    async def get_call_summary(self, conversation_id: str) -> "ToolCallSummary | None":
        """获取会话的调用摘要

        参数：
            conversation_id: 会话 ID

        返回：
            调用摘要或 None
        """
        if not self._knowledge_store:
            return None

        return await self._knowledge_store.get_summary(conversation_id)

    async def get_call_statistics(self) -> dict[str, Any]:
        """获取全局调用统计

        返回：
            统计信息字典
        """
        if not self._knowledge_store:
            return {}

        return await self._knowledge_store.get_statistics()
