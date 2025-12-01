"""AI节点执行器（AI Node Executors）

知识库/分类/MCP节点执行器，支持智能AI工作流。

组件：
- KnowledgeExecutor: 知识库检索执行器
- ClassifyExecutor: 分类执行器
- MCPExecutor: MCP协议执行器
- AINodeFactory: AI节点工厂

功能：
- 知识库检索：模板查询、相似度过滤、重排序
- 智能分类：LLM分类、规则分类、多标签、降级
- MCP调用：动态参数、超时控制、错误处理

设计原则：
- 依赖注入：外部服务通过构造函数注入
- 错误容错：失败时返回错误信息而非抛异常
- 模板支持：Jinja2模板变量替换

"""

import asyncio
import json
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class RetrieverProtocol(Protocol):
    """检索器协议"""

    async def retrieve(
        self, knowledge_base_id: str, query: str, top_k: int
    ) -> list[dict[str, Any]]:
        """检索文档"""
        ...


class RerankerProtocol(Protocol):
    """重排序器协议"""

    async def rerank(self, query: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """重排序文档"""
        ...


class LLMClientProtocol(Protocol):
    """LLM客户端协议"""

    async def generate(self, prompt: str) -> str:
        """生成响应"""
        ...


class MCPClientProtocol(Protocol):
    """MCP客户端协议"""

    async def call_tool(self, server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """调用MCP工具"""
        ...


def render_template(template: str, variables: dict[str, Any]) -> str:
    """渲染简单模板

    支持 {{variable}} 语法

    参数：
        template: 模板字符串
        variables: 变量字典

    返回：
        渲染后的字符串
    """
    result = template
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value))
    return result


class KnowledgeExecutor:
    """知识库检索执行器

    从知识库检索相关文档。

    使用示例：
        executor = KnowledgeExecutor(retriever=my_retriever)
        result = await executor.execute(config, inputs)
    """

    def __init__(self, retriever: RetrieverProtocol, reranker: RerankerProtocol | None = None):
        """初始化

        参数：
            retriever: 检索器
            reranker: 可选的重排序器
        """
        self.retriever = retriever
        self.reranker = reranker

    async def execute(self, config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        """执行知识库检索

        参数：
            config: 配置
            inputs: 输入数据

        返回：
            检索结果
        """
        knowledge_base_id = config.get("knowledge_base_id", "")
        query_template = config.get("query_template", "{{query}}")
        top_k = config.get("top_k", 5)
        similarity_threshold = config.get("similarity_threshold", 0.0)
        rerank_enabled = config.get("rerank_enabled", False)

        # 渲染查询模板
        query = render_template(query_template, inputs)

        try:
            # 检索文档
            documents = await self.retriever.retrieve(
                knowledge_base_id=knowledge_base_id, query=query, top_k=top_k
            )

            # 相似度过滤
            if similarity_threshold > 0:
                documents = [
                    doc for doc in documents if doc.get("score", 0) >= similarity_threshold
                ]

            # 重排序
            if rerank_enabled and self.reranker and documents:
                documents = await self.reranker.rerank(query, documents)

            return {"documents": documents, "query": query, "count": len(documents)}

        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            return {"documents": [], "query": query, "count": 0, "error": str(e)}


class ClassifyExecutor:
    """分类执行器

    支持LLM分类和规则分类。

    使用示例：
        executor = ClassifyExecutor(llm_client=my_llm)
        result = await executor.execute(config, inputs)
    """

    def __init__(self, llm_client: LLMClientProtocol | None = None):
        """初始化

        参数：
            llm_client: 可选的LLM客户端
        """
        self.llm = llm_client

    async def execute(self, config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        """执行分类

        参数：
            config: 配置
            inputs: 输入数据

        返回：
            分类结果
        """
        classification_type = config.get("classification_type", "llm")
        multi_label = config.get("multi_label", False)
        fallback_to_rule = config.get("fallback_to_rule", False)

        text = inputs.get("text", "")

        if classification_type == "rule":
            return await self._rule_classify(config, text)
        elif classification_type == "llm":
            try:
                if multi_label:
                    return await self._llm_multi_classify(config, text)
                else:
                    return await self._llm_classify(config, text)
            except Exception as e:
                logger.warning(f"LLM分类失败: {e}")
                if fallback_to_rule:
                    result = await self._rule_classify(config, text)
                    result["fallback"] = True
                    return result
                raise

        return {"category": None, "confidence": 0}

    async def _llm_classify(self, config: dict[str, Any], text: str) -> dict[str, Any]:
        """LLM单标签分类

        参数：
            config: 配置
            text: 待分类文本

        返回：
            分类结果
        """
        categories = config.get("categories", [])
        custom_prompt = config.get("classification_prompt")

        # 构建分类提示词
        if custom_prompt:
            prompt = render_template(custom_prompt, {"text": text})
        else:
            categories_desc = "\n".join(
                [
                    f"- {c['id']}: {c.get('name', '')} - {c.get('description', '')}"
                    for c in categories
                ]
            )
            prompt = f"""请对以下文本进行分类。

文本: {text}

可用类别:
{categories_desc}

请以JSON格式返回结果:
{{"category": "类别ID", "confidence": 0.0-1.0的置信度, "reasoning": "分类理由"}}
"""

        response = await self.llm.generate(prompt)
        result = json.loads(response)

        return {
            "category": result.get("category"),
            "confidence": result.get("confidence", 0),
            "reasoning": result.get("reasoning", ""),
        }

    async def _llm_multi_classify(self, config: dict[str, Any], text: str) -> dict[str, Any]:
        """LLM多标签分类

        参数：
            config: 配置
            text: 待分类文本

        返回：
            分类结果（多个类别）
        """
        categories = config.get("categories", [])

        categories_desc = "\n".join([f"- {c['id']}: {c.get('name', '')}" for c in categories])

        prompt = f"""请对以下文本进行多标签分类，文本可能属于多个类别。

文本: {text}

可用类别:
{categories_desc}

请以JSON格式返回结果:
{{"categories": [{{"id": "类别ID", "confidence": 0.0-1.0}}]}}
"""

        response = await self.llm.generate(prompt)
        result = json.loads(response)

        return {"categories": result.get("categories", [])}

    async def _rule_classify(self, config: dict[str, Any], text: str) -> dict[str, Any]:
        """规则分类

        参数：
            config: 配置
            text: 待分类文本

        返回：
            分类结果
        """
        categories = config.get("categories", [])
        text_lower = text.lower()

        for category in categories:
            rules = category.get("rules", {})
            keywords = rules.get("keywords", [])

            # 检查关键词匹配
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return {
                        "category": category["id"],
                        "confidence": 1.0,
                        "matched_keyword": keyword,
                    }

        # 没有匹配
        return {"category": None, "confidence": 0}


class MCPExecutor:
    """MCP协议执行器

    调用MCP服务器的工具。

    使用示例：
        executor = MCPExecutor(mcp_client=my_client)
        result = await executor.execute(config, inputs)
    """

    def __init__(self, mcp_client: MCPClientProtocol):
        """初始化

        参数：
            mcp_client: MCP客户端
        """
        self.mcp_client = mcp_client

    async def execute(self, config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        """执行MCP工具调用

        参数：
            config: 配置
            inputs: 输入数据

        返回：
            工具执行结果
        """
        server_name = config.get("server_name", "")
        tool_name = config.get("tool_name", "")
        parameters = config.get("parameters", {})
        timeout_seconds = config.get("timeout_seconds", 60)

        # 渲染参数模板
        rendered_params = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                rendered_params[key] = render_template(value, inputs)
            else:
                rendered_params[key] = value

        try:
            # 带超时的调用
            result = await asyncio.wait_for(
                self.mcp_client.call_tool(
                    server=server_name, tool=tool_name, arguments=rendered_params
                ),
                timeout=timeout_seconds,
            )

            # 确保返回包含success字段
            if "success" not in result:
                result["success"] = True

            return result

        except TimeoutError:
            logger.error(f"MCP调用超时: {server_name}/{tool_name}")
            return {"success": False, "error": f"Timeout after {timeout_seconds} seconds"}
        except Exception as e:
            logger.error(f"MCP调用失败: {e}")
            return {"success": False, "error": str(e)}


class AINodeFactory:
    """AI节点工厂

    创建各种AI节点执行器实例。
    """

    @staticmethod
    def create(
        executor_type: str,
        retriever: RetrieverProtocol | None = None,
        reranker: RerankerProtocol | None = None,
        llm_client: LLMClientProtocol | None = None,
        mcp_client: MCPClientProtocol | None = None,
        **kwargs,
    ):
        """创建AI节点执行器

        参数：
            executor_type: 执行器类型（knowledge, classify, mcp）
            retriever: 检索器（知识库需要）
            reranker: 重排序器（可选）
            llm_client: LLM客户端（分类需要）
            mcp_client: MCP客户端（MCP需要）

        返回：
            执行器实例

        异常：
            ValueError: 未知的执行器类型
        """
        if executor_type == "knowledge":
            if not retriever:
                raise ValueError("知识库执行器需要retriever")
            return KnowledgeExecutor(retriever=retriever, reranker=reranker)

        elif executor_type == "classify":
            return ClassifyExecutor(llm_client=llm_client)

        elif executor_type == "mcp":
            if not mcp_client:
                raise ValueError("MCP执行器需要mcp_client")
            return MCPExecutor(mcp_client=mcp_client)

        else:
            raise ValueError(f"未知的AI节点执行器类型: {executor_type}")


# 导出
__all__ = [
    "KnowledgeExecutor",
    "ClassifyExecutor",
    "MCPExecutor",
    "AINodeFactory",
    "RetrieverProtocol",
    "RerankerProtocol",
    "LLMClientProtocol",
    "MCPClientProtocol",
    "render_template",
]
