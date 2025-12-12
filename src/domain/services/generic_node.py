"""通用节点（GenericNode）

支持子工作流封装的可复用节点组件。

组件：
- NodeType: 节点类型枚举
- NodeLifecycle: 节点生命周期枚举
- ChildNode: 子节点数据类
- GenericNode: 通用节点
- GenericNodeExecutor: 通用节点执行器

功能：
- 子节点管理：添加、移除、重排序
- 展开/折叠：切换显示模式
- 输入输出映射：定义对外接口
- 生命周期管理：临时 → 持久化 → 模板
- 执行代理：按顺序执行子节点

设计原则：
- 封装复杂性：将多节点流程封装为单个可复用单元
- 接口清晰：通过映射定义清晰的输入输出
- 渐进式持久化：从临时到模板的生命周期演进

"""

import copy
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """节点类型枚举"""

    # 基础节点
    START = "start"
    END = "end"

    # 控制流节点
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"

    # AI能力节点
    LLM = "llm"
    KNOWLEDGE = "knowledge"
    CLASSIFY = "classify"
    TEMPLATE = "template"

    # 执行节点
    API = "api"
    CODE = "code"
    MCP = "mcp"

    # 通用节点
    GENERIC = "generic"


class NodeLifecycle(Enum):
    """节点生命周期

    - TEMPORARY: 临时，仅当前会话有效
    - PERSISTED: 持久化，保存到当前工作流
    - TEMPLATE: 模板，用户级可复用
    - GLOBAL: 全局，系统级可用
    """

    TEMPORARY = "temporary"
    PERSISTED = "persisted"
    TEMPLATE = "template"
    GLOBAL = "global"


# 有效的生命周期转换
VALID_LIFECYCLE_TRANSITIONS = {
    NodeLifecycle.TEMPORARY: [NodeLifecycle.PERSISTED],
    NodeLifecycle.PERSISTED: [NodeLifecycle.TEMPLATE, NodeLifecycle.TEMPORARY],
    NodeLifecycle.TEMPLATE: [NodeLifecycle.GLOBAL],
    NodeLifecycle.GLOBAL: [],
}


@dataclass
class ChildNode:
    """子节点

    通用节点内部的子节点数据结构。

    属性：
        id: 节点唯一标识
        type: 节点类型
        config: 节点配置
        position: 节点位置（可选，用于画布显示）
    """

    id: str
    type: NodeType
    config: dict[str, Any] = field(default_factory=dict)
    position: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "config": self.config,
            "position": self.position,
        }


class GenericNode:
    """通用节点

    支持子工作流封装的可复用节点。

    使用示例：
        # 创建通用节点
        node = GenericNode(
            id="pipeline_1",
            name="数据处理管道",
            children=[api_node, code_node, llm_node]
        )

        # 定义输入输出映射
        node.set_input_mapping({"query": "api_node.url"})
        node.set_output_mapping({"result": "llm_node.response"})

        # 保存为模板
        node.promote(NodeLifecycle.PERSISTED)
        node.promote(NodeLifecycle.TEMPLATE)

        # 从模板创建实例
        instance = node.create_instance("instance_1", "workflow_xyz")
    """

    def __init__(
        self,
        id: str,
        name: str,
        description: str | None = None,
        children: list[ChildNode] | None = None,
        lifecycle: NodeLifecycle = NodeLifecycle.TEMPORARY,
    ):
        """初始化

        参数：
            id: 节点唯一标识
            name: 节点名称
            description: 节点描述
            children: 子节点列表
            lifecycle: 生命周期
        """
        self.id = id
        self.name = name
        self.description = description
        self.type = NodeType.GENERIC
        self.lifecycle = lifecycle

        # 子节点
        self._children: list[ChildNode] = children or []

        # 嵌套的通用节点
        self._generic_children: list[GenericNode] = []

        # 展开/折叠状态
        self._collapsed = True

        # 输入输出映射
        self._input_mapping: dict[str, str] = {}
        self._output_mapping: dict[str, str] = {}

    @property
    def children(self) -> list[ChildNode]:
        """获取子节点列表"""
        return self._children

    @property
    def generic_children(self) -> list["GenericNode"]:
        """获取嵌套的通用节点列表"""
        return self._generic_children

    @property
    def is_collapsed(self) -> bool:
        """是否处于折叠状态"""
        return self._collapsed

    # ========== 展开/折叠 ==========

    def expand(self) -> "GenericNode":
        """展开节点

        返回：
            self，支持链式调用
        """
        self._collapsed = False
        return self

    def collapse(self) -> "GenericNode":
        """折叠节点

        返回：
            self，支持链式调用
        """
        self._collapsed = True
        return self

    # ========== 子节点管理 ==========

    def add_child(self, child: ChildNode) -> None:
        """添加子节点

        参数：
            child: 要添加的子节点
        """
        self._children.append(child)

    def add_generic_child(self, generic_node: "GenericNode") -> None:
        """添加嵌套的通用节点

        参数：
            generic_node: 要添加的通用节点
        """
        self._generic_children.append(generic_node)

    def remove_child(self, child_id: str) -> bool:
        """移除子节点

        参数：
            child_id: 要移除的子节点ID

        返回：
            是否成功移除
        """
        for i, child in enumerate(self._children):
            if child.id == child_id:
                self._children.pop(i)
                return True
        return False

    def reorder_children(self, order: list[str]) -> None:
        """重新排序子节点

        参数：
            order: 新的子节点ID顺序
        """
        child_map = {c.id: c for c in self._children}
        self._children = [child_map[id] for id in order if id in child_map]

    # ========== 输入输出映射 ==========

    def set_input_mapping(self, mapping: dict[str, str]) -> None:
        """设置输入映射

        参数：
            mapping: 输入映射 {外部字段: 内部节点.字段}
        """
        self._input_mapping = mapping

    def get_input_mapping(self) -> dict[str, str]:
        """获取输入映射"""
        return self._input_mapping.copy()

    def set_output_mapping(self, mapping: dict[str, str]) -> None:
        """设置输出映射

        参数：
            mapping: 输出映射 {外部字段: 内部节点.字段}
        """
        self._output_mapping = mapping

    def get_output_mapping(self) -> dict[str, str]:
        """获取输出映射"""
        return self._output_mapping.copy()

    # ========== 生命周期管理 ==========

    def promote(self, to: NodeLifecycle) -> "GenericNode":
        """提升生命周期

        参数：
            to: 目标生命周期

        返回：
            self，支持链式调用

        异常：
            ValueError: 无效的生命周期转换
        """
        valid_targets = VALID_LIFECYCLE_TRANSITIONS.get(self.lifecycle, [])

        if to not in valid_targets:
            raise ValueError(f"无效的生命周期转换: {self.lifecycle.value} -> {to.value}")

        self.lifecycle = to
        return self

    def create_instance(self, new_id: str, workflow_id: str) -> "GenericNode":
        """从模板创建实例

        参数：
            new_id: 新实例的ID
            workflow_id: 所属工作流ID

        返回：
            新的GenericNode实例
        """
        # 深拷贝子节点
        new_children = []
        for child in self._children:
            new_child = ChildNode(
                id=f"{new_id}_{child.id}",
                type=child.type,
                config=copy.deepcopy(child.config),
                position=copy.deepcopy(child.position) if child.position else None,
            )
            new_children.append(new_child)

        # 创建新实例
        instance = GenericNode(
            id=new_id,
            name=self.name,
            description=self.description,
            children=new_children,
            lifecycle=NodeLifecycle.TEMPORARY,  # 实例从临时开始
        )

        # 构建旧ID到新ID的映射
        id_mapping = {child.id: f"{new_id}_{child.id}" for child in self._children}

        # 更新输入映射 - 子节点ID需要添加新前缀
        new_input_mapping = {}
        for key, value in self._input_mapping.items():
            if "." in value:
                child_id, field = value.split(".", 1)
                if child_id in id_mapping:
                    new_input_mapping[key] = f"{id_mapping[child_id]}.{field}"
                else:
                    new_input_mapping[key] = value
            else:
                new_input_mapping[key] = value
        instance._input_mapping = new_input_mapping

        # 更新输出映射
        new_output_mapping = {}
        for key, value in self._output_mapping.items():
            if "." in value:
                child_id, field = value.split(".", 1)
                if child_id in id_mapping:
                    new_output_mapping[key] = f"{id_mapping[child_id]}.{field}"
                else:
                    new_output_mapping[key] = value
            else:
                new_output_mapping[key] = value
        instance._output_mapping = new_output_mapping

        return instance

    # ========== 画布数据 ==========

    def to_canvas_data(self) -> dict[str, Any]:
        """转换为画布数据

        返回：
            画布渲染所需的数据结构
        """
        if self._collapsed:
            return {
                "id": self.id,
                "type": "generic",
                "data": {
                    "label": self.name,
                    "description": self.description,
                    "collapsed": True,
                    "childCount": len(self._children),
                    "lifecycle": self.lifecycle.value,
                },
            }
        else:
            data = {
                "id": self.id,
                "type": "generic_expanded",
                "data": {
                    "label": self.name,
                    "description": self.description,
                    "collapsed": False,
                    "children": [c.to_dict() for c in self._children],
                    "lifecycle": self.lifecycle.value,
                },
            }

            # 如果有嵌套的通用节点
            if self._generic_children:
                data["data"]["genericChildren"] = [
                    gc.to_canvas_data() for gc in self._generic_children
                ]

            return data


class NodeExecutorProtocol(Protocol):
    """节点执行器协议"""

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行节点"""
        ...


class GenericNodeExecutor:
    """通用节点执行器

    按顺序执行通用节点内的子节点。

    使用示例：
        executor = GenericNodeExecutor(node_executor=my_executor)
        result = await executor.execute(generic_node, inputs={"query": "test"})
    """

    def __init__(self, node_executor: NodeExecutorProtocol):
        """初始化

        参数：
            node_executor: 单节点执行器
        """
        self.node_executor = node_executor

    async def execute(self, generic_node: GenericNode, inputs: dict[str, Any]) -> dict[str, Any]:
        """执行通用节点

        参数：
            generic_node: 要执行的通用节点
            inputs: 外部输入

        返回：
            执行结果（经过输出映射）
        """
        # 应用输入映射
        mapped_inputs = self._apply_input_mapping(inputs, generic_node.get_input_mapping())

        # 存储每个节点的输出
        node_outputs: dict[str, dict[str, Any]] = {}

        # 按顺序执行子节点
        current_inputs = mapped_inputs.copy()

        for child in generic_node.children:
            # 获取该节点的输入
            node_inputs = self._get_node_inputs(child.id, current_inputs, node_outputs)

            # 执行节点
            output = await self.node_executor.execute(
                node_id=child.id, config=child.config, inputs=node_inputs
            )

            # 存储输出
            node_outputs[child.id] = output

            # 更新当前输入（用于下一个节点）
            current_inputs.update(output)

        # 应用输出映射
        result = self._apply_output_mapping(node_outputs, generic_node.get_output_mapping())

        return result

    def _apply_input_mapping(
        self, inputs: dict[str, Any], mapping: dict[str, str]
    ) -> dict[str, Any]:
        """应用输入映射

        将外部输入映射到内部节点字段。

        参数：
            inputs: 外部输入
            mapping: 输入映射

        返回：
            映射后的输入
        """
        result = {}

        for external_key, internal_path in mapping.items():
            if external_key in inputs:
                # 解析路径：node_id.field
                parts = internal_path.split(".")
                if len(parts) == 2:
                    node_id, field = parts
                    if node_id not in result:
                        result[node_id] = {}
                    result[f"{node_id}.{field}"] = inputs[external_key]
                else:
                    result[internal_path] = inputs[external_key]

        return result

    def _get_node_inputs(
        self, node_id: str, mapped_inputs: dict[str, Any], node_outputs: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """获取节点输入

        参数：
            node_id: 节点ID
            mapped_inputs: 映射后的输入
            node_outputs: 已执行节点的输出

        返回：
            该节点的输入
        """
        inputs = {}

        # 从映射输入中获取
        for key, value in mapped_inputs.items():
            if key.startswith(f"{node_id}."):
                field = key.split(".", 1)[1]
                inputs[field] = value

        # 从前序节点输出中获取
        for _, output in node_outputs.items():
            inputs.update(output)

        return inputs

    def _apply_output_mapping(
        self, node_outputs: dict[str, dict[str, Any]], mapping: dict[str, str]
    ) -> dict[str, Any]:
        """应用输出映射

        将内部节点输出映射为通用节点的输出。

        参数：
            node_outputs: 所有节点的输出
            mapping: 输出映射

        返回：
            映射后的输出
        """
        if not mapping:
            # 无映射时，返回最后一个节点的输出
            if node_outputs:
                last_output = list(node_outputs.values())[-1]
                return last_output
            return {}

        result = {}

        for external_key, internal_path in mapping.items():
            # 解析路径：node_id.field
            parts = internal_path.split(".")
            if len(parts) == 2:
                node_id, field = parts
                if node_id in node_outputs and field in node_outputs[node_id]:
                    result[external_key] = node_outputs[node_id][field]

        return result


# 导出
__all__ = [
    "NodeType",
    "NodeLifecycle",
    "ChildNode",
    "GenericNode",
    "GenericNodeExecutor",
    "NodeExecutorProtocol",
]
