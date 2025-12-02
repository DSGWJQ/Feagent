"""规则生成器 (Rule Generator) - Phase 7.1

业务定义：
- 从用户输入动态生成规则
- 支持目标对齐检测
- 支持工具约束规则生成
- 支持执行策略规则生成

设计原则：
- 单一职责：只负责规则生成
- 关键词提取：从用户描述中提取关键信息
- 语义匹配：使用简单的关键词匹配进行目标对齐检测

使用示例：
    generator = RuleGenerator()
    rules = generator.generate_from_user_input(
        start="我有一份销售数据",
        goal="生成分析报表",
        description="需要脱敏处理"
    )
"""

import logging
import re
from typing import Any
from uuid import uuid4

from src.domain.services.enhanced_rule_repository import (
    EnhancedRule,
    RuleCategory,
    RuleSource,
)
from src.domain.services.rule_engine import RuleAction

logger = logging.getLogger(__name__)


# 常见的敏感数据关键词
PRIVACY_KEYWORDS = [
    "脱敏",
    "隐私",
    "敏感",
    "保密",
    "加密",
    "姓名",
    "身份证",
    "电话",
    "手机",
    "地址",
    "邮箱",
    "密码",
    "银行卡",
    "信用卡",
]

# 时间范围关键词
TIME_KEYWORDS = [
    "本月",
    "本周",
    "今天",
    "昨天",
    "最近",
    "过去",
    "上个月",
    "上周",
    "今年",
    "去年",
]


def extract_chinese_keywords(text: str) -> list[str]:
    """提取中文文本中的关键词

    使用简单的分词和停用词过滤。

    参数：
        text: 输入文本

    返回：
        关键词列表
    """
    # 简单的中文分词（按标点和空格分割，然后提取2-4个字的词组）
    # 移除常见标点
    cleaned = re.sub(r"[，。！？、；：\"\"\"''（）【】\s]+", " ", text)

    # 提取词语
    words = []
    segments = cleaned.split()

    for seg in segments:
        # 提取2-4个字的子串作为关键词候选
        for length in [2, 3, 4]:
            for i in range(len(seg) - length + 1):
                word = seg[i : i + length]
                if word and len(word) >= 2:
                    words.append(word)

        # 也保留完整的段
        if len(seg) >= 2:
            words.append(seg)

    # 去重并过滤常见词
    stopwords = {"我有", "一份", "需要", "进行", "并且", "以及", "或者", "可以", "应该"}
    keywords = list({w for w in words if w not in stopwords and len(w) >= 2})

    return keywords[:20]  # 限制关键词数量


class GoalAlignmentChecker:
    """目标对齐检测器

    职责：
    1. 检查行动是否与目标对齐
    2. 计算对齐分数
    3. 提供偏离原因说明

    使用示例：
        checker = GoalAlignmentChecker()
        score = checker.check_alignment(
            goal="生成销售报表",
            action_description="查询销售数据"
        )
    """

    def __init__(self, threshold: float = 0.5):
        """初始化目标对齐检测器

        参数：
            threshold: 对齐阈值，低于此值视为偏离
        """
        self.threshold = threshold

    def check_alignment(
        self,
        goal: str,
        action_description: str,
        keywords: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> float:
        """检查行动是否与目标对齐

        参数：
            goal: 目标描述
            action_description: 行动描述
            keywords: 可选的关键词列表
            context: 可选的上下文

        返回：
            对齐分数（0.0-1.0）
        """
        # 提取目标关键词
        if keywords:
            goal_keywords = keywords
        else:
            goal_keywords = extract_chinese_keywords(goal)

        # 提取行动关键词
        action_keywords = extract_chinese_keywords(action_description)

        # 计算关键词匹配分数
        if not goal_keywords:
            return 0.5  # 无法提取关键词时返回中性分数

        # 计算匹配的关键词数量
        matches = 0
        for gk in goal_keywords:
            for ak in action_keywords:
                # 检查是否有重叠
                if gk in ak or ak in gk or self._is_semantically_related(gk, ak):
                    matches += 1
                    break

        # 基础匹配分数
        base_score = min(matches / max(len(goal_keywords), 1), 1.0)

        # 检查是否包含危险操作
        danger_keywords = ["删除", "删", "清空", "移除", "drop", "delete", "truncate", "清除"]
        has_danger = any(dk in action_description.lower() for dk in danger_keywords)

        if has_danger and not any(dk in goal.lower() for dk in danger_keywords):
            base_score *= 0.3  # 大幅降低分数

        # 考虑上下文
        if context:
            # 如果在正确的流程中，适当提高分数
            current_step = context.get("current_step", 0)
            total_steps = context.get("total_expected_steps", 1)
            if current_step > 0 and total_steps > 0:
                progress = current_step / total_steps
                if progress < 0.8:  # 还在流程中
                    base_score = min(base_score + 0.1, 1.0)

        return round(base_score, 2)

    def _is_semantically_related(self, word1: str, word2: str) -> bool:
        """检查两个词是否语义相关

        简单实现：检查是否有共同字符或属于同一类别
        """
        # 同义词/相关词映射
        related_groups = [
            {"销售", "订单", "交易", "营收", "收入"},
            {"报表", "报告", "分析", "统计", "汇总"},
            {"数据", "信息", "记录", "内容"},
            {"查询", "获取", "读取", "加载"},
            {"生成", "创建", "制作", "输出"},
            {"客户", "用户", "顾客"},
            {"月度", "每月", "本月", "月"},
        ]

        for group in related_groups:
            if word1 in group and word2 in group:
                return True

        # 检查是否有共同字符（对于中文）
        common = set(word1) & set(word2)
        if len(common) >= 1 and len(word1) >= 2 and len(word2) >= 2:
            return True

        return False

    def is_aligned(
        self,
        goal: str,
        action_description: str,
        keywords: list[str] | None = None,
    ) -> bool:
        """检查行动是否与目标对齐（布尔值）

        参数：
            goal: 目标描述
            action_description: 行动描述
            keywords: 可选的关键词列表

        返回：
            是否对齐
        """
        score = self.check_alignment(goal, action_description, keywords)
        return score >= self.threshold

    def get_deviation_reason(
        self,
        goal: str,
        action_description: str,
    ) -> str:
        """获取偏离原因说明

        参数：
            goal: 目标描述
            action_description: 行动描述

        返回：
            偏离原因说明
        """
        score = self.check_alignment(goal, action_description)

        if score >= self.threshold:
            return ""  # 没有偏离

        goal_keywords = extract_chinese_keywords(goal)
        # action_keywords can be used for detailed analysis if needed
        _ = extract_chinese_keywords(action_description)

        # 生成说明
        reasons = []

        if score < 0.3:
            reasons.append(f"当前行动「{action_description}」与目标「{goal}」严重偏离")
        else:
            reasons.append(f"当前行动与目标相关性较低（对齐分数: {score:.2f}）")

        # 检查危险操作
        danger_keywords = ["删除", "删", "清空", "移除"]
        if any(dk in action_description for dk in danger_keywords):
            reasons.append("检测到潜在的危险操作")

        # 建议
        if goal_keywords:
            reasons.append(f"建议：请确保操作与以下关键词相关：{', '.join(goal_keywords[:5])}")
        else:
            reasons.append("建议：请重新评估当前操作是否有助于达成目标")

        return "；".join(reasons)


class RuleGenerator:
    """规则生成器

    职责：
    1. 从用户输入生成目标对齐规则
    2. 生成工具约束规则
    3. 生成执行策略规则
    4. 生成行为边界规则

    使用示例：
        generator = RuleGenerator()
        rules = generator.generate_from_user_input(
            start="销售数据",
            goal="生成报表"
        )
    """

    def __init__(self):
        """初始化规则生成器"""
        self.goal_checker = GoalAlignmentChecker()

    def generate_from_user_input(
        self,
        start: str,
        goal: str,
        description: str | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> list[EnhancedRule]:
        """从用户输入生成规则

        参数：
            start: 起点描述
            goal: 目标描述
            description: 额外描述
            constraints: 额外约束

        返回：
            生成的规则列表
        """
        rules: list[EnhancedRule] = []

        # 提取关键词
        all_text = f"{start} {goal} {description or ''}"
        keywords = extract_chinese_keywords(all_text)

        # 1. 生成目标对齐规则
        goal_rule = self._create_goal_alignment_rule(goal, keywords)
        rules.append(goal_rule)

        # 2. 检查是否需要数据隐私规则
        if description:
            privacy_rules = self._create_privacy_rules(description)
            rules.extend(privacy_rules)

        # 3. 检查是否有时间范围约束
        if description:
            time_rules = self._create_time_constraint_rules(description)
            rules.extend(time_rules)

        return rules

    def _create_goal_alignment_rule(self, goal: str, keywords: list[str]) -> EnhancedRule:
        """创建目标对齐规则"""

        def check_goal_alignment(ctx: dict) -> bool:
            action_desc = ctx.get("action_description", "")
            alignment_score = ctx.get("alignment_score")

            if alignment_score is not None:
                return alignment_score < 0.5

            # 使用GoalAlignmentChecker
            checker = GoalAlignmentChecker()
            score = checker.check_alignment(goal, action_desc, keywords)
            return score < 0.5

        return EnhancedRule(
            id=f"gen_goal_alignment_{uuid4().hex[:8]}",
            name="目标对齐检测",
            category=RuleCategory.GOAL,
            description=f"检测行动是否与目标「{goal}」对齐",
            condition=check_goal_alignment,
            action=RuleAction.SUGGEST_CORRECTION,
            priority=2,
            source=RuleSource.GENERATED,
            metadata={
                "goal": goal,
                "keywords": keywords,
                "threshold": 0.5,
            },
        )

    def _create_privacy_rules(self, description: str) -> list[EnhancedRule]:
        """创建隐私保护规则"""
        rules = []

        # 检查是否提到隐私相关需求
        has_privacy_need = any(kw in description for kw in PRIVACY_KEYWORDS)

        if has_privacy_need:
            # 提取具体的敏感字段
            sensitive_fields = []
            for kw in PRIVACY_KEYWORDS:
                if kw in description:
                    sensitive_fields.append(kw)

            def check_privacy(ctx: dict) -> bool:
                # 检查是否访问了敏感数据但未脱敏
                data_fields = ctx.get("data_fields", [])
                is_masked = ctx.get("is_data_masked", False)

                if not is_masked:
                    for field in data_fields:
                        for sf in sensitive_fields:
                            if sf in str(field).lower():
                                return True
                return False

            rules.append(
                EnhancedRule(
                    id=f"gen_privacy_{uuid4().hex[:8]}",
                    name="敏感数据脱敏检查",
                    category=RuleCategory.DATA,
                    description="检查敏感数据是否已脱敏处理",
                    condition=check_privacy,
                    action=RuleAction.SUGGEST_CORRECTION,
                    priority=1,
                    source=RuleSource.GENERATED,
                    metadata={
                        "sensitive_fields": sensitive_fields,
                        "suggestion": "请对敏感数据进行脱敏处理",
                    },
                )
            )

        return rules

    def _create_time_constraint_rules(self, description: str) -> list[EnhancedRule]:
        """创建时间约束规则"""
        rules = []

        # 检查是否有时间范围要求
        time_constraints = []
        for kw in TIME_KEYWORDS:
            if kw in description:
                time_constraints.append(kw)

        if time_constraints:
            rules.append(
                EnhancedRule(
                    id=f"gen_time_constraint_{uuid4().hex[:8]}",
                    name="时间范围约束",
                    category=RuleCategory.DATA,
                    description=f"数据应限制在指定时间范围内: {', '.join(time_constraints)}",
                    condition="False",  # 默认不触发，需要具体实现
                    action=RuleAction.LOG_WARNING,
                    priority=3,
                    source=RuleSource.GENERATED,
                    metadata={
                        "time_constraints": time_constraints,
                        "suggestion": f"请确保数据范围符合要求: {', '.join(time_constraints)}",
                    },
                )
            )

        return rules

    def generate_tool_rules(
        self,
        allowed_tools: list[str],
        tool_configs: dict[str, dict] | None = None,
    ) -> list[EnhancedRule]:
        """生成工具约束规则

        参数：
            allowed_tools: 允许的工具列表
            tool_configs: 工具配置

        返回：
            规则列表
        """
        rules = []

        # 1. 工具白名单规则
        def check_tool_allowed(ctx: dict) -> bool:
            requested_tool = ctx.get("requested_tool", "")
            return requested_tool and requested_tool not in allowed_tools

        rules.append(
            EnhancedRule(
                id=f"gen_tool_whitelist_{uuid4().hex[:8]}",
                name="工具白名单检查",
                category=RuleCategory.TOOL,
                description=f"只允许使用以下工具: {', '.join(allowed_tools)}",
                condition=check_tool_allowed,
                action=RuleAction.REJECT_DECISION,
                priority=1,
                source=RuleSource.GENERATED,
                metadata={
                    "allowed_tools": allowed_tools,
                },
            )
        )

        # 2. 工具特定配置规则
        if tool_configs:
            for tool_name, config in tool_configs.items():
                tool_rule = self._create_tool_config_rule(tool_name, config)
                if tool_rule:
                    rules.append(tool_rule)

        return rules

    def _create_tool_config_rule(self, tool_name: str, config: dict) -> EnhancedRule | None:
        """创建工具配置规则"""
        if "forbidden_operations" in config:
            forbidden = config["forbidden_operations"]

            def check_forbidden_ops(ctx: dict) -> bool:
                if ctx.get("requested_tool") != tool_name:
                    return False
                operation = ctx.get("operation", "").upper()
                return any(op.upper() in operation for op in forbidden)

            return EnhancedRule(
                id=f"gen_{tool_name}_forbidden_{uuid4().hex[:8]}",
                name=f"{tool_name}禁止操作检查",
                category=RuleCategory.TOOL,
                description=f"{tool_name}禁止执行: {', '.join(forbidden)}",
                condition=check_forbidden_ops,
                action=RuleAction.REJECT_DECISION,
                priority=1,
                source=RuleSource.GENERATED,
                metadata={
                    "tool": tool_name,
                    "forbidden_operations": forbidden,
                    "config": config,
                },
            )

        return None

    def generate_execution_rules(
        self,
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ) -> list[EnhancedRule]:
        """生成执行策略规则

        参数：
            timeout_seconds: 超时时间
            max_retries: 最大重试次数

        返回：
            规则列表
        """
        rules = []

        # 超时规则
        rules.append(
            EnhancedRule(
                id=f"gen_timeout_{uuid4().hex[:8]}",
                name="执行超时限制",
                category=RuleCategory.EXECUTION,
                description=f"单节点执行不得超过{timeout_seconds}秒",
                condition=f"execution_time > {timeout_seconds}",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.GENERATED,
                metadata={
                    "timeout_seconds": timeout_seconds,
                    "max_retries": max_retries,
                },
            )
        )

        return rules

    def generate_behavior_rules(
        self,
        max_iterations: int = 10,
        max_tokens: int = 10000,
    ) -> list[EnhancedRule]:
        """生成行为边界规则

        参数：
            max_iterations: 最大迭代次数
            max_tokens: 最大token数

        返回：
            规则列表
        """
        rules = []

        # 迭代限制规则
        rules.append(
            EnhancedRule(
                id=f"gen_max_iterations_{uuid4().hex[:8]}",
                name="最大迭代次数限制",
                category=RuleCategory.BEHAVIOR,
                description=f"ReAct循环不得超过{max_iterations}次",
                condition=f"iteration_count > {max_iterations}",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.GENERATED,
                metadata={
                    "max_iterations": max_iterations,
                },
            )
        )

        # Token限制规则
        rules.append(
            EnhancedRule(
                id=f"gen_max_tokens_{uuid4().hex[:8]}",
                name="Token预算限制",
                category=RuleCategory.BEHAVIOR,
                description=f"单次任务不得消耗超过{max_tokens} tokens",
                condition=f"token_used > {max_tokens}",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.GENERATED,
                metadata={
                    "max_tokens": max_tokens,
                },
            )
        )

        return rules

    def generate_all_rules(self, agent_config: dict[str, Any]) -> list[EnhancedRule]:
        """从Agent配置生成所有规则

        参数：
            agent_config: Agent配置字典

        返回：
            规则列表
        """
        rules = []

        # 1. 从用户输入生成规则
        if "start" in agent_config and "goal" in agent_config:
            user_rules = self.generate_from_user_input(
                start=agent_config["start"],
                goal=agent_config["goal"],
                description=agent_config.get("description"),
            )
            rules.extend(user_rules)

        # 2. 工具规则
        if "allowed_tools" in agent_config:
            tool_rules = self.generate_tool_rules(
                allowed_tools=agent_config["allowed_tools"],
                tool_configs=agent_config.get("tool_configs"),
            )
            rules.extend(tool_rules)

        # 3. 执行规则
        if "timeout_seconds" in agent_config:
            exec_rules = self.generate_execution_rules(
                timeout_seconds=agent_config["timeout_seconds"],
                max_retries=agent_config.get("max_retries", 3),
            )
            rules.extend(exec_rules)

        # 4. 行为规则
        if "max_iterations" in agent_config:
            behavior_rules = self.generate_behavior_rules(
                max_iterations=agent_config["max_iterations"],
                max_tokens=agent_config.get("max_tokens", 10000),
            )
            rules.extend(behavior_rules)

        return rules


# 导出
__all__ = [
    "RuleGenerator",
    "GoalAlignmentChecker",
    "extract_chinese_keywords",
]
