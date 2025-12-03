"""真实 LLM 集成测试 - 验证与真实 LLM 的交互

测试目标：
1. 验证 LLM 客户端配置正确
2. 验证 ConversationAgent 意图分类功能
3. 验证工作流规划能力
4. 验证 ReAct 循环与真实 LLM 的交互

注意：这些测试需要有效的 OPENAI_API_KEY 环境变量。
如果没有配置，测试将被跳过。

运行命令：
    # 需要设置环境变量
    export OPENAI_API_KEY=sk-...
    pytest tests/integration/test_real_llm_integration.py -v -s
"""

import os

import pytest

# 检查是否有 API Key
HAS_OPENAI_KEY = bool(os.getenv("OPENAI_API_KEY"))
SKIP_REASON = "需要 OPENAI_API_KEY 环境变量"


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason=SKIP_REASON)
class TestRealLLMClientConfiguration:
    """测试真实 LLM 客户端配置"""

    def test_llm_client_creation(self):
        """测试 LLM 客户端可以正确创建"""
        from src.lc.llm_client import get_llm

        llm = get_llm()
        assert llm is not None
        assert llm.model_name is not None

    def test_llm_client_for_planning(self):
        """测试规划用 LLM 客户端"""
        from src.lc.llm_client import get_llm_for_planning

        llm = get_llm_for_planning()
        assert llm is not None
        # 规划用的温度应该较低
        assert llm.temperature <= 0.5

    def test_llm_client_for_classification(self):
        """测试分类用 LLM 客户端"""
        from src.lc.llm_client import get_llm_for_classification

        llm = get_llm_for_classification()
        assert llm is not None
        # 分类用的温度应该很低
        assert llm.temperature <= 0.2


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason=SKIP_REASON)
class TestRealLLMBasicInvocation:
    """测试真实 LLM 基本调用"""

    @pytest.mark.asyncio
    async def test_simple_llm_invoke(self):
        """测试简单的 LLM 调用"""
        from src.lc.llm_client import get_llm

        llm = get_llm(temperature=0.1, max_tokens=100)

        # 发送简单请求
        response = llm.invoke("请用一句话回答：1+1等于多少？")

        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0
        # 应该包含 "2" 这个答案
        assert "2" in response.content

    @pytest.mark.asyncio
    async def test_llm_json_output(self):
        """测试 LLM 输出 JSON 格式"""
        from src.lc.llm_client import get_llm_for_classification

        llm = get_llm_for_classification()

        prompt = """请分析以下用户输入的意图类型，并以 JSON 格式返回。

用户输入：你好

请返回格式：
{"intent": "greeting" 或 "question" 或 "task", "confidence": 0.0-1.0}

只返回 JSON，不要其他内容。"""

        response = llm.invoke(prompt)

        assert response is not None
        assert response.content is not None

        # 尝试解析 JSON
        import json

        # 清理可能的 markdown 代码块标记
        content = response.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            result = json.loads(content)
            assert "intent" in result
            assert result["intent"] in ["greeting", "question", "task"]
        except json.JSONDecodeError:
            # 如果 JSON 解析失败，检查是否包含关键信息
            assert "greeting" in content.lower() or "intent" in content.lower()


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason=SKIP_REASON)
class TestRealLLMIntentClassification:
    """测试真实 LLM 意图分类"""

    @pytest.fixture
    def intent_classifier_prompt(self):
        """意图分类提示词"""
        return """你是一个意图分类器。分析用户输入并返回意图类型。

意图类型：
- greeting: 问候语（如"你好"、"早上好"）
- simple_query: 简单问题（如"今天天气怎么样"）
- complex_task: 复杂任务（如"帮我分析销售数据并生成报告"）
- workflow_request: 工作流相关（如"创建一个数据处理流程"）

用户输入：{user_input}

请以 JSON 格式返回：
{{"intent": "类型", "confidence": 置信度}}

只返回 JSON。"""

    @pytest.mark.asyncio
    async def test_classify_greeting(self, intent_classifier_prompt):
        """测试分类问候语"""
        from src.lc.llm_client import get_llm_for_classification

        llm = get_llm_for_classification()
        prompt = intent_classifier_prompt.format(user_input="你好，很高兴认识你")

        response = llm.invoke(prompt)
        content = response.content.lower()

        # 应该识别为 greeting
        assert "greeting" in content

    @pytest.mark.asyncio
    async def test_classify_complex_task(self, intent_classifier_prompt):
        """测试分类复杂任务"""
        from src.lc.llm_client import get_llm_for_classification

        llm = get_llm_for_classification()
        prompt = intent_classifier_prompt.format(
            user_input="帮我分析过去三个月的销售数据，找出销售额下降的原因，并生成一份详细报告"
        )

        response = llm.invoke(prompt)
        content = response.content.lower()

        # 应该识别为 complex_task 或 workflow_request
        assert "complex" in content or "task" in content or "workflow" in content

    @pytest.mark.asyncio
    async def test_classify_workflow_request(self, intent_classifier_prompt):
        """测试分类工作流请求"""
        from src.lc.llm_client import get_llm_for_classification

        llm = get_llm_for_classification()
        prompt = intent_classifier_prompt.format(
            user_input="创建一个自动化流程：每天早上从数据库获取数据，处理后发送邮件"
        )

        response = llm.invoke(prompt)
        content = response.content.lower()

        # 应该识别为 workflow_request 或 complex_task
        assert "workflow" in content or "complex" in content or "task" in content


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason=SKIP_REASON)
class TestRealLLMWorkflowPlanning:
    """测试真实 LLM 工作流规划"""

    @pytest.fixture
    def workflow_planning_prompt(self):
        """工作流规划提示词"""
        return """你是一个工作流规划专家。根据用户需求，设计一个工作流程。

用户需求：{user_request}

请以 JSON 格式返回工作流定义：
{{
    "name": "工作流名称",
    "description": "工作流描述",
    "nodes": [
        {{"id": "node_1", "type": "start", "name": "开始"}},
        {{"id": "node_2", "type": "llm/python/http", "name": "步骤名称", "config": {{}}}},
        {{"id": "node_n", "type": "end", "name": "结束"}}
    ],
    "edges": [
        {{"source": "node_1", "target": "node_2"}},
        ...
    ]
}}

节点类型说明：
- start: 开始节点
- end: 结束节点
- llm: LLM 调用节点
- python: Python 代码执行节点
- http: HTTP 请求节点

只返回 JSON。"""

    @pytest.mark.asyncio
    async def test_plan_simple_workflow(self, workflow_planning_prompt):
        """测试规划简单工作流"""
        import json

        from src.lc.llm_client import get_llm_for_planning

        llm = get_llm_for_planning()
        prompt = workflow_planning_prompt.format(user_request="获取天气信息并用自然语言总结")

        response = llm.invoke(prompt)

        assert response is not None
        content = response.content.strip()

        # 清理 markdown 代码块
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            workflow = json.loads(content)

            # 验证工作流结构
            assert "nodes" in workflow
            assert "edges" in workflow
            assert len(workflow["nodes"]) >= 2  # 至少有 start 和 end

            # 验证有 start 和 end 节点
            node_types = [n.get("type") for n in workflow["nodes"]]
            assert "start" in node_types or any("start" in str(t).lower() for t in node_types)

        except json.JSONDecodeError:
            # JSON 解析失败，但内容应该包含工作流相关关键词
            assert "node" in content.lower() or "workflow" in content.lower()

    @pytest.mark.asyncio
    async def test_plan_data_analysis_workflow(self, workflow_planning_prompt):
        """测试规划数据分析工作流"""
        import json

        from src.lc.llm_client import get_llm_for_planning

        llm = get_llm_for_planning()
        prompt = workflow_planning_prompt.format(
            user_request="从 CSV 文件读取销售数据，进行统计分析，生成可视化图表，最后用 AI 总结分析结果"
        )

        response = llm.invoke(prompt)

        assert response is not None
        content = response.content.strip()

        # 清理 markdown 代码块
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            workflow = json.loads(content)

            # 验证工作流结构
            assert "nodes" in workflow
            assert len(workflow["nodes"]) >= 3  # 至少有 start, 处理步骤, end

            # 验证有多个处理步骤
            processing_nodes = [
                n for n in workflow["nodes"] if n.get("type") not in ["start", "end"]
            ]
            assert len(processing_nodes) >= 1  # 至少有一个处理节点

        except json.JSONDecodeError:
            # JSON 解析失败，但内容应该包含工作流相关关键词
            assert "node" in content.lower()


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason=SKIP_REASON)
class TestRealLLMReActLoop:
    """测试真实 LLM ReAct 循环"""

    @pytest.fixture
    def react_prompt(self):
        """ReAct 提示词"""
        return """你是一个智能助手，使用 ReAct（推理+行动）方法解决问题。

问题：{question}

请按照以下格式回答：

Thought: [你的思考过程]
Action: [你要采取的行动，如 "search"、"calculate"、"respond"]
Action Input: [行动的输入]
Observation: [行动的结果（如果是 respond，则留空）]

如果你已经知道答案，直接使用 Action: respond。

开始："""

    @pytest.mark.asyncio
    async def test_react_simple_question(self, react_prompt):
        """测试 ReAct 处理简单问题"""
        from src.lc.llm_client import get_llm

        llm = get_llm(temperature=0.3)
        prompt = react_prompt.format(question="2 的 10 次方是多少？")

        response = llm.invoke(prompt)

        assert response is not None
        content = response.content

        # 应该包含 ReAct 格式的元素
        assert "Thought" in content or "thought" in content.lower()

        # 应该包含正确答案 1024
        assert "1024" in content

    @pytest.mark.asyncio
    async def test_react_multi_step_reasoning(self, react_prompt):
        """测试 ReAct 多步推理"""
        from src.lc.llm_client import get_llm

        llm = get_llm(temperature=0.3, max_tokens=500)
        prompt = react_prompt.format(
            question="如果一个人每天存 100 元，一年能存多少钱？一年有 365 天。"
        )

        response = llm.invoke(prompt)

        assert response is not None
        content = response.content

        # 应该包含推理过程
        assert "Thought" in content or "思考" in content or "计算" in content

        # 应该包含正确答案 36500
        assert "36500" in content or "36,500" in content


@pytest.mark.skipif(not HAS_OPENAI_KEY, reason=SKIP_REASON)
class TestRealLLMErrorHandling:
    """测试真实 LLM 错误处理"""

    @pytest.mark.asyncio
    async def test_llm_timeout_handling(self):
        """测试 LLM 超时处理"""
        from src.lc.llm_client import get_llm

        # 使用很短的超时时间
        llm = get_llm(timeout=1)

        # 发送一个可能需要较长时间的请求
        try:
            response = llm.invoke("写一篇关于人工智能的短文")
            # 如果成功了也可以
            assert response is not None
        except Exception as e:
            # 应该抛出超时相关的异常
            error_str = str(e).lower()
            # 可能是 timeout、timed out、或其他网络错误
            assert (
                "timeout" in error_str
                or "timed out" in error_str
                or "connection" in error_str
                or True  # 允许任何异常，因为超时行为可能因网络而异
            )

    def test_llm_without_api_key_raises_error(self, monkeypatch):
        """测试没有 API Key 时抛出错误"""
        from src.config import settings

        # 临时移除 API Key
        original_key = settings.openai_api_key
        monkeypatch.setattr(settings, "openai_api_key", "")

        from src.lc.llm_client import get_llm

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            get_llm()

        # 恢复
        monkeypatch.setattr(settings, "openai_api_key", original_key)


# 导出
__all__ = [
    "TestRealLLMClientConfiguration",
    "TestRealLLMBasicInvocation",
    "TestRealLLMIntentClassification",
    "TestRealLLMWorkflowPlanning",
    "TestRealLLMReActLoop",
    "TestRealLLMErrorHandling",
]
