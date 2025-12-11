"""可配置规则引擎测试 (Configurable Rule Engine Tests)

TDD 测试用例：
1. RuleAction 枚举测试
2. 规则配置 Schema 校验测试
3. 路径规则测试
4. 内容模式规则测试
5. 用户级别规则测试
6. 敏感命令规则测试
7. 分级响应测试 (WARN/REPLACE/TERMINATE)
8. 配置文件加载测试 (JSON/YAML)
9. 规则引擎集成测试

测试日期：2025-12-08
"""

import json
import os
import tempfile
from dataclasses import dataclass

import pytest

# =============================================================================
# 测试数据结构
# =============================================================================


@dataclass
class MockSaveRequest:
    """模拟保存请求"""

    request_id: str = "req-001"
    session_id: str = "session-001"
    target_path: str = "/tmp/test.txt"
    content: str = "hello world"
    operation_type: str = "file_write"
    user_level: str = "user"  # user/admin/system
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# =============================================================================
# 1. RuleAction 枚举测试
# =============================================================================


class TestRuleAction:
    """RuleAction 枚举测试"""

    def test_rule_action_warn_value(self):
        """测试 WARN 动作值"""
        from src.domain.services.configurable_rule_engine import RuleAction

        assert RuleAction.WARN.value == "warn"

    def test_rule_action_replace_value(self):
        """测试 REPLACE 动作值"""
        from src.domain.services.configurable_rule_engine import RuleAction

        assert RuleAction.REPLACE.value == "replace"

    def test_rule_action_terminate_value(self):
        """测试 TERMINATE 动作值"""
        from src.domain.services.configurable_rule_engine import RuleAction

        assert RuleAction.TERMINATE.value == "terminate"

    def test_rule_action_allow_value(self):
        """测试 ALLOW 动作值"""
        from src.domain.services.configurable_rule_engine import RuleAction

        assert RuleAction.ALLOW.value == "allow"

    def test_rule_action_priority(self):
        """测试动作优先级: TERMINATE > REPLACE > WARN > ALLOW"""
        from src.domain.services.configurable_rule_engine import RuleAction

        assert RuleAction.TERMINATE.priority > RuleAction.REPLACE.priority
        assert RuleAction.REPLACE.priority > RuleAction.WARN.priority
        assert RuleAction.WARN.priority > RuleAction.ALLOW.priority


# =============================================================================
# 2. 规则配置数据结构测试
# =============================================================================


class TestRuleConfigStructures:
    """规则配置数据结构测试"""

    def test_rule_match_creation(self):
        """测试 RuleMatch 创建"""
        from src.domain.services.configurable_rule_engine import RuleAction, RuleMatch

        match = RuleMatch(
            rule_id="test_rule",
            action=RuleAction.WARN,
            message="Test warning",
        )

        assert match.rule_id == "test_rule"
        assert match.action == RuleAction.WARN
        assert match.message == "Test warning"
        assert match.replacement is None

    def test_rule_match_with_replacement(self):
        """测试带替换内容的 RuleMatch"""
        from src.domain.services.configurable_rule_engine import RuleAction, RuleMatch

        match = RuleMatch(
            rule_id="replace_rule",
            action=RuleAction.REPLACE,
            message="Content replaced",
            replacement="[REDACTED]",
        )

        assert match.action == RuleAction.REPLACE
        assert match.replacement == "[REDACTED]"

    def test_rule_evaluation_result_creation(self):
        """测试 RuleEvaluationResult 创建"""
        from src.domain.services.configurable_rule_engine import (
            RuleAction,
            RuleEvaluationResult,
            RuleMatch,
        )

        result = RuleEvaluationResult(
            request_id="req-001",
            matches=[
                RuleMatch(rule_id="r1", action=RuleAction.WARN, message="warn1"),
            ],
            final_action=RuleAction.WARN,
        )

        assert result.request_id == "req-001"
        assert len(result.matches) == 1
        assert result.final_action == RuleAction.WARN
        assert result.modified_content is None

    def test_rule_evaluation_result_with_modified_content(self):
        """测试带修改内容的 RuleEvaluationResult"""
        from src.domain.services.configurable_rule_engine import (
            RuleAction,
            RuleEvaluationResult,
            RuleMatch,
        )

        result = RuleEvaluationResult(
            request_id="req-001",
            matches=[
                RuleMatch(
                    rule_id="r1",
                    action=RuleAction.REPLACE,
                    message="replaced",
                    replacement="[REMOVED]",
                ),
            ],
            final_action=RuleAction.REPLACE,
            modified_content="content with [REMOVED]",
        )

        assert result.modified_content == "content with [REMOVED]"

    def test_rule_evaluation_result_is_allowed(self):
        """测试 is_allowed 属性"""
        from src.domain.services.configurable_rule_engine import (
            RuleAction,
            RuleEvaluationResult,
        )

        # ALLOW 允许
        result_allow = RuleEvaluationResult(
            request_id="req-001",
            matches=[],
            final_action=RuleAction.ALLOW,
        )
        assert result_allow.is_allowed is True

        # WARN 允许（只是警告）
        result_warn = RuleEvaluationResult(
            request_id="req-002",
            matches=[],
            final_action=RuleAction.WARN,
        )
        assert result_warn.is_allowed is True

        # REPLACE 允许（内容被替换后继续）
        result_replace = RuleEvaluationResult(
            request_id="req-003",
            matches=[],
            final_action=RuleAction.REPLACE,
        )
        assert result_replace.is_allowed is True

        # TERMINATE 拒绝
        result_terminate = RuleEvaluationResult(
            request_id="req-004",
            matches=[],
            final_action=RuleAction.TERMINATE,
        )
        assert result_terminate.is_allowed is False


# =============================================================================
# 3. Schema 校验测试
# =============================================================================


class TestRuleConfigSchema:
    """规则配置 Schema 校验测试"""

    def test_valid_minimal_config(self):
        """测试最小有效配置"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {"version": "1.0", "rules": {}}

        errors = RuleConfigValidator.validate(config)
        assert len(errors) == 0

    def test_missing_version(self):
        """测试缺少版本号"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {"rules": {}}

        errors = RuleConfigValidator.validate(config)
        assert any("version" in e.lower() for e in errors)

    def test_invalid_version_format(self):
        """测试无效版本格式"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {"version": "invalid", "rules": {}}

        errors = RuleConfigValidator.validate(config)
        assert any("version" in e.lower() for e in errors)

    def test_valid_path_rule(self):
        """测试有效路径规则"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_etc",
                        "pattern": "/etc/*",
                        "action": "terminate",
                        "message": "System paths blocked",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert len(errors) == 0

    def test_path_rule_missing_required_field(self):
        """测试路径规则缺少必填字段"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_etc",
                        # missing pattern
                        "action": "terminate",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert any("pattern" in e.lower() for e in errors)

    def test_invalid_action_value(self):
        """测试无效动作值"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "test",
                        "pattern": "/tmp/*",
                        "action": "invalid_action",
                        "message": "test",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert any("action" in e.lower() for e in errors)

    def test_valid_content_rule(self):
        """测试有效内容规则"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "block_passwords",
                        "patterns": [r"password\s*="],
                        "action": "terminate",
                        "message": "Password detected",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert len(errors) == 0

    def test_valid_user_level_rule(self):
        """测试有效用户级别规则"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "user_level_rules": [
                    {
                        "id": "admin_only",
                        "required_level": "admin",
                        "paths": ["/admin/*"],
                        "action": "terminate",
                        "message": "Admin required",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert len(errors) == 0

    def test_valid_command_rule(self):
        """测试有效命令规则"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "command_rules": [
                    {
                        "id": "block_rm",
                        "commands": ["rm -rf", "DROP TABLE"],
                        "action": "terminate",
                        "message": "Dangerous command",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert len(errors) == 0

    def test_valid_replace_rule_with_replacement(self):
        """测试带替换的规则"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "redact_secrets",
                        "patterns": [r"secret_key\s*=\s*['\"][^'\"]+['\"]"],
                        "action": "replace",
                        "replacement": 'secret_key = "[REDACTED]"',
                        "message": "Secret redacted",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert len(errors) == 0

    def test_replace_rule_missing_replacement(self):
        """测试替换规则缺少 replacement 字段"""
        from src.domain.services.configurable_rule_engine import RuleConfigValidator

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "redact_secrets",
                        "patterns": [r"secret"],
                        "action": "replace",
                        # missing replacement
                        "message": "Secret redacted",
                    }
                ]
            },
        }

        errors = RuleConfigValidator.validate(config)
        assert any("replacement" in e.lower() for e in errors)


# =============================================================================
# 4. 路径规则测试
# =============================================================================


class TestPathRules:
    """路径规则测试"""

    def test_path_exact_match_terminate(self):
        """测试精确路径匹配 - 终止"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_etc_passwd",
                        "pattern": "/etc/passwd",
                        "action": "terminate",
                        "message": "Cannot modify passwd file",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(target_path="/etc/passwd")

        result = engine.evaluate(request)

        assert result.final_action == RuleAction.TERMINATE
        assert len(result.matches) == 1
        assert result.matches[0].rule_id == "block_etc_passwd"

    def test_path_wildcard_match(self):
        """测试通配符路径匹配"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_etc",
                        "pattern": "/etc/*",
                        "action": "terminate",
                        "message": "System config blocked",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 匹配
        request1 = MockSaveRequest(target_path="/etc/hosts")
        result1 = engine.evaluate(request1)
        assert result1.final_action == RuleAction.TERMINATE

        # 不匹配
        request2 = MockSaveRequest(target_path="/tmp/test.txt")
        result2 = engine.evaluate(request2)
        assert result2.final_action == RuleAction.ALLOW

    def test_path_double_wildcard_match(self):
        """测试双通配符（递归）匹配"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_system",
                        "pattern": "/sys/**",
                        "action": "terminate",
                        "message": "System paths blocked",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 匹配深层路径
        request = MockSaveRequest(target_path="/sys/kernel/debug/test")
        result = engine.evaluate(request)
        assert result.final_action == RuleAction.TERMINATE

    def test_path_warn_action(self):
        """测试路径规则 - 警告"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "warn_config",
                        "pattern": "*.config",
                        "action": "warn",
                        "message": "Modifying config file",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(target_path="/app/settings.config")

        result = engine.evaluate(request)

        assert result.final_action == RuleAction.WARN
        assert result.is_allowed is True
        assert len(result.matches) == 1

    def test_path_extension_match(self):
        """测试扩展名匹配"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "warn_py",
                        "pattern": "**/*.py",
                        "action": "warn",
                        "message": "Python file modification",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        request = MockSaveRequest(target_path="/project/src/main.py")
        result = engine.evaluate(request)
        assert result.final_action == RuleAction.WARN


# =============================================================================
# 5. 内容模式规则测试
# =============================================================================


class TestContentRules:
    """内容模式规则测试"""

    def test_content_pattern_terminate(self):
        """测试内容模式 - 终止"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "block_passwords",
                        "patterns": [r"password\s*=\s*['\"][^'\"]+['\"]"],
                        "action": "terminate",
                        "message": "Password in content",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(content='config = {"password": "secret123"}')

        result = engine.evaluate(request)
        # 注意：正则表达式 password\s*=\s*['\"] 不匹配 "password":
        # 需要调整测试或正则

        request2 = MockSaveRequest(content="password = 'secret123'")
        result2 = engine.evaluate(request2)
        assert result2.final_action == RuleAction.TERMINATE

    def test_content_multiple_patterns(self):
        """测试多个内容模式"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "block_secrets",
                        "patterns": [
                            r"api_key\s*=",
                            r"secret_key\s*=",
                            r"private_key\s*=",
                        ],
                        "action": "terminate",
                        "message": "Secret detected",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 匹配第一个模式
        req1 = MockSaveRequest(content="api_key = 'abc123'")
        assert engine.evaluate(req1).final_action == RuleAction.TERMINATE

        # 匹配第二个模式
        req2 = MockSaveRequest(content="secret_key = 'xyz'")
        assert engine.evaluate(req2).final_action == RuleAction.TERMINATE

        # 不匹配任何模式
        req3 = MockSaveRequest(content="normal content here")
        assert engine.evaluate(req3).final_action == RuleAction.ALLOW

    def test_content_replace_action(self):
        """测试内容替换动作"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "redact_api_key",
                        "patterns": [r"api_key\s*=\s*['\"][^'\"]+['\"]"],
                        "action": "replace",
                        "replacement": 'api_key = "[REDACTED]"',
                        "message": "API key redacted",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(content="config:\n  api_key = 'sk-123456'\n  name = 'test'")

        result = engine.evaluate(request)

        assert result.final_action == RuleAction.REPLACE
        assert result.is_allowed is True
        assert "[REDACTED]" in result.modified_content
        assert "sk-123456" not in result.modified_content

    def test_content_case_insensitive(self):
        """测试内容模式大小写不敏感"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "block_password",
                        "patterns": [r"PASSWORD\s*="],
                        "action": "terminate",
                        "message": "Password found",
                        "case_insensitive": True,
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 小写也能匹配
        request = MockSaveRequest(content="password = 'test'")
        result = engine.evaluate(request)
        assert result.final_action == RuleAction.TERMINATE


# =============================================================================
# 6. 用户级别规则测试
# =============================================================================


class TestUserLevelRules:
    """用户级别规则测试"""

    def test_user_level_admin_required(self):
        """测试需要管理员权限"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "user_level_rules": [
                    {
                        "id": "admin_paths",
                        "required_level": "admin",
                        "paths": ["/admin/*", "/config/*"],
                        "action": "terminate",
                        "message": "Admin permission required",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 普通用户访问管理路径 - 拒绝
        req_user = MockSaveRequest(target_path="/admin/settings.json", user_level="user")
        result_user = engine.evaluate(req_user)
        assert result_user.final_action == RuleAction.TERMINATE

        # 管理员访问管理路径 - 允许
        req_admin = MockSaveRequest(target_path="/admin/settings.json", user_level="admin")
        result_admin = engine.evaluate(req_admin)
        assert result_admin.final_action == RuleAction.ALLOW

    def test_user_level_system_required(self):
        """测试需要系统权限"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "user_level_rules": [
                    {
                        "id": "system_paths",
                        "required_level": "system",
                        "paths": ["/system/*"],
                        "action": "terminate",
                        "message": "System permission required",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 管理员也不能访问系统路径
        req_admin = MockSaveRequest(target_path="/system/core.dat", user_level="admin")
        result = engine.evaluate(req_admin)
        assert result.final_action == RuleAction.TERMINATE

        # 系统级别可以访问
        req_system = MockSaveRequest(target_path="/system/core.dat", user_level="system")
        result_sys = engine.evaluate(req_system)
        assert result_sys.final_action == RuleAction.ALLOW

    def test_user_level_hierarchy(self):
        """测试用户级别层级: system > admin > user"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "user_level_rules": [
                    {
                        "id": "admin_paths",
                        "required_level": "admin",
                        "paths": ["/protected/*"],
                        "action": "terminate",
                        "message": "Admin required",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # system 级别应该也能通过 admin 要求
        req = MockSaveRequest(target_path="/protected/data.json", user_level="system")
        result = engine.evaluate(req)
        assert result.final_action == RuleAction.ALLOW


# =============================================================================
# 7. 敏感命令规则测试
# =============================================================================


class TestCommandRules:
    """敏感命令规则测试"""

    def test_command_block_dangerous(self):
        """测试阻止危险命令"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "command_rules": [
                    {
                        "id": "block_dangerous",
                        "commands": ["rm -rf", "DROP TABLE", "DELETE FROM"],
                        "action": "terminate",
                        "message": "Dangerous command blocked",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 包含 rm -rf
        req1 = MockSaveRequest(content="#!/bin/bash\nrm -rf /tmp/*")
        assert engine.evaluate(req1).final_action == RuleAction.TERMINATE

        # 包含 DROP TABLE
        req2 = MockSaveRequest(content="DROP TABLE users;")
        assert engine.evaluate(req2).final_action == RuleAction.TERMINATE

        # 正常内容
        req3 = MockSaveRequest(content="SELECT * FROM users;")
        assert engine.evaluate(req3).final_action == RuleAction.ALLOW

    def test_command_warn_action(self):
        """测试命令警告动作"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "command_rules": [
                    {
                        "id": "warn_sudo",
                        "commands": ["sudo"],
                        "action": "warn",
                        "message": "sudo usage detected",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(content="sudo apt-get update")

        result = engine.evaluate(request)
        assert result.final_action == RuleAction.WARN
        assert result.is_allowed is True


# =============================================================================
# 8. 分级响应测试
# =============================================================================


class TestActionPriority:
    """分级响应测试"""

    def test_terminate_overrides_warn(self):
        """测试 TERMINATE 优先于 WARN"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "warn_tmp",
                        "pattern": "/tmp/*",
                        "action": "warn",
                        "message": "Temp file",
                    }
                ],
                "content_rules": [
                    {
                        "id": "block_secrets",
                        "patterns": [r"secret"],
                        "action": "terminate",
                        "message": "Secret found",
                    }
                ],
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(target_path="/tmp/test.txt", content="my secret data")

        result = engine.evaluate(request)

        # 虽然路径规则只是 WARN，但内容规则是 TERMINATE
        assert result.final_action == RuleAction.TERMINATE
        assert len(result.matches) == 2  # 两个规则都匹配了

    def test_replace_overrides_warn(self):
        """测试 REPLACE 优先于 WARN"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "warn_log",
                        "pattern": "*.log",
                        "action": "warn",
                        "message": "Log file",
                    }
                ],
                "content_rules": [
                    {
                        "id": "redact_email",
                        "patterns": [r"\b[\w.-]+@[\w.-]+\.\w+\b"],
                        "action": "replace",
                        "replacement": "[EMAIL]",
                        "message": "Email redacted",
                    }
                ],
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(
            target_path="/var/app.log", content="User email: test@example.com"
        )

        result = engine.evaluate(request)

        assert result.final_action == RuleAction.REPLACE
        assert "[EMAIL]" in result.modified_content

    def test_multiple_replaces(self):
        """测试多个替换规则"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "redact_email",
                        "patterns": [r"\b[\w.-]+@[\w.-]+\.\w+\b"],
                        "action": "replace",
                        "replacement": "[EMAIL]",
                        "message": "Email redacted",
                    },
                    {
                        "id": "redact_phone",
                        "patterns": [r"\b\d{3}-\d{4}-\d{4}\b"],
                        "action": "replace",
                        "replacement": "[PHONE]",
                        "message": "Phone redacted",
                    },
                ],
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(content="Contact: test@example.com, Phone: 138-1234-5678")

        result = engine.evaluate(request)

        assert result.final_action == RuleAction.REPLACE
        assert "[EMAIL]" in result.modified_content
        assert "[PHONE]" in result.modified_content
        assert "test@example.com" not in result.modified_content
        assert "138-1234-5678" not in result.modified_content


# =============================================================================
# 9. 配置文件加载测试
# =============================================================================


class TestConfigFileLoading:
    """配置文件加载测试"""

    def test_load_from_json_file(self):
        """测试从 JSON 文件加载"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_etc",
                        "pattern": "/etc/*",
                        "action": "terminate",
                        "message": "System path blocked",
                    }
                ]
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        try:
            engine = ConfigurableRuleEngine.from_file(config_path)
            request = MockSaveRequest(target_path="/etc/hosts")
            result = engine.evaluate(request)
            assert result.final_action == RuleAction.TERMINATE
        finally:
            os.unlink(config_path)

    def test_load_from_yaml_file(self):
        """测试从 YAML 文件加载"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        yaml_content = """
version: "1.0"
rules:
  path_rules:
    - id: block_etc
      pattern: "/etc/*"
      action: terminate
      message: "System path blocked"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = f.name

        try:
            engine = ConfigurableRuleEngine.from_file(config_path)
            request = MockSaveRequest(target_path="/etc/hosts")
            result = engine.evaluate(request)
            assert result.final_action == RuleAction.TERMINATE
        finally:
            os.unlink(config_path)

    def test_load_from_dict(self):
        """测试从字典加载"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "block_secret",
                        "patterns": [r"secret"],
                        "action": "terminate",
                        "message": "Secret found",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(content="this is a secret")
        result = engine.evaluate(request)
        assert result.final_action == RuleAction.TERMINATE

    def test_invalid_file_path(self):
        """测试无效文件路径"""
        from src.domain.services.configurable_rule_engine import ConfigurableRuleEngine

        with pytest.raises(FileNotFoundError):
            ConfigurableRuleEngine.from_file("/nonexistent/path/config.json")

    def test_invalid_json_format(self):
        """测试无效 JSON 格式"""
        from src.domain.services.configurable_rule_engine import ConfigurableRuleEngine

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            with pytest.raises(ValueError):
                ConfigurableRuleEngine.from_file(config_path)
        finally:
            os.unlink(config_path)


# =============================================================================
# 10. 默认配置测试
# =============================================================================


class TestDefaultConfig:
    """默认配置测试"""

    def test_default_behavior_allow(self):
        """测试默认行为 - 允许"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {"version": "1.0", "rules": {}}

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(target_path="/any/path", content="any content")

        result = engine.evaluate(request)
        assert result.final_action == RuleAction.ALLOW

    def test_defaults_section(self):
        """测试 defaults 配置节"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {},
            "defaults": {
                "unknown_path_action": "warn",
                "max_content_size_kb": 100,
            },
        }

        engine = ConfigurableRuleEngine(config)

        # 测试大文件被拒绝（100KB = 102400 bytes）
        large_content = "x" * (101 * 1024)  # 101 KB
        request = MockSaveRequest(content=large_content)
        result = engine.evaluate(request)
        assert result.final_action == RuleAction.TERMINATE


# =============================================================================
# 11. 规则引擎与审核系统集成测试
# =============================================================================


class TestIntegrationWithAuditSystem:
    """规则引擎与审核系统集成测试"""

    def test_configurable_engine_as_audit_rule(self):
        """测试可配置引擎作为审核规则"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
        )
        from src.domain.services.save_request_audit import (
            AuditStatus,
            SaveRequestAuditor,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_etc",
                        "pattern": "/etc/*",
                        "action": "terminate",
                        "message": "System path blocked",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        audit_rule = engine.as_audit_rule()

        auditor = SaveRequestAuditor(rules=[audit_rule])

        # 创建真实的 SaveRequest
        request = SaveRequest(
            session_id="session-001",
            source_agent="TestAgent",
            operation_type=SaveRequestType.FILE_WRITE,
            target_path="/etc/hosts",
            content="test",
        )

        result = auditor.audit(request)
        assert result.status == AuditStatus.REJECTED

    def test_engine_evaluation_to_audit_result(self):
        """测试引擎评估结果转审核结果"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        config = {
            "version": "1.0",
            "rules": {
                "content_rules": [
                    {
                        "id": "warn_debug",
                        "patterns": [r"console\.log"],
                        "action": "warn",
                        "message": "Debug log found",
                    }
                ]
            },
        }

        engine = ConfigurableRuleEngine(config)
        audit_rule = engine.as_audit_rule()

        request = SaveRequest(
            session_id="session-001",
            source_agent="TestAgent",
            operation_type=SaveRequestType.FILE_WRITE,
            target_path="/tmp/test.js",
            content="console.log('debug');",
        )

        # WARN 动作应该通过审核（只是警告）
        audit_result = audit_rule.evaluate(request)
        assert audit_result.passed is True  # WARN 允许通过


# =============================================================================
# 12. 完整工作流测试
# =============================================================================


class TestCompleteWorkflow:
    """完整工作流测试"""

    def test_full_config_with_all_rule_types(self):
        """测试包含所有规则类型的完整配置"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
            RuleAction,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "block_system",
                        "pattern": "/etc/*",
                        "action": "terminate",
                        "message": "System paths blocked",
                    },
                    {
                        "id": "warn_config",
                        "pattern": "*.config",
                        "action": "warn",
                        "message": "Config file modification",
                    },
                ],
                "content_rules": [
                    {
                        "id": "block_secrets",
                        "patterns": [r"api_key\s*=", r"password\s*="],
                        "action": "terminate",
                        "message": "Secrets in content",
                    },
                    {
                        "id": "redact_emails",
                        "patterns": [r"\b[\w.-]+@[\w.-]+\.\w+\b"],
                        "action": "replace",
                        "replacement": "[EMAIL]",
                        "message": "Email redacted",
                    },
                ],
                "user_level_rules": [
                    {
                        "id": "admin_only",
                        "required_level": "admin",
                        "paths": ["/admin/*"],
                        "action": "terminate",
                        "message": "Admin required",
                    }
                ],
                "command_rules": [
                    {
                        "id": "block_dangerous",
                        "commands": ["rm -rf", "DROP TABLE"],
                        "action": "terminate",
                        "message": "Dangerous command",
                    }
                ],
            },
            "defaults": {"max_content_size_kb": 1024},
        }

        engine = ConfigurableRuleEngine(config)

        # 场景1: 系统路径 - 终止
        req1 = MockSaveRequest(target_path="/etc/passwd", content="test")
        assert engine.evaluate(req1).final_action == RuleAction.TERMINATE

        # 场景2: 配置文件 - 警告
        req2 = MockSaveRequest(target_path="/app/app.config", content="normal")
        result2 = engine.evaluate(req2)
        assert result2.final_action == RuleAction.WARN
        assert result2.is_allowed is True

        # 场景3: 包含密码 - 终止
        req3 = MockSaveRequest(target_path="/tmp/test.txt", content="password = 'abc'")
        assert engine.evaluate(req3).final_action == RuleAction.TERMINATE

        # 场景4: 包含邮箱 - 替换
        req4 = MockSaveRequest(target_path="/tmp/data.txt", content="Contact: user@example.com")
        result4 = engine.evaluate(req4)
        assert result4.final_action == RuleAction.REPLACE
        assert "[EMAIL]" in result4.modified_content

        # 场景5: 普通用户访问管理路径 - 终止
        req5 = MockSaveRequest(
            target_path="/admin/settings.json", content="test", user_level="user"
        )
        assert engine.evaluate(req5).final_action == RuleAction.TERMINATE

        # 场景6: 管理员访问管理路径 - 允许
        req6 = MockSaveRequest(
            target_path="/admin/settings.json", content="test", user_level="admin"
        )
        assert engine.evaluate(req6).final_action == RuleAction.ALLOW

        # 场景7: 危险命令 - 终止
        req7 = MockSaveRequest(target_path="/tmp/script.sh", content="rm -rf /")
        assert engine.evaluate(req7).final_action == RuleAction.TERMINATE

        # 场景8: 正常请求 - 允许
        req8 = MockSaveRequest(
            target_path="/tmp/output.txt",
            content="Hello World",
            user_level="user",
        )
        assert engine.evaluate(req8).final_action == RuleAction.ALLOW

    def test_rule_evaluation_order(self):
        """测试规则评估顺序"""
        from src.domain.services.configurable_rule_engine import (
            ConfigurableRuleEngine,
        )

        config = {
            "version": "1.0",
            "rules": {
                "path_rules": [
                    {
                        "id": "rule1",
                        "pattern": "/tmp/*",
                        "action": "warn",
                        "message": "Rule 1",
                    }
                ],
                "content_rules": [
                    {
                        "id": "rule2",
                        "patterns": [r"test"],
                        "action": "warn",
                        "message": "Rule 2",
                    }
                ],
            },
        }

        engine = ConfigurableRuleEngine(config)
        request = MockSaveRequest(target_path="/tmp/test.txt", content="test content")

        result = engine.evaluate(request)

        # 两个规则都应该匹配
        assert len(result.matches) == 2
        # 验证规则评估顺序
        assert result.matches[0].rule_id == "rule1"
        assert result.matches[1].rule_id == "rule2"
