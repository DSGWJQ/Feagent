"""PlanGeneratorChain 测试

测试目标：
1. 测试 Chain 是否能正常创建
2. 测试 Chain 是否能生成有效的计划
3. 测试输出格式是否正确（JSON）
4. 测试任务数量是否在范围内（3-7 个）

测试策略：
- 使用真实的 LLM（不 Mock）
- 测试多个场景（简单、复杂）
- 验证输出格式和内容

为什么使用真实 LLM？
- PlanGeneratorChain 的核心是 LLM，Mock 无法测试真实效果
- 需要验证 Prompt 是否有效
- 需要验证 LLM 是否能输出有效 JSON

注意：
- 这些测试会调用真实的 LLM API，会产生费用
- 如果 API Key 未配置，测试会跳过
"""

import pytest

from src.config import settings


# 检查 API Key 是否配置
def is_llm_configured() -> bool:
    """检查 LLM 是否配置"""
    return bool(settings.openai_api_key and settings.openai_api_key != "your-api-key-here")


# 如果 LLM 未配置，跳过所有测试
pytestmark = pytest.mark.skipif(
    not is_llm_configured(),
    reason="LLM 未配置，跳过测试。请在 .env 中配置 OPENAI_API_KEY",
)


class TestPlanGeneratorChain:
    """PlanGeneratorChain 测试类"""

    def test_create_chain(self):
        """测试 1：测试 Chain 是否能正常创建

        验证：
        - Chain 对象能正常创建
        - 不抛出异常
        """
        from src.lc.chains.plan_generator import create_plan_generator_chain

        # 创建 Chain
        chain = create_plan_generator_chain()

        # 验证 Chain 不为 None
        assert chain is not None

    def test_generate_simple_plan(self):
        """测试 2：测试生成简单计划

        场景：
        - 起点：我有一个 CSV 文件
        - 目标：分析销售数据

        验证：
        - 能生成计划
        - 输出是 list
        - 每个任务包含 name 和 description
        - 任务数量在 3-7 个之间
        """
        from src.lc.chains.plan_generator import create_plan_generator_chain

        # 创建 Chain
        chain = create_plan_generator_chain()

        # 调用 Chain
        result = chain.invoke(
            {
                "start": "我有一个 CSV 文件，包含销售数据",
                "goal": "分析销售数据，生成报告",
            }
        )

        # 验证输出类型
        assert isinstance(result, list), f"输出应该是 list，实际是 {type(result)}"

        # 验证任务数量
        assert 3 <= len(result) <= 7, f"任务数量应该在 3-7 个之间，实际是 {len(result)} 个"

        # 验证每个任务的结构
        for i, task in enumerate(result):
            assert isinstance(task, dict), f"任务 {i} 应该是 dict，实际是 {type(task)}"
            assert "name" in task, f"任务 {i} 缺少 name 字段"
            assert "description" in task, f"任务 {i} 缺少 description 字段"
            assert isinstance(task["name"], str), f"任务 {i} 的 name 应该是 str"
            assert isinstance(task["description"], str), f"任务 {i} 的 description 应该是 str"
            assert len(task["name"]) > 0, f"任务 {i} 的 name 不能为空"
            assert len(task["description"]) > 0, f"任务 {i} 的 description 不能为空"

        # 打印结果（便于调试）
        print("\n生成的计划：")
        for i, task in enumerate(result, 1):
            print(f"{i}. {task['name']}")
            print(f"   {task['description']}")

    def test_generate_complex_plan(self):
        """测试 3：测试生成复杂计划

        场景：
        - 起点：我有一个网站 URL
        - 目标：爬取数据并存储到数据库

        验证：
        - 能生成计划
        - 任务数量在 3-7 个之间
        - 任务内容合理
        """
        from src.lc.chains.plan_generator import create_plan_generator_chain

        # 创建 Chain
        chain = create_plan_generator_chain()

        # 调用 Chain
        result = chain.invoke(
            {
                "start": "我有一个网站 URL，需要爬取商品信息",
                "goal": "爬取商品数据并存储到数据库",
            }
        )

        # 验证输出类型
        assert isinstance(result, list)

        # 验证任务数量
        assert 3 <= len(result) <= 7, f"任务数量应该在 3-7 个之间，实际是 {len(result)} 个"

        # 验证每个任务的结构
        for task in result:
            assert "name" in task
            assert "description" in task

        # 打印结果（便于调试）
        print("\n生成的计划：")
        for i, task in enumerate(result, 1):
            print(f"{i}. {task['name']}")
            print(f"   {task['description']}")

    def test_generate_plan_with_chinese(self):
        """测试 4：测试中文场景

        场景：
        - 起点和目标都是中文
        - 验证 LLM 能正确处理中文

        验证：
        - 能生成计划
        - 输出是中文
        """
        from src.lc.chains.plan_generator import create_plan_generator_chain

        # 创建 Chain
        chain = create_plan_generator_chain()

        # 调用 Chain
        result = chain.invoke(
            {
                "start": "我有一份 Excel 表格，包含员工信息",
                "goal": "统计各部门人数，生成可视化图表",
            }
        )

        # 验证输出类型
        assert isinstance(result, list)

        # 验证任务数量
        assert 3 <= len(result) <= 7

        # 验证每个任务的结构
        for task in result:
            assert "name" in task
            assert "description" in task

        # 打印结果（便于调试）
        print("\n生成的计划：")
        for i, task in enumerate(result, 1):
            print(f"{i}. {task['name']}")
            print(f"   {task['description']}")

    def test_output_format(self):
        """测试 5：测试输出格式

        验证：
        - 输出是 list[dict]
        - 每个 dict 只包含 name 和 description
        - 没有多余的字段
        """
        from src.lc.chains.plan_generator import create_plan_generator_chain

        # 创建 Chain
        chain = create_plan_generator_chain()

        # 调用 Chain
        result = chain.invoke(
            {
                "start": "我有一个文本文件",
                "goal": "提取关键词",
            }
        )

        # 验证输出类型
        assert isinstance(result, list)

        # 验证每个任务只包含 name 和 description
        for task in result:
            assert set(task.keys()) == {
                "name",
                "description",
            }, f"任务应该只包含 name 和 description，实际包含 {task.keys()}"


# 手动测试函数（不使用 pytest）
def manual_test():
    """手动测试函数

    用于快速测试 Chain 是否工作
    运行：python -c "from tests.unit.lc.test_plan_generator import manual_test; manual_test()"
    """
    from src.lc.chains.plan_generator import create_plan_generator_chain

    print("=" * 60)
    print("手动测试 PlanGeneratorChain")
    print("=" * 60)

    # 创建 Chain
    chain = create_plan_generator_chain()

    # 测试场景
    test_cases = [
        {
            "start": "我有一个 CSV 文件，包含销售数据",
            "goal": "分析销售数据，生成报告",
        },
        {
            "start": "我有一个网站 URL",
            "goal": "爬取数据并存储到数据库",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试场景 {i}：")
        print(f"起点：{test_case['start']}")
        print(f"目标：{test_case['goal']}")

        # 调用 Chain
        result = chain.invoke(test_case)

        # 打印结果
        print(f"\n生成的计划（{len(result)} 个任务）：")
        for j, task in enumerate(result, 1):
            print(f"{j}. {task['name']}")
            print(f"   {task['description']}")

    print("\n" + "=" * 60)
    print("✅ 手动测试完成")
    print("=" * 60)


if __name__ == "__main__":
    manual_test()
