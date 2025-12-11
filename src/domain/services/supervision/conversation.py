"""Phase 34.14: ConversationSupervisionModule extracted from supervision_modules."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .models import ComprehensiveCheckResult, DetectionResult


class ConversationSupervisionModule:
    """对话提示监控模块

    检测对话中的偏见、有害内容和稳定性问题。
    """

    # 默认偏见检测模式
    DEFAULT_BIAS_PATTERNS = {
        "gender_bias": [
            r"只有男性才能",
            r"只有女性才能",
            r"男人应该",
            r"女人应该",
            r"男性更适合",
            r"女性更适合",
        ],
        "racial_bias": [
            r"某些民族.*更",
            r"某些种族.*更",
            r"天生.*更聪明",
            r"天生.*更笨",
        ],
        "age_bias": [
            r"老年人都",
            r"年轻人都",
            r"老人不会",
        ],
    }

    # 默认有害内容检测模式
    DEFAULT_HARMFUL_PATTERNS = {
        "violence": [
            r"如何制造武器",
            r"如何伤害",
            r"教我.*杀",
            r"制造.*炸弹",
            r"制造危险物品",
        ],
        "illegal_activity": [
            r"如何.*黑客攻击",
            r"如何.*入侵",
            r"如何.*破解",
            r"网络攻击",
            r"如何进行.*攻击",
        ],
        "self_harm": [
            r"如何自我伤害",
            r"如何.*自杀",
            r"自伤方法",
        ],
    }

    # 默认稳定性检测模式
    DEFAULT_STABILITY_PATTERNS = {
        "prompt_injection": [
            r"忽略之前的指令",
            r"忽略.*指令",
            r"无视.*规则",
            r"不要遵守",
        ],
        "jailbreak": [
            r"假装你是.*没有限制",
            r"扮演.*无限制",
            r"DAN模式",
            r"开发者模式",
        ],
    }

    # 上下文溢出阈值
    MAX_INPUT_LENGTH = 50000

    def __init__(self) -> None:
        """初始化对话监督模块"""
        self.rules: dict[str, dict[str, Any]] = {}
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """初始化默认规则"""
        # 偏见规则
        for category, patterns in self.DEFAULT_BIAS_PATTERNS.items():
            self.rules[f"bias_{category}"] = {
                "type": "bias",
                "category": category,
                "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
                "severity": "medium",
            }

        # 有害内容规则
        for category, patterns in self.DEFAULT_HARMFUL_PATTERNS.items():
            self.rules[f"harmful_{category}"] = {
                "type": "harmful",
                "category": category,
                "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
                "severity": "high",
            }

        # 稳定性规则
        for category, patterns in self.DEFAULT_STABILITY_PATTERNS.items():
            self.rules[f"stability_{category}"] = {
                "type": "stability",
                "category": category,
                "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
                "severity": "high",
            }

    def add_bias_rule(
        self,
        rule_id: str,
        patterns: list[str],
        category: str,
        severity: str = "medium",
    ) -> None:
        """添加自定义偏见规则

        参数：
            rule_id: 规则ID
            patterns: 匹配模式列表
            category: 偏见类别
            severity: 严重性
        """
        self.rules[rule_id] = {
            "type": "bias",
            "category": category,
            "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
            "severity": severity,
        }

    def check_bias(self, text: str) -> DetectionResult:
        """检测偏见

        参数：
            text: 输入文本

        返回：
            检测结果
        """
        for _rule_id, rule in self.rules.items():
            if rule["type"] != "bias":
                continue

            for pattern in rule["patterns"]:
                if pattern.search(text):
                    return DetectionResult(
                        detected=True,
                        category=rule["category"],
                        severity=rule["severity"],
                        message=f"检测到偏见内容: {rule['category']}",
                    )

        return DetectionResult(detected=False)

    def check_harmful_content(self, text: str) -> DetectionResult:
        """检测有害内容

        参数：
            text: 输入文本

        返回：
            检测结果
        """
        for _rule_id, rule in self.rules.items():
            if rule["type"] != "harmful":
                continue

            for pattern in rule["patterns"]:
                if pattern.search(text):
                    return DetectionResult(
                        detected=True,
                        category=rule["category"],
                        severity=rule["severity"],
                        message=f"检测到有害内容: {rule['category']}",
                    )

        return DetectionResult(detected=False)

    def check_stability(self, text: str) -> DetectionResult:
        """检测稳定性问题

        参数：
            text: 输入文本

        返回：
            检测结果
        """
        # 检查上下文溢出
        if len(text) > self.MAX_INPUT_LENGTH:
            return DetectionResult(
                detected=True,
                category="context_overflow",
                severity="high",
                message=f"输入长度 ({len(text)}) 超过限制 ({self.MAX_INPUT_LENGTH})",
            )

        # 检查其他稳定性问题
        for _rule_id, rule in self.rules.items():
            if rule["type"] != "stability":
                continue

            for pattern in rule["patterns"]:
                if pattern.search(text):
                    return DetectionResult(
                        detected=True,
                        category=rule["category"],
                        severity=rule["severity"],
                        message=f"检测到稳定性问题: {rule['category']}",
                    )

        return DetectionResult(detected=False)

    def check_all(self, text: str) -> ComprehensiveCheckResult:
        """综合检查

        参数：
            text: 输入文本

        返回：
            综合检查结果
        """
        result = ComprehensiveCheckResult()

        # 检查偏见
        bias_result = self.check_bias(text)
        if bias_result.detected:
            result.add_issue(bias_result)

        # 检查有害内容
        harmful_result = self.check_harmful_content(text)
        if harmful_result.detected:
            result.add_issue(harmful_result)
            result.action = "block"  # 有害内容直接阻止

        # 检查稳定性
        stability_result = self.check_stability(text)
        if stability_result.detected:
            result.add_issue(stability_result)
            if stability_result.category in ["prompt_injection", "jailbreak"]:
                result.action = "block"

        return result

    def create_injection_context(
        self,
        issue_type: str,
        severity: str,
        message: str,
        action: str = "warn",
    ) -> dict[str, Any]:
        """创建注入上下文

        参数：
            issue_type: 问题类型
            severity: 严重性
            message: 消息
            action: 动作

        返回：
            上下文字典
        """
        return {
            "warning": message,
            "issue_type": issue_type,
            "severity": severity,
            "action": action,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }


__all__ = ["ConversationSupervisionModule"]
