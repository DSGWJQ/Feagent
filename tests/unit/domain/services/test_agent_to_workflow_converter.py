"""AgentToWorkflowConverter 单元测试

测试目标：
1. 测试 Agent 和 Tasks 到 Workflow 的转换
2. 测试节点类型推断逻辑
3. 测试节点配置生成
4. 测试节点位置计算
5. 测试 START 和 END 节点的创建

遵循 TDD 原则：
- 测试先行
- 每个测试只验证一个功能点
- 测试命名清晰描述测试场景
"""

import pytest

from src.domain.entities.agent import Agent
from src.domain.entities.task import Task
from src.domain.services.agent_to_workflow_converter import AgentToWorkflowConverter
from src.domain.value_objects.node_type import NodeType


class TestAgentToWorkflowConverter:
    """AgentToWorkflowConverter 测试类

    测试策略：
    - 正向测试：验证正确的输入产生正确的输出
    - 边界测试：验证空任务列表等边界情况
    - 推断测试：验证节点类型推断的准确性
    """

    @pytest.fixture
    def converter(self) -> AgentToWorkflowConverter:
        """创建转换器实例

        为什么使用 fixture？
        - 避免在每个测试中重复创建转换器
        - 保证测试隔离性（每个测试都有独立的转换器）
        """
        return AgentToWorkflowConverter()

    @pytest.fixture
    def sample_agent(self) -> Agent:
        """创建示例 Agent

        为什么使用 fixture？
        - 避免在每个测试中重复创建 Agent
        - 提供一致的测试数据
        """
        return Agent.create(
            start="我有一个CSV文件，包含销售数据",
            goal="分析数据并生成报告",
            name="测试Agent",
        )

    def test_convert_agent_with_tasks_to_workflow(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：将 Agent 和 Tasks 转换为 Workflow

        验证点：
        1. Workflow 基本信息正确
        2. 节点数量正确（START + Tasks + END）
        3. 边数量正确（节点数 - 1）
        4. Source 和 Source ID 正确
        """
        # Arrange：准备测试数据
        tasks = [
            Task.create(agent_id=sample_agent.id, name="读取CSV文件"),
            Task.create(agent_id=sample_agent.id, name="分析销售数据"),
        ]

        # Act：执行转换
        workflow = converter.convert(sample_agent, tasks)

        # Assert：验证结果
        # 验证 Workflow 基本信息
        assert workflow.name == f"Agent-{sample_agent.name}"
        assert sample_agent.start in workflow.description
        assert sample_agent.goal in workflow.description
        assert workflow.source == "feagent"
        assert workflow.source_id == sample_agent.id

        # 验证节点数量：START + 2个Task + END = 4
        assert len(workflow.nodes) == 4

        # 验证边数量：4个节点 = 3条边
        assert len(workflow.edges) == 3

    def test_convert_creates_start_and_end_nodes(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：转换时创建 START 和 END 节点

        验证点：
        1. 第一个节点是 START 类型
        2. 最后一个节点是 END 类型
        3. START 节点名称为"开始"
        4. END 节点名称为"结束"
        """
        # Arrange
        tasks = [
            Task.create(agent_id=sample_agent.id, name="任务1"),
        ]

        # Act
        workflow = converter.convert(sample_agent, tasks)

        # Assert
        # 验证第一个节点是 START
        assert workflow.nodes[0].type == NodeType.START
        assert workflow.nodes[0].name == "开始"

        # 验证最后一个节点是 END
        assert workflow.nodes[-1].type == NodeType.END
        assert workflow.nodes[-1].name == "结束"

    def test_infer_node_type_for_file_operations(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：推断文件操作的节点类型

        验证点：
        包含"读取"、"加载"、"获取"、"下载"等关键词的任务
        应该被推断为 FILE 类型
        """
        # Arrange：创建包含文件操作关键词的任务
        tasks = [
            Task.create(agent_id=sample_agent.id, name="读取CSV文件"),
            Task.create(agent_id=sample_agent.id, name="加载数据"),
            Task.create(agent_id=sample_agent.id, name="获取文件"),
            Task.create(agent_id=sample_agent.id, name="下载报告"),
        ]

        # Act
        workflow = converter.convert(sample_agent, tasks)

        # Assert：所有这些任务都应该被推断为 FILE 类型
        # 跳过 START 和 END 节点
        task_nodes = workflow.nodes[1:-1]
        for node in task_nodes:
            assert node.type == NodeType.FILE, f"任务 '{node.name}' 应该被推断为 FILE 类型"

    def test_infer_node_type_for_http_requests(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：推断 HTTP 请求的节点类型

        验证点：
        包含"调用"、"请求"、"API"、"HTTP"等关键词的任务
        应该被推断为 HTTP 类型
        """
        # Arrange
        tasks = [
            Task.create(agent_id=sample_agent.id, name="调用天气API"),
            Task.create(agent_id=sample_agent.id, name="请求数据"),
            Task.create(agent_id=sample_agent.id, name="HTTP接口"),
        ]

        # Act
        workflow = converter.convert(sample_agent, tasks)

        # Assert
        task_nodes = workflow.nodes[1:-1]
        for node in task_nodes:
            assert node.type == NodeType.HTTP, f"任务 '{node.name}' 应该被推断为 HTTP 类型"

    def test_infer_node_type_for_llm_analysis(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：推断 LLM 分析的节点类型

        验证点：
        包含"分析"、"理解"、"总结"、"提取"等关键词的任务
        应该被推断为 LLM 类型
        """
        # Arrange
        tasks = [
            Task.create(agent_id=sample_agent.id, name="分析销售数据"),
            Task.create(agent_id=sample_agent.id, name="理解文本"),
            Task.create(agent_id=sample_agent.id, name="总结报告"),
            Task.create(agent_id=sample_agent.id, name="提取关键信息"),
        ]

        # Act
        workflow = converter.convert(sample_agent, tasks)

        # Assert
        task_nodes = workflow.nodes[1:-1]
        for node in task_nodes:
            assert node.type == NodeType.LLM, f"任务 '{node.name}' 应该被推断为 LLM 类型"

    def test_infer_node_type_defaults_to_prompt(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：无法推断时默认为 PROMPT 类型

        验证点：
        不包含任何已知关键词的任务应该默认为 PROMPT 类型
        """
        # Arrange
        tasks = [
            Task.create(agent_id=sample_agent.id, name="未知任务"),
            Task.create(agent_id=sample_agent.id, name="神秘操作"),
        ]

        # Act
        workflow = converter.convert(sample_agent, tasks)

        # Assert
        task_nodes = workflow.nodes[1:-1]
        for node in task_nodes:
            assert node.type == NodeType.PROMPT, f"任务 '{node.name}' 应该默认为 PROMPT 类型"

    def test_generate_node_config_for_llm(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：为 LLM 节点生成配置

        验证点：
        1. LLM 节点配置包含 model 字段
        2. LLM 节点配置包含 temperature 字段
        3. LLM 节点配置包含 prompt 字段（使用任务描述）
        """
        # Arrange
        task = Task.create(
            agent_id=sample_agent.id,
            name="分析数据",
            description="使用AI分析销售数据",
        )

        # Act
        node_type = converter._infer_node_type(task)
        config = converter._generate_node_config(task, node_type)

        # Assert
        assert node_type == NodeType.LLM
        assert config["model"] == "kimi"
        assert config["temperature"] == 0.7
        assert config["prompt"] == "使用AI分析销售数据"

    def test_generate_node_config_for_http(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：为 HTTP 节点生成配置

        验证点：
        1. HTTP 节点配置包含 method 字段（默认 GET）
        2. HTTP 节点配置包含 url 字段（空字符串，需用户填写）
        3. HTTP 节点配置包含 headers 字段（空字典）
        """
        # Arrange
        task = Task.create(agent_id=sample_agent.id, name="调用API")

        # Act
        node_type = converter._infer_node_type(task)
        config = converter._generate_node_config(task, node_type)

        # Assert
        assert node_type == NodeType.HTTP
        assert config["method"] == "GET"
        assert config["url"] == ""
        assert config["headers"] == {}

    def test_calculate_node_position_horizontal_layout(
        self,
        converter: AgentToWorkflowConverter,
    ):
        """测试：节点位置计算（水平布局）

        验证点：
        1. 第一个节点（START）位置：x=50, y=250
        2. 第二个节点位置：x=250, y=250
        3. 第三个节点位置：x=450, y=250
        4. 节点间距为 200px
        5. 所有节点在同一水平线（y=250）
        """
        # Act
        pos0 = converter._calculate_position(0)
        pos1 = converter._calculate_position(1)
        pos2 = converter._calculate_position(2)

        # Assert
        # 验证第一个节点位置
        assert pos0.x == 50
        assert pos0.y == 250

        # 验证节点间距为 200px
        assert pos1.x == 250
        assert pos1.y == 250

        assert pos2.x == 450
        assert pos2.y == 250

    def test_edges_connect_all_nodes_sequentially(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：边正确连接所有节点

        验证点：
        1. 边的数量等于节点数量 - 1
        2. 第一条边连接 START 和第一个 Task
        3. 最后一条边连接最后一个 Task 和 END
        4. 所有边按顺序连接节点
        """
        # Arrange
        tasks = [
            Task.create(agent_id=sample_agent.id, name="任务1"),
            Task.create(agent_id=sample_agent.id, name="任务2"),
            Task.create(agent_id=sample_agent.id, name="任务3"),
        ]

        # Act
        workflow = converter.convert(sample_agent, tasks)

        # Assert
        # 验证边的数量：4个节点（START + 3个Task）+ END = 5个节点 = 4条边
        # 但实际应该是 5个节点（START + 3个Task + END）= 4条边
        assert len(workflow.edges) == len(workflow.nodes) - 1

        # 验证第一条边连接 START 和第一个 Task
        first_edge = workflow.edges[0]
        assert first_edge.source_node_id == workflow.nodes[0].id  # START
        assert first_edge.target_node_id == workflow.nodes[1].id  # Task1

        # 验证最后一条边连接最后一个 Task 和 END
        last_edge = workflow.edges[-1]
        assert last_edge.source_node_id == workflow.nodes[-2].id  # 最后一个Task
        assert last_edge.target_node_id == workflow.nodes[-1].id  # END

    def test_convert_with_empty_task_list(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：转换空任务列表

        验证点：
        即使没有任务，也应该创建包含 START 和 END 的 Workflow
        """
        # Arrange
        tasks = []

        # Act
        workflow = converter.convert(sample_agent, tasks)

        # Assert
        # 应该只有 START 和 END 两个节点
        assert len(workflow.nodes) == 2
        assert workflow.nodes[0].type == NodeType.START
        assert workflow.nodes[1].type == NodeType.END

        # 应该只有一条边连接 START 和 END
        assert len(workflow.edges) == 1
        assert workflow.edges[0].source_node_id == workflow.nodes[0].id
        assert workflow.edges[0].target_node_id == workflow.nodes[1].id

    def test_node_config_uses_task_description_when_available(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：节点配置优先使用任务描述

        验证点：
        当任务有描述时，应该使用描述而不是任务名称作为配置
        """
        # Arrange
        task = Task.create(
            agent_id=sample_agent.id,
            name="分析数据",
            description="详细的任务描述：使用AI深度分析",
        )

        # Act
        node_type = converter._infer_node_type(task)
        config = converter._generate_node_config(task, node_type)

        # Assert
        assert config["prompt"] == "详细的任务描述：使用AI深度分析"

    def test_node_config_falls_back_to_task_name(
        self,
        converter: AgentToWorkflowConverter,
        sample_agent: Agent,
    ):
        """测试：没有描述时使用任务名称

        验证点：
        当任务没有描述时，应该使用任务名称作为配置
        """
        # Arrange
        task = Task.create(
            agent_id=sample_agent.id,
            name="分析数据",
            description=None,
        )

        # Act
        node_type = converter._infer_node_type(task)
        config = converter._generate_node_config(task, node_type)

        # Assert
        assert config["prompt"] == "分析数据"
