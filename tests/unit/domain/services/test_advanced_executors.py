"""高级执行器测试

TDD测试 - 条件/循环/并行执行器

Phase 3.4: 完整执行器 (条件/循环/并行)

测试分类：
1. 条件执行器测试 - ConditionExecutor
2. 循环执行器测试 - LoopExecutor
3. 并行执行器测试 - ParallelExecutor
4. 真实业务场景测试 - 复杂控制流
"""

import asyncio
from unittest.mock import AsyncMock

import pytest


class TestConditionExecutor:
    """条件执行器测试"""

    @pytest.mark.asyncio
    async def test_execute_simple_condition_true_branch(self):
        """测试：简单条件 - 执行true分支

        真实业务场景：
        - 用户请求分类
        - 如果是"技术问题" -> 转给技术支持
        - 如果是"销售问题" -> 转给销售团队

        验收标准：
        - 条件为真时执行true分支
        """
        from src.domain.services.advanced_executors import ConditionExecutor

        executor = ConditionExecutor()

        condition_config = {
            "expression": "category == 'technical'",
            "true_branch": "tech_support_node",
            "false_branch": "sales_node",
        }

        inputs = {"category": "technical", "query": "如何安装软件？"}

        result = await executor.execute(condition_config, inputs)

        assert result["branch"] == "true"
        assert result["next_node"] == "tech_support_node"

    @pytest.mark.asyncio
    async def test_execute_simple_condition_false_branch(self):
        """测试：简单条件 - 执行false分支

        验收标准：
        - 条件为假时执行false分支
        """
        from src.domain.services.advanced_executors import ConditionExecutor

        executor = ConditionExecutor()

        condition_config = {
            "expression": "category == 'technical'",
            "true_branch": "tech_support_node",
            "false_branch": "sales_node",
        }

        inputs = {"category": "sales", "query": "产品价格是多少？"}

        result = await executor.execute(condition_config, inputs)

        assert result["branch"] == "false"
        assert result["next_node"] == "sales_node"

    @pytest.mark.asyncio
    async def test_execute_complex_condition(self):
        """测试：复杂条件表达式

        真实业务场景：
        - 订单金额 > 1000 且 会员等级 >= 2 -> 享受折扣
        - 否则 -> 原价

        验收标准：
        - 支持复杂布尔表达式
        """
        from src.domain.services.advanced_executors import ConditionExecutor

        executor = ConditionExecutor()

        condition_config = {
            "expression": "amount > 1000 and level >= 2",
            "true_branch": "discount_node",
            "false_branch": "normal_price_node",
        }

        # 满足条件
        inputs = {"amount": 1500, "level": 3}
        result = await executor.execute(condition_config, inputs)
        assert result["branch"] == "true"

        # 不满足条件（金额不够）
        inputs = {"amount": 500, "level": 3}
        result = await executor.execute(condition_config, inputs)
        assert result["branch"] == "false"

    @pytest.mark.asyncio
    async def test_execute_multi_branch_condition(self):
        """测试：多分支条件（else-if）

        真实业务场景：
        - 分数 >= 90 -> A
        - 分数 >= 80 -> B
        - 分数 >= 60 -> C
        - 否则 -> F

        验收标准：
        - 支持多分支条件
        - 按顺序评估，命中即返回
        """
        from src.domain.services.advanced_executors import ConditionExecutor

        executor = ConditionExecutor()

        condition_config = {
            "type": "multi_branch",
            "branches": [
                {"condition": "score >= 90", "node": "grade_a_node"},
                {"condition": "score >= 80", "node": "grade_b_node"},
                {"condition": "score >= 60", "node": "grade_c_node"},
            ],
            "default_branch": "grade_f_node",
        }

        # 测试A
        result = await executor.execute(condition_config, {"score": 95})
        assert result["next_node"] == "grade_a_node"

        # 测试B
        result = await executor.execute(condition_config, {"score": 85})
        assert result["next_node"] == "grade_b_node"

        # 测试F
        result = await executor.execute(condition_config, {"score": 50})
        assert result["next_node"] == "grade_f_node"


class TestLoopExecutor:
    """循环执行器测试"""

    @pytest.mark.asyncio
    async def test_for_each_loop(self):
        """测试：for_each循环

        真实业务场景：
        - 批量处理用户列表
        - 对每个用户发送通知

        验收标准：
        - 遍历数组中的每个元素
        - 返回所有迭代结果
        """
        from src.domain.services.advanced_executors import LoopExecutor

        # Mock子节点执行器
        mock_node_executor = AsyncMock()
        mock_node_executor.execute.side_effect = [
            {"notification_sent": True, "user_id": 1},
            {"notification_sent": True, "user_id": 2},
            {"notification_sent": True, "user_id": 3},
        ]

        executor = LoopExecutor(node_executor=mock_node_executor)

        loop_config = {
            "type": "for_each",
            "array_input": "users",
            "item_variable": "current_user",
            "body_node": "send_notification_node",
        }

        inputs = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"},
            ]
        }

        result = await executor.execute(loop_config, inputs)

        assert len(result["iterations"]) == 3
        assert mock_node_executor.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_range_loop(self):
        """测试：range循环

        真实业务场景：
        - 生成5个随机测试数据
        - 每次迭代索引从0到4

        验收标准：
        - 指定开始、结束、步长
        - 正确迭代指定次数
        """
        from src.domain.services.advanced_executors import LoopExecutor

        mock_node_executor = AsyncMock()
        mock_node_executor.execute.return_value = {"data": "generated"}

        executor = LoopExecutor(node_executor=mock_node_executor)

        loop_config = {
            "type": "range",
            "start": 0,
            "end": 5,
            "step": 1,
            "index_variable": "i",
            "body_node": "generate_data_node",
        }

        result = await executor.execute(loop_config, {})

        assert len(result["iterations"]) == 5
        assert mock_node_executor.execute.call_count == 5

    @pytest.mark.asyncio
    async def test_while_loop_with_condition(self):
        """测试：while循环

        真实业务场景：
        - 轮询API直到数据就绪
        - 最多尝试10次

        验收标准：
        - 条件为真时继续循环
        - 条件为假或达到最大次数时停止
        """
        from src.domain.services.advanced_executors import LoopExecutor

        # 模拟：前2次返回not_ready，第3次返回ready
        mock_node_executor = AsyncMock()
        mock_node_executor.execute.side_effect = [
            {"status": "not_ready"},
            {"status": "not_ready"},
            {"status": "ready"},
        ]

        executor = LoopExecutor(node_executor=mock_node_executor)

        loop_config = {
            "type": "while",
            "condition": "status != 'ready'",
            "max_iterations": 10,
            "body_node": "poll_api_node",
        }

        inputs = {"status": "not_ready"}

        result = await executor.execute(loop_config, inputs)

        # 应该执行3次后退出
        assert result["iteration_count"] == 3
        assert result["exit_reason"] == "condition_false"

    @pytest.mark.asyncio
    async def test_loop_with_break(self):
        """测试：循环中断

        真实业务场景：
        - 搜索列表中的目标元素
        - 找到后立即停止

        验收标准：
        - 支持提前中断循环
        """
        from src.domain.services.advanced_executors import LoopExecutor

        mock_node_executor = AsyncMock()
        mock_node_executor.execute.side_effect = [
            {"found": False},
            {"found": True, "_break": True},  # 找到了，中断
            {"found": False},  # 这个不应该执行
        ]

        executor = LoopExecutor(node_executor=mock_node_executor)

        loop_config = {
            "type": "for_each",
            "array_input": "items",
            "item_variable": "item",
            "body_node": "search_node",
            "break_on": "_break",
        }

        inputs = {"items": [1, 2, 3, 4, 5]}

        result = await executor.execute(loop_config, inputs)

        assert result["iteration_count"] == 2
        assert result["exit_reason"] == "break"


class TestParallelExecutor:
    """并行执行器测试"""

    @pytest.mark.asyncio
    async def test_parallel_execution_all_branches(self):
        """测试：并行执行所有分支

        真实业务场景：
        - 同时调用多个API获取数据
        - 用户信息、订单信息、推荐信息同时获取

        验收标准：
        - 所有分支并行执行
        - 收集所有结果
        """
        from src.domain.services.advanced_executors import ParallelExecutor

        mock_node_executor = AsyncMock()

        async def mock_execute(node_id, inputs):
            await asyncio.sleep(0.1)  # 模拟网络延迟
            return {f"{node_id}_result": f"data_from_{node_id}"}

        mock_node_executor.execute.side_effect = mock_execute

        executor = ParallelExecutor(node_executor=mock_node_executor)

        parallel_config = {
            "branches": [
                {"node": "get_user_info", "output_key": "user"},
                {"node": "get_orders", "output_key": "orders"},
                {"node": "get_recommendations", "output_key": "recommendations"},
            ]
        }

        inputs = {"user_id": "123"}

        result = await executor.execute(parallel_config, inputs)

        # 验证所有分支都执行了
        assert "user" in result
        assert "orders" in result
        assert "recommendations" in result
        assert mock_node_executor.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_parallel_execution_with_timeout(self):
        """测试：并行执行带超时

        真实业务场景：
        - 调用外部API
        - 设置超时，防止无限等待

        验收标准：
        - 支持设置超时
        - 超时的分支返回错误
        """
        from src.domain.services.advanced_executors import ParallelExecutor

        mock_node_executor = AsyncMock()

        async def mock_execute(node_id, inputs):
            if node_id == "slow_api":
                await asyncio.sleep(2)  # 慢API
            else:
                await asyncio.sleep(0.1)
            return {"result": "ok"}

        mock_node_executor.execute.side_effect = mock_execute

        executor = ParallelExecutor(node_executor=mock_node_executor)

        parallel_config = {
            "branches": [
                {"node": "fast_api", "output_key": "fast"},
                {"node": "slow_api", "output_key": "slow"},
            ],
            "timeout": 0.5,  # 0.5秒超时
        }

        result = await executor.execute(parallel_config, {})

        # fast_api应该成功
        assert "fast" in result
        # slow_api应该超时
        assert result.get("slow", {}).get("error") == "timeout"

    @pytest.mark.asyncio
    async def test_parallel_execution_with_error_handling(self):
        """测试：并行执行错误处理

        真实业务场景：
        - 部分API调用失败
        - 不应影响其他分支

        验收标准：
        - 单个分支失败不影响其他分支
        - 失败分支返回错误信息
        """
        from src.domain.services.advanced_executors import ParallelExecutor

        mock_node_executor = AsyncMock()

        async def mock_execute(node_id, inputs):
            if node_id == "failing_api":
                raise Exception("API调用失败")
            return {"result": "ok"}

        mock_node_executor.execute.side_effect = mock_execute

        executor = ParallelExecutor(node_executor=mock_node_executor)

        parallel_config = {
            "branches": [
                {"node": "good_api", "output_key": "good"},
                {"node": "failing_api", "output_key": "failed"},
            ],
            "fail_fast": False,  # 不快速失败
        }

        result = await executor.execute(parallel_config, {})

        # good_api应该成功
        assert result["good"]["result"] == "ok"
        # failing_api应该有错误
        assert "error" in result["failed"]

    @pytest.mark.asyncio
    async def test_parallel_execution_wait_for_first(self):
        """测试：并行执行等待第一个完成

        真实业务场景：
        - 从多个镜像源下载文件
        - 任意一个完成即可

        验收标准：
        - 返回第一个完成的结果
        - 取消其他分支
        """
        from src.domain.services.advanced_executors import ParallelExecutor

        mock_node_executor = AsyncMock()

        async def mock_execute(node_id, inputs):
            if node_id == "fast_mirror":
                await asyncio.sleep(0.1)
            else:
                await asyncio.sleep(1)  # 慢镜像
            return {"source": node_id, "data": "file_content"}

        mock_node_executor.execute.side_effect = mock_execute

        executor = ParallelExecutor(node_executor=mock_node_executor)

        parallel_config = {
            "branches": [
                {"node": "fast_mirror", "output_key": "result"},
                {"node": "slow_mirror_1", "output_key": "result"},
                {"node": "slow_mirror_2", "output_key": "result"},
            ],
            "wait_for": "first",  # 等待第一个完成
        }

        result = await executor.execute(parallel_config, {})

        # 应该是快镜像的结果
        assert result["winner"]["source"] == "fast_mirror"


class TestRealWorldScenarios:
    """真实业务场景测试"""

    @pytest.mark.asyncio
    async def test_approval_workflow(self):
        """测试：审批工作流

        真实业务场景：
        - 请假申请 -> 条件判断天数
          - <= 3天 -> 直接经理审批
          - > 3天 -> 部门经理审批 -> 人事审批

        验收标准：
        - 正确路由到对应审批流程
        """
        from src.domain.services.advanced_executors import (
            ConditionExecutor,
        )

        condition_executor = ConditionExecutor()

        # 3天以下请假
        config = {
            "expression": "days <= 3",
            "true_branch": "direct_manager_approval",
            "false_branch": "department_approval_flow",
        }

        result = await condition_executor.execute(config, {"days": 2})
        assert result["next_node"] == "direct_manager_approval"

        result = await condition_executor.execute(config, {"days": 5})
        assert result["next_node"] == "department_approval_flow"

    @pytest.mark.asyncio
    async def test_batch_data_processing(self):
        """测试：批量数据处理

        真实业务场景：
        - 导入1000条用户数据
        - 每100条一批并行处理
        - 每批内串行验证和保存

        验收标准：
        - 正确分批
        - 批内串行处理
        """
        from src.domain.services.advanced_executors import LoopExecutor

        mock_node_executor = AsyncMock()
        mock_node_executor.execute.return_value = {"processed": True}

        executor = LoopExecutor(node_executor=mock_node_executor)

        loop_config = {
            "type": "for_each",
            "array_input": "batches",
            "item_variable": "batch",
            "body_node": "process_batch_node",
        }

        # 模拟10个批次
        inputs = {"batches": [list(range(i * 100, (i + 1) * 100)) for i in range(10)]}

        result = await executor.execute(loop_config, inputs)

        assert result["iteration_count"] == 10

    @pytest.mark.asyncio
    async def test_multi_api_aggregation(self):
        """测试：多API聚合

        真实业务场景：
        - 用户仪表板页面
        - 并行调用：用户信息、订单列表、通知、推荐
        - 聚合所有结果返回前端

        验收标准：
        - 并行调用4个API
        - 聚合结果到单个对象
        """
        from src.domain.services.advanced_executors import ParallelExecutor

        mock_node_executor = AsyncMock()

        results = {
            "get_user": {"name": "Alice", "email": "alice@example.com"},
            "get_orders": [{"id": 1, "amount": 100}],
            "get_notifications": [{"id": 1, "msg": "新消息"}],
            "get_recommendations": [{"id": 1, "product": "推荐商品"}],
        }

        async def mock_execute(node_id, inputs):
            return results.get(node_id, {})

        mock_node_executor.execute.side_effect = mock_execute

        executor = ParallelExecutor(node_executor=mock_node_executor)

        parallel_config = {
            "branches": [
                {"node": "get_user", "output_key": "user"},
                {"node": "get_orders", "output_key": "orders"},
                {"node": "get_notifications", "output_key": "notifications"},
                {"node": "get_recommendations", "output_key": "recommendations"},
            ]
        }

        result = await executor.execute(parallel_config, {"user_id": "123"})

        assert result["user"]["name"] == "Alice"
        assert len(result["orders"]) == 1
        assert len(result["notifications"]) == 1
        assert len(result["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """测试：指数退避重试

        真实业务场景：
        - 调用不稳定的外部API
        - 失败后重试，每次间隔加倍
        - 最多重试3次

        验收标准：
        - 支持重试机制
        - 重试间隔指数增长
        """
        from src.domain.services.advanced_executors import LoopExecutor

        call_count = 0

        async def mock_execute(node_id, inputs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"success": False, "_retry": True}
            return {"success": True}

        mock_node_executor = AsyncMock()
        mock_node_executor.execute.side_effect = mock_execute

        executor = LoopExecutor(node_executor=mock_node_executor)

        loop_config = {
            "type": "while",
            "condition": "not success",
            "max_iterations": 5,
            "body_node": "call_api_node",
            "retry_config": {
                "enabled": True,
                "base_delay": 0.1,
                "max_delay": 1.0,
                "exponential": True,
            },
        }

        inputs = {"success": False}
        result = await executor.execute(loop_config, inputs)

        assert result["iteration_count"] == 3
        assert result["final_result"]["success"] is True


class TestExecutorFactory:
    """执行器工厂测试"""

    def test_create_condition_executor(self):
        """测试：创建条件执行器"""
        from src.domain.services.advanced_executors import ExecutorFactory

        executor = ExecutorFactory.create("condition")
        assert executor is not None

    def test_create_loop_executor(self):
        """测试：创建循环执行器"""
        from src.domain.services.advanced_executors import ExecutorFactory

        mock_node_executor = AsyncMock()
        executor = ExecutorFactory.create("loop", node_executor=mock_node_executor)
        assert executor is not None

    def test_create_parallel_executor(self):
        """测试：创建并行执行器"""
        from src.domain.services.advanced_executors import ExecutorFactory

        mock_node_executor = AsyncMock()
        executor = ExecutorFactory.create("parallel", node_executor=mock_node_executor)
        assert executor is not None

    def test_invalid_executor_type(self):
        """测试：无效的执行器类型"""
        from src.domain.services.advanced_executors import ExecutorFactory

        with pytest.raises(ValueError, match="未知"):
            ExecutorFactory.create("invalid_type")
