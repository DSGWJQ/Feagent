"""
场景提示词与 Task Prompt 注入系统

该模块实现:
1. ScenarioPrompt - 场景提示词数据结构
2. ScenarioPromptLoader - 从 YAML/JSON 加载场景提示词
3. TaskPrompt - 任务提示词数据结构
4. TaskPromptGenerator - 生成子任务提示词
5. TemplateComposer - 模板组合与变量替换
6. TaskTypeRegistry / TaskTypeConfig - 任务类型注册
7. ScenarioRegistry - 场景注册表
8. SubtaskPromptService - ConversationAgent 集成服务
9. ScenarioSchemaValidator - Schema 校验器
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ============================================================================
# 异常类
# ============================================================================


class ScenarioSchemaError(Exception):
    """场景 Schema 验证错误"""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class ScenarioPrompt:
    """
    场景提示词数据结构

    用于定义特定领域/场景的提示词模板，如金融分析、法律合规等。

    Attributes:
        scenario_id: 唯一标识符
        name: 场景名称
        description: 场景描述
        domain: 领域分类 (如 finance, legal, medical)
        system_prompt: 系统提示词模板
        guidelines: 指南列表
        constraints: 约束条件列表
        variables: 支持的变量列表 (如 ["company_name", "report_date"])
        examples: 示例列表
        tags: 标签列表
    """

    scenario_id: str
    name: str
    description: str
    domain: str
    system_prompt: str
    guidelines: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "system_prompt": self.system_prompt,
            "guidelines": self.guidelines,
            "constraints": self.constraints,
            "variables": self.variables,
            "examples": self.examples,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioPrompt:
        """从字典创建实例"""
        return cls(
            scenario_id=data["scenario_id"],
            name=data["name"],
            description=data.get("description", ""),
            domain=data["domain"],
            system_prompt=data["system_prompt"],
            guidelines=data.get("guidelines", []),
            constraints=data.get("constraints", []),
            variables=data.get("variables", []),
            examples=data.get("examples", []),
            tags=data.get("tags", []),
        )


@dataclass
class TaskPrompt:
    """
    任务提示词数据结构

    用于为子 Agent 生成具体任务的提示词指导。

    Attributes:
        task_id: 任务 ID
        task_type: 任务类型
        objective: 任务目标
        context: 上下文信息
        instructions: 任务指令列表
        constraints: 约束条件列表
        expected_output: 预期输出描述
        scenario_id: 关联的场景 ID
        scenario_context: 场景上下文描述
    """

    task_id: str
    task_type: str
    objective: str
    context: str | dict[str, Any] = ""
    instructions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    expected_output: str = ""
    scenario_id: str | None = None
    scenario_context: str = ""

    def render(self) -> str:
        """渲染为完整的提示词字符串"""
        parts = []

        # 添加任务类型和目标
        parts.append(f"## 任务类型: {self.task_type}")
        parts.append(f"\n### 目标\n{self.objective}")

        # 添加上下文
        if self.context:
            parts.append("\n### 上下文")
            if isinstance(self.context, dict):
                for key, value in self.context.items():
                    parts.append(f"- {key}: {value}")
            else:
                parts.append(self.context)

        # 添加场景上下文
        if self.scenario_context:
            parts.append(f"\n### 场景上下文\n{self.scenario_context}")

        # 添加指令
        if self.instructions:
            parts.append("\n### 指令")
            for instr in self.instructions:
                parts.append(f"- {instr}")

        # 添加约束
        if self.constraints:
            parts.append("\n### 约束")
            for constraint in self.constraints:
                parts.append(f"- {constraint}")

        # 添加预期输出
        if self.expected_output:
            parts.append(f"\n### 预期输出\n{self.expected_output}")

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "objective": self.objective,
            "context": self.context,
            "instructions": self.instructions,
            "constraints": self.constraints,
            "expected_output": self.expected_output,
            "scenario_id": self.scenario_id,
            "scenario_context": self.scenario_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskPrompt:
        """从字典创建实例"""
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            objective=data["objective"],
            context=data.get("context", ""),
            instructions=data.get("instructions", []),
            constraints=data.get("constraints", []),
            expected_output=data.get("expected_output", ""),
            scenario_id=data.get("scenario_id"),
            scenario_context=data.get("scenario_context", ""),
        )


@dataclass
class TaskTypeConfig:
    """
    任务类型配置

    Attributes:
        task_type: 任务类型标识
        name: 任务类型名称
        default_instructions: 默认指令列表
        default_constraints: 默认约束列表
        expected_output_format: 默认输出格式
    """

    task_type: str
    name: str
    default_instructions: list[str] = field(default_factory=list)
    default_constraints: list[str] = field(default_factory=list)
    expected_output_format: str = ""


@dataclass
class ValidationResult:
    """Schema 校验结果"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


# ============================================================================
# 默认任务类型配置
# ============================================================================

DEFAULT_TASK_TYPE_CONFIGS: dict[str, TaskTypeConfig] = {
    "data_analysis": TaskTypeConfig(
        task_type="data_analysis",
        name="数据分析",
        default_instructions=[
            "深入分析数据，提取关键洞察",
            "识别数据模式和趋势",
            "提供数据驱动的建议",
        ],
        default_constraints=[
            "确保数据准确性",
            "标注数据来源",
        ],
        expected_output_format="结构化分析报告",
    ),
    "summarization": TaskTypeConfig(
        task_type="summarization",
        name="内容摘要",
        default_instructions=[
            "提取核心要点和关键信息",
            "保持摘要简洁明了",
            "总结主要结论和建议",
        ],
        default_constraints=[
            "保持原意准确性",
            "避免遗漏重要信息",
        ],
        expected_output_format="简洁摘要",
    ),
    "code_generation": TaskTypeConfig(
        task_type="code_generation",
        name="代码生成",
        default_instructions=[
            "生成高质量、可维护的代码",
            "遵循最佳实践和代码规范",
            "添加必要的注释和文档",
            "实现完整的错误处理",
        ],
        default_constraints=[
            "代码需通过静态检查",
            "遵循项目编码规范",
        ],
        expected_output_format="完整可执行代码",
    ),
    "compliance_check": TaskTypeConfig(
        task_type="compliance_check",
        name="合规检查",
        default_instructions=[
            "检查条款完整性和合规性",
            "标注潜在风险点",
            "提供改进建议",
        ],
        default_constraints=[
            "依据相关法规标准",
            "客观公正评估",
        ],
        expected_output_format="合规检查报告",
    ),
}


# ============================================================================
# Schema 验证
# ============================================================================

SCENARIO_REQUIRED_FIELDS = ["scenario_id", "name", "domain", "system_prompt"]


def validate_scenario_data(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    验证场景配置数据是否符合 Schema

    Args:
        data: 待验证的字典数据

    Returns:
        (is_valid, errors) 元组
    """
    errors = []

    # 检查必需字段
    for field_name in SCENARIO_REQUIRED_FIELDS:
        if field_name not in data:
            errors.append(f"缺少必需字段: {field_name}")
        elif not data[field_name]:
            errors.append(f"字段 {field_name} 不能为空")

    # 检查字段类型
    if "guidelines" in data and not isinstance(data["guidelines"], list):
        errors.append("guidelines 字段必须是列表类型")
    if "constraints" in data and not isinstance(data["constraints"], list):
        errors.append("constraints 字段必须是列表类型")
    if "variables" in data and not isinstance(data["variables"], list):
        errors.append("variables 字段必须是列表类型")

    return len(errors) == 0, errors


class ScenarioSchemaValidator:
    """场景 Schema 校验器"""

    def __init__(self):
        """初始化校验器"""
        self.required_fields = SCENARIO_REQUIRED_FIELDS

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """
        验证场景数据

        Args:
            data: 待验证的字典数据

        Returns:
            ValidationResult 实例
        """
        is_valid, errors = validate_scenario_data(data)
        return ValidationResult(is_valid=is_valid, errors=errors)


# ============================================================================
# 加载器
# ============================================================================


class ScenarioPromptLoader:
    """
    场景提示词加载器

    支持从 YAML 和 JSON 文件加载场景配置，并进行 Schema 验证。
    """

    def __init__(self, validate: bool = True):
        """
        初始化加载器

        Args:
            validate: 是否在加载时验证 Schema
        """
        self.validate = validate
        self._validator = ScenarioSchemaValidator()

    def load_from_file(self, file_path: str | Path) -> ScenarioPrompt:
        """
        从文件加载场景 (自动检测 YAML/JSON)

        Args:
            file_path: 文件路径

        Returns:
            ScenarioPrompt 实例

        Raises:
            ScenarioSchemaError: Schema 验证失败
            FileNotFoundError: 文件不存在
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        with open(file_path, encoding="utf-8") as f:
            if suffix in (".yaml", ".yml"):
                data = yaml.safe_load(f)
            elif suffix == ".json":
                data = json.load(f)
            else:
                raise ValueError(f"不支持的文件格式: {suffix}")

        if not isinstance(data, dict):
            raise ValueError(f"Invalid file format in {file_path}")

        if self.validate:
            result = self._validator.validate(data)
            if not result.is_valid:
                raise ScenarioSchemaError(f"Schema 验证失败: {file_path}", result.errors)

        return ScenarioPrompt.from_dict(data)

    def load_from_yaml(self, file_path: str | Path) -> ScenarioPrompt:
        """从 YAML 文件加载场景"""
        return self.load_from_file(file_path)

    def load_from_json(self, file_path: str | Path) -> ScenarioPrompt:
        """从 JSON 文件加载场景"""
        return self.load_from_file(file_path)

    def load_from_directory(self, dir_path: str | Path) -> dict[str, ScenarioPrompt]:
        """
        从目录加载所有场景配置

        Args:
            dir_path: 目录路径

        Returns:
            {scenario_id: ScenarioPrompt} 字典
        """
        dir_path = Path(dir_path)
        scenarios: dict[str, ScenarioPrompt] = {}

        # 加载所有支持的文件
        for pattern in ("*.yaml", "*.yml", "*.json"):
            for file_path in dir_path.glob(pattern):
                try:
                    scenario = self.load_from_file(file_path)
                    scenarios[scenario.scenario_id] = scenario
                except (ScenarioSchemaError, yaml.YAMLError, json.JSONDecodeError):
                    continue  # 跳过无效文件

        return scenarios

    def validate_schema(self, data: dict[str, Any]) -> ValidationResult:
        """
        验证数据是否符合 Schema

        Args:
            data: 待验证的字典数据

        Returns:
            ValidationResult 实例
        """
        return self._validator.validate(data)


# ============================================================================
# Task Prompt 生成器
# ============================================================================


class TaskPromptGenerator:
    """
    任务提示词生成器

    根据任务类型和上下文生成适合子 Agent 的提示词。
    """

    def __init__(self):
        """初始化生成器"""
        self._task_types: dict[str, TaskTypeConfig] = {}
        self._current_scenario: ScenarioPrompt | None = None

        # 注册默认任务类型
        for task_type, config in DEFAULT_TASK_TYPE_CONFIGS.items():
            self._task_types[task_type] = config

    def set_scenario(self, scenario: ScenarioPrompt) -> None:
        """
        设置当前场景

        Args:
            scenario: 场景提示词实例
        """
        self._current_scenario = scenario

    def clear_scenario(self) -> None:
        """清除当前场景"""
        self._current_scenario = None

    def register_task_type(self, config: TaskTypeConfig) -> None:
        """
        注册任务类型

        Args:
            config: 任务类型配置
        """
        self._task_types[config.task_type] = config

    def list_task_types(self) -> list[str]:
        """
        列出所有注册的任务类型

        Returns:
            任务类型列表
        """
        return list(self._task_types.keys())

    def generate(
        self,
        task_id: str,
        task_type: str,
        objective: str,
        context: dict[str, Any] | None = None,
        instructions: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> TaskPrompt:
        """
        生成任务提示词

        Args:
            task_id: 任务 ID
            task_type: 任务类型
            objective: 任务目标
            context: 上下文信息
            instructions: 额外指令 (会与默认指令合并)
            constraints: 额外约束 (会与默认约束合并)

        Returns:
            TaskPrompt 实例
        """
        # 获取任务类型配置
        config = self._task_types.get(task_type)

        # 合并指令
        merged_instructions = []
        if config:
            merged_instructions.extend(config.default_instructions)
        if instructions:
            merged_instructions.extend(instructions)

        # 合并约束
        merged_constraints = []
        if config:
            merged_constraints.extend(config.default_constraints)
        if constraints:
            merged_constraints.extend(constraints)

        # 处理场景
        scenario_id = None
        scenario_context = ""
        if self._current_scenario:
            scenario_id = self._current_scenario.scenario_id
            scenario_context = (
                f"{self._current_scenario.name}: {self._current_scenario.description}"
            )
            # 添加场景约束
            merged_constraints.extend(self._current_scenario.constraints)

        # 构建上下文字符串
        context_str = ""
        if context:
            context_str = "; ".join(f"{k}: {v}" for k, v in context.items())

        return TaskPrompt(
            task_id=task_id,
            task_type=task_type,
            objective=objective,
            context=context_str,
            instructions=merged_instructions,
            constraints=merged_constraints,
            expected_output=config.expected_output_format if config else "",
            scenario_id=scenario_id,
            scenario_context=scenario_context,
        )


# ============================================================================
# 模板组合器
# ============================================================================


class TemplateComposer:
    """
    模板组合器

    用于将通用模板与场景模板组合，并进行变量替换。
    """

    # 变量占位符模式: {variable_name}
    VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")

    def __init__(self):
        """初始化组合器"""
        pass

    def compose(
        self,
        generic_template: str,
        scenario: ScenarioPrompt,
        task_content: str = "",
    ) -> str:
        """
        组合通用模板与场景模板

        Args:
            generic_template: 通用模板字符串
            scenario: 场景提示词
            task_content: 任务内容

        Returns:
            组合后的模板字符串
        """
        # 构建场景内容
        scenario_parts = []
        scenario_parts.append(f"## 场景: {scenario.name}")
        scenario_parts.append(f"领域: {scenario.domain}\n")
        scenario_parts.append(scenario.system_prompt)

        if scenario.guidelines:
            scenario_parts.append("\n### 指南")
            for guideline in scenario.guidelines:
                scenario_parts.append(f"- {guideline}")

        scenario_content = "\n".join(scenario_parts)

        # 替换占位符
        result = generic_template.replace("{scenario_content}", scenario_content)
        result = result.replace("{task_content}", task_content)

        return result

    def substitute_variables(
        self,
        template: str,
        variables: dict[str, Any],
        default_value: str | None = None,
    ) -> str:
        """
        替换模板中的变量

        Args:
            template: 模板字符串
            variables: 变量字典
            default_value: 缺失变量的默认值

        Returns:
            替换后的字符串
        """

        def replace_match(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name in variables:
                return str(variables[var_name])
            elif default_value is not None:
                return default_value
            else:
                # 保留原占位符
                return match.group(0)

        return self.VARIABLE_PATTERN.sub(replace_match, template)

    def extract_variables(self, template: str) -> list[str]:
        """
        从模板中提取变量名

        Args:
            template: 模板字符串

        Returns:
            变量名列表
        """
        variables = []
        for match in self.VARIABLE_PATTERN.finditer(template):
            var_name = match.group(1)
            if var_name not in variables:
                variables.append(var_name)
        return variables


# ============================================================================
# 注册表
# ============================================================================


class TaskTypeRegistry:
    """
    任务类型注册表

    管理和注册自定义任务类型及其模板配置。
    """

    def __init__(self):
        """初始化注册表"""
        self._registry: dict[str, TaskTypeConfig] = {}

        # 注册默认任务类型
        for task_type, config in DEFAULT_TASK_TYPE_CONFIGS.items():
            self._registry[task_type] = config

    def register(self, config: TaskTypeConfig) -> None:
        """
        注册任务类型

        Args:
            config: 任务类型配置
        """
        self._registry[config.task_type] = config

    def get(self, task_type: str) -> TaskTypeConfig | None:
        """
        获取任务类型配置

        Args:
            task_type: 任务类型标识

        Returns:
            任务类型配置或 None
        """
        return self._registry.get(task_type)

    def list_types(self) -> list[str]:
        """
        列出所有注册的任务类型

        Returns:
            任务类型列表
        """
        return list(self._registry.keys())

    def unregister(self, task_type: str) -> bool:
        """
        注销任务类型

        Args:
            task_type: 任务类型标识

        Returns:
            是否成功注销
        """
        if task_type in self._registry:
            del self._registry[task_type]
            return True
        return False


class ScenarioRegistry:
    """
    场景注册表

    管理和注册场景提示词。
    """

    def __init__(self):
        """初始化注册表"""
        self._scenarios: dict[str, ScenarioPrompt] = {}
        self._domain_index: dict[str, list[str]] = {}

    def register(self, scenario: ScenarioPrompt) -> None:
        """
        注册场景

        Args:
            scenario: 场景提示词实例
        """
        self._scenarios[scenario.scenario_id] = scenario

        # 更新领域索引
        if scenario.domain not in self._domain_index:
            self._domain_index[scenario.domain] = []
        if scenario.scenario_id not in self._domain_index[scenario.domain]:
            self._domain_index[scenario.domain].append(scenario.scenario_id)

    def get(self, scenario_id: str) -> ScenarioPrompt | None:
        """
        获取场景

        Args:
            scenario_id: 场景 ID

        Returns:
            场景实例或 None
        """
        return self._scenarios.get(scenario_id)

    def list_by_domain(self, domain: str) -> list[ScenarioPrompt]:
        """
        按领域列出场景

        Args:
            domain: 领域名称

        Returns:
            该领域的场景列表
        """
        scenario_ids = self._domain_index.get(domain, [])
        return [self._scenarios[sid] for sid in scenario_ids if sid in self._scenarios]

    def list_all(self) -> list[ScenarioPrompt]:
        """
        列出所有场景

        Returns:
            所有场景列表
        """
        return list(self._scenarios.values())

    def list_domains(self) -> list[str]:
        """
        列出所有领域

        Returns:
            领域名称列表
        """
        return list(self._domain_index.keys())

    def unregister(self, scenario_id: str) -> bool:
        """
        注销场景

        Args:
            scenario_id: 场景 ID

        Returns:
            是否成功注销
        """
        if scenario_id in self._scenarios:
            scenario = self._scenarios[scenario_id]
            del self._scenarios[scenario_id]

            # 更新领域索引
            if scenario.domain in self._domain_index:
                if scenario_id in self._domain_index[scenario.domain]:
                    self._domain_index[scenario.domain].remove(scenario_id)

            return True
        return False


# ============================================================================
# ConversationAgent 集成服务
# ============================================================================


class SubtaskPromptService:
    """
    子任务提示词服务

    为 ConversationAgent 提供子任务提示词生成功能。
    """

    def __init__(self):
        """初始化服务"""
        self._generator = TaskPromptGenerator()
        self._current_scenario: ScenarioPrompt | None = None

    def set_scenario(self, scenario: ScenarioPrompt) -> None:
        """
        设置当前场景

        Args:
            scenario: 场景提示词实例
        """
        self._current_scenario = scenario
        self._generator.set_scenario(scenario)

    def clear_scenario(self) -> None:
        """清除当前场景"""
        self._current_scenario = None
        self._generator.clear_scenario()

    def generate_for_subtask(self, subtask: dict[str, Any]) -> TaskPrompt:
        """
        为子任务生成提示词

        Args:
            subtask: 子任务字典，包含 id, type, description, context

        Returns:
            TaskPrompt 实例
        """
        return self._generator.generate(
            task_id=subtask.get("id", "unknown"),
            task_type=subtask.get("type", "unknown"),
            objective=subtask.get("description", ""),
            context=subtask.get("context"),
        )

    def generate_for_subtasks(self, subtasks: list[dict[str, Any]]) -> list[TaskPrompt]:
        """
        为多个子任务生成提示词

        Args:
            subtasks: 子任务列表

        Returns:
            TaskPrompt 实例列表
        """
        return [self.generate_for_subtask(subtask) for subtask in subtasks]


# ============================================================================
# 工厂函数
# ============================================================================


def create_scenario_prompt(
    scenario_id: str,
    name: str,
    domain: str,
    system_prompt: str,
    description: str = "",
    **kwargs: Any,
) -> ScenarioPrompt:
    """
    创建场景提示词的便捷函数

    Args:
        scenario_id: 唯一标识符
        name: 场景名称
        domain: 领域分类
        system_prompt: 系统提示词
        description: 场景描述
        **kwargs: 其他可选参数

    Returns:
        ScenarioPrompt 实例
    """
    return ScenarioPrompt(
        scenario_id=scenario_id,
        name=name,
        description=description,
        domain=domain,
        system_prompt=system_prompt,
        guidelines=kwargs.get("guidelines", []),
        constraints=kwargs.get("constraints", []),
        variables=kwargs.get("variables", []),
        examples=kwargs.get("examples", []),
        tags=kwargs.get("tags", []),
    )


def create_task_prompt(
    task_id: str,
    task_type: str,
    objective: str,
    **kwargs: Any,
) -> TaskPrompt:
    """
    创建任务提示词的便捷函数

    Args:
        task_id: 任务 ID
        task_type: 任务类型
        objective: 任务目标
        **kwargs: 其他可选参数

    Returns:
        TaskPrompt 实例
    """
    return TaskPrompt(
        task_id=task_id,
        task_type=task_type,
        objective=objective,
        context=kwargs.get("context", ""),
        instructions=kwargs.get("instructions", []),
        constraints=kwargs.get("constraints", []),
        expected_output=kwargs.get("expected_output", ""),
        scenario_id=kwargs.get("scenario_id"),
        scenario_context=kwargs.get("scenario_context", ""),
    )
