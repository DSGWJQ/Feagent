"""ClassifyTaskUseCase - 任务分类用例

V2新功能：智能任务分类

业务场景：
用户创建任务时，系统通过 LLM 自动分类任务类型，
帮助选择最适合的工作流和工具

职责：
1. 接收任务描述（start, goal）
2. 调用 LLM 分析任务类型
3. 返回分类结果和置信度

第一性原则：
- 用例协调 Domain Service 和 LLM 服务
- 分类逻辑使用 LLM（而非规则引擎），因为更灵活
- 返回结果包含置信度，允许用户确认
"""

from dataclasses import dataclass
from typing import Any

from src.domain.value_objects.task_type import TaskType


@dataclass
class ClassifyTaskInput:
    """任务分类输入参数

    属性说明：
    - start: 任务起点描述
    - goal: 任务目标描述
    - context: 额外上下文（可选，如历史任务、用户偏好）
    """

    start: str
    goal: str
    context: dict[str, Any] | None = None


@dataclass
class ClassifyTaskOutput:
    """任务分类输出结果

    属性说明：
    - task_type: 分类的任务类型
    - confidence: 置信度（0-1之间，1表示最高）
    - reasoning: 分类理由（LLM 给出的解释）
    - suggested_tools: 建议使用的工具列表（可选）
    """

    task_type: TaskType
    confidence: float
    reasoning: str
    suggested_tools: list[str] | None = None


class ClassifyTaskUseCase:
    """任务分类用例

    V2阶段实现：
    - 基于 LLM 的智能分类
    - 返回分类结果和置信度
    - 提供分类理由和建议工具

    依赖：
    - LLM 服务（通过 LLMProvider）

    执行流程：
    1. 构造分类提示词
    2. 调用 LLM 分析任务
    3. 解析 LLM 响应
    4. 返回分类结果
    """

    def __init__(self, llm_client: Any = None):
        """初始化用例

        参数：
            llm_client: LLM 客户端（可选，用于实际调用 LLM）

        说明：
            V2阶段可以先用规则引擎实现，后续再集成 LLM
        """
        self.llm_client = llm_client

    def execute(self, input_data: ClassifyTaskInput) -> ClassifyTaskOutput:
        """执行任务分类用例

        参数：
            input_data: ClassifyTaskInput 输入参数

        返回：
            ClassifyTaskOutput 分类结果

        说明：
            V2阶段使用简化的规则引擎
            未来可以替换为真正的 LLM 调用
        """
        # V2阶段：使用简化的关键词匹配规则
        # TODO: 未来替换为 LLM 调用
        task_type, confidence, reasoning = self._classify_by_keywords(
            input_data.start, input_data.goal
        )

        # 根据任务类型推荐工具
        suggested_tools = self._suggest_tools(task_type)

        return ClassifyTaskOutput(
            task_type=task_type,
            confidence=confidence,
            reasoning=reasoning,
            suggested_tools=suggested_tools,
        )

    def _classify_by_keywords(self, start: str, goal: str) -> tuple[TaskType, float, str]:
        """基于关键词的简化分类（V2临时实现）

        参数：
            start: 任务起点
            goal: 任务目标

        返回：
            (TaskType, confidence, reasoning) 元组
        """
        combined_text = f"{start} {goal}".lower()

        # 关键词规则
        if any(kw in combined_text for kw in ["分析", "统计", "数据", "报表", "图表", "趋势"]):
            return (
                TaskType.DATA_ANALYSIS,
                0.85,
                "检测到数据分析相关关键词：分析、统计、数据、报表等",
            )

        if any(kw in combined_text for kw in ["写", "生成", "创建", "编写", "翻译", "内容"]):
            return (
                TaskType.CONTENT_CREATION,
                0.80,
                "检测到内容创建相关关键词：写、生成、创建、编写等",
            )

        if any(kw in combined_text for kw in ["研究", "调查", "搜索", "查找", "了解"]):
            return (
                TaskType.RESEARCH,
                0.80,
                "检测到研究相关关键词：研究、调查、搜索等",
            )

        if any(kw in combined_text for kw in ["错误", "bug", "问题", "修复", "调试", "为什么"]):
            return (
                TaskType.PROBLEM_SOLVING,
                0.75,
                "检测到问题解决相关关键词：错误、bug、问题、修复等",
            )

        if any(kw in combined_text for kw in ["自动", "定时", "每天", "每周", "批量"]):
            return (
                TaskType.AUTOMATION,
                0.75,
                "检测到自动化相关关键词：自动、定时、每天、批量等",
            )

        # 默认分类为 UNKNOWN
        return (
            TaskType.UNKNOWN,
            0.50,
            "未能匹配到明确的任务类型关键词，建议用户手动确认",
        )

    def _suggest_tools(self, task_type: TaskType) -> list[str]:
        """根据任务类型推荐工具

        参数：
            task_type: 任务类型

        返回：
            推荐的工具名称列表
        """
        tool_suggestions = {
            TaskType.DATA_ANALYSIS: ["database", "http", "python"],
            TaskType.CONTENT_CREATION: ["llm", "http"],
            TaskType.RESEARCH: ["http", "llm", "database"],
            TaskType.PROBLEM_SOLVING: ["llm", "database", "file"],
            TaskType.AUTOMATION: ["http", "database", "file"],
            TaskType.UNKNOWN: [],
        }

        return tool_suggestions.get(task_type, [])

    # ========== 未来 LLM 集成的接口（预留） ==========

    async def _classify_by_llm(self, start: str, goal: str) -> tuple[TaskType, float, str]:
        """使用 LLM 进行任务分类（未来实现）

        参数：
            start: 任务起点
            goal: 任务目标

        返回：
            (TaskType, confidence, reasoning) 元组

        说明：
            此方法为未来 LLM 集成预留
            需要构造 Prompt 并调用 LLM API
        """
        # TODO: 实现 LLM 调用
        # 1. 构造 Prompt
        # 2. 调用 self.llm_client
        # 3. 解析响应
        # 4. 返回结果
        raise NotImplementedError("LLM 分类功能尚未实现")
