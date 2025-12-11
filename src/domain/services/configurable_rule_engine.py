"""可配置规则引擎模块 (Configurable Rule Engine)

业务定义：
- 提供基于 YAML/JSON 配置的规则引擎
- 支持路径规则、内容模式规则、用户级别规则、敏感命令规则
- 支持分级响应：WARN（警告）、REPLACE（替换）、TERMINATE（终止）

设计原则：
- 配置驱动：所有规则通过配置文件定义
- 可扩展性：易于添加新规则类型
- 安全优先：TERMINATE 优先级最高

实现日期：2025-12-08
"""

import fnmatch
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================


class RuleAction(str, Enum):
    """规则动作枚举

    动作优先级: TERMINATE > REPLACE > WARN > ALLOW
    """

    ALLOW = "allow"  # 允许
    WARN = "warn"  # 警告但允许
    REPLACE = "replace"  # 替换内容后允许
    TERMINATE = "terminate"  # 终止任务

    @property
    def priority(self) -> int:
        """获取动作优先级（数值越高优先级越高）"""
        priorities = {
            RuleAction.ALLOW: 0,
            RuleAction.WARN: 1,
            RuleAction.REPLACE: 2,
            RuleAction.TERMINATE: 3,
        }
        return priorities[self]


class UserLevel(str, Enum):
    """用户级别枚举

    级别层级: system > admin > user
    """

    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"

    @property
    def level(self) -> int:
        """获取级别数值"""
        levels = {
            UserLevel.USER: 0,
            UserLevel.ADMIN: 1,
            UserLevel.SYSTEM: 2,
        }
        return levels[self]

    @classmethod
    def from_string(cls, value: str) -> "UserLevel":
        """从字符串创建"""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.USER


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class RuleMatch:
    """单个规则匹配结果

    属性：
        rule_id: 规则 ID
        action: 匹配的动作
        message: 消息说明
        replacement: 替换内容（仅 REPLACE 动作时使用）
    """

    rule_id: str
    action: RuleAction
    message: str
    replacement: str | None = None


@dataclass
class RuleEvaluationResult:
    """规则评估结果

    属性：
        request_id: 请求 ID
        matches: 所有匹配的规则
        final_action: 最终动作（取优先级最高的）
        modified_content: 修改后的内容（如有替换）
        timestamp: 评估时间戳
    """

    request_id: str
    matches: list[RuleMatch]
    final_action: RuleAction
    modified_content: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_allowed(self) -> bool:
        """是否允许继续执行

        ALLOW, WARN, REPLACE 都允许执行
        只有 TERMINATE 阻止执行
        """
        return self.final_action != RuleAction.TERMINATE

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "matches": [
                {
                    "rule_id": m.rule_id,
                    "action": m.action.value,
                    "message": m.message,
                    "replacement": m.replacement,
                }
                for m in self.matches
            ],
            "final_action": self.final_action.value,
            "is_allowed": self.is_allowed,
            "modified_content": self.modified_content,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Schema 校验器
# =============================================================================


class RuleConfigValidator:
    """规则配置校验器"""

    VALID_ACTIONS = {"allow", "warn", "replace", "terminate"}
    VALID_USER_LEVELS = {"user", "admin", "system"}
    VERSION_PATTERN = re.compile(r"^\d+\.\d+$")

    @classmethod
    def validate(cls, config: dict) -> list[str]:
        """校验配置

        参数：
            config: 配置字典

        返回：
            错误列表（空列表表示校验通过）
        """
        errors = []

        # 校验版本号
        if "version" not in config:
            errors.append("Missing required field: version")
        elif not cls.VERSION_PATTERN.match(str(config["version"])):
            errors.append(f"Invalid version format: {config['version']} (expected: X.Y)")

        # 校验规则部分
        rules = config.get("rules", {})

        # 校验路径规则
        for i, rule in enumerate(rules.get("path_rules", [])):
            errors.extend(cls._validate_path_rule(rule, i))

        # 校验内容规则
        for i, rule in enumerate(rules.get("content_rules", [])):
            errors.extend(cls._validate_content_rule(rule, i))

        # 校验用户级别规则
        for i, rule in enumerate(rules.get("user_level_rules", [])):
            errors.extend(cls._validate_user_level_rule(rule, i))

        # 校验命令规则
        for i, rule in enumerate(rules.get("command_rules", [])):
            errors.extend(cls._validate_command_rule(rule, i))

        return errors

    @classmethod
    def _validate_path_rule(cls, rule: dict, index: int) -> list[str]:
        """校验路径规则"""
        errors = []
        prefix = f"path_rules[{index}]"

        if "id" not in rule:
            errors.append(f"{prefix}: Missing required field: id")
        if "pattern" not in rule:
            errors.append(f"{prefix}: Missing required field: pattern")
        if "action" not in rule:
            errors.append(f"{prefix}: Missing required field: action")
        elif rule["action"] not in cls.VALID_ACTIONS:
            errors.append(f"{prefix}: Invalid action: {rule['action']}")

        # REPLACE 动作需要 replacement 字段
        if rule.get("action") == "replace" and "replacement" not in rule:
            errors.append(f"{prefix}: REPLACE action requires 'replacement' field")

        return errors

    @classmethod
    def _validate_content_rule(cls, rule: dict, index: int) -> list[str]:
        """校验内容规则"""
        errors = []
        prefix = f"content_rules[{index}]"

        if "id" not in rule:
            errors.append(f"{prefix}: Missing required field: id")
        if "patterns" not in rule:
            errors.append(f"{prefix}: Missing required field: patterns")
        elif not isinstance(rule["patterns"], list):
            errors.append(f"{prefix}: 'patterns' must be a list")
        if "action" not in rule:
            errors.append(f"{prefix}: Missing required field: action")
        elif rule["action"] not in cls.VALID_ACTIONS:
            errors.append(f"{prefix}: Invalid action: {rule['action']}")

        # REPLACE 动作需要 replacement 字段
        if rule.get("action") == "replace" and "replacement" not in rule:
            errors.append(f"{prefix}: REPLACE action requires 'replacement' field")

        return errors

    @classmethod
    def _validate_user_level_rule(cls, rule: dict, index: int) -> list[str]:
        """校验用户级别规则"""
        errors = []
        prefix = f"user_level_rules[{index}]"

        if "id" not in rule:
            errors.append(f"{prefix}: Missing required field: id")
        if "required_level" not in rule:
            errors.append(f"{prefix}: Missing required field: required_level")
        elif rule["required_level"] not in cls.VALID_USER_LEVELS:
            errors.append(f"{prefix}: Invalid user level: {rule['required_level']}")
        if "paths" not in rule:
            errors.append(f"{prefix}: Missing required field: paths")
        if "action" not in rule:
            errors.append(f"{prefix}: Missing required field: action")
        elif rule["action"] not in cls.VALID_ACTIONS:
            errors.append(f"{prefix}: Invalid action: {rule['action']}")

        return errors

    @classmethod
    def _validate_command_rule(cls, rule: dict, index: int) -> list[str]:
        """校验命令规则"""
        errors = []
        prefix = f"command_rules[{index}]"

        if "id" not in rule:
            errors.append(f"{prefix}: Missing required field: id")
        if "commands" not in rule:
            errors.append(f"{prefix}: Missing required field: commands")
        elif not isinstance(rule["commands"], list):
            errors.append(f"{prefix}: 'commands' must be a list")
        if "action" not in rule:
            errors.append(f"{prefix}: Missing required field: action")
        elif rule["action"] not in cls.VALID_ACTIONS:
            errors.append(f"{prefix}: Invalid action: {rule['action']}")

        return errors


# =============================================================================
# 可配置规则引擎
# =============================================================================


class ConfigurableRuleEngine:
    """可配置规则引擎

    支持从 dict/JSON/YAML 加载配置，评估保存请求。
    """

    def __init__(self, config: dict):
        """初始化

        参数：
            config: 配置字典
        """
        # 校验配置
        errors = RuleConfigValidator.validate(config)
        if errors:
            raise ValueError(f"Invalid configuration: {'; '.join(errors)}")

        self._config = config
        self._version = config["version"]
        self._rules = config.get("rules", {})
        self._defaults = config.get("defaults", {})

        # 编译内容规则的正则表达式
        self._compiled_content_rules = self._compile_content_rules()

        logger.info(f"ConfigurableRuleEngine initialized with version {self._version}")

    def _compile_content_rules(self) -> list[dict]:
        """预编译内容规则的正则表达式"""
        compiled = []

        for rule in self._rules.get("content_rules", []):
            patterns = []
            flags = re.IGNORECASE if rule.get("case_insensitive", False) else 0

            for pattern in rule.get("patterns", []):
                try:
                    patterns.append(re.compile(pattern, flags))
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}': {e}")

            compiled.append(
                {
                    "id": rule["id"],
                    "patterns": patterns,
                    "action": RuleAction(rule["action"]),
                    "message": rule.get("message", ""),
                    "replacement": rule.get("replacement"),
                }
            )

        return compiled

    @classmethod
    def from_file(cls, file_path: str) -> "ConfigurableRuleEngine":
        """从文件加载配置

        支持 JSON 和 YAML 格式。

        参数：
            file_path: 配置文件路径

        返回：
            ConfigurableRuleEngine 实例
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        content = path.read_text(encoding="utf-8")

        if path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml

                config = yaml.safe_load(content)
            except ImportError:
                raise ImportError("PyYAML is required for YAML configuration files")
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML format: {e}")
        else:
            try:
                config = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format: {e}")

        return cls(config)

    def evaluate(self, request: Any) -> RuleEvaluationResult:
        """评估请求

        参数：
            request: 保存请求对象（需要有 target_path, content, user_level 等属性）

        返回：
            RuleEvaluationResult 评估结果
        """
        request_id = getattr(request, "request_id", "unknown")
        matches: list[RuleMatch] = []
        modified_content = getattr(request, "content", "")

        # 1. 检查默认的内容大小限制
        max_size_kb = self._defaults.get("max_content_size_kb")
        if max_size_kb:
            content = getattr(request, "content", "")
            if isinstance(content, str):
                size = len(content.encode("utf-8"))
            else:
                size = len(content)

            if size > max_size_kb * 1024:
                matches.append(
                    RuleMatch(
                        rule_id="default_max_size",
                        action=RuleAction.TERMINATE,
                        message=f"Content size ({size} bytes) exceeds limit ({max_size_kb}KB)",
                    )
                )

        # 2. 评估路径规则
        path_matches = self._evaluate_path_rules(request)
        matches.extend(path_matches)

        # 3. 评估内容规则（同时处理替换）
        content_matches, modified_content = self._evaluate_content_rules(request, modified_content)
        matches.extend(content_matches)

        # 4. 评估用户级别规则
        user_level_matches = self._evaluate_user_level_rules(request)
        matches.extend(user_level_matches)

        # 5. 评估命令规则
        command_matches = self._evaluate_command_rules(request)
        matches.extend(command_matches)

        # 6. 确定最终动作（取最高优先级）
        if matches:
            final_action = max((m.action for m in matches), key=lambda a: a.priority)
        else:
            final_action = RuleAction.ALLOW

        # 7. 如果有替换，返回修改后的内容
        has_replacement = any(m.action == RuleAction.REPLACE for m in matches)

        result = RuleEvaluationResult(
            request_id=request_id,
            matches=matches,
            final_action=final_action,
            modified_content=modified_content if has_replacement else None,
        )

        logger.info(
            f"Evaluated request {request_id}: "
            f"{len(matches)} rules matched, final_action={final_action.value}"
        )

        return result

    def _evaluate_path_rules(self, request: Any) -> list[RuleMatch]:
        """评估路径规则"""
        matches = []
        target_path = getattr(request, "target_path", "")

        for rule in self._rules.get("path_rules", []):
            pattern = rule["pattern"]

            if self._match_path(target_path, pattern):
                matches.append(
                    RuleMatch(
                        rule_id=rule["id"],
                        action=RuleAction(rule["action"]),
                        message=rule.get("message", f"Path matched pattern: {pattern}"),
                        replacement=rule.get("replacement"),
                    )
                )

        return matches

    def _match_path(self, path: str, pattern: str) -> bool:
        """匹配路径模式

        支持：
        - 精确匹配
        - 单层通配符 (*)
        - 递归通配符 (**)
        - 扩展名匹配 (*.ext)
        """
        # 标准化路径
        path = path.replace("\\", "/")
        pattern = pattern.replace("\\", "/")

        # 递归通配符处理
        if "**" in pattern:
            # ** 匹配任意层级
            pattern_parts = pattern.split("**")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts

                # 前缀匹配
                if prefix and not path.startswith(prefix.rstrip("/")):
                    return False

                # 后缀匹配（如果有）
                if suffix:
                    suffix = suffix.lstrip("/")
                    if suffix and not fnmatch.fnmatch(path, f"*{suffix}"):
                        return False

                return True

        # 精确匹配
        if path == pattern:
            return True

        # fnmatch 通配符匹配
        if fnmatch.fnmatch(path, pattern):
            return True

        # 前缀匹配（处理 /etc/* 这类模式）
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if path.startswith(prefix + "/") or path == prefix:
                return True

        return False

    def _evaluate_content_rules(self, request: Any, content: str) -> tuple[list[RuleMatch], str]:
        """评估内容规则并处理替换"""
        matches = []
        modified = content

        for rule in self._compiled_content_rules:
            for pattern in rule["patterns"]:
                if pattern.search(content):
                    matches.append(
                        RuleMatch(
                            rule_id=rule["id"],
                            action=rule["action"],
                            message=rule["message"],
                            replacement=rule["replacement"],
                        )
                    )

                    # 处理替换
                    if rule["action"] == RuleAction.REPLACE and rule["replacement"]:
                        modified = pattern.sub(rule["replacement"], modified)

                    break  # 一个规则只匹配一次

        return matches, modified

    def _evaluate_user_level_rules(self, request: Any) -> list[RuleMatch]:
        """评估用户级别规则"""
        matches = []
        target_path = getattr(request, "target_path", "")
        user_level_str = getattr(request, "user_level", "user")
        user_level = UserLevel.from_string(user_level_str)

        for rule in self._rules.get("user_level_rules", []):
            required_level = UserLevel.from_string(rule["required_level"])
            paths = rule.get("paths", [])

            # 检查路径是否匹配
            path_matched = False
            for pattern in paths:
                if self._match_path(target_path, pattern):
                    path_matched = True
                    break

            if not path_matched:
                continue

            # 检查用户级别是否满足要求
            if user_level.level < required_level.level:
                matches.append(
                    RuleMatch(
                        rule_id=rule["id"],
                        action=RuleAction(rule["action"]),
                        message=rule.get("message", f"Requires {required_level.value} permission"),
                        replacement=rule.get("replacement"),
                    )
                )

        return matches

    def _evaluate_command_rules(self, request: Any) -> list[RuleMatch]:
        """评估敏感命令规则"""
        matches = []
        content = getattr(request, "content", "")

        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8", errors="ignore")
            except Exception:
                return matches

        for rule in self._rules.get("command_rules", []):
            commands = rule.get("commands", [])

            for cmd in commands:
                if cmd.lower() in content.lower():
                    matches.append(
                        RuleMatch(
                            rule_id=rule["id"],
                            action=RuleAction(rule["action"]),
                            message=rule.get("message", f"Dangerous command detected: {cmd}"),
                            replacement=rule.get("replacement"),
                        )
                    )
                    break  # 一个规则只匹配一次

        return matches

    def as_audit_rule(self) -> "ConfigurableEngineAuditRule":
        """转换为审核规则

        返回可以添加到 SaveRequestAuditor 的审核规则。
        """
        return ConfigurableEngineAuditRule(self)


# =============================================================================
# 审核规则适配器
# =============================================================================


class ConfigurableEngineAuditRule:
    """可配置引擎审核规则适配器

    将 ConfigurableRuleEngine 适配为 AuditRule 接口。
    """

    def __init__(self, engine: ConfigurableRuleEngine):
        """初始化

        参数：
            engine: ConfigurableRuleEngine 实例
        """
        self._engine = engine

    @property
    def rule_id(self) -> str:
        """规则唯一标识"""
        return "configurable_engine"

    @property
    def name(self) -> str:
        """规则名称"""
        return "Configurable Rule Engine"

    def evaluate(self, request: Any) -> Any:
        """评估请求

        参数：
            request: SaveRequest 实例

        返回：
            AuditRuleResult 评估结果
        """
        from src.domain.services.save_request_audit import AuditRuleResult

        result = self._engine.evaluate(request)

        if result.final_action == RuleAction.TERMINATE:
            # 合并所有拒绝消息
            messages = [m.message for m in result.matches if m.action == RuleAction.TERMINATE]
            reason = "; ".join(messages) if messages else "Request terminated by rule engine"

            return AuditRuleResult(
                passed=False,
                rule_id=self.rule_id,
                reason=reason,
            )

        # WARN 和 REPLACE 都允许通过
        return AuditRuleResult(
            passed=True,
            rule_id=self.rule_id,
        )


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "RuleAction",
    "UserLevel",
    "RuleMatch",
    "RuleEvaluationResult",
    "RuleConfigValidator",
    "ConfigurableRuleEngine",
    "ConfigurableEngineAuditRule",
]
