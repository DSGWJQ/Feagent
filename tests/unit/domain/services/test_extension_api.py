"""扩展API测试

Phase 4.3: 扩展API - TDD测试

测试覆盖:
- 插件系统 (PluginManager)
- 自定义节点API (CustomNodeRegistry)
- 插件生命周期 (PluginLifecycle)
- 钩子系统 (HookSystem)
"""

import pytest


class TestPluginManager:
    """插件管理器测试"""

    def test_register_plugin(self):
        """测试：注册插件

        真实场景：
        - 用户开发自定义插件
        - 系统启动时加载插件

        验收标准：
        - 正确注册插件
        - 插件元信息可查询
        """
        from src.domain.services.extension_api import Plugin, PluginManager

        manager = PluginManager()

        # 创建插件
        plugin = Plugin(
            id="my_custom_plugin",
            name="我的自定义插件",
            version="1.0.0",
            author="developer@example.com",
        )

        manager.register(plugin)

        assert manager.has_plugin("my_custom_plugin")
        registered = manager.get_plugin("my_custom_plugin")
        assert registered.name == "我的自定义插件"
        assert registered.version == "1.0.0"

    def test_plugin_with_dependencies(self):
        """测试：带依赖的插件

        真实场景：
        - 插件A依赖插件B
        - 需要按正确顺序加载

        验收标准：
        - 检查依赖是否满足
        - 依赖缺失时报错
        """
        from src.domain.services.extension_api import Plugin, PluginDependencyError, PluginManager

        manager = PluginManager()

        # 插件B（被依赖）
        plugin_b = Plugin(id="plugin_b", name="插件B", version="1.0.0")

        # 插件A（依赖B）
        plugin_a = Plugin(id="plugin_a", name="插件A", version="1.0.0", dependencies=["plugin_b"])

        # 先注册A，应该失败（依赖未满足）
        with pytest.raises(PluginDependencyError):
            manager.register(plugin_a)

        # 先注册B，再注册A
        manager.register(plugin_b)
        manager.register(plugin_a)

        assert manager.has_plugin("plugin_a")
        assert manager.has_plugin("plugin_b")

    def test_plugin_version_conflict(self):
        """测试：插件版本冲突

        真实场景：
        - 已注册同ID插件
        - 版本不同时的处理

        验收标准：
        - 检测版本冲突
        - 支持强制覆盖
        """
        from src.domain.services.extension_api import (
            Plugin,
            PluginManager,
            PluginVersionConflictError,
        )

        manager = PluginManager()

        plugin_v1 = Plugin(id="my_plugin", name="插件", version="1.0.0")
        plugin_v2 = Plugin(id="my_plugin", name="插件", version="2.0.0")

        manager.register(plugin_v1)

        # 默认不允许覆盖
        with pytest.raises(PluginVersionConflictError):
            manager.register(plugin_v2)

        # 强制覆盖
        manager.register(plugin_v2, force=True)
        assert manager.get_plugin("my_plugin").version == "2.0.0"

    def test_unregister_plugin(self):
        """测试：卸载插件

        真实场景：
        - 动态卸载插件
        - 清理插件资源

        验收标准：
        - 正确卸载
        - 清理相关钩子
        """
        from src.domain.services.extension_api import Plugin, PluginManager

        manager = PluginManager()

        plugin = Plugin(id="temp_plugin", name="临时插件", version="1.0.0")
        manager.register(plugin)

        assert manager.has_plugin("temp_plugin")

        manager.unregister("temp_plugin")

        assert not manager.has_plugin("temp_plugin")


class TestPluginLifecycle:
    """插件生命周期测试"""

    @pytest.mark.asyncio
    async def test_plugin_activation(self):
        """测试：插件激活

        真实场景：
        - 插件初始化资源
        - 连接外部服务

        验收标准：
        - 调用activate回调
        - 状态正确更新
        """
        from src.domain.services.extension_api import Plugin, PluginManager, PluginStatus

        manager = PluginManager()

        activated = False

        async def on_activate(ctx):
            nonlocal activated
            activated = True
            return {"initialized": True}

        plugin = Plugin(
            id="lifecycle_plugin", name="生命周期插件", version="1.0.0", on_activate=on_activate
        )

        manager.register(plugin)
        await manager.activate("lifecycle_plugin")

        assert activated
        assert manager.get_plugin("lifecycle_plugin").status == PluginStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_plugin_deactivation(self):
        """测试：插件停用

        真实场景：
        - 释放插件资源
        - 断开外部连接

        验收标准：
        - 调用deactivate回调
        - 资源正确释放
        """
        from src.domain.services.extension_api import Plugin, PluginManager, PluginStatus

        manager = PluginManager()

        deactivated = False

        async def on_deactivate(ctx):
            nonlocal deactivated
            deactivated = True

        plugin = Plugin(
            id="cleanup_plugin", name="清理插件", version="1.0.0", on_deactivate=on_deactivate
        )

        manager.register(plugin)
        await manager.activate("cleanup_plugin")
        await manager.deactivate("cleanup_plugin")

        assert deactivated
        assert manager.get_plugin("cleanup_plugin").status == PluginStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_plugin_error_handling(self):
        """测试：插件错误处理

        真实场景：
        - 插件激活失败
        - 运行时错误

        验收标准：
        - 错误被捕获
        - 状态标记为错误
        """
        from src.domain.services.extension_api import Plugin, PluginManager, PluginStatus

        manager = PluginManager()

        async def failing_activate(ctx):
            raise ValueError("激活失败")

        plugin = Plugin(
            id="failing_plugin", name="失败插件", version="1.0.0", on_activate=failing_activate
        )

        manager.register(plugin)

        with pytest.raises(ValueError):
            await manager.activate("failing_plugin")

        assert manager.get_plugin("failing_plugin").status == PluginStatus.ERROR


class TestCustomNodeRegistry:
    """自定义节点注册表测试"""

    def test_register_custom_node_type(self):
        """测试：注册自定义节点类型

        真实场景：
        - 用户定义新的节点类型
        - 扩展工作流能力

        验收标准：
        - 正确注册节点类型
        - 包含输入输出Schema
        """
        from src.domain.services.extension_api import CustomNodeRegistry, NodeDefinition

        registry = CustomNodeRegistry()

        # 定义自定义节点
        node_def = NodeDefinition(
            type="custom_ai_summarizer",
            name="AI摘要器",
            description="使用AI生成文本摘要",
            category="ai",
            input_schema={
                "text": {"type": "string", "required": True},
                "max_length": {"type": "integer", "default": 200},
            },
            output_schema={"summary": {"type": "string"}},
        )

        registry.register(node_def)

        assert registry.has_node_type("custom_ai_summarizer")
        registered = registry.get_node_definition("custom_ai_summarizer")
        assert registered.name == "AI摘要器"
        assert "text" in registered.input_schema

    def test_register_node_with_executor(self):
        """测试：注册带执行器的节点

        真实场景：
        - 节点需要自定义执行逻辑
        - 执行器处理输入产生输出

        验收标准：
        - 执行器被正确关联
        - 可通过registry获取执行器
        """
        from src.domain.services.extension_api import (
            CustomNodeRegistry,
            NodeDefinition,
            NodeExecutor,
        )

        registry = CustomNodeRegistry()

        class SummarizerExecutor(NodeExecutor):
            async def execute(self, config: dict, inputs: dict) -> dict:
                text = inputs.get("text", "")
                max_len = config.get("max_length", 200)
                summary = text[:max_len] + "..." if len(text) > max_len else text
                return {"summary": summary}

        node_def = NodeDefinition(
            type="custom_summarizer", name="摘要器", executor_class=SummarizerExecutor
        )

        registry.register(node_def)

        executor = registry.get_executor("custom_summarizer")
        assert executor is not None
        assert isinstance(executor, SummarizerExecutor)

    @pytest.mark.asyncio
    async def test_execute_custom_node(self):
        """测试：执行自定义节点

        真实场景：
        - 工作流运行时执行自定义节点
        - 处理输入产生输出

        验收标准：
        - 正确执行节点逻辑
        - 返回符合Schema的输出
        """
        from src.domain.services.extension_api import (
            CustomNodeRegistry,
            NodeDefinition,
            NodeExecutor,
        )

        registry = CustomNodeRegistry()

        class CalculatorExecutor(NodeExecutor):
            async def execute(self, config: dict, inputs: dict) -> dict:
                operation = config.get("operation", "add")
                a = inputs.get("a", 0)
                b = inputs.get("b", 0)

                if operation == "add":
                    return {"result": a + b}
                elif operation == "multiply":
                    return {"result": a * b}
                return {"result": 0}

        node_def = NodeDefinition(
            type="calculator", name="计算器", executor_class=CalculatorExecutor
        )

        registry.register(node_def)

        # 执行节点
        result = await registry.execute(
            node_type="calculator", config={"operation": "multiply"}, inputs={"a": 5, "b": 3}
        )

        assert result["result"] == 15

    def test_list_nodes_by_category(self):
        """测试：按分类列出节点

        真实场景：
        - 前端显示节点面板
        - 按类型过滤节点

        验收标准：
        - 正确分类
        - 返回完整信息
        """
        from src.domain.services.extension_api import CustomNodeRegistry, NodeDefinition

        registry = CustomNodeRegistry()

        # 注册多个节点
        registry.register(NodeDefinition(type="ai_chat", name="AI对话", category="ai"))
        registry.register(NodeDefinition(type="ai_summary", name="AI摘要", category="ai"))
        registry.register(
            NodeDefinition(type="http_request", name="HTTP请求", category="integration")
        )
        registry.register(
            NodeDefinition(type="db_query", name="数据库查询", category="integration")
        )

        ai_nodes = registry.list_by_category("ai")
        integration_nodes = registry.list_by_category("integration")

        assert len(ai_nodes) == 2
        assert len(integration_nodes) == 2
        assert all(n.category == "ai" for n in ai_nodes)


class TestHookSystem:
    """钩子系统测试"""

    @pytest.mark.asyncio
    async def test_register_and_trigger_hook(self):
        """测试：注册和触发钩子

        真实场景：
        - 插件在特定事件时执行代码
        - 如：工作流执行前/后

        验收标准：
        - 钩子被正确注册
        - 事件触发时执行
        """
        from src.domain.services.extension_api import HookSystem

        hooks = HookSystem()

        results = []

        async def on_workflow_start(ctx):
            results.append(f"workflow started: {ctx['workflow_id']}")

        hooks.register("workflow:start", on_workflow_start)

        await hooks.trigger("workflow:start", {"workflow_id": "wf_123"})

        assert len(results) == 1
        assert "wf_123" in results[0]

    @pytest.mark.asyncio
    async def test_multiple_handlers_for_hook(self):
        """测试：同一钩子多个处理器

        真实场景：
        - 多个插件监听同一事件
        - 按优先级执行

        验收标准：
        - 所有处理器都执行
        - 按优先级顺序
        """
        from src.domain.services.extension_api import HookSystem

        hooks = HookSystem()

        execution_order = []

        async def handler_a(ctx):
            execution_order.append("A")

        async def handler_b(ctx):
            execution_order.append("B")

        async def handler_c(ctx):
            execution_order.append("C")

        # 不同优先级注册
        hooks.register("node:execute", handler_b, priority=50)
        hooks.register("node:execute", handler_a, priority=10)  # 最高优先级
        hooks.register("node:execute", handler_c, priority=100)

        await hooks.trigger("node:execute", {})

        # 按优先级排序执行
        assert execution_order == ["A", "B", "C"]

    @pytest.mark.asyncio
    async def test_hook_can_modify_context(self):
        """测试：钩子可以修改上下文

        真实场景：
        - 拦截器模式
        - 修改请求/响应

        验收标准：
        - 上下文可被修改
        - 后续钩子看到修改
        """
        from src.domain.services.extension_api import HookSystem

        hooks = HookSystem()

        async def add_timestamp(ctx):
            ctx["timestamp"] = "2025-12-01T00:00:00Z"

        async def add_user_info(ctx):
            ctx["user"] = "admin"

        hooks.register("request:before", add_timestamp)
        hooks.register("request:before", add_user_info)

        context = {"data": "test"}
        await hooks.trigger("request:before", context)

        assert context["timestamp"] == "2025-12-01T00:00:00Z"
        assert context["user"] == "admin"

    @pytest.mark.asyncio
    async def test_hook_can_abort_execution(self):
        """测试：钩子可以中止执行

        真实场景：
        - 权限检查失败
        - 验证不通过

        验收标准：
        - 返回abort信号
        - 后续钩子不执行
        """
        from src.domain.services.extension_api import HookAbort, HookSystem

        hooks = HookSystem()

        async def permission_check(ctx):
            if not ctx.get("has_permission"):
                raise HookAbort("权限不足")

        async def process_request(ctx):
            ctx["processed"] = True

        hooks.register("action:before", permission_check, priority=1)
        hooks.register("action:before", process_request, priority=100)

        context = {"has_permission": False}

        with pytest.raises(HookAbort, match="权限不足"):
            await hooks.trigger("action:before", context)

        # process_request不应该执行
        assert "processed" not in context

    @pytest.mark.asyncio
    async def test_unregister_hook(self):
        """测试：注销钩子

        真实场景：
        - 插件卸载时清理钩子
        - 动态管理钩子

        验收标准：
        - 正确注销
        - 不再触发
        """
        from src.domain.services.extension_api import HookSystem

        hooks = HookSystem()

        call_count = 0

        async def handler(ctx):
            nonlocal call_count
            call_count += 1

        handler_id = hooks.register("test:event", handler)

        await hooks.trigger("test:event", {})
        assert call_count == 1

        hooks.unregister(handler_id)

        await hooks.trigger("test:event", {})
        assert call_count == 1  # 没有增加


class TestRealWorldScenarios:
    """真实业务场景测试"""

    @pytest.mark.asyncio
    async def test_custom_llm_provider_plugin(self):
        """测试：自定义LLM提供商插件

        真实业务场景：
        - 企业接入私有LLM服务
        - 通过插件扩展LLM能力

        验收标准：
        - 插件正确注册
        - 自定义节点可用
        - 执行时调用正确的服务
        """
        from src.domain.services.extension_api import (
            CustomNodeRegistry,
            HookSystem,
            NodeDefinition,
            NodeExecutor,
            Plugin,
            PluginManager,
        )

        manager = PluginManager()
        registry = CustomNodeRegistry()
        hooks = HookSystem()

        # 模拟私有LLM服务调用
        llm_calls = []

        class PrivateLLMExecutor(NodeExecutor):
            async def execute(self, config: dict, inputs: dict) -> dict:
                prompt = inputs.get("prompt", "")
                model = config.get("model", "private-gpt")

                llm_calls.append({"model": model, "prompt": prompt})

                # 模拟响应
                return {"response": f"来自{model}的回复: 处理了'{prompt}'"}

        # 定义插件
        async def on_activate(ctx):
            # 注册自定义节点
            node_def = NodeDefinition(
                type="private_llm",
                name="私有LLM",
                description="调用企业私有LLM服务",
                category="ai",
                input_schema={"prompt": {"type": "string"}},
                output_schema={"response": {"type": "string"}},
                executor_class=PrivateLLMExecutor,
            )
            registry.register(node_def)

        plugin = Plugin(
            id="private_llm_plugin",
            name="私有LLM插件",
            version="1.0.0",
            author="enterprise@example.com",
            on_activate=on_activate,
        )

        # 安装并激活插件
        manager.register(plugin)
        await manager.activate("private_llm_plugin")

        # 使用自定义节点
        result = await registry.execute(
            node_type="private_llm",
            config={"model": "enterprise-gpt-4"},
            inputs={"prompt": "总结一下今天的工作"},
        )

        assert "enterprise-gpt-4" in result["response"]
        assert len(llm_calls) == 1
        assert llm_calls[0]["model"] == "enterprise-gpt-4"

    @pytest.mark.asyncio
    async def test_workflow_audit_plugin(self):
        """测试：工作流审计插件

        真实业务场景：
        - 记录所有工作流执行
        - 合规审计需求

        验收标准：
        - 钩子正确触发
        - 审计日志完整
        """
        from src.domain.services.extension_api import HookSystem, Plugin, PluginManager

        manager = PluginManager()
        hooks = HookSystem()

        # 审计日志
        audit_logs = []

        async def audit_workflow_start(ctx):
            audit_logs.append(
                {
                    "event": "workflow_started",
                    "workflow_id": ctx["workflow_id"],
                    "user": ctx.get("user", "anonymous"),
                    "timestamp": ctx.get("timestamp"),
                }
            )

        async def audit_workflow_end(ctx):
            audit_logs.append(
                {
                    "event": "workflow_completed",
                    "workflow_id": ctx["workflow_id"],
                    "status": ctx.get("status"),
                    "duration_ms": ctx.get("duration_ms"),
                }
            )

        async def audit_node_execute(ctx):
            audit_logs.append(
                {
                    "event": "node_executed",
                    "workflow_id": ctx["workflow_id"],
                    "node_id": ctx["node_id"],
                    "node_type": ctx.get("node_type"),
                }
            )

        # 定义审计插件
        async def on_activate(ctx):
            hooks.register("workflow:start", audit_workflow_start)
            hooks.register("workflow:end", audit_workflow_end)
            hooks.register("node:executed", audit_node_execute)

        plugin = Plugin(
            id="audit_plugin", name="审计插件", version="1.0.0", on_activate=on_activate
        )

        manager.register(plugin)
        await manager.activate("audit_plugin")

        # 模拟工作流执行
        await hooks.trigger(
            "workflow:start",
            {"workflow_id": "wf_001", "user": "admin", "timestamp": "2025-12-01T10:00:00Z"},
        )

        await hooks.trigger(
            "node:executed", {"workflow_id": "wf_001", "node_id": "node_1", "node_type": "llm"}
        )

        await hooks.trigger(
            "node:executed", {"workflow_id": "wf_001", "node_id": "node_2", "node_type": "api"}
        )

        await hooks.trigger(
            "workflow:end", {"workflow_id": "wf_001", "status": "success", "duration_ms": 1500}
        )

        # 验证审计日志
        assert len(audit_logs) == 4
        assert audit_logs[0]["event"] == "workflow_started"
        assert audit_logs[-1]["event"] == "workflow_completed"
        assert audit_logs[-1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_data_transformation_plugin(self):
        """测试：数据转换插件

        真实业务场景：
        - 不同系统间数据格式转换
        - 自定义转换规则

        验收标准：
        - 转换节点正确工作
        - 支持多种转换类型
        """
        from src.domain.services.extension_api import (
            CustomNodeRegistry,
            NodeDefinition,
            NodeExecutor,
            Plugin,
            PluginManager,
        )

        manager = PluginManager()
        registry = CustomNodeRegistry()

        class JSONTransformExecutor(NodeExecutor):
            async def execute(self, config: dict, inputs: dict) -> dict:
                data = inputs.get("data", {})
                mapping = config.get("field_mapping", {})

                result = {}
                for target_field, source_path in mapping.items():
                    # 简单的路径解析
                    value = data
                    for key in source_path.split("."):
                        value = value.get(key, None) if value else None
                    result[target_field] = value

                return {"transformed": result}

        async def on_activate(ctx):
            registry.register(
                NodeDefinition(
                    type="json_transform",
                    name="JSON转换",
                    description="JSON字段映射转换",
                    category="transform",
                    executor_class=JSONTransformExecutor,
                )
            )

        plugin = Plugin(
            id="transform_plugin", name="数据转换插件", version="1.0.0", on_activate=on_activate
        )

        manager.register(plugin)
        await manager.activate("transform_plugin")

        # 使用转换节点
        input_data = {
            "user": {"profile": {"name": "张三", "email": "zhangsan@example.com"}},
            "order": {"id": "ORD001", "total": 199.99},
        }

        result = await registry.execute(
            node_type="json_transform",
            config={
                "field_mapping": {
                    "customer_name": "user.profile.name",
                    "customer_email": "user.profile.email",
                    "order_number": "order.id",
                    "amount": "order.total",
                }
            },
            inputs={"data": input_data},
        )

        assert result["transformed"]["customer_name"] == "张三"
        assert result["transformed"]["order_number"] == "ORD001"
        assert result["transformed"]["amount"] == 199.99


class TestExtensionAPIFactory:
    """扩展API工厂测试"""

    def test_create_extension_context(self):
        """测试：创建扩展上下文"""
        from src.domain.services.extension_api import ExtensionAPIFactory

        ctx = ExtensionAPIFactory.create()

        assert ctx.plugin_manager is not None
        assert ctx.node_registry is not None
        assert ctx.hooks is not None

    def test_create_with_builtin_hooks(self):
        """测试：创建时注册内置钩子"""
        from src.domain.services.extension_api import ExtensionAPIFactory

        ctx = ExtensionAPIFactory.create(register_builtin_hooks=True)

        # 应该有内置钩子点
        hook_points = ctx.hooks.list_hook_points()
        assert "workflow:start" in hook_points
        assert "workflow:end" in hook_points
        assert "node:before_execute" in hook_points
        assert "node:after_execute" in hook_points
