"""NodeExecutor Port（节点执行器端口）

Domain 层端口：定义节点执行器接口

为什么是 Port？
- 节点执行需要外部依赖（HTTP 客户端、LLM API 等）
- Domain 层不能直接依赖这些实现
- 通过 Port 定义接口，Infrastructure 层实现
"""

from abc import ABC, abstractmethod
from typing import Any

from src.domain.entities.node import Node


class NodeExecutor(ABC):
    """节点执行器接口
    
    每种节点类型都有对应的执行器实现
    """

    @abstractmethod
    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行节点
        
        参数：
            node: 节点实体
            inputs: 输入数据（来自前驱节点）
            context: 执行上下文（共享变量）
            
        返回：
            节点输出
            
        异常：
            DomainError: 执行失败
        """
        pass


class NodeExecutorRegistry:
    """节点执行器注册表
    
    管理所有节点类型的执行器
    """

    def __init__(self):
        self._executors: dict[str, NodeExecutor] = {}

    def register(self, node_type: str, executor: NodeExecutor) -> None:
        """注册执行器
        
        参数：
            node_type: 节点类型
            executor: 执行器实例
        """
        self._executors[node_type] = executor

    def get(self, node_type: str) -> NodeExecutor | None:
        """获取执行器
        
        参数：
            node_type: 节点类型
            
        返回：
            执行器实例，如果未注册则返回 None
        """
        return self._executors.get(node_type)

    def has(self, node_type: str) -> bool:
        """检查是否已注册执行器
        
        参数：
            node_type: 节点类型
            
        返回：
            是否已注册
        """
        return node_type in self._executors

