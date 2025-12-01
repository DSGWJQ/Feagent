"""AgentToWorkflowConverter - Agent 到 Workflow 转换服务

业务场景：
当用户创建 Agent 后，系统自动生成 Workflow，将 Agent 的 Tasks 转换为可视化的节点和边。

职责：
1. 接收 Agent 和 Tasks 列表
2. 推断每个 Task 的节点类型（基于关键词匹配）
3. 生成节点配置（根据节点类型）
4. 计算节点位置（水平排列）
5. 创建 START 和 END 节点
6. 创建边（连接所有节点）
7. 返回 Workflow 实体

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- Domain 服务：封装复杂的业务逻辑
- 启发式规则：通过关键词推断节点类型
- 默认策略：无法推断时使用 PROMPT 节点

为什么是 Domain 服务？
1. 转换逻辑是核心业务规则
2. 不属于任何单个实体（跨 Agent、Task、Workflow）
3. 纯业务逻辑，不依赖基础设施
4. 可以被多个用例复用

为什么使用启发式规则？
1. 快速：不需要额外的 LLM 调用
2. 准确：大部分任务名称包含明确的动词
3. 可扩展：可以轻松添加新规则
4. 可降级：无法推断时使用默认类型
"""

import re
from typing import Any

from src.domain.entities.agent import Agent
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.task import Task
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class AgentToWorkflowConverter:
    """Agent 到 Workflow 转换器

    职责：
    - 将 Agent 和 Tasks 转换为 Workflow
    - 推断节点类型
    - 生成节点配置
    - 计算节点位置
    """

    # 节点类型推断规则（关键词 → NodeType）
    # 格式：正则表达式 → NodeType
    TYPE_INFERENCE_RULES = {
        r"读取|加载|获取|下载|导入|打开": NodeType.FILE,
        r"调用|请求|API|HTTP|接口|访问": NodeType.HTTP,
        r"分析|理解|总结|提取|推理|思考|判断": NodeType.LLM,
        r"转换|处理|格式化|映射|解析": NodeType.TRANSFORM,
        r"查询|数据库|SQL|存储|插入|更新": NodeType.DATABASE,
        r"条件|如果|判断|分支": NodeType.CONDITIONAL,
        r"循环|遍历|重复|迭代": NodeType.LOOP,
        r"通知|发送|邮件|消息|推送": NodeType.NOTIFICATION,
        r"图像|图片|生成图|绘制|可视化": NodeType.IMAGE,
        r"音频|语音|声音": NodeType.AUDIO,
    }

    # 默认节点类型（无法推断时使用）
    DEFAULT_NODE_TYPE = NodeType.PROMPT

    # 节点布局参数
    START_X = 50
    START_Y = 250
    NODE_SPACING = 200  # 节点间距
    NODE_Y = 250  # 所有节点在同一水平线上

    def convert(self, agent: Agent, tasks: list[Task]) -> Workflow:
        """将 Agent 和 Tasks 转换为 Workflow

        业务流程：
        1. 创建 START 节点
        2. 为每个 Task 创建节点
           - 推断节点类型
           - 生成节点配置
           - 计算节点位置
        3. 创建 END 节点
        4. 创建边（连接所有节点）
        5. 创建 Workflow 实体

        参数：
            agent: Agent 实体
            tasks: Task 列表

        返回：
            Workflow 实体

        示例：
        >>> agent = Agent.create(start="CSV文件", goal="分析数据")
        >>> tasks = [
        ...     Task.create(agent_id=agent.id, name="读取CSV文件"),
        ...     Task.create(agent_id=agent.id, name="分析销售数据"),
        ... ]
        >>> converter = AgentToWorkflowConverter()
        >>> workflow = converter.convert(agent, tasks)
        >>> len(workflow.nodes)  # START + 2 tasks + END
        4
        >>> len(workflow.edges)  # 3 条边
        3
        """
        nodes: list[Node] = []
        edges: list[Edge] = []

        # 步骤 1: 创建 START 节点
        start_node = self._create_start_node()
        nodes.append(start_node)

        # 步骤 2: 为每个 Task 创建节点
        previous_node_id = start_node.id
        for index, task in enumerate(tasks):
            # 2.1 推断节点类型
            node_type = self._infer_node_type(task)

            # 2.2 生成节点配置
            node_config = self._generate_node_config(task, node_type)

            # 2.3 计算节点位置
            position = self._calculate_position(index + 1)  # +1 因为 START 占用第 0 个位置

            # 2.4 创建节点
            node = Node.create(
                type=node_type,
                name=task.name,
                config=node_config,
                position=position,
            )
            nodes.append(node)

            # 2.5 创建边（连接前一个节点和当前节点）
            edge = Edge.create(
                source_node_id=previous_node_id,
                target_node_id=node.id,
            )
            edges.append(edge)

            # 更新前一个节点 ID
            previous_node_id = node.id

        # 步骤 3: 创建 END 节点
        end_node = self._create_end_node(len(tasks) + 1)  # +1 因为 START 占用第 0 个位置
        nodes.append(end_node)

        # 步骤 4: 创建最后一条边（最后一个 Task → END）
        final_edge = Edge.create(
            source_node_id=previous_node_id,
            target_node_id=end_node.id,
        )
        edges.append(final_edge)

        # 步骤 5: 创建 Workflow 实体
        workflow_name = f"Agent-{agent.name}"
        workflow_description = f"从「{agent.start}」到「{agent.goal}」的自动生成工作流"

        workflow = Workflow.create(
            name=workflow_name,
            description=workflow_description,
            nodes=nodes,
            edges=edges,
            source="feagent",
            source_id=agent.id,
        )

        return workflow

    def _infer_node_type(self, task: Task) -> NodeType:
        """推断任务的节点类型

        推断策略：
        1. 遍历所有推断规则
        2. 检查任务名称或描述是否匹配规则（正则表达式）
        3. 返回第一个匹配的节点类型
        4. 如果没有匹配，返回默认类型（PROMPT）

        参数：
            task: Task 实体

        返回：
            NodeType: 推断的节点类型

        示例：
        >>> task1 = Task.create(agent_id="...", name="读取CSV文件")
        >>> converter = AgentToWorkflowConverter()
        >>> converter._infer_node_type(task1)
        <NodeType.FILE: 'file'>

        >>> task2 = Task.create(agent_id="...", name="调用天气API")
        >>> converter._infer_node_type(task2)
        <NodeType.HTTP: 'http'>

        >>> task3 = Task.create(agent_id="...", name="未知任务")
        >>> converter._infer_node_type(task3)
        <NodeType.PROMPT: 'prompt'>
        """
        # 构造搜索文本：任务名称 + 任务描述
        search_text = task.name
        if task.description:
            search_text += " " + task.description

        # 遍历推断规则
        for pattern, node_type in self.TYPE_INFERENCE_RULES.items():
            if re.search(pattern, search_text, re.IGNORECASE):
                return node_type

        # 没有匹配，返回默认类型
        return self.DEFAULT_NODE_TYPE

    def _generate_node_config(self, task: Task, node_type: NodeType) -> dict[str, Any]:
        """生成节点配置

        根据节点类型生成初始配置：
        - LLM: 提供默认的 model 和 prompt
        - PROMPT: 使用任务描述作为模板
        - HTTP: 提供默认的 method 和空 url（需要用户填写）
        - 其他: 空配置

        参数：
            task: Task 实体
            node_type: 节点类型

        返回：
            dict: 节点配置

        示例：
        >>> task = Task.create(agent_id="...", name="分析数据", description="使用AI分析销售数据")
        >>> converter = AgentToWorkflowConverter()
        >>> config = converter._generate_node_config(task, NodeType.LLM)
        >>> config["model"]
        'kimi'
        """
        if node_type == NodeType.LLM:
            return {
                "model": "kimi",
                "temperature": 0.7,
                "prompt": task.description or task.name,
            }
        elif node_type == NodeType.PROMPT:
            return {
                "template": task.description or task.name,
            }
        elif node_type == NodeType.HTTP:
            return {
                "method": "GET",
                "url": "",  # 需要用户填写
                "headers": {},
            }
        elif node_type == NodeType.FILE:
            return {
                "operation": "read",  # read/write/delete
                "path": "",  # 需要用户填写
            }
        elif node_type == NodeType.DATABASE:
            return {
                "operation": "query",  # query/insert/update/delete
                "sql": "",  # 需要用户填写
            }
        elif node_type == NodeType.TRANSFORM:
            return {
                "expression": task.description or "",
            }
        else:
            # 其他类型：空配置
            return {}

    def _calculate_position(self, index: int) -> Position:
        """计算节点位置

        布局策略：
        - 所有节点在同一水平线上（y = NODE_Y）
        - 节点从左到右排列
        - 每个节点间隔 NODE_SPACING

        参数：
            index: 节点索引（0 是 START，1 是第一个 Task，以此类推）

        返回：
            Position: 节点位置

        示例：
        >>> converter = AgentToWorkflowConverter()
        >>> pos0 = converter._calculate_position(0)
        >>> pos0.x, pos0.y
        (50, 250)

        >>> pos1 = converter._calculate_position(1)
        >>> pos1.x, pos1.y
        (250, 250)
        """
        x = self.START_X + index * self.NODE_SPACING
        y = self.NODE_Y
        return Position(x=x, y=y)

    def _create_start_node(self) -> Node:
        """创建 START 节点

        START 节点是工作流的入口，固定位置在 (START_X, START_Y)

        返回：
            Node: START 节点

        示例：
        >>> converter = AgentToWorkflowConverter()
        >>> start = converter._create_start_node()
        >>> start.type
        <NodeType.START: 'start'>
        >>> start.name
        '开始'
        """
        return Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=self._calculate_position(0),
        )

    def _create_end_node(self, index: int) -> Node:
        """创建 END 节点

        END 节点是工作流的出口，位置根据节点总数计算

        参数：
            index: 节点索引（应该是节点总数 - 1）

        返回：
            Node: END 节点

        示例：
        >>> converter = AgentToWorkflowConverter()
        >>> end = converter._create_end_node(3)
        >>> end.type
        <NodeType.END: 'end'>
        >>> end.name
        '结束'
        """
        return Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=self._calculate_position(index),
        )


# 为什么使用类而不是函数？
# 1. 封装：将相关的方法组织在一起
# 2. 可测试：可以单独测试每个方法
# 3. 可扩展：未来可以添加新的推断规则或配置
# 4. 可复用：可以在多个用例中使用

# 为什么不使用 LLM 推断类型？
# 1. 快速：启发式规则不需要网络请求
# 2. 可预测：规则是确定的，易于调试
# 3. 成本低：不需要额外的 LLM Token
# 4. 离线可用：不依赖外部服务

# 未来可以改进的地方：
# 1. 支持 LLM 推断（作为降级策略）
# 2. 支持自定义推断规则（通过配置文件）
# 3. 支持垂直布局或自动布局
# 4. 支持节点分组（按功能分类）
# 5. 支持从任务描述中提取配置参数（如 URL、SQL 等）
