"""提示词模板系统 (Prompt Template System)

提供结构化提示词的模块化设计，支持：
1. 四大模块：角色定义、行为准则、工具使用规范、输出格式
2. 变量占位符与动态渲染
3. 模板组合与继承
4. YAML 配置文件加载
5. 模板验证与版本管理

设计原则：
- 模块化：每个提示词组件独立管理
- 可组合：模块可自由组合生成完整提示词
- 可配置：通过 YAML 文件配置，无需修改代码
- 可验证：提供完整的验证机制

创建日期：2025-12-07
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# 异常定义
# =============================================================================


class TemplateError(Exception):
    """模板相关错误基类"""

    pass


class TemplateRenderError(TemplateError):
    """模板渲染错误"""

    pass


class TemplateValidationError(TemplateError):
    """模板验证错误"""

    pass


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class PromptModule:
    """提示词模块

    表示一个可复用的提示词模块，包含模板、变量定义和适用范围。

    属性：
        name: 模块名称（唯一标识）
        version: 版本号（语义化版本）
        description: 模块描述
        template: 模板字符串，使用 {variable} 格式定义变量
        variables: 声明的变量列表
        applicable_agents: 适用的 Agent 类型列表
        metadata: 额外的元数据
    """

    name: str
    version: str
    description: str
    template: str
    variables: list[str]
    applicable_agents: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    # 变量提取正则表达式
    _VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")

    def extract_variables(self) -> set[str]:
        """从模板中提取变量名

        返回：
            模板中使用的变量名集合
        """
        return set(self._VARIABLE_PATTERN.findall(self.template))

    def validate_variables(self) -> bool:
        """验证声明的变量与模板中的变量是否匹配

        返回：
            True 如果完全匹配，False 否则
        """
        extracted = self.extract_variables()
        declared = set(self.variables)
        return extracted == declared

    def get_missing_variables(self) -> set[str]:
        """获取模板中存在但未声明的变量

        返回：
            未声明的变量名集合
        """
        extracted = self.extract_variables()
        declared = set(self.variables)
        return extracted - declared

    def get_unused_variables(self) -> set[str]:
        """获取声明但未在模板中使用的变量

        返回：
            未使用的变量名集合
        """
        extracted = self.extract_variables()
        declared = set(self.variables)
        return declared - extracted

    def render(self, **kwargs: Any) -> str:
        """渲染模板

        参数：
            **kwargs: 变量值

        返回：
            渲染后的字符串

        异常：
            TemplateRenderError: 如果缺少必需的变量
        """
        missing = self.extract_variables() - set(kwargs.keys())
        if missing:
            raise TemplateRenderError(
                f"Missing required variables for module '{self.name}': {missing}"
            )

        result = self.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result


@dataclass
class ValidationResult:
    """验证结果

    属性：
        is_valid: 是否验证通过
        errors: 错误列表
        warnings: 警告列表
        missing_variables: 缺失的变量
        unused_variables: 未使用的变量
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_variables: list[str] = field(default_factory=list)
    unused_variables: list[str] = field(default_factory=list)


# =============================================================================
# 内置模块定义
# =============================================================================

# 角色定义模块
ROLE_DEFINITION_MODULE = PromptModule(
    name="role_definition",
    version="1.0.0",
    description="定义 Agent 的身份、职责和能力范围",
    template="""## 角色定义

你是一个 **{agent_name}**。

### 职责
{responsibility}

### 核心能力
{capabilities}
""",
    variables=["agent_name", "responsibility", "capabilities"],
    applicable_agents=["ConversationAgent", "WorkflowAgent", "CoordinatorAgent"],
    metadata={"category": "identity", "priority": 1},
)

# 行为准则模块
BEHAVIOR_GUIDELINES_MODULE = PromptModule(
    name="behavior_guidelines",
    version="1.0.0",
    description="定义 Agent 应该遵循的行为规范和原则",
    template="""## 行为准则

### 核心原则
{principles}

### 约束条件
{constraints}

### 禁止行为
{forbidden_actions}
""",
    variables=["principles", "constraints", "forbidden_actions"],
    applicable_agents=["ConversationAgent", "WorkflowAgent", "CoordinatorAgent"],
    metadata={"category": "behavior", "priority": 2},
)

# 工具使用规范模块
TOOL_USAGE_MODULE = PromptModule(
    name="tool_usage",
    version="1.0.0",
    description="定义可用工具及其使用方式",
    template="""## 工具使用规范

### 可用工具
{allowed_tools}

### 工具说明
{tool_descriptions}

### 使用示例
{usage_examples}
""",
    variables=["allowed_tools", "tool_descriptions", "usage_examples"],
    applicable_agents=["ConversationAgent", "WorkflowAgent"],
    metadata={"category": "tools", "priority": 3},
)

# 输出格式模块
OUTPUT_FORMAT_MODULE = PromptModule(
    name="output_format",
    version="1.0.0",
    description="定义 Agent 输出的格式要求",
    template="""## 输出格式

### 格式类型
{format_type}

### 输出 Schema
```json
{output_schema}
```

### 示例
```json
{examples}
```
""",
    variables=["format_type", "output_schema", "examples"],
    applicable_agents=["ConversationAgent", "WorkflowAgent", "CoordinatorAgent"],
    metadata={"category": "output", "priority": 4},
)

# 内置模块列表
BUILTIN_MODULES = [
    ROLE_DEFINITION_MODULE,
    BEHAVIOR_GUIDELINES_MODULE,
    TOOL_USAGE_MODULE,
    OUTPUT_FORMAT_MODULE,
]


# =============================================================================
# 模板注册表
# =============================================================================


class PromptTemplateRegistry:
    """提示词模板注册表

    管理所有已注册的提示词模块，提供加载、查询和渲染功能。
    """

    def __init__(self) -> None:
        """初始化注册表"""
        self._modules: dict[str, dict[str, PromptModule]] = {}  # name -> version -> module

    def register(self, module: PromptModule) -> None:
        """注册模块

        参数：
            module: 要注册的模块
        """
        if module.name not in self._modules:
            self._modules[module.name] = {}
        self._modules[module.name][module.version] = module

    def load_builtin_modules(self) -> None:
        """加载所有内置模块"""
        for module in BUILTIN_MODULES:
            self.register(module)

    def get_module(self, name: str, version: str | None = None) -> PromptModule | None:
        """获取模块

        参数：
            name: 模块名称
            version: 版本号，如果为 None 则返回最新版本

        返回：
            模块实例，如果不存在则返回 None
        """
        if name not in self._modules:
            return None

        versions = self._modules[name]
        if version:
            return versions.get(version)

        # 返回最新版本（按版本号排序）
        if versions:
            latest_version = sorted(versions.keys())[-1]
            return versions[latest_version]
        return None

    def get_modules_for_agent(self, agent_type: str) -> list[PromptModule]:
        """获取适用于特定 Agent 的所有模块

        参数：
            agent_type: Agent 类型名称

        返回：
            适用模块列表
        """
        result = []
        for versions in self._modules.values():
            for module in versions.values():
                if agent_type in module.applicable_agents:
                    result.append(module)
                    break  # 每个模块只取一个版本
        return result

    def render_module(self, name: str, **kwargs: Any) -> str:
        """渲染指定模块

        参数：
            name: 模块名称
            **kwargs: 变量值

        返回：
            渲染后的字符串

        异常：
            TemplateRenderError: 如果模块不存在或缺少变量
        """
        module = self.get_module(name)
        if module is None:
            raise TemplateRenderError(f"Module '{name}' not found")
        return module.render(**kwargs)

    def list_modules(self) -> list[str]:
        """列出所有已注册的模块名称

        返回：
            模块名称列表
        """
        return list(self._modules.keys())


# =============================================================================
# 模板组合器
# =============================================================================


class PromptTemplateComposer:
    """提示词模板组合器

    将多个模块组合成完整的提示词。
    """

    def __init__(self, registry: PromptTemplateRegistry) -> None:
        """初始化组合器

        参数：
            registry: 模板注册表
        """
        self._registry = registry

    def compose(
        self,
        modules: list[str],
        variables: dict[str, Any],
        separator: str = "\n\n---\n\n",
    ) -> str:
        """组合多个模块

        参数：
            modules: 要组合的模块名称列表
            variables: 所有模块使用的变量
            separator: 模块之间的分隔符

        返回：
            组合后的完整提示词
        """
        rendered_parts = []

        for module_name in modules:
            module = self._registry.get_module(module_name)
            if module is None:
                raise TemplateRenderError(f"Module '{module_name}' not found")

            # 只传递该模块需要的变量
            module_vars = {k: v for k, v in variables.items() if k in module.variables}
            rendered = module.render(**module_vars)
            rendered_parts.append(rendered)

        return separator.join(rendered_parts)

    def generate_for_agent(
        self,
        agent_type: str,
        variables: dict[str, Any],
        separator: str = "\n\n---\n\n",
    ) -> str:
        """为特定 Agent 生成完整提示词

        参数：
            agent_type: Agent 类型
            variables: 变量值
            separator: 模块分隔符

        返回：
            生成的完整提示词
        """
        modules = self._registry.get_modules_for_agent(agent_type)

        # 按优先级排序
        modules.sort(key=lambda m: m.metadata.get("priority", 99))

        module_names = [m.name for m in modules]
        return self.compose(module_names, variables, separator)


# =============================================================================
# 模板加载器
# =============================================================================


class PromptTemplateLoader:
    """提示词模板加载器

    从 YAML 文件加载模板。
    """

    def load_from_yaml(self, file_path: Path) -> PromptModule:
        """从 YAML 文件加载模块

        参数：
            file_path: YAML 文件路径

        返回：
            加载的模块

        异常：
            FileNotFoundError: 文件不存在
            TemplateValidationError: YAML 格式错误
        """
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise TemplateValidationError(f"Invalid YAML format in {file_path}")

        return PromptModule(
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            template=data.get("template", ""),
            variables=data.get("variables", []),
            applicable_agents=data.get("applicable_agents", []),
            metadata=data.get("metadata", {}),
        )

    def load_directory(self, directory: Path) -> list[PromptModule]:
        """从目录加载所有 YAML 模板

        参数：
            directory: 目录路径

        返回：
            加载的模块列表
        """
        modules = []
        for yaml_file in directory.glob("*.yaml"):
            try:
                module = self.load_from_yaml(yaml_file)
                modules.append(module)
            except Exception:
                # 跳过无效文件
                pass
        return modules


# =============================================================================
# 模板验证器
# =============================================================================


class PromptTemplateValidator:
    """提示词模板验证器

    验证模板的语法、变量完整性等。
    """

    # 变量模式：{variable_name}
    _VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")
    # 无效模式：未闭合的括号
    _INVALID_PATTERN = re.compile(r"\{[^}]*\{|\}[^{]*\}")

    def validate_syntax(self, template: str) -> ValidationResult:
        """验证模板语法

        参数：
            template: 模板字符串

        返回：
            验证结果
        """
        errors = []

        # 检查括号匹配
        open_count = template.count("{")
        close_count = template.count("}")

        if open_count != close_count:
            errors.append(f"Mismatched braces: {open_count} opening, {close_count} closing")

        # 检查无效模式
        if self._INVALID_PATTERN.search(template):
            errors.append("Invalid brace pattern detected")

        # 检查空变量名
        if "{}" in template:
            errors.append("Empty variable name detected")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def validate_variables(self, module: PromptModule) -> ValidationResult:
        """验证模块的变量声明

        参数：
            module: 要验证的模块

        返回：
            验证结果
        """
        missing = list(module.get_missing_variables())
        unused = list(module.get_unused_variables())

        errors = []
        warnings = []

        if missing:
            errors.append(f"Undeclared variables in template: {missing}")

        if unused:
            warnings.append(f"Declared but unused variables: {unused}")

        return ValidationResult(
            is_valid=len(missing) == 0,
            errors=errors,
            warnings=warnings,
            missing_variables=missing,
            unused_variables=unused,
        )

    def validate_module(self, module: PromptModule) -> ValidationResult:
        """完整验证模块

        参数：
            module: 要验证的模块

        返回：
            验证结果
        """
        # 语法验证
        syntax_result = self.validate_syntax(module.template)
        if not syntax_result.is_valid:
            return syntax_result

        # 变量验证
        var_result = self.validate_variables(module)

        return var_result
