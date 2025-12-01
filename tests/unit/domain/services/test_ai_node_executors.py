"""AI节点执行器测试

TDD测试 - 知识库/分类/MCP节点执行器

Phase 3.4.2: AI节点执行器 (Knowledge/Classify/MCP)

测试分类：
1. 知识库节点执行器测试 - KnowledgeExecutor
2. 分类节点执行器测试 - ClassifyExecutor
3. MCP节点执行器测试 - MCPExecutor
4. 真实业务场景测试 - 复杂AI工作流
"""

import json
from unittest.mock import AsyncMock

import pytest


class TestKnowledgeExecutor:
    """知识库节点执行器测试"""

    @pytest.mark.asyncio
    async def test_retrieve_from_knowledge_base(self):
        """测试：从知识库检索

        真实业务场景：
        - 用户问："公司的退货政策是什么？"
        - 系统从知识库检索相关文档
        - 返回最相关的内容

        验收标准：
        - 根据query检索知识库
        - 返回top_k个结果
        - 结果包含文档内容和相似度
        """
        from src.domain.services.ai_node_executors import KnowledgeExecutor

        # Mock知识库检索服务
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [
            {"content": "退货政策：7天无理由退货...", "score": 0.95, "doc_id": "doc_1"},
            {"content": "退货流程：1.申请退货...", "score": 0.88, "doc_id": "doc_2"},
            {"content": "退货注意事项：...", "score": 0.82, "doc_id": "doc_3"},
        ]

        executor = KnowledgeExecutor(retriever=mock_retriever)

        config = {
            "knowledge_base_id": "kb_policy",
            "query_template": "{{query}}",
            "top_k": 3,
            "similarity_threshold": 0.7,
        }

        inputs = {"query": "公司的退货政策是什么？"}

        result = await executor.execute(config, inputs)

        assert len(result["documents"]) == 3
        assert result["documents"][0]["score"] >= 0.9
        mock_retriever.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_with_template_query(self):
        """测试：模板化查询

        真实业务场景：
        - 查询模板："关于{{product}}的{{question_type}}"
        - 输入：product="iPhone", question_type="保修"
        - 生成查询："关于iPhone的保修"

        验收标准：
        - 支持Jinja2模板
        - 正确替换变量
        """
        from src.domain.services.ai_node_executors import KnowledgeExecutor

        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [
            {"content": "iPhone保修政策...", "score": 0.92, "doc_id": "doc_1"}
        ]

        executor = KnowledgeExecutor(retriever=mock_retriever)

        config = {
            "knowledge_base_id": "kb_products",
            "query_template": "关于{{product}}的{{question_type}}",
            "top_k": 5,
        }

        inputs = {"product": "iPhone", "question_type": "保修"}

        result = await executor.execute(config, inputs)

        # 验证查询被正确构建
        call_args = mock_retriever.retrieve.call_args
        assert "iPhone" in call_args[1]["query"]
        assert "保修" in call_args[1]["query"]

    @pytest.mark.asyncio
    async def test_filter_by_similarity_threshold(self):
        """测试：相似度阈值过滤

        验收标准：
        - 只返回高于阈值的结果
        """
        from src.domain.services.ai_node_executors import KnowledgeExecutor

        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [
            {"content": "相关内容", "score": 0.85, "doc_id": "doc_1"},
            {"content": "较相关内容", "score": 0.72, "doc_id": "doc_2"},
            {"content": "不太相关", "score": 0.55, "doc_id": "doc_3"},  # 低于阈值
        ]

        executor = KnowledgeExecutor(retriever=mock_retriever)

        config = {
            "knowledge_base_id": "kb_test",
            "query_template": "{{query}}",
            "top_k": 10,
            "similarity_threshold": 0.7,
        }

        result = await executor.execute(config, {"query": "测试查询"})

        # 只有2个结果高于0.7阈值
        assert len(result["documents"]) == 2

    @pytest.mark.asyncio
    async def test_rerank_results(self):
        """测试：结果重排序

        真实业务场景：
        - 初步检索后，使用更精确的模型重排序
        - 提高最终结果质量

        验收标准：
        - 支持可选的重排序
        - 重排序后顺序可能改变
        """
        from src.domain.services.ai_node_executors import KnowledgeExecutor

        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [
            {"content": "内容A", "score": 0.85, "doc_id": "doc_a"},
            {"content": "内容B", "score": 0.80, "doc_id": "doc_b"},
        ]

        mock_reranker = AsyncMock()
        mock_reranker.rerank.return_value = [
            {"content": "内容B", "score": 0.92, "doc_id": "doc_b"},  # B排到前面
            {"content": "内容A", "score": 0.88, "doc_id": "doc_a"},
        ]

        executor = KnowledgeExecutor(retriever=mock_retriever, reranker=mock_reranker)

        config = {
            "knowledge_base_id": "kb_test",
            "query_template": "{{query}}",
            "top_k": 5,
            "rerank_enabled": True,
        }

        result = await executor.execute(config, {"query": "测试"})

        # 重排序后B应该在前面
        assert result["documents"][0]["doc_id"] == "doc_b"
        mock_reranker.rerank.assert_called_once()


class TestClassifyExecutor:
    """分类节点执行器测试"""

    @pytest.mark.asyncio
    async def test_llm_classification(self):
        """测试：LLM分类

        真实业务场景：
        - 用户输入："我想退款"
        - 系统分类为："退款/售后"类别
        - 路由到对应处理流程

        验收标准：
        - 使用LLM进行分类
        - 返回分类结果和置信度
        """
        from src.domain.services.ai_node_executors import ClassifyExecutor

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {"category": "refund", "confidence": 0.92, "reasoning": "用户明确表达退款意图"}
        )

        executor = ClassifyExecutor(llm_client=mock_llm)

        config = {
            "classification_type": "llm",
            "categories": [
                {"id": "inquiry", "name": "咨询", "description": "产品咨询"},
                {"id": "refund", "name": "退款", "description": "退款相关"},
                {"id": "complaint", "name": "投诉", "description": "投诉建议"},
            ],
        }

        inputs = {"text": "我想退款，订单号123456"}

        result = await executor.execute(config, inputs)

        assert result["category"] == "refund"
        assert result["confidence"] >= 0.9

    @pytest.mark.asyncio
    async def test_rule_based_classification(self):
        """测试：规则分类

        真实业务场景：
        - 根据关键词规则快速分类
        - 不需要调用LLM，速度更快

        验收标准：
        - 支持关键词规则
        - 匹配到规则立即返回
        """
        from src.domain.services.ai_node_executors import ClassifyExecutor

        executor = ClassifyExecutor()

        config = {
            "classification_type": "rule",
            "categories": [
                {"id": "refund", "name": "退款", "rules": {"keywords": ["退款", "退钱", "退货"]}},
                {"id": "inquiry", "name": "咨询", "rules": {"keywords": ["怎么", "如何", "什么"]}},
            ],
        }

        # 测试退款关键词
        result = await executor.execute(config, {"text": "我要退款"})
        assert result["category"] == "refund"

        # 测试咨询关键词
        result = await executor.execute(config, {"text": "这个产品怎么使用"})
        assert result["category"] == "inquiry"

    @pytest.mark.asyncio
    async def test_multi_label_classification(self):
        """测试：多标签分类

        真实业务场景：
        - 一个问题可能属于多个类别
        - 如："退款后能换货吗？" -> 退款 + 换货

        验收标准：
        - 支持多标签
        - 返回多个类别及其置信度
        """
        from src.domain.services.ai_node_executors import ClassifyExecutor

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "categories": [
                    {"id": "refund", "confidence": 0.85},
                    {"id": "exchange", "confidence": 0.78},
                ]
            }
        )

        executor = ClassifyExecutor(llm_client=mock_llm)

        config = {
            "classification_type": "llm",
            "multi_label": True,
            "categories": [
                {"id": "refund", "name": "退款"},
                {"id": "exchange", "name": "换货"},
                {"id": "inquiry", "name": "咨询"},
            ],
        }

        result = await executor.execute(config, {"text": "退款后能换货吗？"})

        assert len(result["categories"]) == 2
        assert any(c["id"] == "refund" for c in result["categories"])
        assert any(c["id"] == "exchange" for c in result["categories"])

    @pytest.mark.asyncio
    async def test_classification_with_fallback(self):
        """测试：分类降级

        真实业务场景：
        - LLM分类失败时，降级到规则分类
        - 保证服务可用性

        验收标准：
        - LLM失败时自动降级
        - 返回降级标记
        """
        from src.domain.services.ai_node_executors import ClassifyExecutor

        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("LLM服务不可用")

        executor = ClassifyExecutor(llm_client=mock_llm)

        config = {
            "classification_type": "llm",
            "fallback_to_rule": True,
            "categories": [{"id": "refund", "name": "退款", "rules": {"keywords": ["退款"]}}],
        }

        result = await executor.execute(config, {"text": "我要退款"})

        assert result["category"] == "refund"
        assert result["fallback"] is True


class TestMCPExecutor:
    """MCP节点执行器测试"""

    @pytest.mark.asyncio
    async def test_call_mcp_tool(self):
        """测试：调用MCP工具

        真实业务场景：
        - 调用外部MCP服务器的工具
        - 如：调用文件系统工具读取文件

        验收标准：
        - 正确连接MCP服务器
        - 调用指定工具
        - 返回工具执行结果
        """
        from src.domain.services.ai_node_executors import MCPExecutor

        mock_mcp_client = AsyncMock()
        mock_mcp_client.call_tool.return_value = {"content": "文件内容...", "success": True}

        executor = MCPExecutor(mcp_client=mock_mcp_client)

        config = {
            "server_name": "filesystem",
            "tool_name": "read_file",
            "parameters": {"path": "/data/config.json"},
        }

        result = await executor.execute(config, {})

        assert result["success"] is True
        assert "content" in result
        mock_mcp_client.call_tool.assert_called_once_with(
            server="filesystem", tool="read_file", arguments={"path": "/data/config.json"}
        )

    @pytest.mark.asyncio
    async def test_mcp_with_dynamic_parameters(self):
        """测试：动态参数

        真实业务场景：
        - MCP工具参数来自工作流变量
        - 如：文件路径来自上一个节点的输出

        验收标准：
        - 支持从inputs获取参数
        - 支持参数模板
        """
        from src.domain.services.ai_node_executors import MCPExecutor

        mock_mcp_client = AsyncMock()
        mock_mcp_client.call_tool.return_value = {"result": "ok"}

        executor = MCPExecutor(mcp_client=mock_mcp_client)

        config = {
            "server_name": "database",
            "tool_name": "query",
            "parameters": {"sql": "SELECT * FROM users WHERE id = {{user_id}}"},
        }

        inputs = {"user_id": 123}

        result = await executor.execute(config, inputs)

        # 验证参数被正确替换
        call_args = mock_mcp_client.call_tool.call_args
        assert "123" in call_args[1]["arguments"]["sql"]

    @pytest.mark.asyncio
    async def test_mcp_timeout_handling(self):
        """测试：超时处理

        验收标准：
        - 支持超时配置
        - 超时时返回错误
        """
        import asyncio

        from src.domain.services.ai_node_executors import MCPExecutor

        mock_mcp_client = AsyncMock()

        async def slow_call(*args, **kwargs):
            await asyncio.sleep(2)
            return {"result": "ok"}

        mock_mcp_client.call_tool.side_effect = slow_call

        executor = MCPExecutor(mcp_client=mock_mcp_client)

        config = {
            "server_name": "slow_server",
            "tool_name": "slow_tool",
            "parameters": {},
            "timeout_seconds": 0.5,
        }

        result = await executor.execute(config, {})

        assert result["success"] is False
        assert "timeout" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_mcp_error_handling(self):
        """测试：错误处理

        验收标准：
        - MCP调用失败时返回错误信息
        - 不抛出异常
        """
        from src.domain.services.ai_node_executors import MCPExecutor

        mock_mcp_client = AsyncMock()
        mock_mcp_client.call_tool.side_effect = Exception("MCP服务器连接失败")

        executor = MCPExecutor(mcp_client=mock_mcp_client)

        config = {"server_name": "unavailable", "tool_name": "some_tool", "parameters": {}}

        result = await executor.execute(config, {})

        assert result["success"] is False
        assert "error" in result


class TestRealWorldScenarios:
    """真实业务场景测试"""

    @pytest.mark.asyncio
    async def test_customer_service_flow(self):
        """测试：客服工作流

        真实业务场景：
        1. 用户输入问题
        2. 分类问题类型
        3. 从知识库检索相关内容
        4. 生成回答

        验收标准：
        - 完整流程执行
        - 各节点正确协作
        """
        from src.domain.services.ai_node_executors import ClassifyExecutor, KnowledgeExecutor

        # 1. 分类
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {"category": "product_inquiry", "confidence": 0.88}
        )

        classify_executor = ClassifyExecutor(llm_client=mock_llm)

        classify_config = {
            "classification_type": "llm",
            "categories": [
                {"id": "product_inquiry", "name": "产品咨询"},
                {"id": "after_sales", "name": "售后服务"},
            ],
        }

        classify_result = await classify_executor.execute(
            classify_config, {"text": "iPhone 15的电池续航怎么样？"}
        )

        assert classify_result["category"] == "product_inquiry"

        # 2. 知识库检索
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [
            {
                "content": "iPhone 15配备3349mAh电池，视频播放可达20小时...",
                "score": 0.91,
                "doc_id": "iphone15_spec",
            }
        ]

        knowledge_executor = KnowledgeExecutor(retriever=mock_retriever)

        knowledge_config = {
            "knowledge_base_id": "kb_products",
            "query_template": "{{query}}",
            "top_k": 3,
        }

        knowledge_result = await knowledge_executor.execute(
            knowledge_config, {"query": "iPhone 15电池续航"}
        )

        assert len(knowledge_result["documents"]) >= 1
        assert "电池" in knowledge_result["documents"][0]["content"]

    @pytest.mark.asyncio
    async def test_document_qa_with_mcp(self):
        """测试：文档问答+MCP

        真实业务场景：
        1. 使用MCP工具读取文档
        2. 分析文档内容
        3. 基于文档回答问题

        验收标准：
        - MCP正确读取文档
        - 文档内容被后续节点使用
        """
        from src.domain.services.ai_node_executors import MCPExecutor

        mock_mcp_client = AsyncMock()
        mock_mcp_client.call_tool.return_value = {
            "content": "# 项目文档\n\n## 概述\n这是一个AI Agent平台...",
            "success": True,
        }

        mcp_executor = MCPExecutor(mcp_client=mock_mcp_client)

        config = {
            "server_name": "filesystem",
            "tool_name": "read_file",
            "parameters": {"path": "{{file_path}}"},
        }

        result = await mcp_executor.execute(config, {"file_path": "/docs/README.md"})

        assert result["success"] is True
        assert "AI Agent" in result["content"]

    @pytest.mark.asyncio
    async def test_intelligent_routing(self):
        """测试：智能路由

        真实业务场景：
        - 根据问题类型和紧急程度路由
        - 高优先级 + 投诉 -> 人工客服
        - 普通咨询 -> AI回答

        验收标准：
        - 多条件分类
        - 正确路由决策
        """
        from src.domain.services.ai_node_executors import ClassifyExecutor

        mock_llm = AsyncMock()

        # 第一次调用：分类问题类型
        # 第二次调用：判断优先级
        mock_llm.generate.side_effect = [
            json.dumps({"category": "complaint", "confidence": 0.9}),
            json.dumps({"category": "high", "confidence": 0.85}),
        ]

        executor = ClassifyExecutor(llm_client=mock_llm)

        # 分类问题类型
        type_result = await executor.execute(
            {
                "classification_type": "llm",
                "categories": [
                    {"id": "inquiry", "name": "咨询"},
                    {"id": "complaint", "name": "投诉"},
                ],
            },
            {"text": "你们的产品质量太差了！要投诉！"},
        )

        # 判断优先级
        priority_result = await executor.execute(
            {
                "classification_type": "llm",
                "categories": [
                    {"id": "high", "name": "高优先级"},
                    {"id": "normal", "name": "普通"},
                ],
            },
            {"text": "你们的产品质量太差了！要投诉！"},
        )

        # 路由决策
        should_route_to_human = (
            type_result["category"] == "complaint" and priority_result["category"] == "high"
        )

        assert should_route_to_human is True


class TestAINodeFactory:
    """AI节点工厂测试"""

    def test_create_knowledge_executor(self):
        """测试：创建知识库执行器"""
        from src.domain.services.ai_node_executors import AINodeFactory

        mock_retriever = AsyncMock()
        executor = AINodeFactory.create("knowledge", retriever=mock_retriever)
        assert executor is not None

    def test_create_classify_executor(self):
        """测试：创建分类执行器"""
        from src.domain.services.ai_node_executors import AINodeFactory

        executor = AINodeFactory.create("classify")
        assert executor is not None

    def test_create_mcp_executor(self):
        """测试：创建MCP执行器"""
        from src.domain.services.ai_node_executors import AINodeFactory

        mock_mcp_client = AsyncMock()
        executor = AINodeFactory.create("mcp", mcp_client=mock_mcp_client)
        assert executor is not None

    def test_invalid_executor_type(self):
        """测试：无效的执行器类型"""
        from src.domain.services.ai_node_executors import AINodeFactory

        with pytest.raises(ValueError, match="未知"):
            AINodeFactory.create("invalid")
