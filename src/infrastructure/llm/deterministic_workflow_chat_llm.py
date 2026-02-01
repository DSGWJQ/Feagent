"""Deterministic workflow chat LLM stub.

Provides a predictable, offline-safe workflow modification plan based on
simple keyword heuristics. Intended for ENABLE_TEST_SEED_API environments.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class DeterministicWorkflowChatLLM:
    """Return deterministic workflow modifications for common prompts."""

    def generate_modifications(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        message = _extract_message(user_prompt)
        node_types = _plan_node_types(message)
        if not node_types:
            node_types = ["transform"]

        suffix = _stable_suffix(message)
        nodes_to_add: list[dict[str, Any]] = []
        for idx, node_type in enumerate(node_types, start=1):
            nodes_to_add.append(
                {
                    "type": node_type,
                    "name": _node_name(node_type, idx, suffix),
                    "config": _node_config(node_type, idx, suffix),
                    "position": {"x": 220 + idx * 200, "y": 240},
                }
            )

        edges_to_add = _chain_edges(nodes_to_add)
        return {
            "intent": "add_node",
            "confidence": 0.4,
            "action": "add_node",
            "nodes_to_add": nodes_to_add,
            "nodes_to_update": [],
            "nodes_to_delete": [],
            "edges_to_add": edges_to_add,
            "edges_to_delete": [],
            "edges_to_update": [],
            "ai_message": f"已生成确定性工作流（节点数: {len(nodes_to_add)}）。",
            "react_steps": [
                {
                    "step": 1,
                    "thought": "deterministic stub plan",
                    "action": {"type": "add_node", "nodes": node_types},
                    "observation": f"prepared {len(nodes_to_add)} nodes",
                }
            ],
        }

    async def generate_modifications_async(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        return self.generate_modifications(system_prompt, user_prompt)


def _extract_message(user_prompt: str) -> str:
    if not isinstance(user_prompt, str):
        return ""
    for marker in ("用户新消息：", "用户请求："):
        if marker in user_prompt:
            return user_prompt.split(marker, 1)[1].strip()
    return user_prompt.strip()


def _stable_suffix(message: str) -> str:
    if not message:
        return "0000"
    digest = hashlib.md5(message.encode("utf-8")).hexdigest()
    return digest[:4]


def _plan_node_types(message: str) -> list[str]:
    text = message or ""
    lower = text.lower()

    if _contains_all(text, ["去重", "去空"]) or "数据清洗" in text:
        return ["database", "transform", "database"]

    if _contains_any(text, ["销售", "报告", "markdown", "报表"]):
        return ["database", "transform", "python", "textModel", "file"]

    if _contains_any(text, ["订单", "api", "接口"]) and _contains_any(text, ["入库", "同步"]):
        return ["httpRequest", "transform", "database"]

    if _contains_any(text, ["异常", "阈值", "校验", "规则"]) and "通知" in text:
        return ["python", "conditional", "notification"]

    if _contains_any(text, ["遍历", "循环", "批量"]) and _contains_any(text, ["用户", "列表"]):
        return ["database", "loop", "httpRequest", "transform"]

    if _contains_any(text, ["营销", "文案", "卖点"]) and _contains_any(
        text, ["保存", "文件", "通知"]
    ):
        return ["prompt", "textModel", "file", "notification"]

    if _contains_any(text, ["抽取", "结构化"]) or _contains_any(
        lower, ["name", "phone", "issue", "priority"]
    ):
        return ["textModel", "structuredOutput", "database"]

    if _contains_any(text, ["向量", "embedding"]):
        return ["embeddingModel", "database"]

    if _contains_any(text, ["图片", "配图", "image"]):
        return ["textModel", "imageGeneration", "file"]

    if _contains_any(text, ["语音", "音频", "tts"]):
        return ["textModel", "audio", "file"]

    if _contains_any(text, ["评分", "计算", "代码"]) or _contains_any(
        lower, ["python", "javascript"]
    ):
        return ["python", "transform", "file"]

    if _contains_any(text, ["通知", "webhook"]):
        return ["database", "notification"]

    required = _extract_required_nodes(text)
    if required:
        return required

    return []


def _extract_required_nodes(text: str) -> list[str]:
    if "要求包含" not in text:
        return []
    tail = text.split("要求包含", 1)[1]
    tokens = [t.strip() for t in re.split(r"[，,;/、\s]+", tail) if t.strip()]

    mapping = [
        ("数据库", "database"),
        ("db", "database"),
        ("http", "httpRequest"),
        ("api", "httpRequest"),
        ("transform", "transform"),
        ("数据转换", "transform"),
        ("python", "python"),
        ("javascript", "javascript"),
        ("条件", "conditional"),
        ("循环", "loop"),
        ("提示词", "prompt"),
        ("llm", "textModel"),
        ("文本模型", "textModel"),
        ("文件", "file"),
        ("通知", "notification"),
        ("向量", "embeddingModel"),
        ("embedding", "embeddingModel"),
        ("图片", "imageGeneration"),
        ("图像", "imageGeneration"),
        ("音频", "audio"),
        ("语音", "audio"),
        ("结构化", "structuredOutput"),
    ]

    ordered: list[str] = []
    for token in tokens:
        lower = token.lower()
        for key, node_type in mapping:
            if key in token or key in lower:
                if node_type not in ordered:
                    ordered.append(node_type)
    return ordered


def _contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(word in text or word in lower for word in keywords)


def _contains_all(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return all(word in text or word in lower for word in keywords)


def _node_name(node_type: str, idx: int, suffix: str) -> str:
    label = {
        "database": "数据库",
        "transform": "数据转换",
        "python": "Python",
        "javascript": "JavaScript",
        "textModel": "文本模型",
        "prompt": "提示词",
        "file": "文件",
        "httpRequest": "HTTP",
        "notification": "通知",
        "loop": "循环",
        "conditional": "条件",
        "embeddingModel": "向量",
        "imageGeneration": "图像",
        "audio": "音频",
        "structuredOutput": "结构化",
    }.get(node_type, "节点")
    return f"{label}-{idx}-{suffix}"


def _node_config(node_type: str, idx: int, suffix: str) -> dict[str, Any]:
    if node_type == "database":
        return {
            "database_url": "sqlite:///tmp/e2e/deterministic_workflow.db",
            "sql": "SELECT 1 as value",
            "params": {},
        }
    if node_type == "transform":
        return {"type": "field_mapping", "mapping": {"data": "input1"}}
    if node_type == "python":
        return {"code": "result = {'value': 1}"}
    if node_type == "javascript":
        return {"code": "result = input1"}
    if node_type == "prompt":
        return {"content": "请根据输入生成内容：{input1}"}
    if node_type == "textModel":
        return {
            "model": "openai/gpt-4o-mini",
            "temperature": 0,
            "maxTokens": 200,
            "prompt": "生成结果",
        }
    if node_type == "file":
        return {
            "operation": "write",
            "path": f"tmp/e2e/{suffix}_step{idx}.txt",
            "encoding": "utf-8",
            "content": "output: {input1}",
        }
    if node_type == "httpRequest":
        return {
            "url": "https://example.test/api",
            "method": "GET",
            "headers": {},
            "mock_response": {
                "status": 200,
                "data": {"items": [{"id": "item-1", "value": 1}]},
            },
        }
    if node_type == "notification":
        return {
            "type": "webhook",
            "url": "https://example.test/webhook",
            "headers": {},
            "include_input": True,
            "subject": "Workflow Notification",
            "message": "Workflow completed",
        }
    if node_type == "loop":
        return {"type": "range", "start": 0, "end": 1, "step": 1, "code": "result = i"}
    if node_type == "conditional":
        return {"condition": "True"}
    if node_type == "embeddingModel":
        return {"model": "openai/text-embedding-3-small", "input": "faq text"}
    if node_type == "imageGeneration":
        return {
            "model": "openai/dall-e-3",
            "prompt": "活动海报",
            "aspectRatio": "1:1",
            "outputFormat": "png",
        }
    if node_type == "audio":
        return {"model": "openai/tts-1", "text": "示例摘要", "voice": "alloy"}
    if node_type == "structuredOutput":
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "issue": {"type": "string"},
                "priority": {"type": "string"},
            },
            "required": ["name", "phone", "issue", "priority"],
        }
        return {
            "model": "openai/gpt-4o-mini",
            "schemaName": "Ticket",
            "schema": json.dumps(schema, ensure_ascii=False),
            "prompt": "Extract name/phone/issue/priority from the input.",
        }
    return {}


def _chain_edges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not nodes:
        return []
    edges = [{"source": "开始", "target": nodes[0]["name"], "condition": None}]
    for prev, cur in zip(nodes, nodes[1:], strict=False):
        edges.append({"source": prev["name"], "target": cur["name"], "condition": None})
    edges.append({"source": nodes[-1]["name"], "target": "结束", "condition": None})
    return edges
