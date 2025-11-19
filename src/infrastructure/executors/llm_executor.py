"""LLM Executor（LLM 执行器）

Infrastructure 层：实现 LLM 文本生成节点执行器
"""

import json
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class LlmExecutor(NodeExecutor):
    """LLM 文本生成节点执行器
    
    支持 OpenAI、Anthropic、Google 等模型
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 LLM 节点
        
        配置参数：
            model: 模型名称（如 openai/gpt-4）
            temperature: 温度参数
            maxTokens: 最大 token 数
            prompt: 提示词（可选，如果未提供则从输入获取）
            structuredOutput: 是否使用结构化输出
            schema: 结构化输出的 schema
        """
        # 获取配置
        model = node.config.get("model", "openai/gpt-4")
        temperature = node.config.get("temperature", 0.7)
        max_tokens = node.config.get("maxTokens", 2000)
        prompt = node.config.get("prompt", "")
        structured_output = node.config.get("structuredOutput", False)
        schema_str = node.config.get("schema", "")

        # 如果没有配置 prompt，从输入获取
        if not prompt and inputs:
            first_key = next(iter(inputs))
            prompt = str(inputs[first_key])

        if not prompt:
            raise DomainError("LLM 节点缺少 prompt")

        # 解析模型提供商
        if "/" in model:
            provider, model_name = model.split("/", 1)
        else:
            provider = "openai"
            model_name = model

        # 调用对应的 LLM API
        try:
            if provider == "openai":
                return await self._call_openai(model_name, prompt, temperature, max_tokens, structured_output, schema_str)
            elif provider == "anthropic":
                return await self._call_anthropic(model_name, prompt, temperature, max_tokens)
            elif provider == "google":
                return await self._call_google(model_name, prompt, temperature, max_tokens)
            else:
                raise DomainError(f"不支持的 LLM 提供商: {provider}")
        except Exception as e:
            raise DomainError(f"LLM 调用失败: {str(e)}")

    async def _call_openai(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        structured_output: bool,
        schema_str: str,
    ) -> Any:
        """调用 OpenAI API"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise DomainError("未安装 openai 库，请运行: pip install openai")

        client = AsyncOpenAI(api_key=self.api_key)

        # 构建请求参数
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # 如果使用结构化输出
        if structured_output and schema_str:
            try:
                schema = json.loads(schema_str)
                kwargs["response_format"] = {"type": "json_schema", "json_schema": schema}
            except json.JSONDecodeError:
                raise DomainError(f"LLM 节点 schema 格式错误: {schema_str}")

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content

        # 如果是结构化输出，尝试解析 JSON
        if structured_output and content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content

        return content

    async def _call_anthropic(self, model: str, prompt: str, temperature: float, max_tokens: int) -> str:
        """调用 Anthropic API"""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise DomainError("未安装 anthropic 库，请运行: pip install anthropic")

        client = AsyncAnthropic(api_key=self.api_key)

        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    async def _call_google(self, model: str, prompt: str, temperature: float, max_tokens: int) -> str:
        """调用 Google Gemini API"""
        # TODO: 实现 Google Gemini API 调用
        raise DomainError("Google Gemini API 暂未实现")

