"""扩展API模块（Extension API）

Phase 4.3: 扩展API

组件：
- PluginManager: 插件管理器
- Plugin: 插件定义
- CustomNodeRegistry: 自定义节点注册表
- NodeDefinition: 节点定义
- NodeExecutor: 节点执行器基类
- HookSystem: 钩子系统
- ExtensionAPIFactory: 工厂类

功能：
- 插件注册/卸载/生命周期管理
- 自定义节点类型扩展
- 钩子系统实现AOP
- 依赖管理和版本控制

设计原则：
- 开放扩展：支持用户自定义
- 安全隔离：插件间相互隔离
- 生命周期：完整的激活/停用流程

"""

import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============ 异常定义 ============


class PluginDependencyError(Exception):
    """插件依赖错误"""

    pass


class PluginVersionConflictError(Exception):
    """插件版本冲突错误"""

    pass


class HookAbort(Exception):
    """钩子中止异常"""

    pass


# ============ 插件状态 ============


class PluginStatus(Enum):
    """插件状态"""

    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


# ============ 插件定义 ============


@dataclass
class Plugin:
    """插件定义

    属性：
        id: 插件唯一标识
        name: 插件名称
        version: 版本号
        author: 作者
        dependencies: 依赖的其他插件ID列表
        on_activate: 激活时的回调
        on_deactivate: 停用时的回调
        status: 当前状态
    """

    id: str
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    on_activate: Callable | None = None
    on_deactivate: Callable | None = None
    status: PluginStatus = PluginStatus.REGISTERED
    metadata: dict[str, Any] = field(default_factory=dict)


# ============ 插件管理器 ============


class PluginManager:
    """插件管理器

    管理插件的注册、激活、停用和卸载。

    使用示例：
        manager = PluginManager()
        manager.register(plugin)
        await manager.activate(plugin.id)
    """

    def __init__(self):
        """初始化"""
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin, force: bool = False) -> None:
        """注册插件

        参数：
            plugin: 插件实例
            force: 是否强制覆盖已存在的插件

        异常：
            PluginDependencyError: 依赖未满足
            PluginVersionConflictError: 版本冲突
        """
        # 检查依赖
        for dep_id in plugin.dependencies:
            if dep_id not in self._plugins:
                raise PluginDependencyError(f"插件 {plugin.id} 依赖 {dep_id}，但该依赖未注册")

        # 检查版本冲突
        if plugin.id in self._plugins and not force:
            existing = self._plugins[plugin.id]
            if existing.version != plugin.version:
                raise PluginVersionConflictError(
                    f"插件 {plugin.id} 已存在版本 {existing.version}，无法注册版本 {plugin.version}"
                )

        self._plugins[plugin.id] = plugin
        logger.info(f"插件已注册: {plugin.id} v{plugin.version}")

    def unregister(self, plugin_id: str) -> bool:
        """卸载插件

        参数：
            plugin_id: 插件ID

        返回：
            是否成功卸载
        """
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            logger.info(f"插件已卸载: {plugin_id}")
            return True
        return False

    def has_plugin(self, plugin_id: str) -> bool:
        """检查插件是否存在"""
        return plugin_id in self._plugins

    def get_plugin(self, plugin_id: str) -> Plugin | None:
        """获取插件"""
        return self._plugins.get(plugin_id)

    async def activate(self, plugin_id: str) -> None:
        """激活插件

        参数：
            plugin_id: 插件ID

        异常：
            KeyError: 插件不存在
            Exception: 激活回调抛出的异常
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            raise KeyError(f"插件不存在: {plugin_id}")

        try:
            if plugin.on_activate:
                ctx = {"plugin_id": plugin_id}
                await plugin.on_activate(ctx)

            plugin.status = PluginStatus.ACTIVE
            logger.info(f"插件已激活: {plugin_id}")

        except Exception as e:
            plugin.status = PluginStatus.ERROR
            logger.error(f"插件激活失败 {plugin_id}: {e}")
            raise

    async def deactivate(self, plugin_id: str) -> None:
        """停用插件

        参数：
            plugin_id: 插件ID
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return

        try:
            if plugin.on_deactivate:
                ctx = {"plugin_id": plugin_id}
                await plugin.on_deactivate(ctx)

            plugin.status = PluginStatus.INACTIVE
            logger.info(f"插件已停用: {plugin_id}")

        except Exception as e:
            logger.error(f"插件停用失败 {plugin_id}: {e}")
            raise

    def list_plugins(self) -> list[Plugin]:
        """列出所有插件"""
        return list(self._plugins.values())


# ============ 节点执行器基类 ============


class NodeExecutor(ABC):
    """节点执行器抽象基类

    自定义节点需要继承此类并实现execute方法。

    使用示例：
        class MyExecutor(NodeExecutor):
            async def execute(self, config, inputs):
                return {"result": "done"}
    """

    @abstractmethod
    async def execute(self, config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        """执行节点逻辑

        参数：
            config: 节点配置
            inputs: 输入数据

        返回：
            输出数据
        """
        pass


# ============ 节点定义 ============


@dataclass
class NodeDefinition:
    """节点定义

    属性：
        type: 节点类型（唯一标识）
        name: 显示名称
        description: 描述
        category: 分类
        input_schema: 输入Schema
        output_schema: 输出Schema
        executor_class: 执行器类
    """

    type: str
    name: str
    description: str = ""
    category: str = "custom"
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    executor_class: type[NodeExecutor] | None = None
    icon: str = ""
    color: str = ""


# ============ 自定义节点注册表 ============


class CustomNodeRegistry:
    """自定义节点注册表

    管理自定义节点类型的注册和执行。

    使用示例：
        registry = CustomNodeRegistry()
        registry.register(node_def)
        result = await registry.execute("my_node", config, inputs)
    """

    def __init__(self):
        """初始化"""
        self._nodes: dict[str, NodeDefinition] = {}
        self._executors: dict[str, NodeExecutor] = {}

    def register(self, node_def: NodeDefinition) -> None:
        """注册节点定义

        参数：
            node_def: 节点定义
        """
        self._nodes[node_def.type] = node_def

        # 如果有执行器类，创建实例
        if node_def.executor_class:
            self._executors[node_def.type] = node_def.executor_class()

        logger.info(f"节点类型已注册: {node_def.type}")

    def unregister(self, node_type: str) -> bool:
        """注销节点类型"""
        if node_type in self._nodes:
            del self._nodes[node_type]
            if node_type in self._executors:
                del self._executors[node_type]
            return True
        return False

    def has_node_type(self, node_type: str) -> bool:
        """检查节点类型是否存在"""
        return node_type in self._nodes

    def get_node_definition(self, node_type: str) -> NodeDefinition | None:
        """获取节点定义"""
        return self._nodes.get(node_type)

    def get_executor(self, node_type: str) -> NodeExecutor | None:
        """获取节点执行器"""
        return self._executors.get(node_type)

    async def execute(
        self, node_type: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行节点

        参数：
            node_type: 节点类型
            config: 节点配置
            inputs: 输入数据

        返回：
            执行结果
        """
        executor = self._executors.get(node_type)
        if not executor:
            raise ValueError(f"节点类型 {node_type} 没有执行器")

        return await executor.execute(config, inputs)

    def list_by_category(self, category: str) -> list[NodeDefinition]:
        """按分类列出节点

        参数：
            category: 分类名称

        返回：
            该分类下的节点定义列表
        """
        return [node for node in self._nodes.values() if node.category == category]

    def list_all(self) -> list[NodeDefinition]:
        """列出所有节点定义"""
        return list(self._nodes.values())

    def list_categories(self) -> list[str]:
        """列出所有分类"""
        return list(set(node.category for node in self._nodes.values()))


# ============ 钩子处理器 ============


@dataclass
class HookHandler:
    """钩子处理器"""

    id: str
    hook_point: str
    handler: Callable
    priority: int = 50
    plugin_id: str | None = None


# ============ 钩子系统 ============


class HookSystem:
    """钩子系统

    实现AOP风格的扩展机制。

    使用示例：
        hooks = HookSystem()
        hooks.register("workflow:start", my_handler)
        await hooks.trigger("workflow:start", context)
    """

    # 内置钩子点
    BUILTIN_HOOK_POINTS = [
        "workflow:start",
        "workflow:end",
        "node:before_execute",
        "node:after_execute",
        "request:before",
        "request:after",
        "error:occurred",
    ]

    def __init__(self):
        """初始化"""
        self._handlers: dict[str, list[HookHandler]] = {}
        self._handler_map: dict[str, HookHandler] = {}

    def register(
        self, hook_point: str, handler: Callable, priority: int = 50, plugin_id: str | None = None
    ) -> str:
        """注册钩子处理器

        参数：
            hook_point: 钩子点名称
            handler: 处理函数
            priority: 优先级（越小越先执行）
            plugin_id: 关联的插件ID

        返回：
            处理器ID
        """
        handler_id = str(uuid.uuid4())

        hook_handler = HookHandler(
            id=handler_id,
            hook_point=hook_point,
            handler=handler,
            priority=priority,
            plugin_id=plugin_id,
        )

        if hook_point not in self._handlers:
            self._handlers[hook_point] = []

        self._handlers[hook_point].append(hook_handler)
        self._handler_map[handler_id] = hook_handler

        # 按优先级排序
        self._handlers[hook_point].sort(key=lambda h: h.priority)

        return handler_id

    def unregister(self, handler_id: str) -> bool:
        """注销钩子处理器

        参数：
            handler_id: 处理器ID

        返回：
            是否成功注销
        """
        if handler_id not in self._handler_map:
            return False

        handler = self._handler_map[handler_id]
        hook_point = handler.hook_point

        if hook_point in self._handlers:
            self._handlers[hook_point] = [
                h for h in self._handlers[hook_point] if h.id != handler_id
            ]

        del self._handler_map[handler_id]
        return True

    def unregister_by_plugin(self, plugin_id: str) -> int:
        """注销插件的所有钩子

        参数：
            plugin_id: 插件ID

        返回：
            注销的处理器数量
        """
        to_remove = [h.id for h in self._handler_map.values() if h.plugin_id == plugin_id]

        for handler_id in to_remove:
            self.unregister(handler_id)

        return len(to_remove)

    async def trigger(self, hook_point: str, context: dict[str, Any]) -> None:
        """触发钩子

        参数：
            hook_point: 钩子点名称
            context: 上下文数据（可被处理器修改）

        异常：
            HookAbort: 处理器中止执行
        """
        handlers = self._handlers.get(hook_point, [])

        for handler in handlers:
            try:
                result = handler.handler(context)
                # 支持异步处理器
                if hasattr(result, "__await__"):
                    await result
            except HookAbort:
                raise
            except Exception as e:
                logger.error(f"钩子处理器错误 {handler.id}: {e}")
                raise

    def list_hook_points(self) -> list[str]:
        """列出所有钩子点"""
        return list(set(list(self._handlers.keys()) + self.BUILTIN_HOOK_POINTS))

    def list_handlers(self, hook_point: str) -> list[HookHandler]:
        """列出钩子点的所有处理器"""
        return self._handlers.get(hook_point, [])


# ============ 扩展上下文 ============


@dataclass
class ExtensionContext:
    """扩展上下文

    包含所有扩展API组件的容器。
    """

    plugin_manager: PluginManager
    node_registry: CustomNodeRegistry
    hooks: HookSystem


# ============ 工厂类 ============


class ExtensionAPIFactory:
    """扩展API工厂

    创建和配置扩展API组件。

    使用示例：
        ctx = ExtensionAPIFactory.create()
    """

    @staticmethod
    def create(register_builtin_hooks: bool = False) -> ExtensionContext:
        """创建扩展上下文

        参数：
            register_builtin_hooks: 是否注册内置钩子点

        返回：
            扩展上下文
        """
        plugin_manager = PluginManager()
        node_registry = CustomNodeRegistry()
        hooks = HookSystem()

        if register_builtin_hooks:
            # 确保内置钩子点存在（即使没有处理器）
            for hook_point in HookSystem.BUILTIN_HOOK_POINTS:
                if hook_point not in hooks._handlers:
                    hooks._handlers[hook_point] = []

        return ExtensionContext(
            plugin_manager=plugin_manager, node_registry=node_registry, hooks=hooks
        )


# 导出
__all__ = [
    "PluginManager",
    "Plugin",
    "PluginStatus",
    "PluginDependencyError",
    "PluginVersionConflictError",
    "CustomNodeRegistry",
    "NodeDefinition",
    "NodeExecutor",
    "HookSystem",
    "HookHandler",
    "HookAbort",
    "ExtensionContext",
    "ExtensionAPIFactory",
]
