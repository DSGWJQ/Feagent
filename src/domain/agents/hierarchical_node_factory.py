"""层次化节点工厂 (HierarchicalNodeFactory) - Phase 4

业务定义：
- 根据节点类型自动创建层次化结构
- 当创建"数据处理"类型节点时，自动生成父节点+容器子节点
- 检测代码依赖并配置容器

设计原则：
- 智能检测：根据节点名称/类型判断是否需要容器执行
- 自动化：自动创建父子结构
- 可配置：支持自定义容器关键词和配置

使用示例：
    factory = HierarchicalNodeFactory()
    node = factory.create_node(name="数据处理", code="import pandas")
    # node 是父节点，包含一个容器子节点
"""

import re
from dataclasses import dataclass, field
from typing import Any

from src.domain.agents.node_definition import (
    NodeDefinition,
    NodeDefinitionFactory,
    NodeType,
)

# 默认容器关键词
DEFAULT_CONTAINER_KEYWORDS = [
    "数据处理",
    "data_processing",
    "机器学习",
    "ML",
    "模型训练",
    "深度学习",
    "数据分析",
    "ETL",
    "大数据",
    "pandas",
    "numpy",
    "sklearn",
    "tensorflow",
    "pytorch",
]

# Python 包名映射（import 名称 -> pip 包名）
PACKAGE_NAME_MAPPING = {
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "yaml": "pyyaml",
}


@dataclass
class HierarchicalNodeFactory:
    """层次化节点工厂

    根据节点类型自动创建适当的层次结构。

    属性：
        container_keywords: 需要容器执行的关键词列表
        default_image: 默认 Docker 镜像
        default_timeout: 默认超时时间
        default_memory_limit: 默认内存限制
    """

    container_keywords: list[str] = field(default_factory=lambda: DEFAULT_CONTAINER_KEYWORDS.copy())
    default_image: str = "python:3.11-slim"
    default_timeout: int = 60
    default_memory_limit: str = "256m"

    def needs_container_execution(self, name: str) -> bool:
        """判断节点是否需要容器执行

        参数：
            name: 节点名称

        返回：
            是否需要容器执行
        """
        name_lower = name.lower()
        for keyword in self.container_keywords:
            if keyword.lower() in name_lower:
                return True
        return False

    def create_node(
        self,
        name: str,
        code: str,
        description: str = "",
        container_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> NodeDefinition:
        """创建节点

        如果节点需要容器执行，自动创建层次结构（父节点+容器子节点）。
        否则创建简单的 Python 节点。

        参数：
            name: 节点名称
            code: Python 代码
            description: 节点描述
            container_config: 容器配置（可选）
            **kwargs: 额外配置

        返回：
            NodeDefinition 实例（可能是父节点）
        """
        if self.needs_container_execution(name):
            return self._create_hierarchical_node(
                name=name,
                code=code,
                description=description,
                container_config=container_config,
                **kwargs,
            )
        else:
            return self._create_simple_node(
                name=name,
                code=code,
                description=description,
                **kwargs,
            )

    def _create_hierarchical_node(
        self,
        name: str,
        code: str,
        description: str = "",
        container_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> NodeDefinition:
        """创建层次化节点

        创建一个 GENERIC 父节点和一个 CONTAINER 子节点。

        参数：
            name: 节点名称
            code: Python 代码
            description: 节点描述
            container_config: 容器配置
            **kwargs: 额外配置

        返回：
            父节点（包含容器子节点）
        """
        # 创建父节点
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name=name,
            description=description,
            collapsed=True,
        )

        # 准备容器配置
        config = self._prepare_container_config(code, container_config)

        # 创建容器子节点
        child = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name=f"{name} - Container",
            code=code,
            description=f"容器执行: {description}" if description else "容器执行节点",
            is_container=True,
            container_config=config,
        )

        # 建立父子关系
        parent.add_child(child)

        return parent

    def _create_simple_node(
        self,
        name: str,
        code: str,
        description: str = "",
        **kwargs: Any,
    ) -> NodeDefinition:
        """创建简单 Python 节点

        参数：
            name: 节点名称
            code: Python 代码
            description: 节点描述
            **kwargs: 额外配置

        返回：
            Python 节点
        """
        return NodeDefinitionFactory.create_python_node(
            name=name,
            code=code,
            description=description,
            **kwargs,
        )

    def _prepare_container_config(
        self,
        code: str,
        custom_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """准备容器配置

        自动检测代码依赖并合并自定义配置。

        参数：
            code: Python 代码
            custom_config: 自定义配置

        返回：
            完整的容器配置
        """
        # 基础配置
        config = {
            "image": self.default_image,
            "timeout": self.default_timeout,
            "memory_limit": self.default_memory_limit,
            "pip_packages": [],
        }

        # 自动检测依赖
        dependencies = self._detect_dependencies(code)
        config["pip_packages"] = dependencies

        # 合并自定义配置
        if custom_config:
            config.update(custom_config)

        return config

    def _detect_dependencies(self, code: str) -> list[str]:
        """检测代码依赖

        从代码中提取 import 语句，转换为 pip 包名。

        参数：
            code: Python 代码

        返回：
            pip 包名列表
        """
        packages = set()

        # 匹配 import xxx 和 from xxx import yyy
        import_patterns = [
            r"^import\s+(\w+)",
            r"^from\s+(\w+)",
        ]

        for line in code.split("\n"):
            line = line.strip()
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    module_name = match.group(1)
                    # 跳过标准库
                    if not self._is_stdlib(module_name):
                        # 转换为 pip 包名
                        pip_name = PACKAGE_NAME_MAPPING.get(module_name, module_name)
                        packages.add(pip_name)

        return sorted(packages)

    def _is_stdlib(self, module_name: str) -> bool:
        """判断是否为标准库模块

        参数：
            module_name: 模块名称

        返回：
            是否为标准库
        """
        stdlib_modules = {
            "os",
            "sys",
            "re",
            "json",
            "time",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "math",
            "random",
            "string",
            "io",
            "pathlib",
            "typing",
            "abc",
            "dataclasses",
            "enum",
            "copy",
            "logging",
            "unittest",
            "asyncio",
            "concurrent",
            "threading",
            "multiprocessing",
            "subprocess",
            "socket",
            "http",
            "urllib",
            "email",
            "html",
            "xml",
            "csv",
            "sqlite3",
            "pickle",
            "hashlib",
            "uuid",
            "tempfile",
            "shutil",
            "glob",
            "fnmatch",
            "inspect",
            "traceback",
            "warnings",
            "contextlib",
            "heapq",
            "bisect",
            "array",
            "struct",
            "codecs",
            "base64",
            "binascii",
            "textwrap",
            "difflib",
            "pprint",
        }
        return module_name in stdlib_modules

    def create_multi_step_node(
        self,
        name: str,
        steps: list[dict[str, Any]],
        description: str = "",
    ) -> NodeDefinition:
        """创建多步骤节点

        创建一个父节点，包含多个容器子节点（每个步骤一个）。

        参数：
            name: 父节点名称
            steps: 步骤列表，每个步骤包含 name 和 code
            description: 父节点描述

        返回：
            父节点（包含多个容器子节点）
        """
        # 创建父节点
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name=name,
            description=description,
            collapsed=True,
        )

        # 创建每个步骤的子节点
        for step in steps:
            step_name = step.get("name", "步骤")
            step_code = step.get("code", "")
            step_description = step.get("description", f"步骤: {step_name}")

            # 准备容器配置
            config = self._prepare_container_config(step_code, step.get("config"))

            child = NodeDefinition(
                node_type=NodeType.CONTAINER,
                name=step_name,
                code=step_code,
                description=step_description,
                is_container=True,
                container_config=config,
            )

            parent.add_child(child)

        return parent


# 导出
__all__ = [
    "DEFAULT_CONTAINER_KEYWORDS",
    "PACKAGE_NAME_MAPPING",
    "HierarchicalNodeFactory",
]
