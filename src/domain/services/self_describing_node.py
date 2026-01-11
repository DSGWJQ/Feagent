"""自描述节点服务 (Self-Describing Node Service)

业务定义：
- 根据 YAML 元数据动态加载节点定义
- 支持父节点展开子节点执行并聚合输出
- 提供自描述执行事件供 Coordinator/前端消费

设计原则：
- YAML 驱动：节点行为由 YAML 定义决定
- 层次化执行：支持父子节点嵌套
- 事件驱动：执行过程发布自描述事件

核心组件：
- YamlNodeLoader: YAML 节点加载器
- SelfDescribingNodeExecutor: 自描述节点执行器
- SelfDescribingExecutionEvent: 执行事件
- WorkflowAgentAdapter: WorkflowAgent 适配器
"""

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ==================== 数据类 ====================


@dataclass
class ParameterDefinition:
    """参数定义"""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class NestedNodeDefinition:
    """嵌套节点定义（子节点）"""

    name: str
    executor_type: str = "code"
    language: str = "python"
    parameters: list[ParameterDefinition] = field(default_factory=list)
    nested: "NestedConfig | None" = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NestedNodeDefinition":
        """从字典创建"""
        params = []
        for p in data.get("parameters", []):
            params.append(
                ParameterDefinition(
                    name=p.get("name", ""),
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                    default=p.get("default"),
                    enum=p.get("enum"),
                )
            )

        nested = None
        if "nested" in data:
            nested = NestedConfig.from_dict(data["nested"])

        return cls(
            name=data.get("name", ""),
            executor_type=data.get("executor_type", "code"),
            language=data.get("language", "python"),
            parameters=params,
            nested=nested,
        )


@dataclass
class NestedConfig:
    """嵌套配置"""

    parallel: bool = False
    children: list[NestedNodeDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NestedConfig":
        """从字典创建"""
        children = []
        for child_data in data.get("children", []):
            children.append(NestedNodeDefinition.from_dict(child_data))

        return cls(
            parallel=data.get("parallel", False),
            children=children,
        )


@dataclass
class ErrorStrategy:
    """错误处理策略"""

    on_failure: str = "abort"  # abort, skip, continue
    retry_max_attempts: int = 1


@dataclass
class ExecutionConfig:
    """执行配置"""

    timeout_seconds: int = 30
    sandbox: bool = True


@dataclass
class SelfDescribingNodeDefinition:
    """自描述节点定义"""

    name: str
    kind: str = "node"
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = ""
    executor_type: str = "code"
    language: str = "python"
    parameters: list[ParameterDefinition] = field(default_factory=list)
    returns: dict[str, Any] = field(default_factory=dict)
    nested: NestedConfig | None = None
    error_strategy: ErrorStrategy = field(default_factory=ErrorStrategy)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    output_aggregation: str = "merge"  # merge, list, first, last

    @property
    def has_children(self) -> bool:
        """是否有子节点"""
        return self.nested is not None and len(self.nested.children) > 0

    @property
    def children(self) -> list[NestedNodeDefinition]:
        """获取子节点列表"""
        if self.nested:
            return self.nested.children
        return []

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "SelfDescribingNodeDefinition":
        """从 YAML 字符串创建

        参数：
            yaml_content: YAML 格式的节点定义

        返回：
            节点定义实例

        异常：
            ValueError: 当 YAML 内容无效或嵌套配置无效时
        """
        try:
            data = yaml.safe_load(yaml_content)
            if not data or not isinstance(data, dict):
                raise ValueError("无效的 YAML 内容：必须是非空字典")

            # 验证嵌套配置
            if "nested" in data:
                nested_data = data["nested"]
                if not isinstance(nested_data, dict):
                    raise ValueError("无效的嵌套配置：nested 必须是字典")

                children = nested_data.get("children")
                if children is None:
                    raise ValueError("无效的嵌套配置：缺少 children 字段")
                if not isinstance(children, list):
                    raise ValueError("无效的嵌套配置：children 必须是列表")
                if len(children) == 0:
                    raise ValueError("无效的嵌套配置：children 不能为空列表")

            return cls.from_dict(data)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析错误: {e}") from e

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SelfDescribingNodeDefinition":
        """从字典创建"""
        # 解析参数
        params = []
        for p in data.get("parameters", []):
            params.append(
                ParameterDefinition(
                    name=p.get("name", ""),
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                    default=p.get("default"),
                    enum=p.get("enum"),
                )
            )

        # 解析嵌套配置
        nested = None
        if "nested" in data:
            nested = NestedConfig.from_dict(data["nested"])

        # 解析错误策略
        error_data = data.get("error_strategy", {})
        error_strategy = ErrorStrategy(
            on_failure=error_data.get("on_failure", "abort"),
            retry_max_attempts=error_data.get("retry", {}).get("max_attempts", 1),
        )

        # 解析执行配置
        exec_data = data.get("execution", {})
        execution = ExecutionConfig(
            timeout_seconds=exec_data.get("timeout_seconds", 30),
            sandbox=exec_data.get("sandbox", True),
        )

        return cls(
            name=data.get("name", ""),
            kind=data.get("kind", "node"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            category=data.get("category", ""),
            executor_type=data.get("executor_type", "code"),
            language=data.get("language", "python"),
            parameters=params,
            returns=data.get("returns", {}),
            nested=nested,
            error_strategy=error_strategy,
            execution=execution,
            output_aggregation=data.get("output_aggregation", "merge"),
        )


@dataclass
class NodeExecutionResult:
    """节点执行结果"""

    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    children_results: dict[str, "NodeExecutionResult"] | None = None
    aggregated_output: dict[str, Any] | None = None
    execution_time_ms: float = 0.0

    @classmethod
    def failure(cls, error: str) -> "NodeExecutionResult":
        """创建失败结果"""
        return cls(success=False, error=error)

    @classmethod
    def ok(cls, output: dict[str, Any]) -> "NodeExecutionResult":
        """创建成功结果"""
        return cls(success=True, output=output)


@dataclass
class SelfDescribingExecutionEvent:
    """自描述执行事件"""

    node_name: str = ""
    node_description: str = ""
    node_version: str = ""
    executor_type: str = ""
    status: str = ""  # started, running, completed, failed
    parameters_info: list[dict[str, Any]] | None = None
    children_names: list[str] | None = None
    execution_time_ms: float | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    timestamp: float = field(default_factory=time.time)


# ==================== YamlNodeLoader ====================


class YamlNodeLoader:
    """YAML 节点加载器

    从 YAML 文件加载节点定义。
    """

    def __init__(self, definitions_dir: str) -> None:
        self.definitions_dir = Path(definitions_dir)

    def load(self, node_name: str) -> SelfDescribingNodeDefinition | None:
        """加载节点定义

        参数：
            node_name: 节点名称

        返回：
            节点定义，如果不存在返回 None
        """
        yaml_path = self.definitions_dir / f"{node_name}.yaml"
        if not yaml_path.exists():
            return None

        try:
            content = yaml_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                return None
            return SelfDescribingNodeDefinition.from_dict(data)
        except Exception:
            return None

    def load_all(self) -> list[SelfDescribingNodeDefinition]:
        """加载所有节点定义

        返回：
            节点定义列表
        """
        definitions = []
        if not self.definitions_dir.exists():
            return definitions

        for yaml_path in self.definitions_dir.glob("*.yaml"):
            try:
                content = yaml_path.read_text(encoding="utf-8")
                data = yaml.safe_load(content)
                if data and isinstance(data, dict):
                    definitions.append(SelfDescribingNodeDefinition.from_dict(data))
            except Exception:
                continue

        return definitions

    def get_metadata_for_prompt(self, node_name: str) -> str:
        """获取节点元数据用于 Prompt

        参数：
            node_name: 节点名称

        返回：
            格式化的元数据字符串
        """
        node_def = self.load(node_name)
        if not node_def:
            return f"节点 {node_name} 未找到"

        params_str = ""
        for p in node_def.parameters:
            required = "必需" if p.required else "可选"
            default = f"，默认值: {p.default}" if p.default is not None else ""
            params_str += f"  - {p.name} ({p.type}, {required}): {p.description}{default}\n"

        return f"""节点: {node_def.name}
描述: {node_def.description}
版本: {node_def.version}
执行器类型: {node_def.executor_type}
参数:
{params_str}"""


# ==================== SelfDescribingNodeExecutor ====================


class SelfDescribingNodeExecutor:
    """自描述节点执行器

    根据 YAML 元数据执行节点，支持父子节点嵌套。
    """

    def __init__(
        self,
        definitions_dir: str,
        scripts_dir: str | None = None,
        sandbox_executor: Any = None,
        event_handler: Callable[[SelfDescribingExecutionEvent], Coroutine[Any, Any, None]]
        | None = None,
    ) -> None:
        self.loader = YamlNodeLoader(definitions_dir)
        self.definitions_dir = Path(definitions_dir)
        self.scripts_dir = Path(scripts_dir) if scripts_dir else self.definitions_dir / "scripts"
        self.sandbox_executor = sandbox_executor
        self.event_handler = event_handler

    async def _emit_event(self, event: SelfDescribingExecutionEvent) -> None:
        """发送事件"""
        if self.event_handler:
            await self.event_handler(event)

    async def execute_node(
        self,
        node_name: str,
        inputs: dict[str, Any],
    ) -> NodeExecutionResult:
        """执行节点

        参数：
            node_name: 节点名称
            inputs: 输入数据

        返回：
            执行结果
        """
        start_time = time.time()

        # 加载节点定义
        node_def = self.loader.load(node_name)
        if not node_def:
            # 尝试处理无效 YAML
            yaml_path = self.definitions_dir / f"{node_name}.yaml"
            if yaml_path.exists():
                return NodeExecutionResult.failure(f"无法解析 YAML: {node_name}")
            return NodeExecutionResult.failure(f"节点未找到: {node_name}")

        # 发送开始事件
        await self._emit_event(
            SelfDescribingExecutionEvent(
                node_name=node_def.name,
                node_description=node_def.description,
                node_version=node_def.version,
                executor_type=node_def.executor_type,
                status="started",
                parameters_info=[
                    {"name": p.name, "type": p.type, "description": p.description}
                    for p in node_def.parameters
                ],
                children_names=[c.name for c in node_def.children]
                if node_def.has_children
                else None,
            )
        )

        # 验证必需参数
        validation_error = self._validate_inputs(node_def, inputs)
        if validation_error:
            await self._emit_event(
                SelfDescribingExecutionEvent(
                    node_name=node_def.name,
                    status="failed",
                    error=validation_error,
                )
            )
            return NodeExecutionResult.failure(validation_error)

        # 应用默认值
        inputs = self._apply_defaults(node_def, inputs)

        try:
            # 根据是否有子节点决定执行方式
            if node_def.has_children:
                result = await self._execute_with_children(node_def, inputs)
            else:
                result = await self._execute_single(node_def, inputs)

            execution_time = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time

            # 发送完成事件
            await self._emit_event(
                SelfDescribingExecutionEvent(
                    node_name=node_def.name,
                    node_description=node_def.description,
                    node_version=node_def.version,
                    status="completed" if result.success else "failed",
                    execution_time_ms=execution_time,
                    output=result.output if result.success else None,
                    error=result.error,
                )
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = str(e)

            await self._emit_event(
                SelfDescribingExecutionEvent(
                    node_name=node_def.name,
                    status="failed",
                    error=error_msg,
                    execution_time_ms=execution_time,
                )
            )

            return NodeExecutionResult.failure(error_msg)

    def _validate_inputs(
        self, node_def: SelfDescribingNodeDefinition, inputs: dict[str, Any]
    ) -> str | None:
        """验证输入参数"""
        for param in node_def.parameters:
            if param.required and param.name not in inputs and param.default is None:
                return f"缺少必需参数: {param.name}"
        return None

    def _apply_defaults(
        self, node_def: SelfDescribingNodeDefinition, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """应用默认值"""
        result = inputs.copy()
        for param in node_def.parameters:
            if param.name not in result and param.default is not None:
                result[param.name] = param.default
        return result

    async def _execute_single(
        self, node_def: SelfDescribingNodeDefinition, inputs: dict[str, Any]
    ) -> NodeExecutionResult:
        """执行单个节点（无子节点）"""
        if node_def.executor_type == "code":
            return await self._execute_code_node(node_def, inputs)
        elif node_def.executor_type == "llm":
            return await self._execute_llm_node(node_def, inputs)
        else:
            # 默认返回成功
            return NodeExecutionResult.ok(inputs)

    async def _execute_code_node(
        self, node_def: SelfDescribingNodeDefinition, inputs: dict[str, Any]
    ) -> NodeExecutionResult:
        """执行代码节点"""
        # 查找代码文件
        code_path = self.scripts_dir / f"{node_def.name}.py"
        if not code_path.exists():
            # 如果没有代码文件，使用沙箱执行器的默认行为
            if self.sandbox_executor:
                # 生成简单的默认代码
                default_code = """
def main(**kwargs):
    return {"result": kwargs, "success": True}
"""
                return await self._run_in_sandbox(
                    default_code, inputs, node_def.execution.timeout_seconds
                )

            return NodeExecutionResult.ok(inputs)

        # 读取代码
        code = code_path.read_text(encoding="utf-8")

        if self.sandbox_executor:
            return await self._run_in_sandbox(code, inputs, node_def.execution.timeout_seconds)

        return NodeExecutionResult.ok(inputs)

    async def _run_in_sandbox(
        self, code: str, inputs: dict[str, Any], timeout_seconds: int = 30
    ) -> NodeExecutionResult:
        """在沙箱中运行代码"""
        try:
            from src.domain.services.sandbox_executor import SandboxConfig

            config = SandboxConfig(timeout_seconds=timeout_seconds)

            # 直接执行代码，期望代码设置 output 全局变量
            wrapped_code = code

            result = self.sandbox_executor.execute(
                code=wrapped_code,
                config=config,
                input_data=inputs,
            )

            if hasattr(result, "success"):
                if result.success:
                    # 优先使用 output_data（SandboxResult 的实际属性名）
                    output = {}
                    if hasattr(result, "output_data") and result.output_data:
                        output = result.output_data
                    elif hasattr(result, "output") and result.output:
                        output = result.output
                    return NodeExecutionResult.ok(output)
                else:
                    # 检查错误来源
                    error = "执行失败"
                    if hasattr(result, "stderr") and result.stderr:
                        error = result.stderr
                    elif hasattr(result, "error") and result.error:
                        error = result.error
                    # 检查是否超时
                    if hasattr(result, "timed_out") and result.timed_out:
                        return NodeExecutionResult.failure("执行超时 (timeout)")
                    return NodeExecutionResult.failure(error)
            else:
                return NodeExecutionResult.ok(result if isinstance(result, dict) else {})

        except Exception as e:
            return NodeExecutionResult.failure(str(e))

    async def _execute_llm_node(
        self, node_def: SelfDescribingNodeDefinition, inputs: dict[str, Any]
    ) -> NodeExecutionResult:
        """执行 LLM 节点"""
        # LLM 节点暂时返回模拟结果
        return NodeExecutionResult.ok({"llm_response": "模拟响应", "inputs": inputs})

    async def _execute_with_children(
        self, node_def: SelfDescribingNodeDefinition, inputs: dict[str, Any]
    ) -> NodeExecutionResult:
        """执行带子节点的父节点"""
        if not node_def.nested:
            return NodeExecutionResult.ok({})

        children_results: dict[str, NodeExecutionResult] = {}

        if node_def.nested.parallel:
            # 并行执行
            children_results = await self._execute_children_parallel(
                node_def.nested.children, inputs, node_def.error_strategy
            )
        else:
            # 顺序执行
            children_results = await self._execute_children_sequential(
                node_def.nested.children, inputs, node_def.error_strategy
            )

        # 检查是否有失败
        has_failure = any(not r.success for r in children_results.values())
        if has_failure and node_def.error_strategy.on_failure == "abort":
            failed_children = [name for name, r in children_results.items() if not r.success]
            return NodeExecutionResult(
                success=False,
                error=f"子节点执行失败: {', '.join(failed_children)}",
                children_results=children_results,
            )

        # 聚合输出
        aggregated = self._aggregate_outputs(children_results, node_def.output_aggregation)

        return NodeExecutionResult(
            success=True,
            output=aggregated,
            children_results=children_results,
            aggregated_output=aggregated,
        )

    async def _execute_children_sequential(
        self,
        children: list[NestedNodeDefinition],
        inputs: dict[str, Any],
        error_strategy: ErrorStrategy,
    ) -> dict[str, NodeExecutionResult]:
        """顺序执行子节点"""
        results: dict[str, NodeExecutionResult] = {}
        current_inputs = inputs.copy()

        for child in children:
            result = await self._execute_child_node(child, current_inputs)
            results[child.name] = result

            if not result.success and error_strategy.on_failure == "abort":
                break

            # 将输出传递给下一个节点
            if result.success and result.output:
                current_inputs.update(result.output)

        return results

    async def _execute_children_parallel(
        self,
        children: list[NestedNodeDefinition],
        inputs: dict[str, Any],
        error_strategy: ErrorStrategy,
    ) -> dict[str, NodeExecutionResult]:
        """并行执行子节点"""

        async def execute_child(child: NestedNodeDefinition) -> tuple[str, NodeExecutionResult]:
            result = await self._execute_child_node(child, inputs)
            return child.name, result

        tasks = [execute_child(child) for child in children]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, NodeExecutionResult] = {}
        for item in task_results:
            if isinstance(item, BaseException):
                continue
            name, result = item
            results[name] = result

        return results

    async def _execute_child_node(
        self, child: NestedNodeDefinition, inputs: dict[str, Any]
    ) -> NodeExecutionResult:
        """执行子节点"""
        # 发送子节点开始事件
        await self._emit_event(
            SelfDescribingExecutionEvent(
                node_name=child.name,
                executor_type=child.executor_type,
                status="started",
            )
        )

        if self.sandbox_executor:
            # 生成子节点代码或使用默认
            code_path = self.scripts_dir / f"{child.name}.py"
            if code_path.exists():
                code = code_path.read_text(encoding="utf-8")
            else:
                code = """
def main(**kwargs):
    return {"result": kwargs, "success": True}
"""
            return await self._run_in_sandbox(code, inputs, timeout_seconds=30)

        # 如果没有沙箱执行器，返回成功
        return NodeExecutionResult.ok({"child": child.name, "inputs": inputs})

    def _aggregate_outputs(
        self, results: dict[str, NodeExecutionResult], strategy: str
    ) -> dict[str, Any]:
        """聚合子节点输出"""
        if strategy == "merge":
            aggregated: dict[str, Any] = {}
            for name, result in results.items():
                if result.success and result.output:
                    aggregated[name] = result.output
            return aggregated

        elif strategy == "list":
            return {"results": [r.output for r in results.values() if r.success]}

        elif strategy == "first":
            for result in results.values():
                if result.success:
                    return result.output
            return {}

        elif strategy == "last":
            last_output: dict[str, Any] = {}
            for result in results.values():
                if result.success:
                    last_output = result.output
            return last_output

        return {}


# ==================== WorkflowAgentAdapter ====================


class WorkflowAgentAdapter:
    """WorkflowAgent 适配器

    为 WorkflowAgent 提供自描述节点支持。
    """

    def __init__(
        self,
        definitions_dir: str,
        scripts_dir: str | None = None,
        sandbox_executor: Any = None,
    ) -> None:
        self.definitions_dir = Path(definitions_dir)
        self.scripts_dir = Path(scripts_dir) if scripts_dir else self.definitions_dir / "scripts"
        self.sandbox_executor = sandbox_executor
        self.loader = YamlNodeLoader(definitions_dir)
        self.executor = SelfDescribingNodeExecutor(
            definitions_dir=definitions_dir,
            scripts_dir=str(self.scripts_dir),
            sandbox_executor=sandbox_executor,
        )

    def get_node_info(self, node_name: str) -> dict[str, Any] | None:
        """获取节点信息

        参数：
            node_name: 节点名称

        返回：
            节点信息字典
        """
        node_def = self.loader.load(node_name)
        if not node_def:
            return None

        return {
            "name": node_def.name,
            "description": node_def.description,
            "version": node_def.version,
            "executor_type": node_def.executor_type,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                }
                for p in node_def.parameters
            ],
            "has_children": node_def.has_children,
            "children": [c.name for c in node_def.children] if node_def.has_children else [],
        }

    async def execute_workflow(self, workflow_def: dict[str, Any]) -> dict[str, Any]:
        """执行工作流

        参数：
            workflow_def: 工作流定义

        返回：
            执行结果
        """
        nodes = workflow_def.get("nodes", [])
        # edges are reserved for future use in topological sorting
        _ = workflow_def.get("edges", [])

        if not nodes:
            return {"success": True, "results": {}}

        # 构建执行顺序（简单实现：按节点顺序）
        node_results: dict[str, Any] = {}
        current_inputs: dict[str, Any] = {}

        # 按拓扑顺序执行（简化：按定义顺序）
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            node_config = node.get("config", {})

            # 合并配置和当前输入
            inputs = {**current_inputs, **node_config}

            # 执行节点
            result = await self.executor.execute_node(
                node_name=node_type,
                inputs=inputs,
            )

            node_results[node_id] = {
                "success": result.success,
                "output": result.output,
                "error": result.error,
            }

            # 传递输出到下一个节点
            if result.success and result.output:
                current_inputs.update(result.output)

            # 如果失败，停止执行
            if not result.success:
                return {
                    "success": False,
                    "results": node_results,
                    "failed_node": node_id,
                    "error": result.error,
                }

        return {
            "success": True,
            "results": node_results,
        }
