"""
工作流依赖图与自动连线 (Workflow Dependency Graph)

业务定义：
- 自动解析节点间的输入输出依赖关系
- 根据依赖创建 DAG 边
- 拓扑排序确保正确执行顺序
- 数据流自动传递

核心组件：
- DependencyGraphBuilder: 依赖图构建器
- TopologicalExecutor: 拓扑排序执行器
- WorkflowDependencyExecutor: 工作流依赖执行器
- DependencyExecutionEvent: 依赖执行事件
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ==================== 数据类 ====================


@dataclass
class DependencyExecutionEvent:
    """依赖执行事件

    用于记录和广播节点执行状态，包含依赖信息。
    """

    node_name: str
    status: str  # started, completed, failed
    dependencies: list[str] = field(default_factory=list)
    execution_order: int = 0
    execution_time_ms: float = 0.0
    output_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_name": self.node_name,
            "status": self.status,
            "dependencies": self.dependencies,
            "execution_order": self.execution_order,
            "execution_time_ms": self.execution_time_ms,
            "output_keys": self.output_keys,
        }


@dataclass
class WorkflowExecutionResult:
    """工作流执行结果"""

    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    children_results: dict[str, Any] = field(default_factory=dict)
    aggregated_output: dict[str, Any] | None = None
    execution_order: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


# ==================== 依赖图构建器 ====================


class DependencyGraphBuilder:
    """依赖图构建器

    解析节点定义中的输入输出引用，构建依赖关系图。
    """

    # 引用格式: node_name.output.field_name 或 node_name.output
    REFERENCE_PATTERN = re.compile(r"^(\w+)\.output(?:\.(\w+))?$")

    def parse_input_references(self, node_def: dict[str, Any]) -> dict[str, dict[str, str | None]]:
        """解析输入引用

        参数：
            node_def: 节点定义

        返回：
            输入名 -> {node: 依赖节点名, path: 输出路径} 的映射
        """
        refs: dict[str, dict[str, str | None]] = {}
        inputs = node_def.get("inputs", {})

        if not isinstance(inputs, dict):
            return refs

        for input_name, input_spec in inputs.items():
            if not isinstance(input_spec, dict):
                continue

            from_ref = input_spec.get("from", "")
            if not from_ref:
                continue

            # 解析引用格式: node_name.output.field_name
            match = self.REFERENCE_PATTERN.match(from_ref)
            if match:
                source_node = match.group(1)
                field_path = match.group(2)  # 可能为 None
                refs[input_name] = {
                    "node": source_node,
                    "path": f"output.{field_path}" if field_path else "output",
                }
            else:
                # 无效格式，记录但不添加到引用
                logger.warning(f"无效的输入引用格式: {from_ref}")

        return refs

    def parse_output_schema(self, node_def: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """解析输出模式

        参数：
            node_def: 节点定义

        返回：
            输出字段名 -> 类型信息的映射
        """
        outputs = node_def.get("outputs", {})
        if not isinstance(outputs, dict):
            return {}
        return outputs

    def resolve_dependencies(self, nodes: list[dict[str, Any]]) -> dict[str, list[str]]:
        """解析节点间依赖关系

        参数：
            nodes: 节点定义列表

        返回：
            节点名 -> 依赖节点名列表的映射
        """
        # 构建节点名集合
        node_names = {n.get("name", "") for n in nodes if n.get("name")}

        dependencies: dict[str, list[str]] = defaultdict(list)

        for node in nodes:
            node_name = node.get("name", "")
            if not node_name:
                continue

            dependencies[node_name] = []

            # 解析输入引用
            refs = self.parse_input_references(node)
            for _input_name, ref_info in refs.items():
                source_node = ref_info.get("node")
                if source_node and source_node in node_names:
                    if source_node != node_name:  # 排除自引用
                        if source_node not in dependencies[node_name]:
                            dependencies[node_name].append(source_node)

        return dict(dependencies)

    def create_edges(self, nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
        """根据依赖关系创建边

        参数：
            nodes: 节点定义列表

        返回：
            边列表，每个边包含 source 和 target
        """
        edges: list[dict[str, str]] = []
        dependencies = self.resolve_dependencies(nodes)

        for target_node, source_nodes in dependencies.items():
            for source_node in source_nodes:
                edges.append({"source": source_node, "target": target_node})

        return edges

    def wire_children(self, parent_node: dict[str, Any]) -> list[dict[str, str]]:
        """为父节点的子节点创建连线

        参数：
            parent_node: 父节点定义

        返回：
            子节点间的边列表
        """
        nested = parent_node.get("nested", {})
        children = nested.get("children", [])

        if not children:
            return []

        return self.create_edges(children)


# ==================== 拓扑排序执行器 ====================


class TopologicalExecutor:
    """拓扑排序执行器

    使用 Kahn 算法进行拓扑排序，确保按依赖顺序执行。
    """

    def topological_sort(
        self,
        nodes: list[str],
        edges: list[tuple[str, str]],
    ) -> list[str]:
        """拓扑排序

        参数：
            nodes: 节点名列表
            edges: 边列表 (source, target)

        返回：
            按拓扑顺序排列的节点名列表

        异常：
            ValueError: 如果存在循环依赖
        """
        # 构建入度表和邻接表
        in_degree: dict[str, int] = dict.fromkeys(nodes, 0)
        adjacency: dict[str, list[str]] = {node: [] for node in nodes}

        for source, target in edges:
            if source in adjacency and target in in_degree:
                adjacency[source].append(target)
                in_degree[target] += 1

        # Kahn 算法
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检测循环
        if len(result) != len(nodes):
            remaining = set(nodes) - set(result)
            raise ValueError(f"检测到循环依赖 (cycle detected): {remaining}")

        return result


# ==================== 工作流依赖执行器 ====================


class WorkflowDependencyExecutor:
    """工作流依赖执行器

    整合依赖解析、拓扑排序和执行，支持数据流传递。
    """

    def __init__(
        self,
        definitions_dir: str,
        scripts_dir: str | None = None,
        sandbox_executor: Any = None,
        event_callback: Callable[[DependencyExecutionEvent], None] | None = None,
    ) -> None:
        self.definitions_dir = Path(definitions_dir)
        self.scripts_dir = Path(scripts_dir) if scripts_dir else None
        self.sandbox_executor = sandbox_executor
        self.event_callback = event_callback

        self.graph_builder = DependencyGraphBuilder()
        self.topo_executor = TopologicalExecutor()

        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def execute_workflow(
        self,
        workflow_name: str,
        inputs: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """执行工作流

        参数：
            workflow_name: 工作流名称
            inputs: 初始输入

        返回：
            执行结果
        """
        start_time = time.time()

        # 加载工作流定义
        yaml_file = self.definitions_dir / f"{workflow_name}.yaml"
        if not yaml_file.exists():
            return WorkflowExecutionResult(
                success=False,
                error=f"工作流定义不存在: {workflow_name}",
            )

        with open(yaml_file, encoding="utf-8") as f:
            workflow_def = yaml.safe_load(f)

        if not isinstance(workflow_def, dict):
            return WorkflowExecutionResult(
                success=False,
                error="Invalid workflow definition format",
            )

        # 获取子节点
        nested = workflow_def.get("nested", {})
        children = nested.get("children", []) if isinstance(nested, dict) else []

        if not children:
            return WorkflowExecutionResult(
                success=True,
                output=inputs,
            )

        # 解析依赖并创建边
        edges = self.graph_builder.create_edges(children)
        node_names = [c["name"] for c in children]
        edge_tuples = [(e["source"], e["target"]) for e in edges]

        # 拓扑排序
        try:
            execution_order = self.topo_executor.topological_sort(node_names, edge_tuples)
        except ValueError as e:
            return WorkflowExecutionResult(
                success=False,
                error=str(e),
            )

        self._logger.info(f"执行顺序: {' -> '.join(execution_order)}")

        # 依赖解析
        dependencies = self.graph_builder.resolve_dependencies(children)

        # 构建节点名到定义的映射
        node_map = {c["name"]: c for c in children}

        # 存储每个节点的输出
        node_outputs: dict[str, dict[str, Any]] = {}
        children_results: dict[str, Any] = {}

        # 按顺序执行
        for order_idx, node_name in enumerate(execution_order):
            node_def = node_map.get(node_name, {})
            node_deps = dependencies.get(node_name, [])

            # 构建输入：从依赖节点的输出获取
            node_inputs = self._build_node_inputs(node_def, node_outputs, inputs)

            # 发布开始事件
            self._emit_event(
                DependencyExecutionEvent(
                    node_name=node_name,
                    status="started",
                    dependencies=node_deps,
                    execution_order=order_idx,
                )
            )

            self._logger.info(
                f"执行节点 [{order_idx + 1}/{len(execution_order)}]: {node_name} "
                f"(依赖: {node_deps or 'none'})"
            )

            # 执行节点
            node_start = time.time()
            try:
                result = await self._execute_node(node_name, node_inputs)
                node_outputs[node_name] = result
                children_results[node_name] = {
                    "success": True,
                    "output": result,
                }
                node_time = (time.time() - node_start) * 1000

                # 发布完成事件
                self._emit_event(
                    DependencyExecutionEvent(
                        node_name=node_name,
                        status="completed",
                        dependencies=node_deps,
                        execution_order=order_idx,
                        execution_time_ms=node_time,
                        output_keys=list(result.keys()) if isinstance(result, dict) else [],
                    )
                )

            except Exception as e:
                node_time = (time.time() - node_start) * 1000
                self._logger.error(f"节点 {node_name} 执行失败: {e}")

                # 发布失败事件
                self._emit_event(
                    DependencyExecutionEvent(
                        node_name=node_name,
                        status="failed",
                        dependencies=node_deps,
                        execution_order=order_idx,
                        execution_time_ms=node_time,
                    )
                )

                children_results[node_name] = {
                    "success": False,
                    "error": str(e),
                }

                # 根据错误策略决定是否继续
                error_strategy = (
                    workflow_def.get("error_strategy", {}) if isinstance(workflow_def, dict) else {}
                )
                on_failure = (
                    error_strategy.get("on_failure", "abort")
                    if isinstance(error_strategy, dict)
                    else "abort"
                )
                if on_failure == "abort":
                    return WorkflowExecutionResult(
                        success=False,
                        error=f"节点 {node_name} 执行失败: {e}",
                        children_results=children_results,
                        execution_order=execution_order[: order_idx + 1],
                    )

        # 聚合输出
        aggregation = workflow_def.get("output_aggregation", "merge")
        aggregated = self._aggregate_outputs(node_outputs, aggregation)

        total_time = (time.time() - start_time) * 1000

        return WorkflowExecutionResult(
            success=True,
            output=aggregated,
            children_results=children_results,
            aggregated_output=node_outputs,
            execution_order=execution_order,
            execution_time_ms=total_time,
        )

    def _build_node_inputs(
        self,
        node_def: dict[str, Any],
        node_outputs: dict[str, dict[str, Any]],
        global_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """构建节点输入

        从依赖节点的输出和全局输入中提取所需数据。
        """
        result: dict[str, Any] = {}

        # 解析输入引用
        refs = self.graph_builder.parse_input_references(node_def)

        for input_name, ref_info in refs.items():
            source_node = ref_info.get("node")
            path = ref_info.get("path", "output")

            if source_node == "parent":
                # 从全局输入获取
                result[input_name] = global_inputs
            elif source_node and source_node in node_outputs:
                # 从依赖节点输出获取
                source_output = node_outputs[source_node]

                # 解析路径
                if path and "." in path:
                    parts = path.split(".")
                    value = source_output
                    for part in parts[1:]:  # 跳过 "output"
                        if isinstance(value, dict):
                            value = value.get(part, value)
                    result[input_name] = value
                else:
                    result[input_name] = source_output

        return result

    async def _execute_node(
        self,
        node_name: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """执行单个节点"""
        # 查找脚本
        if self.scripts_dir:
            script_path = self.scripts_dir / f"{node_name}.py"
            if script_path.exists():
                return await self._execute_script(script_path, inputs)

        # 没有脚本，返回输入
        return inputs

    async def _execute_script(
        self,
        script_path: Path,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """在沙箱中执行脚本"""
        code = script_path.read_text(encoding="utf-8")

        if self.sandbox_executor:
            from src.domain.services.sandbox_executor import SandboxConfig

            config = SandboxConfig(timeout_seconds=30)
            result = self.sandbox_executor.execute(
                code=code,
                config=config,
                input_data=inputs,
            )
            if hasattr(result, "output_data"):
                return result.output_data or {}
            return {}

        # 使用内置沙箱
        from src.domain.services.sandbox_executor import SandboxExecutor

        executor = SandboxExecutor()
        result = executor.execute(
            code=code,
            input_data=inputs,
        )

        if hasattr(result, "output_data"):
            return result.output_data or {}
        return {}

    def _aggregate_outputs(
        self,
        node_outputs: dict[str, dict[str, Any]],
        strategy: str,
    ) -> dict[str, Any]:
        """聚合节点输出"""
        if strategy == "merge":
            merged: dict[str, Any] = {}
            for _name, output in node_outputs.items():
                if isinstance(output, dict):
                    merged.update(output)
            return merged

        elif strategy == "list":
            return {"results": list(node_outputs.values())}

        elif strategy == "last":
            if node_outputs:
                last_key = list(node_outputs.keys())[-1]
                return node_outputs[last_key]
            return {}

        elif strategy == "first":
            if node_outputs:
                first_key = list(node_outputs.keys())[0]
                return node_outputs[first_key]
            return {}

        # 默认返回全部
        return node_outputs

    def _emit_event(self, event: DependencyExecutionEvent) -> None:
        """发布事件"""
        if self.event_callback:
            self.event_callback(event)

        # 记录日志
        self._logger.info(
            f"[{event.status.upper()}] {event.node_name} "
            f"(order={event.execution_order}, deps={event.dependencies})"
        )
