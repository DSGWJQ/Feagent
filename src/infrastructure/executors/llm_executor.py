"""LLM Executor（LLM 执行器）

Infrastructure 层：实现 LLM 文本生成节点执行器
"""

import json
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor
from src.infrastructure.executors.deterministic_mode import is_deterministic_mode


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
            maxTokens/max_tokens: 最大 token 数
            prompt/user_prompt: 提示词（可选，如果未提供则从输入获取）
            system_prompt: 系统提示词（可选）
            promptSourceNodeId: 当存在多个输入时，指定使用哪个上游节点输出作为 prompt
            structuredOutput: 是否使用结构化输出
            schema: 结构化输出的 schema
        """
        # 获取配置（支持多种命名约定）
        model = node.config.get("model", "openai/gpt-4")
        temperature = node.config.get("temperature", 0.7)
        max_tokens = node.config.get("maxTokens") or node.config.get("max_tokens", 2000)
        prompt = node.config.get("prompt", "") or node.config.get("user_prompt", "")
        system_prompt = node.config.get("system_prompt", "")
        prompt_source = node.config.get("promptSourceNodeId", "") or node.config.get(
            "promptSource", ""
        )
        structured_output = node.config.get("structuredOutput", False)
        schema_str = node.config.get("schema", "")

        # 如果没有配置 prompt，从输入获取（输入 key 为 source_node_id）
        if not prompt:
            if prompt_source:
                # 显式指定了输入源
                if prompt_source not in inputs:
                    available = ", ".join(sorted(inputs.keys()))
                    raise DomainError(
                        f"LLM 节点 promptSourceNodeId 指向的输入不存在: {prompt_source}；"
                        f"可用输入源: [{available}]"
                    )
                prompt = str(inputs[prompt_source])
            else:
                # 未指定输入源，根据输入数量处理
                if not inputs:
                    raise DomainError("LLM 节点缺少 prompt")
                if len(inputs) == 1:
                    # 单输入：直接使用（保持现有行为）
                    prompt = str(next(iter(inputs.values())))
                else:
                    # 多输入：要求明确指定来源
                    available = ", ".join(sorted(inputs.keys()))
                    raise DomainError(
                        f"LLM 节点 prompt 来源不明确：存在多个输入源 [{available}]；"
                        f"请配置 promptSourceNodeId 或使用 Prompt 节点合并输入"
                    )

        if not prompt:
            raise DomainError("LLM 节点缺少 prompt")

        # Deterministic E2E mode: never hit external LLM APIs.
        # Keep output stable and traceable for Playwright runs and local debugging.
        if is_deterministic_mode():
            preview = prompt[:280]
            if structured_output:
                return {
                    "stub": True,
                    "mode": "deterministic",
                    "model": model,
                    "prompt_preview": preview,
                    "report": f"[deterministic stub] {preview}",
                }
            return f"[deterministic stub:{model}] {preview}"

        # 解析模型提供商
        if "/" in model:
            provider, model_name = model.split("/", 1)
        else:
            provider = "openai"
            model_name = model

        # 调用对应的 LLM API
        try:
            if provider == "openai":
                return await self._call_openai(
                    model_name,
                    prompt,
                    temperature,
                    max_tokens,
                    structured_output,
                    schema_str,
                    system_prompt,
                )
            elif provider == "anthropic":
                return await self._call_anthropic(
                    model_name, prompt, temperature, max_tokens, system_prompt
                )
            elif provider == "google":
                return await self._call_google(model_name, prompt, temperature, max_tokens)
            else:
                raise DomainError(f"不支持的 LLM 提供商: {provider}")
        except Exception as e:
            raise DomainError(f"LLM 调用失败: {str(e)}") from e

    async def _call_openai(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        structured_output: bool,
        schema_str: str,
        system_prompt: str = "",
    ) -> Any:
        """调用 OpenAI API"""
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise DomainError("未安装 openai 库，请运行: pip install openai") from e

        client = AsyncOpenAI(api_key=self.api_key)

        # 构建消息列表（支持 system_prompt）
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 构建请求参数
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # 如果使用结构化输出
        if structured_output and schema_str:
            try:
                schema = json.loads(schema_str)
                kwargs["response_format"] = {"type": "json_schema", "json_schema": schema}
            except json.JSONDecodeError as e:
                raise DomainError(f"LLM 节点 schema 格式错误: {schema_str}") from e

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content

        # 如果是结构化输出，尝试解析 JSON
        if structured_output and content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content

        return content

    async def _call_anthropic(
        self, model: str, prompt: str, temperature: float, max_tokens: int, system_prompt: str = ""
    ) -> str:
        """调用 Anthropic API"""
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise DomainError("未安装 anthropic 库，请运行: pip install anthropic") from e

        client = AsyncAnthropic(api_key=self.api_key)

        # 构建请求参数（Anthropic 的 system 是单独参数）
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)
        return response.content[0].text

    async def _call_google(
        self, model: str, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """调用 Google Gemini API"""
        # TODO: 实现 Google Gemini API 调用
        raise DomainError("Google Gemini API 暂未实现")
