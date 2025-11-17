"""PlanGeneratorChain - 计划生成链

职责：
1. 接收用户的起点（start）和目标（goal）
2. 调用 LLM 生成执行计划
3. 解析 LLM 输出，返回 Task 列表（JSON 格式）

设计原则：
1. 使用 LCEL（LangChain Expression Language）
2. 使用 JsonOutputParser 自动解析 JSON
3. 保持简单，只负责生成计划（不创建 Domain 实体）

为什么使用 LCEL？
- 简洁：一行代码完成 prompt | llm | parser
- 可组合：未来可以轻松添加新组件
- 支持流式输出：未来可以实时显示生成过程

为什么使用 JsonOutputParser？
- 自动提取 JSON：即使 LLM 输出了多余文字
- 自动验证：检查 JSON 是否有效
- 容错性强：提高成功率

为什么不在这里创建 Domain 实体？
- 符合分层原则：Chain 不依赖 Domain 层
- 职责分离：Chain 只负责调用 LLM，Use Case 负责创建实体
- 易于测试：可以独立测试 Chain

输入：
- start: 起点（用户当前的状态）
- goal: 目标（用户想要达到的目标）

输出：
- list[dict]: 任务列表，每个任务包含 name 和 description
  [
    {"name": "任务1", "description": "描述1"},
    {"name": "任务2", "description": "描述2"}
  ]
"""

from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable

from src.lc.llm_client import get_llm_for_planning
from src.lc.prompts.plan_generation import get_plan_generation_prompt


def create_plan_generator_chain() -> Runnable[dict[str, Any], list[dict[str, str]]]:
    """创建计划生成链

    为什么使用工厂函数？
    - 延迟初始化：只在需要时创建 Chain
    - 便于测试：可以传入 Mock LLM
    - 便于管理：可以在应用启动时创建

    工作流程：
    1. 接收输入：{"start": "...", "goal": "..."}
    2. Prompt Template：生成提示词
    3. LLM：调用 LLM 生成计划
    4. JsonOutputParser：解析 JSON
    5. 返回输出：[{"name": "...", "description": "..."}, ...]

    返回：
        Runnable: LCEL Chain，输入 {"start": str, "goal": str}，输出 list[dict]

    异常：
        ValueError: 当 LLM 输出无效 JSON 时
        Exception: 当 LLM 调用失败时

    示例：
    >>> chain = create_plan_generator_chain()
    >>> result = chain.invoke({
    ...     "start": "我有一个 CSV 文件",
    ...     "goal": "分析销售数据"
    ... })
    >>> print(result)
    [
        {"name": "读取 CSV 文件", "description": "使用 pandas 读取..."},
        {"name": "数据清洗", "description": "去除空值..."}
    ]
    """
    # 步骤 1: 获取 Prompt Template
    # 为什么使用 get_plan_generation_prompt()？
    # - 封装了 Prompt 的创建逻辑
    # - 便于修改 Prompt（只需修改一个地方）
    # - 便于测试（可以单独测试 Prompt）
    prompt = get_plan_generation_prompt()

    # 步骤 2: 获取 LLM
    # 为什么使用 get_llm_for_planning()？
    # - 使用专门为计划生成优化的 LLM 配置（低温度，确定性输出）
    # - 封装了 LLM 的创建逻辑
    # - 便于切换 LLM（如从 KIMI 切换到 OpenAI）
    llm = get_llm_for_planning()

    # 步骤 3: 创建 Output Parser
    # 为什么使用 JsonOutputParser()？
    # - 自动解析 JSON：将 LLM 的文本输出解析为 Python list/dict
    # - 自动验证：检查 JSON 是否有效
    # - 自动提取：即使 LLM 输出了多余文字，也能提取出 JSON
    parser = JsonOutputParser()

    # 步骤 4: 使用 LCEL 组合 Chain
    # 为什么使用 | 操作符？
    # - LCEL 语法：prompt | llm | parser
    # - 数据流：输入 → prompt → llm → parser → 输出
    # - 简洁优雅：一行代码完成整个流程
    #
    # 执行流程：
    # 1. 输入：{"start": "...", "goal": "..."}
    # 2. prompt：生成提示词（ChatPromptValue）
    # 3. llm：调用 LLM（AIMessage）
    # 4. parser：解析 JSON（list[dict]）
    # 5. 输出：[{"name": "...", "description": "..."}, ...]
    chain = prompt | llm | parser

    return chain


# 为什么不使用类？
# 传统方式：
# class PlanGeneratorChain:
#     def __init__(self):
#         self.prompt = ...
#         self.llm = ...
#         self.parser = ...
#
#     def run(self, start, goal):
#         # 手动调用每个组件
#         pass
#
# LCEL 方式：
# chain = prompt | llm | parser
# result = chain.invoke({"start": "...", "goal": "..."})
#
# LCEL 的优势：
# 1. 代码量少（1 行 vs 10+ 行）
# 2. 更清晰（数据流一目了然）
# 3. 更灵活（可以轻松添加新组件）
# 4. 支持流式输出（chain.stream()）
# 5. 支持批处理（chain.batch()）

# 为什么返回 Runnable 而不是直接返回结果？
# - Runnable 是 LangChain 的核心抽象
# - 可以多次调用（chain.invoke()）
# - 支持流式输出（chain.stream()）
# - 支持批处理（chain.batch()）
# - 便于组合（可以将多个 Runnable 组合成更复杂的 Chain）

# 为什么不在这里处理错误？
# - 错误应该向上传播，由调用者处理
# - Chain 只负责生成计划，不负责错误处理
# - 保持 Chain 简单，符合单一职责原则
# - 调用者（如 Use Case）可以根据需要处理错误（如重试、降级）

# 未来可以添加的功能：
# 1. 错误处理：捕获 JSON 解析错误，重试
# 2. 验证：验证任务数量是否在 3-7 个之间
# 3. 后处理：对任务进行排序、去重等
# 4. 缓存：缓存相同输入的结果
# 5. 日志：记录 LLM 调用日志
# 6. 监控：记录 LLM 调用时间、Token 使用量等
