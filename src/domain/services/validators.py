"""验证器系统

提供决策验证、目标对齐检查、资源监控等功能。

组件：
- Goal: 目标实体
- GoalAlignmentChecker: 目标对齐检查器
- ResourceMonitor: 资源监控器
- DecisionValidator: 综合决策验证器

设计原则：
- 单一职责：每个验证器只关注一个维度
- 组合使用：DecisionValidator组合多个验证器
- 可扩展：易于添加新的验证维度
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Goal:
    """目标实体

    属性：
    - id: 目标唯一标识
    - description: 目标描述
    - status: 状态 (pending | in_progress | completed | failed)
    - parent_id: 父目标ID（用于目标分解）
    - children_ids: 子目标ID列表
    - dependencies: 依赖的目标ID列表
    - success_criteria: 成功标准列表
    - workflow_id: 关联的工作流ID
    """

    id: str
    description: str
    status: str = "pending"
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    workflow_id: str | None = None


@dataclass
class AlignmentResult:
    """目标对齐检查结果

    属性：
    - score: 对齐分数 (0.0-1.0)
    - is_aligned: 是否对齐
    - analysis: 分析说明
    - suggestion: 修正建议（如果不对齐）
    """

    score: float
    is_aligned: bool
    analysis: str
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """综合验证结果

    属性：
    - is_valid: 是否验证通过
    - violations: 违规项列表
    - suggestion: 建议
    - alignment_score: 对齐分数
    """

    is_valid: bool
    violations: list[str] = field(default_factory=list)
    suggestion: str | None = None
    alignment_score: float | None = None


class GoalAlignmentChecker:
    """目标对齐检查器

    使用LLM判断决策是否与当前目标对齐。

    使用示例：
        checker = GoalAlignmentChecker(llm=llm_client)
        result = await checker.check_alignment(goal, decision)
        if not result.is_aligned:
            print(f"建议: {result.suggestion}")
    """

    def __init__(self, llm: Any, threshold: float = 0.5):
        """初始化

        参数：
            llm: LLM客户端（需要有invoke方法）
            threshold: 对齐阈值，低于此值视为不对齐
        """
        self.llm = llm
        self.threshold = threshold

    async def check_alignment(
        self, goal: Goal, decision: dict[str, Any], history: list[dict] | None = None
    ) -> AlignmentResult:
        """检查决策是否与目标对齐

        参数：
            goal: 当前目标
            decision: 决策字典
            history: 可选的历史决策记录

        返回：
            对齐检查结果
        """
        # 构建提示
        history_text = ""
        if history:
            history_text = f"\n历史决策:\n{json.dumps(history[-5:], ensure_ascii=False, indent=2)}"

        prompt = f"""请评估以下决策是否与目标对齐：

目标: {goal.description}

决策:
- 类型: {decision.get("type", "unknown")}
- 节点类型: {decision.get("node_type", "unknown")}
- 推理: {decision.get("reasoning", "N/A")}
{history_text}

请给出对齐程度评分(0-1)和简要分析。

输出格式 (JSON):
{{
    "score": 0.8,
    "is_aligned": true,
    "analysis": "分析说明",
    "suggestion": "如果不对齐，给出建议；否则为null"
}}"""

        try:
            # 调用LLM
            response = await self.llm.invoke([{"role": "user", "content": prompt}])

            # 解析响应
            content = response.content if hasattr(response, "content") else str(response)

            # 尝试解析JSON
            result_data = json.loads(content)

            return AlignmentResult(
                score=result_data.get("score", 0.5),
                is_aligned=result_data.get("is_aligned", True),
                analysis=result_data.get("analysis", ""),
                suggestion=result_data.get("suggestion"),
            )

        except (json.JSONDecodeError, Exception) as e:
            # 解析失败时返回默认值
            return AlignmentResult(
                score=0.5, is_aligned=True, analysis=f"检查失败: {str(e)}", suggestion=None
            )


class ResourceMonitor:
    """资源监控器

    监控资源使用情况，包括：
    - Token使用量
    - 迭代次数
    - 执行时间

    使用示例：
        monitor = ResourceMonitor(token_limit=10000, max_iterations=10)
        monitor.record_token_usage(500)
        monitor.record_iteration()
        if not monitor.is_within_limits():
            print(monitor.get_violations())
    """

    def __init__(
        self, token_limit: int = 10000, max_iterations: int = 10, time_limit_seconds: float = 60.0
    ):
        """初始化

        参数：
            token_limit: Token限制
            max_iterations: 最大迭代次数
            time_limit_seconds: 时间限制（秒）
        """
        self.token_limit = token_limit
        self.max_iterations = max_iterations
        self.time_limit_seconds = time_limit_seconds

        # 使用计数
        self._tokens_used = 0
        self._iteration_count = 0
        self._start_time: float | None = None

    @property
    def tokens_used(self) -> int:
        """已使用的Token数"""
        return self._tokens_used

    @property
    def iteration_count(self) -> int:
        """迭代次数"""
        return self._iteration_count

    def record_token_usage(self, tokens: int) -> None:
        """记录Token使用

        参数：
            tokens: 使用的Token数
        """
        self._tokens_used += tokens

    def record_iteration(self) -> None:
        """记录一次迭代"""
        self._iteration_count += 1

    def start_timer(self) -> None:
        """启动计时器"""
        self._start_time = time.time()

    def get_elapsed_time(self) -> float:
        """获取已用时间（秒）"""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def get_usage_ratio(self, resource: str) -> float:
        """获取资源使用比例

        参数：
            resource: 资源类型 (tokens | iterations | time)

        返回：
            使用比例 (0.0-1.0+)
        """
        if resource == "tokens":
            return self._tokens_used / self.token_limit if self.token_limit > 0 else 0.0
        elif resource == "iterations":
            return self._iteration_count / self.max_iterations if self.max_iterations > 0 else 0.0
        elif resource == "time":
            if self.time_limit_seconds <= 0:
                return 0.0
            return self.get_elapsed_time() / self.time_limit_seconds
        return 0.0

    def is_within_limits(self) -> bool:
        """检查是否在限制范围内

        返回：
            是否所有资源都在限制内
        """
        # 检查Token
        if self._tokens_used > self.token_limit:
            return False

        # 检查迭代次数
        if self._iteration_count > self.max_iterations:
            return False

        # 检查时间
        if self._start_time is not None:
            if self.get_elapsed_time() > self.time_limit_seconds:
                return False

        return True

    def get_violations(self) -> dict[str, str]:
        """获取违规项

        返回：
            违规项字典 {资源类型: 违规描述}
        """
        violations = {}

        if self._tokens_used > self.token_limit:
            violations["tokens"] = f"Token使用量 {self._tokens_used} 超过限制 {self.token_limit}"

        if self._iteration_count > self.max_iterations:
            violations["iterations"] = (
                f"迭代次数 {self._iteration_count} 超过限制 {self.max_iterations}"
            )

        if self._start_time is not None:
            elapsed = self.get_elapsed_time()
            if elapsed > self.time_limit_seconds:
                violations["time"] = f"执行时间 {elapsed:.1f}s 超过限制 {self.time_limit_seconds}s"

        return violations

    def get_status(self) -> dict[str, Any]:
        """获取资源状态

        返回：
            包含所有资源维度的状态字典
        """
        return {
            "tokens": {
                "used": self._tokens_used,
                "limit": self.token_limit,
                "ratio": self.get_usage_ratio("tokens"),
            },
            "iterations": {
                "count": self._iteration_count,
                "limit": self.max_iterations,
                "ratio": self.get_usage_ratio("iterations"),
            },
            "time": {
                "elapsed": self.get_elapsed_time(),
                "limit": self.time_limit_seconds,
                "ratio": self.get_usage_ratio("time"),
            },
            "within_limits": self.is_within_limits(),
        }

    def reset(self) -> None:
        """重置所有计数"""
        self._tokens_used = 0
        self._iteration_count = 0
        self._start_time = None


class DecisionValidator:
    """综合决策验证器

    组合目标对齐检查和资源监控，提供综合验证。

    使用示例：
        validator = DecisionValidator(
            alignment_checker=alignment_checker,
            resource_monitor=resource_monitor
        )
        result = await validator.validate(decision, goal)
        if not result.is_valid:
            for violation in result.violations:
                print(violation)
    """

    def __init__(
        self,
        alignment_checker: GoalAlignmentChecker,
        resource_monitor: ResourceMonitor,
        alignment_threshold: float = 0.5,
    ):
        """初始化

        参数：
            alignment_checker: 目标对齐检查器
            resource_monitor: 资源监控器
            alignment_threshold: 对齐阈值
        """
        self.alignment_checker = alignment_checker
        self.resource_monitor = resource_monitor
        self.alignment_threshold = alignment_threshold

    async def validate(
        self, decision: dict[str, Any], goal: Goal, history: list[dict] | None = None
    ) -> ValidationResult:
        """验证决策

        参数：
            decision: 决策字典
            goal: 当前目标
            history: 可选的历史记录

        返回：
            验证结果
        """
        violations = []
        suggestion = None
        alignment_score = None

        # 1. 检查资源限制
        if not self.resource_monitor.is_within_limits():
            resource_violations = self.resource_monitor.get_violations()
            for _, msg in resource_violations.items():
                violations.append(f"[Resource] {msg}")

        # 2. 检查目标对齐
        alignment_result = await self.alignment_checker.check_alignment(goal, decision, history)
        alignment_score = alignment_result.score

        if not alignment_result.is_aligned:
            violations.append(f"[Alignment] {alignment_result.analysis}")
            suggestion = alignment_result.suggestion

        # 综合判定
        is_valid = len(violations) == 0

        return ValidationResult(
            is_valid=is_valid,
            violations=violations,
            suggestion=suggestion,
            alignment_score=alignment_score,
        )


# 导出
__all__ = [
    "Goal",
    "AlignmentResult",
    "ValidationResult",
    "GoalAlignmentChecker",
    "ResourceMonitor",
    "DecisionValidator",
]
