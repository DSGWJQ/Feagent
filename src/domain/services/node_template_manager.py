"""节点模板管理器 (Node Template Manager) - 阶段4

业务定义：
- 管理节点模板的注册、查询和实例化
- 支持从模板创建新的工作流节点
- 模板是可复用的节点配置，与具体工作流解耦

核心功能：
- register_template: 注册新模板
- list_templates: 列出所有可用模板
- get_template: 获取模板详情
- instantiate: 从模板创建节点实例
"""

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from src.domain.services.node_registry import (
    Node,
    NodeScope,
    NodeType,
    PromotionStatus,
)


@dataclass
class NodeTemplate:
    """节点模板

    存储可复用的节点配置。

    属性：
    - id: 模板唯一标识
    - name: 模板名称
    - node_type: 节点类型
    - config: 节点配置
    - description: 模板描述
    - created_at: 创建时间
    - usage_count: 使用次数
    """

    id: str
    name: str
    node_type: NodeType
    config: dict[str, Any]
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0


class NodeTemplateManager:
    """节点模板管理器

    职责：
    1. 注册和管理节点模板
    2. 提供模板查询接口
    3. 从模板实例化新节点

    使用示例：
        manager = NodeTemplateManager()

        # 注册模板
        template_id = manager.register_template(
            name="数据分析模板",
            node_type=NodeType.LLM,
            config={"model": "gpt-4", "user_prompt": "分析数据"},
        )

        # 实例化模板
        node = manager.instantiate(template_id, workflow_id="wf_new")
    """

    def __init__(self):
        """初始化模板管理器"""
        self._templates: dict[str, NodeTemplate] = {}

    def register_template(
        self,
        name: str,
        node_type: NodeType,
        config: dict[str, Any],
        description: str = "",
        template_id: str | None = None,
    ) -> str:
        """注册新模板

        参数：
            name: 模板名称
            node_type: 节点类型
            config: 节点配置
            description: 模板描述
            template_id: 可选，指定模板ID

        返回：
            模板ID
        """
        tid = template_id or f"tpl_{uuid4().hex[:12]}"

        template = NodeTemplate(
            id=tid,
            name=name,
            node_type=node_type,
            config=copy.deepcopy(config),  # 深拷贝避免外部修改
            description=description,
        )

        self._templates[tid] = template
        return tid

    def list_templates(self, node_type: NodeType | None = None) -> list[dict[str, Any]]:
        """列出所有模板

        参数：
            node_type: 可选，按节点类型过滤

        返回：
            模板列表（字典格式）
        """
        result = []

        for template in self._templates.values():
            if node_type and template.node_type != node_type:
                continue

            result.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "node_type": template.node_type.value,
                    "description": template.description,
                    "created_at": template.created_at.isoformat(),
                    "usage_count": template.usage_count,
                }
            )

        return result

    def get_template(self, template_id: str) -> dict[str, Any]:
        """获取模板详情

        参数：
            template_id: 模板ID

        返回：
            模板详情（包含config）

        异常：
            ValueError: 模板不存在
        """
        template = self._templates.get(template_id)

        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        return {
            "id": template.id,
            "name": template.name,
            "node_type": template.node_type.value,
            "config": copy.deepcopy(template.config),  # 返回副本
            "description": template.description,
            "created_at": template.created_at.isoformat(),
            "usage_count": template.usage_count,
        }

    def instantiate(
        self,
        template_id: str,
        workflow_id: str,
        node_id: str | None = None,
        config_overrides: dict[str, Any] | None = None,
    ) -> Node:
        """从模板创建节点实例

        创建一个新的节点，继承模板的配置但是独立的实例。

        参数：
            template_id: 模板ID
            workflow_id: 目标工作流ID（用于追踪）
            node_id: 可选，指定节点ID
            config_overrides: 可选，配置覆盖

        返回：
            新节点实例

        异常：
            ValueError: 模板不存在
        """
        template = self._templates.get(template_id)

        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        # 增加使用计数
        template.usage_count += 1

        # 合并配置
        config = copy.deepcopy(template.config)
        if config_overrides:
            config.update(config_overrides)

        # 创建新节点
        node = Node(
            id=node_id or f"node_{uuid4().hex[:12]}",
            type=template.node_type,
            config=config,
            scope=NodeScope.WORKFLOW,  # 实例化后回到工作流作用域
            version=1,
            promotion_status=PromotionStatus.DRAFT,
            source_template_id=template_id,  # 记录来源模板
        )

        return node

    def delete_template(self, template_id: str) -> bool:
        """删除模板

        参数：
            template_id: 模板ID

        返回：
            是否删除成功
        """
        if template_id in self._templates:
            del self._templates[template_id]
            return True
        return False

    def update_template(
        self,
        template_id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """更新模板

        参数：
            template_id: 模板ID
            name: 新名称（可选）
            config: 新配置（可选）
            description: 新描述（可选）

        返回：
            更新后的模板

        异常：
            ValueError: 模板不存在
        """
        template = self._templates.get(template_id)

        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        if name is not None:
            template.name = name
        if config is not None:
            template.config = copy.deepcopy(config)
        if description is not None:
            template.description = description

        return self.get_template(template_id)


# 导出
__all__ = [
    "NodeTemplate",
    "NodeTemplateManager",
]
