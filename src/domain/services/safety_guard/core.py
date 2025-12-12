"""SafetyGuard - 安全校验服务

从 CoordinatorAgent 提取的安全校验能力，封装：
- 文件操作安全校验（路径遍历、黑白名单、内容大小）
- API调用安全校验（URL scheme、域名、SSRF防护）
- 人机交互安全校验（提示注入、敏感内容）

设计要点：
- 方法签名与 CoordinatorAgent 现有接口完全一致（向后兼容）
- 延迟导入避免循环依赖
- 提供配置接口允许动态调整规则
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class ValidationResult:
    """验证结果

    属性：
    - is_valid: 是否验证通过
    - errors: 错误信息列表
    - correction: 可选的修正后决策
    """

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    correction: dict[str, Any] | None = None


class SafetyGuard:
    """安全校验服务

    提供文件操作、API调用、人机交互的安全验证。

    使用示例：
        guard = SafetyGuard()
        guard.configure_file_security(whitelist=["/allowed"])
        result = await guard.validate_file_operation("node1", "read", "/allowed/file.txt")
        if not result.is_valid:
            print(f"Validation failed: {result.errors}")
    """

    def __init__(
        self,
        file_security_config: dict[str, Any] | None = None,
        api_whitelist: set[str] | None = None,
        api_blacklist: set[str] | None = None,
        allowed_api_schemes: set[str] | None = None,
        human_sensitive_patterns: list[str] | None = None,
    ) -> None:
        """初始化安全校验器

        参数：
            file_security_config: 文件安全配置字典
            api_whitelist: API域名白名单
            api_blacklist: API域名黑名单
            allowed_api_schemes: 允许的URL scheme集合
            human_sensitive_patterns: 人机交互额外敏感词模式
        """
        # 文件安全配置（默认值）
        self._file_security_config = file_security_config or {
            "whitelist": [],
            "blacklist": ["/etc", "/sys", "/proc", "/root", "/boot", "/dev"],
            "max_content_bytes": 2 * 1024 * 1024,  # 2MB
            "allowed_operations": {"read", "write", "append", "delete", "list"},
        }

        # API域名配置
        self._api_domain_whitelist: set[str] = api_whitelist or set()
        self._api_domain_blacklist: set[str] = api_blacklist or set()
        self._allowed_api_schemes: set[str] = allowed_api_schemes or {"http", "https"}

        # 人机交互敏感词
        self._human_sensitive_patterns: list[str] | None = human_sensitive_patterns

    # ==================== 配置接口 ====================

    def configure_file_security(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        max_content_bytes: int | None = None,
        allowed_operations: set[str] | None = None,
    ) -> None:
        """配置文件操作安全规则

        参数:
            whitelist: 允许访问的路径白名单
            blacklist: 禁止访问的路径黑名单
            max_content_bytes: 内容最大字节数限制
            allowed_operations: 允许的操作类型集合
        """
        if whitelist is not None:
            self._file_security_config["whitelist"] = whitelist
        if blacklist is not None:
            self._file_security_config["blacklist"] = blacklist
        if max_content_bytes is not None:
            self._file_security_config["max_content_bytes"] = max_content_bytes
        if allowed_operations is not None:
            self._file_security_config["allowed_operations"] = allowed_operations

    def configure_api_domains(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        allowed_schemes: set[str] | None = None,
    ) -> None:
        """配置API域名白名单规则

        参数:
            whitelist: 允许访问的域名白名单
            blacklist: 禁止访问的域名黑名单
            allowed_schemes: 允许的URL scheme集合
        """
        if whitelist is not None:
            self._api_domain_whitelist = {d.lower() for d in whitelist}
        if blacklist is not None:
            self._api_domain_blacklist = {d.lower() for d in blacklist}
        if allowed_schemes is not None:
            self._allowed_api_schemes = allowed_schemes

    # ==================== 文件操作校验 ====================

    async def validate_file_operation(
        self,
        node_id: str,
        operation: str | None,
        path: str | None,
        config: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """验证文件操作安全性

        参数:
            node_id: 节点ID
            operation: 文件操作类型（read/write/append/delete/list）
            path: 文件路径
            config: 节点配置，包含content等字段

        返回:
            ValidationResult: 验证结果
        """
        from src.domain.services.save_request_audit import SensitiveContentRule

        errors: list[str] = []

        # 检查operation合法性
        if not operation or operation not in self._file_security_config["allowed_operations"]:
            errors.append(f"invalid operation: {operation}")

        # 检查path必填
        if not path:
            errors.append("path is required")
            return ValidationResult(is_valid=False, errors=errors)

        # 路径遍历检测
        raw_path = Path(path)
        if ".." in raw_path.parts:
            errors.append("path contains traversal segments")

        # 解析路径
        try:
            target_path = Path(path).expanduser().resolve()
        except Exception as e:
            errors.append(f"invalid path format: {e}")
            return ValidationResult(is_valid=False, errors=errors)

        # 黑名单检查
        for blacklist_pattern in self._file_security_config["blacklist"]:
            try:
                if target_path.is_relative_to(Path(blacklist_pattern).resolve()):
                    errors.append(f"path is blacklisted: {blacklist_pattern}")
                    break
            except (ValueError, TypeError):
                # Python 3.8兼容或无效路径
                if str(target_path).startswith(blacklist_pattern):
                    errors.append(f"path is blacklisted: {blacklist_pattern}")
                    break

        # 白名单检查
        whitelist = self._file_security_config["whitelist"]
        if whitelist:
            is_in_whitelist = False
            for allowed_root in whitelist:
                try:
                    if target_path.is_relative_to(Path(allowed_root).expanduser().resolve()):
                        is_in_whitelist = True
                        break
                except (ValueError, TypeError):
                    if str(target_path).startswith(allowed_root):
                        is_in_whitelist = True
                        break

            if not is_in_whitelist:
                errors.append("path not in whitelist")

        # 写/追加操作的内容检查
        config = config or {}
        if operation in {"write", "append"}:
            content = config.get("content")
            if content is None:
                errors.append("content is required for write/append")
            else:
                # 内容大小检查
                content_bytes = len(str(content).encode("utf-8"))
                max_bytes = self._file_security_config["max_content_bytes"]
                if content_bytes > max_bytes:
                    errors.append(f"content exceeds max size: {content_bytes} > {max_bytes}")

                # 敏感内容检查
                sens_rule = SensitiveContentRule()
                # 创建临时请求对象用于检测
                mock_request = type("Request", (), {"content": str(content)})()
                sens_result = sens_rule.evaluate(mock_request)
                if not sens_result.passed:
                    errors.append("content contains sensitive information")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # ==================== API调用校验 ====================

    async def validate_api_request(
        self,
        node_id: str,
        url: str | None,
        method: str | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> ValidationResult:
        """验证API请求安全性

        参数:
            node_id: 节点ID
            url: API URL
            method: HTTP方法
            headers: 请求头
            body: 请求体

        返回:
            ValidationResult: 验证结果
        """
        errors: list[str] = []

        # URL必填
        if not url:
            errors.append("url is required")
            return ValidationResult(is_valid=False, errors=errors)

        # URL解析
        try:
            parsed = urlparse(url)
        except Exception as e:
            errors.append(f"invalid url format: {e}")
            return ValidationResult(is_valid=False, errors=errors)

        # Scheme检查
        if parsed.scheme not in self._allowed_api_schemes:
            errors.append(f"url scheme not allowed: {parsed.scheme}")

        # Hostname必填
        host = parsed.hostname or ""
        if not host:
            errors.append("hostname is required")
            return ValidationResult(is_valid=False, errors=errors)

        # 转小写进行比较（域名不区分大小写）
        host_lower = host.lower()

        # 黑名单检查
        if host_lower in self._api_domain_blacklist:
            errors.append(f"domain is blacklisted: {host}")

        # 白名单检查
        if self._api_domain_whitelist and host_lower not in self._api_domain_whitelist:
            errors.append(f"domain not in whitelist: {host}")

        # SSRF防护：检测私有IP和本地地址
        # 检查常见的本地主机名
        if host_lower in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
            errors.append(f"loopback address not allowed: {host}")
        else:
            # 尝试解析为IP地址
            try:
                ip = ipaddress.ip_address(host)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    errors.append(f"private/loopback IP not allowed: {host}")
            except ValueError:
                # 不是IP地址，跳过此检查
                pass

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # ==================== 人机交互校验 ====================

    async def validate_human_interaction(
        self,
        node_id: str,
        prompt: str,
        expected_inputs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """验证人机交互内容安全性

        参数:
            node_id: 节点ID
            prompt: 显示给用户的提示文本
            expected_inputs: 预期输入字段列表
            metadata: 附加元数据

        返回:
            ValidationResult: 验证结果
        """
        from src.domain.services.save_request_audit import SensitiveContentRule

        errors: list[str] = []

        # 提示必填
        if not prompt or not prompt.strip():
            errors.append("prompt is required")
            return ValidationResult(is_valid=False, errors=errors)

        # 长度限制
        if len(prompt) > 4000:
            errors.append("prompt too long (max 4000 chars)")

        # 提示注入检测
        lower_prompt = prompt.lower()
        injection_keywords = [
            "ignore previous instructions",
            "bypass safety",
            "disable filter",
            "override system",
            "disregard all",
        ]
        for keyword in injection_keywords:
            if keyword in lower_prompt:
                errors.append(f"prompt contains injection keyword: {keyword}")
                break

        # 敏感内容检测
        sens_rule = SensitiveContentRule(additional_patterns=self._human_sensitive_patterns or [])
        mock_request = type("Request", (), {"content": prompt})()
        sens_result = sens_rule.evaluate(mock_request)
        if not sens_result.passed:
            errors.append("prompt contains sensitive information")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


__all__ = ["SafetyGuard"]
