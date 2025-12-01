"""GoalDecomposer 目标分解器测试

TDD测试 - 智能目标分解功能

Phase 3.2: 智能目标分解 (GoalDecomposer)

测试分类：
1. Goal实体测试 - 目标数据结构
2. 基础分解测试 - 单层目标分解
3. 依赖关系测试 - 子目标依赖处理
4. LLM集成测试 - 实际LLM分解
5. 真实业务场景测试 - 复杂目标分解
"""

import json
from unittest.mock import AsyncMock

import pytest


class TestGoalEntity:
    """Goal实体测试"""

    def test_create_goal_with_description(self):
        """测试：创建带描述的目标

        真实业务场景：
        - 用户输入："帮我创建一个用户注册流程"
        - 系统需要把这个目标封装为Goal实体

        验收标准：
        - 目标有唯一ID
        - 目标有描述
        - 初始状态为pending
        """
        from src.domain.services.goal_decomposer import Goal, GoalStatus

        goal = Goal(id="goal_1", description="创建用户注册流程")

        assert goal.id == "goal_1"
        assert goal.description == "创建用户注册流程"
        assert goal.status == GoalStatus.PENDING
        assert goal.parent_id is None
        assert goal.dependencies == []
        assert goal.success_criteria == []

    def test_create_sub_goal_with_parent(self):
        """测试：创建带父目标的子目标

        真实业务场景：
        - 父目标："创建用户注册流程"
        - 子目标："实现邮箱验证"，属于父目标

        验收标准：
        - 子目标有parent_id指向父目标
        - 子目标ID包含父目标ID前缀
        """
        from src.domain.services.goal_decomposer import Goal

        parent = Goal(id="goal_1", description="创建用户注册流程")
        child = Goal(id="goal_1_sub_0", description="实现邮箱验证", parent_id=parent.id)

        assert child.parent_id == "goal_1"
        assert child.id.startswith("goal_1")

    def test_goal_with_success_criteria(self):
        """测试：目标带完成标准

        真实业务场景：
        - 目标："实现用户登录"
        - 完成标准：["用户可以输入账号密码", "验证成功跳转首页", "验证失败显示错误"]

        验收标准：
        - 目标可以附带多个完成标准
        - 完成标准用于判断目标是否完成
        """
        from src.domain.services.goal_decomposer import Goal

        goal = Goal(
            id="goal_1",
            description="实现用户登录",
            success_criteria=["用户可以输入账号密码", "验证成功跳转首页", "验证失败显示错误"],
        )

        assert len(goal.success_criteria) == 3
        assert "验证成功跳转首页" in goal.success_criteria

    def test_goal_with_dependencies(self):
        """测试：目标带依赖关系

        真实业务场景：
        - 目标A："创建数据库表"
        - 目标B："实现CRUD接口" 依赖 目标A

        验收标准：
        - 目标可以声明依赖其他目标
        - 依赖关系用目标ID表示
        """
        from src.domain.services.goal_decomposer import Goal

        goal_a = Goal(id="goal_a", description="创建数据库表")
        goal_b = Goal(id="goal_b", description="实现CRUD接口", dependencies=["goal_a"])

        assert "goal_a" in goal_b.dependencies

    def test_goal_status_transitions(self):
        """测试：目标状态流转

        真实业务场景：
        - pending -> in_progress -> completed
        - pending -> in_progress -> failed

        验收标准：
        - 目标状态可以正确流转
        - 状态包括：pending, in_progress, completed, failed
        """
        from src.domain.services.goal_decomposer import Goal, GoalStatus

        goal = Goal(id="goal_1", description="测试目标")

        assert goal.status == GoalStatus.PENDING

        goal.start()
        assert goal.status == GoalStatus.IN_PROGRESS

        goal.complete()
        assert goal.status == GoalStatus.COMPLETED

    def test_goal_fail_status(self):
        """测试：目标失败状态"""
        from src.domain.services.goal_decomposer import Goal, GoalStatus

        goal = Goal(id="goal_1", description="测试目标")
        goal.start()
        goal.fail()

        assert goal.status == GoalStatus.FAILED


class TestBasicDecomposition:
    """基础分解测试"""

    @pytest.mark.asyncio
    async def test_decompose_simple_goal(self):
        """测试：分解简单目标

        真实业务场景：
        - 用户目标："创建一个TODO应用"
        - 预期分解为：
          1. 设计数据模型
          2. 创建前端界面
          3. 实现后端API

        验收标准：
        - 返回3-7个子目标
        - 每个子目标有描述和完成标准
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer

        # Mock LLM返回
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "sub_goals": [
                    {
                        "description": "设计数据模型",
                        "dependencies": [],
                        "success_criteria": ["定义TODO实体", "确定字段"],
                    },
                    {
                        "description": "创建前端界面",
                        "dependencies": [0],
                        "success_criteria": ["实现列表页", "实现编辑页"],
                    },
                    {
                        "description": "实现后端API",
                        "dependencies": [0],
                        "success_criteria": ["CRUD接口", "数据验证"],
                    },
                ]
            }
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        parent_goal = Goal(id="goal_1", description="创建一个TODO应用")

        sub_goals = await decomposer.decompose(parent_goal)

        assert len(sub_goals) >= 3
        assert len(sub_goals) <= 7
        assert all(g.parent_id == parent_goal.id for g in sub_goals)
        assert sub_goals[0].description == "设计数据模型"

    @pytest.mark.asyncio
    async def test_decompose_preserves_parent_reference(self):
        """测试：分解后子目标保持父目标引用

        验收标准：
        - 所有子目标的parent_id指向原目标
        - 子目标ID包含父目标ID前缀
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "sub_goals": [
                    {"description": "子目标1", "dependencies": [], "success_criteria": []},
                    {"description": "子目标2", "dependencies": [], "success_criteria": []},
                ]
            }
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        parent = Goal(id="parent_goal", description="父目标")

        sub_goals = await decomposer.decompose(parent)

        assert all(g.parent_id == "parent_goal" for g in sub_goals)
        assert sub_goals[0].id == "parent_goal_sub_0"
        assert sub_goals[1].id == "parent_goal_sub_1"


class TestDependencyHandling:
    """依赖关系测试"""

    @pytest.mark.asyncio
    async def test_establish_dependencies_between_subgoals(self):
        """测试：建立子目标之间的依赖关系

        真实业务场景：
        - 子目标1: "创建数据库" (无依赖)
        - 子目标2: "实现API" (依赖子目标1)
        - 子目标3: "实现前端" (依赖子目标2)

        验收标准：
        - 依赖关系正确建立
        - 依赖使用子目标ID
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "sub_goals": [
                    {"description": "创建数据库", "dependencies": [], "success_criteria": []},
                    {"description": "实现API", "dependencies": [0], "success_criteria": []},
                    {"description": "实现前端", "dependencies": [1], "success_criteria": []},
                ]
            }
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        parent = Goal(id="project", description="完整项目")

        sub_goals = await decomposer.decompose(parent)

        # 子目标0无依赖
        assert sub_goals[0].dependencies == []
        # 子目标1依赖子目标0
        assert "project_sub_0" in sub_goals[1].dependencies
        # 子目标2依赖子目标1
        assert "project_sub_1" in sub_goals[2].dependencies

    @pytest.mark.asyncio
    async def test_get_execution_order_respects_dependencies(self):
        """测试：获取执行顺序尊重依赖关系

        真实业务场景：
        - A (无依赖)
        - B (依赖A)
        - C (依赖A)
        - D (依赖B和C)

        执行顺序应该是：A -> [B,C] -> D

        验收标准：
        - 返回正确的执行顺序
        - 被依赖的目标排在前面
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "sub_goals": [
                    {"description": "A", "dependencies": [], "success_criteria": []},
                    {"description": "B", "dependencies": [0], "success_criteria": []},
                    {"description": "C", "dependencies": [0], "success_criteria": []},
                    {"description": "D", "dependencies": [1, 2], "success_criteria": []},
                ]
            }
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        parent = Goal(id="project", description="项目")

        sub_goals = await decomposer.decompose(parent)
        execution_order = decomposer.get_execution_order(sub_goals)

        # A应该在B和C之前
        a_idx = execution_order.index("project_sub_0")
        b_idx = execution_order.index("project_sub_1")
        c_idx = execution_order.index("project_sub_2")
        d_idx = execution_order.index("project_sub_3")

        assert a_idx < b_idx
        assert a_idx < c_idx
        assert b_idx < d_idx
        assert c_idx < d_idx

    @pytest.mark.asyncio
    async def test_detect_circular_dependencies(self):
        """测试：检测循环依赖

        真实业务场景：
        - A依赖B
        - B依赖A (循环!)

        验收标准：
        - 检测到循环依赖时抛出异常
        """
        from src.domain.services.goal_decomposer import (
            CircularDependencyError,
            Goal,
            GoalDecomposer,
        )

        mock_llm = AsyncMock()
        # 模拟循环依赖 - A依赖B，B依赖A
        mock_llm.generate.return_value = json.dumps(
            {
                "sub_goals": [
                    {"description": "A", "dependencies": [1], "success_criteria": []},
                    {"description": "B", "dependencies": [0], "success_criteria": []},
                ]
            }
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        parent = Goal(id="project", description="项目")

        sub_goals = await decomposer.decompose(parent)

        with pytest.raises(CircularDependencyError):
            decomposer.get_execution_order(sub_goals)


class TestLLMIntegration:
    """LLM集成测试"""

    @pytest.mark.asyncio
    async def test_prompt_includes_goal_description(self):
        """测试：提示词包含目标描述

        验收标准：
        - LLM调用时，提示词包含原始目标描述
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {"sub_goals": [{"description": "测试", "dependencies": [], "success_criteria": []}]}
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        goal = Goal(id="goal_1", description="实现用户认证系统")

        await decomposer.decompose(goal)

        # 验证LLM被调用
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args[0][0]
        assert "实现用户认证系统" in call_args

    @pytest.mark.asyncio
    async def test_handle_llm_json_parse_error(self):
        """测试：处理LLM返回非法JSON

        验收标准：
        - LLM返回非法JSON时抛出明确异常
        """
        from src.domain.services.goal_decomposer import DecompositionError, Goal, GoalDecomposer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "这不是有效的JSON"

        decomposer = GoalDecomposer(llm_client=mock_llm)
        goal = Goal(id="goal_1", description="测试目标")

        with pytest.raises(DecompositionError, match="JSON"):
            await decomposer.decompose(goal)

    @pytest.mark.asyncio
    async def test_handle_empty_subgoals(self):
        """测试：处理空子目标列表

        验收标准：
        - LLM返回空子目标时抛出异常
        """
        from src.domain.services.goal_decomposer import DecompositionError, Goal, GoalDecomposer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps({"sub_goals": []})

        decomposer = GoalDecomposer(llm_client=mock_llm)
        goal = Goal(id="goal_1", description="测试目标")

        with pytest.raises(DecompositionError, match="空"):
            await decomposer.decompose(goal)


class TestRealWorldScenarios:
    """真实业务场景测试"""

    @pytest.mark.asyncio
    async def test_decompose_ecommerce_checkout_flow(self):
        """测试：分解电商结算流程

        真实业务场景：
        - 用户目标："实现电商网站的结算流程"
        - 预期分解：
          1. 购物车管理
          2. 地址管理
          3. 支付集成
          4. 订单生成
          5. 发送通知

        验收标准：
        - 正确分解为多个子目标
        - 依赖关系合理（如订单生成依赖购物车和地址）
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "sub_goals": [
                    {
                        "description": "实现购物车管理",
                        "dependencies": [],
                        "success_criteria": ["添加商品", "修改数量", "删除商品"],
                    },
                    {
                        "description": "实现地址管理",
                        "dependencies": [],
                        "success_criteria": ["添加地址", "选择地址", "设置默认"],
                    },
                    {
                        "description": "集成支付系统",
                        "dependencies": [],
                        "success_criteria": ["支付宝", "微信支付", "银行卡"],
                    },
                    {
                        "description": "生成订单",
                        "dependencies": [0, 1, 2],
                        "success_criteria": ["计算总价", "生成订单号", "保存订单"],
                    },
                    {
                        "description": "发送通知",
                        "dependencies": [3],
                        "success_criteria": ["短信通知", "邮件通知", "APP推送"],
                    },
                ]
            }
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        goal = Goal(id="checkout", description="实现电商网站的结算流程")

        sub_goals = await decomposer.decompose(goal)

        # 验证数量
        assert len(sub_goals) == 5

        # 验证依赖关系
        order_goal = next(g for g in sub_goals if "订单" in g.description)
        assert len(order_goal.dependencies) == 3  # 依赖购物车、地址、支付

        # 验证执行顺序
        order = decomposer.get_execution_order(sub_goals)
        cart_idx = next(i for i, id in enumerate(order) if "sub_0" in id)
        order_idx = next(i for i, id in enumerate(order) if "sub_3" in id)
        notify_idx = next(i for i, id in enumerate(order) if "sub_4" in id)

        assert cart_idx < order_idx < notify_idx

    @pytest.mark.asyncio
    async def test_hierarchical_decomposition(self):
        """测试：层级分解（子目标再分解）

        真实业务场景：
        - 大目标："构建完整的CRM系统"
        - 第一层分解："客户管理"、"销售管理"、"报表分析"
        - "客户管理"再分解："客户列表"、"客户详情"、"客户搜索"

        验收标准：
        - 支持对子目标进行再次分解
        - 保持层级关系清晰
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer

        # 第一次分解的mock
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = [
            # 第一层分解
            json.dumps(
                {
                    "sub_goals": [
                        {"description": "客户管理模块", "dependencies": [], "success_criteria": []},
                        {
                            "description": "销售管理模块",
                            "dependencies": [0],
                            "success_criteria": [],
                        },
                        {
                            "description": "报表分析模块",
                            "dependencies": [0, 1],
                            "success_criteria": [],
                        },
                    ]
                }
            ),
            # 第二层分解（对"客户管理"再分解）
            json.dumps(
                {
                    "sub_goals": [
                        {"description": "客户列表页面", "dependencies": [], "success_criteria": []},
                        {
                            "description": "客户详情页面",
                            "dependencies": [0],
                            "success_criteria": [],
                        },
                        {
                            "description": "客户搜索功能",
                            "dependencies": [0],
                            "success_criteria": [],
                        },
                    ]
                }
            ),
        ]

        decomposer = GoalDecomposer(llm_client=mock_llm)

        # 第一层分解
        root_goal = Goal(id="crm", description="构建完整的CRM系统")
        level1_goals = await decomposer.decompose(root_goal)

        assert len(level1_goals) == 3
        assert level1_goals[0].parent_id == "crm"

        # 第二层分解
        customer_goal = level1_goals[0]  # 客户管理模块
        level2_goals = await decomposer.decompose(customer_goal)

        assert len(level2_goals) == 3
        assert all(g.parent_id == customer_goal.id for g in level2_goals)
        assert level2_goals[0].id.startswith("crm_sub_0_sub_")

    @pytest.mark.asyncio
    async def test_convert_goals_to_workflow_nodes(self):
        """测试：将目标转换为工作流节点

        真实业务场景：
        - 分解后的子目标需要转换为可执行的工作流节点
        - 每个目标对应一个或多个节点

        验收标准：
        - 支持目标到节点的转换
        - 保留依赖关系作为边
        """
        from src.domain.services.goal_decomposer import Goal, GoalDecomposer, GoalToNodeConverter

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "sub_goals": [
                    {"description": "获取用户数据", "dependencies": [], "success_criteria": []},
                    {"description": "处理数据", "dependencies": [0], "success_criteria": []},
                    {"description": "保存结果", "dependencies": [1], "success_criteria": []},
                ]
            }
        )

        decomposer = GoalDecomposer(llm_client=mock_llm)
        goal = Goal(id="pipeline", description="数据处理流程")

        sub_goals = await decomposer.decompose(goal)

        # 转换为节点
        converter = GoalToNodeConverter()
        nodes, edges = converter.convert(sub_goals)

        assert len(nodes) == 3
        assert len(edges) == 2  # 0->1, 1->2

        # 验证节点包含目标描述
        assert nodes[0]["data"]["description"] == "获取用户数据"

        # 验证边连接正确
        assert edges[0]["source"] == "pipeline_sub_0"
        assert edges[0]["target"] == "pipeline_sub_1"


class TestGoalProgress:
    """目标进度跟踪测试"""

    def test_track_goal_progress(self):
        """测试：跟踪目标进度

        真实业务场景：
        - 主目标有3个子目标
        - 完成1个子目标后，进度应该是33%

        验收标准：
        - 能够计算目标完成进度
        - 子目标完成影响父目标进度
        """
        from src.domain.services.goal_decomposer import Goal, GoalProgress

        parent = Goal(id="parent", description="父目标")
        children = [
            Goal(id="child_1", description="子目标1", parent_id="parent"),
            Goal(id="child_2", description="子目标2", parent_id="parent"),
            Goal(id="child_3", description="子目标3", parent_id="parent"),
        ]

        progress_tracker = GoalProgress()
        progress_tracker.add_goal(parent)
        for child in children:
            progress_tracker.add_goal(child)

        # 初始进度为0
        assert progress_tracker.get_progress(parent.id) == 0.0

        # 完成一个子目标
        children[0].start()
        children[0].complete()
        progress_tracker.update_goal(children[0])

        # 进度应该是 1/3 ≈ 33%
        assert abs(progress_tracker.get_progress(parent.id) - 0.333) < 0.01

    def test_all_subgoals_complete_marks_parent_complete(self):
        """测试：所有子目标完成时标记父目标完成

        验收标准：
        - 当所有子目标完成时，父目标自动标记为完成
        """
        from src.domain.services.goal_decomposer import Goal, GoalProgress, GoalStatus

        parent = Goal(id="parent", description="父目标")
        children = [
            Goal(id="child_1", description="子目标1", parent_id="parent"),
            Goal(id="child_2", description="子目标2", parent_id="parent"),
        ]

        progress_tracker = GoalProgress()
        progress_tracker.add_goal(parent)
        for child in children:
            progress_tracker.add_goal(child)

        # 完成所有子目标
        for child in children:
            child.start()
            child.complete()
            progress_tracker.update_goal(child)

        # 父目标应该自动完成
        assert progress_tracker.get_progress(parent.id) == 1.0
        assert parent.status == GoalStatus.COMPLETED
