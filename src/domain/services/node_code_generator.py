"""节点代码生成器 (Node Code Generator) - ConversationAgent 代码生成与节点注册

业务定义：
- 分析用户需求与现有节点的缺口
- 自动生成 YAML 定义和代码
- 注册新节点到系统

设计原则：
- 安全优先：生成的代码符合沙箱约束
- 可回滚：注册失败时能够清理
- 可扩展：支持多种编程语言

核心组件：
- NodeGapAnalyzer: 分析节点缺口
- NodeCodeGenerator: 生成 YAML 和代码
- NodeRegistrationService: 注册节点到系统
- NodeGenerationPrompts: Prompt 模板
- ConversationAgentCodeGenExtension: ConversationAgent 扩展
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ==================== 数据类 ====================


@dataclass
class GapAnalysisResult:
    """缺口分析结果"""

    has_gap: bool = False
    missing_capabilities: list[str] = field(default_factory=list)
    suggested_node_name: str = ""
    suggested_language: str = "python"
    inferred_parameters: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class YamlGenerationResult:
    """YAML 生成结果"""

    yaml_content: str = ""
    is_valid: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class CodeGenerationResult:
    """代码生成结果"""

    code: str = ""
    language: str = "python"
    is_valid: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class CompleteGenerationResult:
    """完整生成结果（YAML + 代码）"""

    node_name: str = ""
    yaml_content: str = ""
    code: str = ""
    language: str = "python"
    is_valid: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class WriteResult:
    """写入结果"""

    success: bool = False
    file_path: str | None = None
    error: str | None = None
    already_exists: bool = False


@dataclass
class RegistrationResult:
    """注册结果"""

    success: bool = False
    yaml_path: str | None = None
    code_path: str | None = None
    error: str | None = None


@dataclass
class NewFunctionalityResult:
    """新功能请求处理结果"""

    success: bool = False
    generated_node_name: str | None = None
    yaml_path: str | None = None
    code_path: str | None = None
    error: str | None = None


# ==================== 语言关键词 ====================

PYTHON_KEYWORDS = [
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "计算",
    "分析",
    "数据",
    "统计",
    "矩阵",
    "数学",
    "机器学习",
    "深度学习",
    "sklearn",
    "tensorflow",
    "pytorch",
    "json",
    "csv",
    "xml",
    "yaml",
    "文件",
    "读取",
    "写入",
    "处理",
    "转换",
    "解析",
    "格式化",
    "算法",
    "排序",
    "搜索",
    "遍历",
    "递归",
    "动态规划",
    "图论",
    "树",
    "链表",
    "栈",
    "队列",
    "哈希",
    "python",
    "pip",
    "import",
]

JAVASCRIPT_KEYWORDS = [
    "dom",
    "浏览器",
    "页面",
    "html",
    "css",
    "前端",
    "react",
    "vue",
    "angular",
    "node",
    "npm",
    "localStorage",
    "sessionStorage",
    "cookie",
    "ajax",
    "fetch",
    "axios",
    "jquery",
    "事件",
    "监听",
    "点击",
    "滚动",
    "动画",
    "canvas",
    "svg",
    "webgl",
    "javascript",
    "js",
    "typescript",
    "ts",
]

# 支持的语言
SUPPORTED_LANGUAGES = ["python", "javascript"]

# 沙箱安全模块白名单
SAFE_MODULES = [
    "math",
    "decimal",
    "fractions",
    "statistics",
    "random",
    "json",
    "csv",
    "collections",
    "itertools",
    "functools",
    "operator",
    "string",
    "re",
    "textwrap",
    "unicodedata",
    "datetime",
    "time",
    "calendar",
    "copy",
    "typing",
    "dataclasses",
    "enum",
]


# ==================== NodeGapAnalyzer ====================


class NodeGapAnalyzer:
    """节点缺口分析器

    分析用户需求与现有节点的匹配程度，识别需要新建的功能。
    """

    def __init__(self) -> None:
        # 常见节点功能映射
        self._capability_keywords: dict[str, list[str]] = {
            "http_request": ["http", "api", "请求", "获取", "发送", "url", "rest", "接口"],
            "json_parser": ["json", "解析", "parse", "转换"],
            "data_transformer": ["转换", "transform", "映射", "格式"],
            "calculator": ["计算", "加", "减", "乘", "除", "运算"],
            "text_processor": ["文本", "字符串", "处理", "替换", "提取"],
        }

    def analyze(
        self,
        task_description: str,
        existing_nodes: list[str],
        coordinator_context: dict[str, Any] | None = None,
    ) -> GapAnalysisResult:
        """分析任务需求与现有节点的缺口

        参数：
            task_description: 任务描述
            existing_nodes: 现有节点列表
            coordinator_context: 协调者上下文（可选）

        返回：
            缺口分析结果
        """
        if not task_description or not task_description.strip():
            raise ValueError("任务描述不能为空")

        task_lower = task_description.lower()

        # 检查现有节点是否能满足需求
        matched_nodes = self._find_matching_nodes(task_lower, existing_nodes)

        if matched_nodes:
            # 现有节点可以满足需求
            return GapAnalysisResult(
                has_gap=False,
                missing_capabilities=[],
                suggested_node_name="",
                confidence=0.9,
            )

        # 需要新节点
        missing_capabilities = self._extract_missing_capabilities(task_description)
        suggested_name = self._suggest_node_name(task_description, coordinator_context)
        suggested_language = self._suggest_language(task_description)
        inferred_params = self._infer_parameters(task_description)

        return GapAnalysisResult(
            has_gap=True,
            missing_capabilities=missing_capabilities,
            suggested_node_name=suggested_name,
            suggested_language=suggested_language,
            inferred_parameters=inferred_params,
            confidence=0.8,
        )

    def _find_matching_nodes(self, task_lower: str, existing_nodes: list[str]) -> list[str]:
        """查找匹配的现有节点"""
        matched = []
        for node_name in existing_nodes:
            node_lower = node_name.lower()
            # 检查节点名是否与任务相关
            if node_lower in task_lower:
                matched.append(node_name)
            # 检查节点功能关键词
            keywords = self._capability_keywords.get(node_lower, [])
            for keyword in keywords:
                if keyword in task_lower:
                    matched.append(node_name)
                    break
        return matched

    def _extract_missing_capabilities(self, task_description: str) -> list[str]:
        """提取缺失的功能"""
        capabilities = []

        # 提取动作词
        action_patterns = [
            r"计算(.+?)(?:的|$)",
            r"获取(.+?)(?:的|$)",
            r"处理(.+?)(?:的|$)",
            r"分析(.+?)(?:的|$)",
            r"生成(.+?)(?:的|$)",
            r"转换(.+?)(?:的|$)",
        ]

        for pattern in action_patterns:
            matches = re.findall(pattern, task_description)
            capabilities.extend(matches)

        if not capabilities:
            # 如果没有匹配到，使用任务描述的关键部分
            capabilities.append(task_description[:50])

        return capabilities

    def _suggest_node_name(
        self, task_description: str, coordinator_context: dict[str, Any] | None = None
    ) -> str:
        """建议节点名称"""
        task_lower = task_description.lower()

        # 检查常见模式
        name_patterns = [
            (r"macd", "macd_calculator"),
            (r"rsi", "rsi_calculator"),
            (r"移动平均|moving average", "moving_average_calculator"),
            (r"斐波那契|fibonacci", "fibonacci_generator"),
            (r"股票|stock", "stock_analyzer"),
            (r"数据.*处理", "data_processor"),
            (r"文本.*处理", "text_processor"),
            (r"计算", "calculator"),
        ]

        for pattern, name in name_patterns:
            if re.search(pattern, task_lower):
                return name

        # 使用协调者上下文
        if coordinator_context:
            hints = coordinator_context.get("knowledge_hints", [])
            if "金融" in str(hints) or "股票" in str(hints):
                return "financial_calculator"

        # 默认名称
        return "custom_processor"

    def _suggest_language(self, task_description: str) -> str:
        """建议编程语言"""
        task_lower = task_description.lower()

        # 检查 JavaScript 关键词
        for keyword in JAVASCRIPT_KEYWORDS:
            if keyword in task_lower:
                return "javascript"

        # 默认 Python
        return "python"

    def _infer_parameters(self, task_description: str) -> list[dict[str, Any]]:
        """推断参数"""
        params = []

        # 常见参数模式
        param_patterns = [
            (r"价格列表|prices?", {"name": "prices", "type": "array", "description": "价格列表"}),
            (
                r"周期|period",
                {"name": "period", "type": "integer", "description": "周期", "default": 5},
            ),
            (r"数据|data", {"name": "data", "type": "object", "description": "输入数据"}),
            (r"文本|text", {"name": "text", "type": "string", "description": "输入文本"}),
            (r"数值|value|number", {"name": "value", "type": "number", "description": "数值"}),
            (r"列表|list|array", {"name": "items", "type": "array", "description": "列表数据"}),
        ]

        for pattern, param in param_patterns:
            if re.search(pattern, task_description, re.IGNORECASE):
                # 避免重复
                if not any(p["name"] == param["name"] for p in params):
                    params.append(param.copy())

        return params


# ==================== NodeCodeGenerator ====================


class NodeCodeGenerator:
    """节点代码生成器

    生成 YAML 定义和代码。
    """

    def generate_yaml(
        self,
        node_name: str,
        description: str,
        language: str,
        parameters: list[dict[str, Any]],
        returns: dict[str, Any],
    ) -> YamlGenerationResult:
        """生成 YAML 定义

        参数：
            node_name: 节点名称
            description: 描述
            language: 编程语言
            parameters: 参数列表
            returns: 返回值定义

        返回：
            YAML 生成结果
        """
        # 规范化节点名称
        sanitized_name = self._sanitize_name(node_name)

        # 构建 YAML 结构
        yaml_dict = {
            "name": sanitized_name,
            "kind": "node",
            "description": description,
            "version": "1.0.0",
            "parameters": self._format_parameters(parameters),
            "returns": returns,
            "executor_type": "code",
            "language": language,
        }

        try:
            dumped = yaml.dump(
                yaml_dict, allow_unicode=True, default_flow_style=False, sort_keys=False
            )
            if dumped is None:
                yaml_content = ""
            elif isinstance(dumped, bytes):
                yaml_content = dumped.decode("utf-8", errors="replace")
            else:
                yaml_content = dumped
            return YamlGenerationResult(yaml_content=yaml_content, is_valid=True)
        except Exception as e:
            return YamlGenerationResult(yaml_content="", is_valid=False, errors=[str(e)])

    def _sanitize_name(self, name: str) -> str:
        """规范化节点名称"""
        # 替换非法字符
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        # 移除连续下划线
        sanitized = re.sub(r"_+", "_", sanitized)
        # 移除首尾下划线
        sanitized = sanitized.strip("_")
        return sanitized.lower()

    def _format_parameters(self, parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """格式化参数列表"""
        formatted = []
        for param in parameters:
            p = {
                "name": param.get("name", "param"),
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
                "required": param.get("required", True),
            }
            if "default" in param:
                p["default"] = param["default"]
            if "enum" in param:
                p["enum"] = param["enum"]
            formatted.append(p)
        return formatted

    def generate_code(
        self,
        node_name: str,
        language: str,
        description: str,
        parameters: list[dict[str, Any]],
        logic_hint: str,
    ) -> CodeGenerationResult:
        """生成代码

        参数：
            node_name: 节点名称
            language: 编程语言
            description: 描述
            parameters: 参数列表
            logic_hint: 逻辑提示

        返回：
            代码生成结果
        """
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"不支持的语言: {language}，支持的语言: {SUPPORTED_LANGUAGES}")

        if language == "python":
            code = self._generate_python_code(node_name, description, parameters, logic_hint)
        else:
            code = self._generate_javascript_code(node_name, description, parameters, logic_hint)

        return CodeGenerationResult(code=code, language=language, is_valid=True)

    def _generate_python_code(
        self,
        node_name: str,
        description: str,
        parameters: list[dict[str, Any]],
        logic_hint: str,
    ) -> str:
        """生成 Python 代码"""
        # 参数列表
        param_names = [p.get("name", f"param_{i}") for i, p in enumerate(parameters)]
        param_str = ", ".join(param_names) if param_names else ""

        # 参数文档
        param_docs = []
        for p in parameters:
            pname = p.get("name", "param")
            ptype = p.get("type", "any")
            pdesc = p.get("description", "")
            param_docs.append(f"        {pname}: {ptype} - {pdesc}")
        param_doc_str = "\n".join(param_docs) if param_docs else "        无参数"

        # 默认值处理
        defaults = []
        for p in parameters:
            pname = p.get("name", "param")
            if "default" in p:
                defaults.append(f"    if {pname} is None:\n        {pname} = {repr(p['default'])}")

        defaults_str = "\n".join(defaults) if defaults else ""

        # 根据 logic_hint 生成核心逻辑
        core_logic = self._generate_python_logic(parameters, logic_hint, node_name)

        code = f'''"""
{description}

节点名称: {node_name}
"""


def main({param_str}):
    """执行节点逻辑

    参数:
{param_doc_str}

    返回:
        dict: 执行结果
    """
{defaults_str}
    try:
{core_logic}
    except Exception as e:
        return {{"error": str(e), "success": False}}
'''
        return code

    def _generate_python_logic(
        self, parameters: list[dict[str, Any]], logic_hint: str, node_name: str
    ) -> str:
        """生成 Python 核心逻辑"""
        param_names = [p.get("name", "param") for p in parameters]
        hint_lower = logic_hint.lower()

        # 根据 logic_hint 生成不同逻辑
        if "平均" in hint_lower or "average" in hint_lower:
            if "prices" in param_names or any("price" in n.lower() for n in param_names):
                return """        # 计算移动平均
        if not prices or len(prices) == 0:
            return {"average": 0, "success": True}
        period = min(period, len(prices)) if period else len(prices)
        recent_prices = prices[-period:]
        average = sum(recent_prices) / len(recent_prices)
        return {"average": average, "success": True}"""

        if "和" in hint_lower or "sum" in hint_lower:
            if "numbers" in param_names:
                return """        # 计算求和
        if not numbers:
            return {"sum": 0, "success": True}
        total = sum(numbers)
        return {"sum": total, "success": True}"""

        if "斐波那契" in hint_lower or "fibonacci" in hint_lower:
            return """        # 生成斐波那契数列
        n = value if value else 10
        if n <= 0:
            return {"sequence": [], "success": True}
        sequence = [0, 1]
        for i in range(2, n):
            sequence.append(sequence[i-1] + sequence[i-2])
        return {"sequence": sequence[:n], "success": True}"""

        if "除" in hint_lower or "divide" in hint_lower:
            return """        # 安全除法
        if b == 0:
            return {"error": "除数不能为零", "success": False}
        result = a / b
        return {"result": result, "success": True}"""

        # 默认逻辑：处理输入并返回
        if param_names:
            param_dict = ", ".join([f'"{n}": {n}' for n in param_names])
            return f"""        # 处理输入数据
        result = {{{param_dict}}}
        return {{"result": result, "success": True}}"""

        return """        # 默认逻辑
        return {"result": None, "success": True}"""

    def _generate_javascript_code(
        self,
        node_name: str,
        description: str,
        parameters: list[dict[str, Any]],
        logic_hint: str,
    ) -> str:
        """生成 JavaScript 代码"""
        param_names = [p.get("name", f"param{i}") for i, p in enumerate(parameters)]
        param_str = ", ".join(param_names) if param_names else ""

        code = f"""/**
 * {description}
 * 节点名称: {node_name}
 */

function main({param_str}) {{
    try {{
        // 处理输入
        const result = {{ {", ".join([f"{n}: {n}" for n in param_names]) if param_names else ""} }};
        return {{ result, success: true }};
    }} catch (error) {{
        return {{ error: error.message, success: false }};
    }}
}}

module.exports = {{ main }};
"""
        return code

    def generate_complete(
        self,
        node_name: str,
        description: str,
        language: str,
        parameters: list[dict[str, Any]],
        logic_hint: str,
    ) -> CompleteGenerationResult:
        """生成完整的节点定义（YAML + 代码）

        参数：
            node_name: 节点名称
            description: 描述
            language: 编程语言
            parameters: 参数列表
            logic_hint: 逻辑提示

        返回：
            完整生成结果
        """
        if not node_name or not node_name.strip():
            raise ValueError("节点名称不能为空")

        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"不支持的语言: {language}")

        errors = []

        # 生成 YAML
        yaml_result = self.generate_yaml(
            node_name=node_name,
            description=description or "自动生成的节点",
            language=language,
            parameters=parameters,
            returns={"type": "object", "properties": {"result": {"type": "object"}}},
        )
        if not yaml_result.is_valid:
            errors.extend(yaml_result.errors)

        # 生成代码
        code_result = self.generate_code(
            node_name=node_name,
            language=language,
            description=description or "自动生成的节点",
            parameters=parameters,
            logic_hint=logic_hint,
        )
        if not code_result.is_valid:
            errors.extend(code_result.errors)

        return CompleteGenerationResult(
            node_name=self._sanitize_name(node_name),
            yaml_content=yaml_result.yaml_content,
            code=code_result.code,
            language=language,
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def infer_parameters(self, description: str) -> list[dict[str, Any]]:
        """从描述推断参数

        参数：
            description: 任务描述

        返回：
            推断的参数列表
        """
        params = []

        # 参数模式
        patterns = [
            (r"价格列表|prices?", "prices", "array", "价格列表"),
            (r"周期|period|天", "period", "integer", "周期"),
            (r"数据|data", "data", "object", "输入数据"),
            (r"文本|text|字符串", "text", "string", "输入文本"),
            (r"数值|value|number|值", "value", "number", "数值"),
        ]

        for pattern, name, ptype, desc in patterns:
            if re.search(pattern, description, re.IGNORECASE):
                if not any(p["name"] == name for p in params):
                    params.append({"name": name, "type": ptype, "description": desc})

        return params

    def suggest_language(self, description: str) -> str:
        """根据描述建议编程语言

        参数：
            description: 任务描述

        返回：
            建议的语言
        """
        desc_lower = description.lower()

        # 检查 JavaScript 关键词
        for keyword in JAVASCRIPT_KEYWORDS:
            if keyword in desc_lower:
                return "javascript"

        # 默认 Python
        return "python"


# ==================== NodeRegistrationService ====================


class NodeRegistrationService:
    """节点注册服务

    将生成的节点注册到系统。
    """

    def __init__(
        self,
        definitions_dir: str | None = None,
        scripts_dir: str | None = None,
        registry: Any = None,
    ) -> None:
        self.definitions_dir = (
            Path(definitions_dir) if definitions_dir else Path("definitions/nodes")
        )
        self.scripts_dir = Path(scripts_dir) if scripts_dir else Path("scripts/nodes")
        self.registry = registry
        self._written_files: list[Path] = []

    def write_definition(
        self,
        node_name: str,
        yaml_content: str,
        overwrite: bool = True,
    ) -> WriteResult:
        """将 YAML 定义写入文件

        参数：
            node_name: 节点名称
            yaml_content: YAML 内容
            overwrite: 是否覆盖已存在的文件

        返回：
            写入结果
        """
        try:
            # 确保目录存在
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            file_path = self.definitions_dir / f"{node_name}.yaml"

            # 检查是否已存在
            if file_path.exists() and not overwrite:
                return WriteResult(success=False, file_path=str(file_path), already_exists=True)

            # 写入文件
            file_path.write_text(yaml_content, encoding="utf-8")
            self._written_files.append(file_path)

            return WriteResult(success=True, file_path=str(file_path))

        except Exception as e:
            return WriteResult(success=False, error=str(e))

    def write_code(
        self,
        node_name: str,
        code: str,
        language: str,
    ) -> WriteResult:
        """将代码写入文件

        参数：
            node_name: 节点名称
            code: 代码内容
            language: 编程语言

        返回：
            写入结果
        """
        try:
            # 确保目录存在
            self.scripts_dir.mkdir(parents=True, exist_ok=True)

            # 确定文件扩展名
            ext = ".py" if language == "python" else ".js"
            file_path = self.scripts_dir / f"{node_name}{ext}"

            # 写入文件
            file_path.write_text(code, encoding="utf-8")
            self._written_files.append(file_path)

            return WriteResult(success=True, file_path=str(file_path))

        except Exception as e:
            return WriteResult(success=False, error=str(e))

    def register_to_registry(
        self,
        node_name: str,
        node_type: str,
        schema: dict[str, Any],
    ) -> WriteResult:
        """注册节点到 NodeRegistry

        参数：
            node_name: 节点名称
            node_type: 节点类型
            schema: 配置 Schema

        返回：
            注册结果
        """
        try:
            if self.registry:
                # 动态创建节点类型
                from src.domain.services.node_registry import NodeType

                # 使用 CODE 类型作为自定义节点的基础
                self.registry.register(NodeType.CODE, schema)

            return WriteResult(success=True)

        except Exception as e:
            return WriteResult(success=False, error=str(e))

    def register_complete(
        self,
        node_name: str,
        yaml_content: str,
        code: str,
        language: str,
    ) -> RegistrationResult:
        """完整注册流程

        参数：
            node_name: 节点名称
            yaml_content: YAML 内容
            code: 代码内容
            language: 编程语言

        返回：
            注册结果
        """
        try:
            # 写入 YAML
            yaml_result = self.write_definition(node_name, yaml_content)
            if not yaml_result.success:
                return RegistrationResult(success=False, error=yaml_result.error)

            # 写入代码
            code_result = self.write_code(node_name, code, language)
            if not code_result.success:
                # 回滚 YAML
                self.rollback(node_name)
                return RegistrationResult(success=False, error=code_result.error)

            return RegistrationResult(
                success=True,
                yaml_path=yaml_result.file_path,
                code_path=code_result.file_path,
            )

        except Exception as e:
            self.rollback(node_name)
            return RegistrationResult(success=False, error=str(e))

    def rollback(self, node_name: str) -> None:
        """回滚注册

        删除已写入的文件。

        参数：
            node_name: 节点名称
        """
        # 删除 YAML 文件
        yaml_path = self.definitions_dir / f"{node_name}.yaml"
        if yaml_path.exists():
            yaml_path.unlink()

        # 删除代码文件
        for ext in [".py", ".js"]:
            code_path = self.scripts_dir / f"{node_name}{ext}"
            if code_path.exists():
                code_path.unlink()

        # 清理记录
        self._written_files = [f for f in self._written_files if node_name not in str(f)]


# ==================== NodeGenerationPrompts ====================


class NodeGenerationPrompts:
    """节点生成的 Prompt 模板"""

    def get_system_prompt(self) -> str:
        """获取系统 Prompt"""
        return """你是一个专业的节点定义生成器。你的任务是根据用户需求生成符合规范的节点定义。

节点定义规范：
1. 每个节点必须有 name、kind、description 字段
2. kind 必须是 "node"
3. parameters 定义输入参数，每个参数包含 name、type、description、required
4. returns 定义返回值结构
5. 代码必须符合沙箱安全要求

YAML 节点定义格式：
```yaml
name: 节点名称
kind: node
description: 节点描述
version: "1.0.0"
parameters:
  - name: param1
    type: string
    description: 参数描述
    required: true
returns:
  type: object
  properties:
    result:
      type: object
executor_type: code
language: python
```

安全约束：
- 禁止使用 os、subprocess、sys 等系统模块
- 禁止使用 eval、exec、compile 等动态执行函数
- 禁止文件操作和网络请求
- 允许使用 math、json、datetime 等安全模块
"""

    def get_analysis_prompt(
        self,
        task_description: str,
        available_tools: list[str],
    ) -> str:
        """获取分析 Prompt

        参数：
            task_description: 任务描述
            available_tools: 可用工具列表

        返回：
            分析 Prompt
        """
        tools_str = "\n".join([f"- {tool}" for tool in available_tools])
        return f"""分析以下任务需求，判断是否需要创建新节点。

任务描述：{task_description}

当前可用的节点/工具：
{tools_str}

请分析：
1. 现有节点是否能满足需求？
2. 如果需要新节点，应该具备什么功能？
3. 建议的节点名称是什么？
4. 需要哪些输入参数？
"""

    def get_code_generation_prompt(
        self,
        node_name: str,
        language: str,
        parameters: list[dict[str, Any]],
    ) -> str:
        """获取代码生成 Prompt

        参数：
            node_name: 节点名称
            language: 编程语言
            parameters: 参数列表

        返回：
            代码生成 Prompt
        """
        params_str = "\n".join([f"- {p.get('name')}: {p.get('type', 'any')}" for p in parameters])

        return f"""生成 {language} 代码实现以下节点功能。

节点名称：{node_name}
编程语言：{language}

输入参数：
{params_str}

安全约束（必须遵守）：
- 禁止导入 os、subprocess、sys、socket 等危险模块
- 禁止使用 eval、exec、compile、__import__ 等函数
- 禁止文件读写操作
- 禁止网络请求
- 只能使用安全模块：math、json、datetime、collections、itertools 等

请生成符合以上约束的代码。
"""

    def get_parameter_inference_prompt(self, task_description: str) -> str:
        """获取参数推断 Prompt

        参数：
            task_description: 任务描述

        返回：
            参数推断 Prompt
        """
        return f"""根据以下任务描述，推断所需的输入参数。

任务描述：{task_description}

请列出需要的参数，包括：
- 参数名称 (name)
- 参数类型 (type): string, number, integer, boolean, array, object
- 参数描述 (description)
- 是否必需 (required)
- 默认值 (default, 如果有)

输出格式为 JSON 数组。
"""


# ==================== ConversationAgentCodeGenExtension ====================


class ConversationAgentCodeGenExtension:
    """ConversationAgent 代码生成扩展

    为 ConversationAgent 提供代码生成能力。
    """

    def __init__(
        self,
        definitions_dir: str | None = None,
        scripts_dir: str | None = None,
    ) -> None:
        self.analyzer = NodeGapAnalyzer()
        self.generator = NodeCodeGenerator()
        self.service = NodeRegistrationService(
            definitions_dir=definitions_dir,
            scripts_dir=scripts_dir,
        )

    def handle_new_functionality_request(
        self,
        user_request: str,
        existing_nodes: list[str],
        coordinator_context: dict[str, Any] | None = None,
    ) -> NewFunctionalityResult:
        """处理新功能请求

        参数：
            user_request: 用户请求
            existing_nodes: 现有节点列表
            coordinator_context: 协调者上下文

        返回：
            处理结果
        """
        try:
            # 1. 分析缺口
            gap_result = self.analyzer.analyze(
                task_description=user_request,
                existing_nodes=existing_nodes,
                coordinator_context=coordinator_context,
            )

            if not gap_result.has_gap:
                return NewFunctionalityResult(
                    success=True,
                    generated_node_name=None,
                    error="现有节点可以满足需求",
                )

            # 2. 生成节点
            gen_result = self.generator.generate_complete(
                node_name=gap_result.suggested_node_name,
                description=gap_result.missing_capabilities[0]
                if gap_result.missing_capabilities
                else user_request,
                language=gap_result.suggested_language,
                parameters=gap_result.inferred_parameters,
                logic_hint=user_request,
            )

            if not gen_result.is_valid:
                return NewFunctionalityResult(
                    success=False,
                    error=f"代码生成失败: {gen_result.errors}",
                )

            # 3. 注册节点
            reg_result = self.service.register_complete(
                node_name=gen_result.node_name,
                yaml_content=gen_result.yaml_content,
                code=gen_result.code,
                language=gen_result.language,
            )

            if not reg_result.success:
                return NewFunctionalityResult(
                    success=False,
                    error=f"节点注册失败: {reg_result.error}",
                )

            return NewFunctionalityResult(
                success=True,
                generated_node_name=gen_result.node_name,
                yaml_path=reg_result.yaml_path,
                code_path=reg_result.code_path,
            )

        except Exception as e:
            return NewFunctionalityResult(success=False, error=str(e))
