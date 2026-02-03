"""Deterministic chat-create templates (test-only).

This module provides stable workflow graphs for Playwright deterministic E2E:
- No external network calls
- Minimal side effects (only when required by the scenario)
- SaveValidator-friendly configs (fail-closed contract alignment)

Rationale:
Routes should not grow ad-hoc graph builders; keep templates centralized and reusable.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError, DomainValidationError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position

TemplateId = Literal[
    "cleaning",
    "http_file_write",
    "db_write_notify",
    "conditional_branch_ab",
    "loop_range_squares",
    "transform_field_mapping",
    "report_pipeline_readback",
    "embedding_to_file_readback",
    "scaffold_min_project",
    "file_list_read_delete",
    "prompt_text_model_file_readback",
    "image_generation_stub",
    "audio_stub",
    "file_append_readback",
    "scaffold_parametrized_project",
    "scaffold_conditional_kind",
    "tool_echo",
    "reject_non_sqlite_db",
    "reject_non_openai_model",
    "reject_cycle_graph",
    "reject_tool_missing_id",
    "reject_structured_missing_schema",
    "reject_structured_invalid_schema_json",
    "reject_notification_missing_url",
    "reject_notification_missing_webhook_url",
    "reject_notification_missing_smtp_host",
    "reject_loop_downstream_iteration",
    "structured_output_ticket",
]


def detect_template(message: str) -> TemplateId | None:
    """Detect a deterministic template by message content.

    Notes:
    - This is only enabled when ENABLE_TEST_SEED_API is true (gated by caller).
    - Prefer explicit task codes (S-01..S-10) to avoid false positives.
    """

    if not isinstance(message, str):
        return None

    text = message.strip()
    if not text:
        return None

    lower = text.lower()

    # Explicit, test-friendly markers first.
    if _has_task_code(text, "S-01"):
        return "http_file_write"
    if _has_task_code(text, "S-02"):
        return "report_pipeline_readback"
    if _has_task_code(text, "S-03"):
        return "db_write_notify"
    if _has_task_code(text, "S-04"):
        return "conditional_branch_ab"
    if _has_task_code(text, "S-05"):
        return "loop_range_squares"
    if _has_task_code(text, "S-06"):
        return "transform_field_mapping"
    if _has_task_code(text, "S-07"):
        return "file_list_read_delete"
    if _has_task_code(text, "S-08"):
        return "structured_output_ticket"
    if _has_task_code(text, "S-09"):
        return "embedding_to_file_readback"
    if _has_task_code(text, "S-10"):
        return "scaffold_min_project"
    if _has_task_code(text, "S-11"):
        return "prompt_text_model_file_readback"
    if _has_task_code(text, "S-12"):
        return "image_generation_stub"
    if _has_task_code(text, "S-13"):
        return "audio_stub"
    if _has_task_code(text, "S-14"):
        return "file_append_readback"
    if _has_task_code(text, "S-15"):
        return "scaffold_parametrized_project"
    if _has_task_code(text, "S-16"):
        return "scaffold_conditional_kind"
    if _has_task_code(text, "S-17"):
        return "tool_echo"
    if _has_task_code(text, "R-01"):
        return "reject_non_sqlite_db"
    if _has_task_code(text, "R-02"):
        return "reject_non_openai_model"
    if _has_task_code(text, "R-03"):
        return "reject_cycle_graph"
    if _has_task_code(text, "R-04"):
        return "reject_tool_missing_id"
    if _has_task_code(text, "R-05"):
        return "reject_structured_missing_schema"
    if _has_task_code(text, "R-06"):
        return "reject_notification_missing_url"
    if _has_task_code(text, "R-07"):
        return "reject_loop_downstream_iteration"
    if _has_task_code(text, "R-08"):
        return "reject_structured_invalid_schema_json"
    if _has_task_code(text, "R-09"):
        return "reject_notification_missing_webhook_url"
    if _has_task_code(text, "R-10"):
        return "reject_notification_missing_smtp_host"

    # Back-compat with existing deterministic cleaning shortcut.
    if "数据清洗" in text or "data cleaning" in lower or "cleaning" in lower:
        return "cleaning"
    if (
        ("去重" in text or "dedup" in lower)
        and ("去空" in text or "null" in lower or "empty" in lower)
        and ("类型" in text or "convert" in lower or "cast" in lower)
    ):
        return "cleaning"

    return None


def workflow_name_for_template(template: TemplateId) -> str:
    return {
        "cleaning": "数据清洗工作流",
        "http_file_write": "HTTP 写文件工作流",
        "db_write_notify": "SQLite 写入通知工作流",
        "conditional_branch_ab": "条件分支工作流",
        "loop_range_squares": "循环生成列表工作流",
        "transform_field_mapping": "字段映射工作流",
        "report_pipeline_readback": "报告流水线工作流",
        "embedding_to_file_readback": "向量化写文件工作流",
        "scaffold_min_project": "项目骨架生成工作流",
        "file_list_read_delete": "文件读写删除工作流",
        "prompt_text_model_file_readback": "Prompt + 文本模型写文件工作流",
        "image_generation_stub": "图像生成工作流",
        "audio_stub": "音频生成工作流",
        "file_append_readback": "文件追加读回工作流",
        "scaffold_parametrized_project": "参数化项目骨架工作流",
        "scaffold_conditional_kind": "条件分支项目骨架工作流",
        "tool_echo": "工具回显工作流",
        "reject_non_sqlite_db": "无效工作流（非 sqlite）",
        "reject_non_openai_model": "无效工作流（非 OpenAI 模型）",
        "reject_cycle_graph": "无效工作流（有环）",
        "reject_tool_missing_id": "无效工作流（缺 tool_id）",
        "reject_structured_missing_schema": "无效工作流（缺 schema）",
        "reject_structured_invalid_schema_json": "无效工作流（schema 非法 JSON）",
        "reject_notification_missing_url": "无效工作流（通知缺 url）",
        "reject_notification_missing_webhook_url": "无效工作流（Slack 通知缺 webhook_url）",
        "reject_notification_missing_smtp_host": "无效工作流（邮件通知缺 smtp_host）",
        "reject_loop_downstream_iteration": "无效工作流（不可表达的循环语义）",
        "structured_output_ticket": "结构化抽取工作流",
    }[template]


def apply_template(*, workflow: Workflow, template: TemplateId) -> None:
    """Mutate the base workflow into the requested deterministic template."""

    start_node = next((n for n in workflow.nodes if n.type == NodeType.START), None)
    end_node = next((n for n in workflow.nodes if n.type == NodeType.END), None)
    if start_node is None or end_node is None:
        raise DomainError("base workflow missing start/end node")

    # Reset edges; keep start/end nodes.
    for edge in list(workflow.edges):
        workflow.remove_edge(edge.id)

    if template == "cleaning":
        _apply_cleaning(workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id)
        return

    if template == "http_file_write":
        _apply_http_file_write(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "db_write_notify":
        _apply_db_write_notify(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "conditional_branch_ab":
        _apply_conditional_branch_ab(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "loop_range_squares":
        _apply_loop_range_squares(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "transform_field_mapping":
        _apply_transform_field_mapping(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "report_pipeline_readback":
        _apply_report_pipeline_readback(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "structured_output_ticket":
        _apply_structured_output_ticket(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "embedding_to_file_readback":
        _apply_embedding_to_file_readback(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "scaffold_min_project":
        _apply_scaffold_min_project(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "file_list_read_delete":
        _apply_file_list_read_delete(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "prompt_text_model_file_readback":
        _apply_prompt_text_model_file_readback(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "image_generation_stub":
        _apply_image_generation_stub(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "audio_stub":
        _apply_audio_stub(workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id)
        return

    if template == "file_append_readback":
        _apply_file_append_readback(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "scaffold_parametrized_project":
        _apply_scaffold_parametrized_project(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "scaffold_conditional_kind":
        _apply_scaffold_conditional_kind(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "tool_echo":
        _apply_tool_echo(workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id)
        return

    if template == "reject_non_sqlite_db":
        _apply_reject_non_sqlite_db(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_non_openai_model":
        _apply_reject_non_openai_model(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_cycle_graph":
        _apply_reject_cycle_graph(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_tool_missing_id":
        _apply_reject_tool_missing_id(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_structured_missing_schema":
        _apply_reject_structured_missing_schema(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_structured_invalid_schema_json":
        _apply_reject_structured_invalid_schema_json(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_notification_missing_url":
        _apply_reject_notification_missing_url(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_notification_missing_webhook_url":
        _apply_reject_notification_missing_webhook_url(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_notification_missing_smtp_host":
        _apply_reject_notification_missing_smtp_host(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    if template == "reject_loop_downstream_iteration":
        _apply_reject_loop_downstream_iteration(
            workflow=workflow, start_node_id=start_node.id, end_node_id=end_node.id
        )
        return

    raise DomainError(f"unsupported deterministic template: {template}")


def _has_task_code(text: str, code: str) -> bool:
    # Accept: "S-01 ..." / "[S-01] ..." / "（S-01）"
    pattern = rf"(?<![A-Za-z0-9]){re.escape(code)}(?![A-Za-z0-9])"
    return re.search(pattern, text) is not None


def _extract_tool_id_from_prompt(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    match = re.search(r"(?i)(?<![A-Za-z0-9])tool_id\s*=\s*(tool_[A-Za-z0-9]+)", text)
    if not match:
        return None
    return match.group(1)


def _apply_cleaning(*, workflow: Workflow, start_node_id: str, end_node_id: str) -> None:
    cleaning_code = """
 # NOTE: PythonExecutor runs with a restricted __builtins__ (no isinstance/Exception/repr).
 # Keep this snippet limited to SAFE_BUILTINS + basic object methods.

payload = input1
rows = payload.get("data") if payload.__class__ is dict else payload
if rows.__class__ is not list:
    rows = []

def _to_number_or_str(value: str):
    s = value.strip()
    if s == "":
        return None
    if s.isdigit():
        return int(s)
    if s.count(".") == 1:
        parts = s.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return float(s)
    return s

cleaned = []
seen = set()

for row in rows:
    if row is None:
        continue
    if row.__class__ is not dict:
        continue

    normalized = {}
    for key, val in row.items():
        if val is None:
            continue
        if val.__class__ is str:
            converted = _to_number_or_str(val)
            if converted is None:
                continue
            normalized[key] = converted
        else:
            normalized[key] = val

    if len(normalized) == 0:
        continue

    dedup_key = tuple(sorted((str(k), str(normalized[k])) for k in normalized.keys()))
    if dedup_key in seen:
        continue
    seen.add(dedup_key)
    cleaned.append(normalized)

result = {"data": cleaned}
""".strip("\n")

    cleaning_node = Node.create(
        type=NodeType.PYTHON,
        name="数据清洗",
        config={"code": cleaning_code},
        position=Position(x=225, y=100),
    )
    workflow.add_node(cleaning_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=cleaning_node.id))
    workflow.add_edge(Edge.create(source_node_id=cleaning_node.id, target_node_id=end_node_id))


def _apply_http_file_write(*, workflow: Workflow, start_node_id: str, end_node_id: str) -> None:
    http_node = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="HTTP(mock)",
        config={
            "url": "https://example.test/api/orders",
            "method": "GET",
            "headers": {},
            # Deterministic mode uses mock_response to avoid external network.
            "mock_response": {"status": 200, "data": {"ok": True, "items": [{"id": "o-1"}]}},
        },
        position=Position(x=225, y=100),
    )
    file_node = Node.create(
        type=NodeType.FILE,
        name="写文件",
        config={
            "operation": "write",
            "path": f"tmp/e2e/http_file_{workflow.id}.txt",
            "encoding": "utf-8",
            # Use template rendering; the engine will JSON-encode objects.
            "content": "output: {input1}",
        },
        position=Position(x=425, y=100),
    )

    workflow.add_node(http_node)
    workflow.add_node(file_node)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=http_node.id))
    workflow.add_edge(Edge.create(source_node_id=http_node.id, target_node_id=file_node.id))
    workflow.add_edge(Edge.create(source_node_id=file_node.id, target_node_id=end_node_id))


def _apply_db_write_notify(*, workflow: Workflow, start_node_id: str, end_node_id: str) -> None:
    database_url = f"sqlite:///tmp/e2e/s03_{workflow.id}.db"

    create_node = Node.create(
        type=NodeType.DATABASE,
        name="建表",
        config={
            "database_url": database_url,
            "sql": "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)",
            "params": {},
        },
        position=Position(x=225, y=100),
    )
    insert_node = Node.create(
        type=NodeType.DATABASE,
        name="写入",
        config={
            "database_url": database_url,
            "sql": "INSERT INTO events (name) VALUES ('ok')",
            "params": {},
        },
        position=Position(x=425, y=100),
    )
    conditional_node = Node.create(
        type=NodeType.CONDITIONAL,
        name="是否写入成功",
        config={"condition": "input1['rows_affected'] > 0"},
        position=Position(x=625, y=100),
    )
    notification_node = Node.create(
        type=NodeType.NOTIFICATION,
        name="通知(webhook)",
        config={
            "type": "webhook",
            "url": "https://example.test/webhook",
            "headers": {},
            "include_input": True,
            "subject": "Insert Done",
            "message": "insert ok",
        },
        position=Position(x=825, y=100),
    )

    workflow.add_node(create_node)
    workflow.add_node(insert_node)
    workflow.add_node(conditional_node)
    workflow.add_node(notification_node)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=create_node.id))
    workflow.add_edge(Edge.create(source_node_id=create_node.id, target_node_id=insert_node.id))
    workflow.add_edge(
        Edge.create(source_node_id=insert_node.id, target_node_id=conditional_node.id)
    )
    workflow.add_edge(
        Edge.create(
            source_node_id=conditional_node.id,
            target_node_id=notification_node.id,
            condition="true",
        )
    )
    workflow.add_edge(
        Edge.create(
            source_node_id=conditional_node.id,
            target_node_id=end_node_id,
            condition="false",
        )
    )
    workflow.add_edge(Edge.create(source_node_id=notification_node.id, target_node_id=end_node_id))


def _apply_conditional_branch_ab(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    conditional_node = Node.create(
        type=NodeType.CONDITIONAL,
        name="input == test ?",
        config={"condition": "input1 == 'test'"},
        position=Position(x=225, y=100),
    )
    node_a = Node.create(
        type=NodeType.JAVASCRIPT,
        name="分支A",
        config={"code": "result = 'A'"},
        position=Position(x=425, y=40),
    )
    node_b = Node.create(
        type=NodeType.JAVASCRIPT,
        name="分支B",
        config={"code": "result = 'B'"},
        position=Position(x=425, y=160),
    )

    workflow.add_node(conditional_node)
    workflow.add_node(node_a)
    workflow.add_node(node_b)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=conditional_node.id))
    workflow.add_edge(
        Edge.create(
            source_node_id=conditional_node.id,
            target_node_id=node_a.id,
            condition="true",
        )
    )
    workflow.add_edge(
        Edge.create(
            source_node_id=conditional_node.id,
            target_node_id=node_b.id,
            condition="false",
        )
    )
    workflow.add_edge(Edge.create(source_node_id=node_a.id, target_node_id=end_node_id))
    workflow.add_edge(Edge.create(source_node_id=node_b.id, target_node_id=end_node_id))


def _apply_loop_range_squares(*, workflow: Workflow, start_node_id: str, end_node_id: str) -> None:
    loop_node = Node.create(
        type=NodeType.LOOP,
        name="range loop",
        config={
            "type": "range",
            "start": 0,
            "end": 5,  # 0..4
            "step": 1,
            "code": "result = {'i': i, 'square': i*i}",
        },
        position=Position(x=225, y=100),
    )
    workflow.add_node(loop_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=loop_node.id))
    workflow.add_edge(Edge.create(source_node_id=loop_node.id, target_node_id=end_node_id))


def _apply_transform_field_mapping(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    transform_node = Node.create(
        type=NodeType.TRANSFORM,
        name="字段映射",
        config={
            "type": "field_mapping",
            "mapping": {
                "id": "input1.user.id",
                "name": "input1.user.profile.name",
            },
        },
        position=Position(x=225, y=100),
    )
    workflow.add_node(transform_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=transform_node.id))
    workflow.add_edge(Edge.create(source_node_id=transform_node.id, target_node_id=end_node_id))


def _apply_report_pipeline_readback(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    # KISS: use a constant SELECT (no fixture setup) so the test is stable and offline.
    database_url = f"sqlite:///tmp/e2e/s02_{workflow.id}.db"

    db_node = Node.create(
        type=NodeType.DATABASE,
        name="查询销售数据",
        config={
            "database_url": database_url,
            "sql": "SELECT 10 as amount UNION ALL SELECT 20 as amount UNION ALL SELECT 30 as amount",
            "params": {},
        },
        position=Position(x=225, y=100),
    )
    wrap_rows = Node.create(
        type=NodeType.TRANSFORM,
        name="包装rows",
        config={"type": "field_mapping", "mapping": {"rows": "input1"}},
        position=Position(x=425, y=100),
    )
    aggregate = Node.create(
        type=NodeType.TRANSFORM,
        name="聚合",
        config={
            "type": "aggregation",
            "field": "rows",
            "operations": ["count", "sum:amount", "avg:amount"],
        },
        position=Position(x=625, y=100),
    )
    write_report = Node.create(
        type=NodeType.FILE,
        name="写报告",
        config={
            "operation": "write",
            "path": f"tmp/e2e/report_{workflow.id}.json",
            "encoding": "utf-8",
            # Keep content parseable as JSON for UI assertions.
            "content": "{input1}",
        },
        position=Position(x=825, y=100),
    )
    read_report = Node.create(
        type=NodeType.FILE,
        name="读报告",
        config={
            "operation": "read",
            "path": "{input1.path}",
            "encoding": "utf-8",
        },
        position=Position(x=1025, y=100),
    )

    workflow.add_node(db_node)
    workflow.add_node(wrap_rows)
    workflow.add_node(aggregate)
    workflow.add_node(write_report)
    workflow.add_node(read_report)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=db_node.id))
    workflow.add_edge(Edge.create(source_node_id=db_node.id, target_node_id=wrap_rows.id))
    workflow.add_edge(Edge.create(source_node_id=wrap_rows.id, target_node_id=aggregate.id))
    workflow.add_edge(Edge.create(source_node_id=aggregate.id, target_node_id=write_report.id))
    workflow.add_edge(Edge.create(source_node_id=write_report.id, target_node_id=read_report.id))
    workflow.add_edge(Edge.create(source_node_id=read_report.id, target_node_id=end_node_id))


def _apply_embedding_to_file_readback(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    embed_node = Node.create(
        type=NodeType.EMBEDDING,
        name="向量化",
        config={
            "model": "openai/text-embedding-3-small",
            "dimensions": 3,
            "input": "FAQ text",
        },
        position=Position(x=225, y=100),
    )
    write_node = Node.create(
        type=NodeType.FILE,
        name="写向量文件",
        config={
            "operation": "write",
            "path": f"tmp/e2e/embedding_{workflow.id}.json",
            "encoding": "utf-8",
            "content": "{input1}",
        },
        position=Position(x=425, y=100),
    )
    read_node = Node.create(
        type=NodeType.FILE,
        name="读向量文件",
        config={"operation": "read", "path": "{input1.path}", "encoding": "utf-8"},
        position=Position(x=625, y=100),
    )

    workflow.add_node(embed_node)
    workflow.add_node(write_node)
    workflow.add_node(read_node)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=embed_node.id))
    workflow.add_edge(Edge.create(source_node_id=embed_node.id, target_node_id=write_node.id))
    workflow.add_edge(Edge.create(source_node_id=write_node.id, target_node_id=read_node.id))
    workflow.add_edge(Edge.create(source_node_id=read_node.id, target_node_id=end_node_id))


def _apply_scaffold_min_project(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    base_dir = f"tmp/scaffold_{workflow.id}"

    write_readme = Node.create(
        type=NodeType.FILE,
        name="写README",
        config={
            "operation": "write",
            "path": f"{base_dir}/README.md",
            "encoding": "utf-8",
            "content": "# Scaffold\n\nGenerated by deterministic chat-create.\n",
        },
        position=Position(x=225, y=80),
    )
    write_main = Node.create(
        type=NodeType.FILE,
        name="写main.py",
        config={
            "operation": "write",
            "path": f"{base_dir}/main.py",
            "encoding": "utf-8",
            "content": "print('hello')\n",
        },
        position=Position(x=425, y=80),
    )
    list_dir = Node.create(
        type=NodeType.FILE,
        name="列目录",
        config={"operation": "list", "path": base_dir},
        position=Position(x=625, y=80),
    )

    workflow.add_node(write_readme)
    workflow.add_node(write_main)
    workflow.add_node(list_dir)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=write_readme.id))
    workflow.add_edge(Edge.create(source_node_id=write_readme.id, target_node_id=write_main.id))
    workflow.add_edge(Edge.create(source_node_id=write_main.id, target_node_id=list_dir.id))
    workflow.add_edge(Edge.create(source_node_id=list_dir.id, target_node_id=end_node_id))


def _apply_scaffold_parametrized_project(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Generate a small project skeleton using template-rendered paths and content.

    This demonstrates the project-generation boundary: we can create files and folders, but we
    cannot run commands (no dependency installation, no `pip/npm` execution).
    """

    base_dir = f"tmp/scaffold_{workflow.id}"
    # Use `initial_input` placeholders so template rendering doesn't depend on the immediate
    # upstream node output (file->file chaining would otherwise break).
    project_dir = f"{base_dir}/{{initial_input.project.name}}"

    write_readme = Node.create(
        type=NodeType.FILE,
        name="写README(参数化)",
        config={
            "operation": "write",
            "path": f"{project_dir}/README.md",
            "encoding": "utf-8",
            "content": "# {initial_input.project.name}\n\nGenerated by workflow.\n",
        },
        position=Position(x=225, y=80),
    )
    write_main = Node.create(
        type=NodeType.FILE,
        name="写main.py(参数化)",
        config={
            "operation": "write",
            "path": f"{project_dir}/main.py",
            "encoding": "utf-8",
            "content": "print('hello {initial_input.project.name}')\n",
        },
        position=Position(x=425, y=80),
    )
    list_dir = Node.create(
        type=NodeType.FILE,
        name="列目录",
        config={"operation": "list", "path": project_dir},
        position=Position(x=625, y=80),
    )
    read_readme = Node.create(
        type=NodeType.FILE,
        name="读README",
        config={"operation": "read", "path": f"{project_dir}/README.md", "encoding": "utf-8"},
        position=Position(x=825, y=80),
    )
    combine = Node.create(
        type=NodeType.TRANSFORM,
        name="汇总输出",
        config={
            "type": "field_mapping",
            # input1=list_dir output, input2=read_readme output
            "mapping": {
                "project_dir": "input1.path",
                "files": "input1.items",
                "readme": "input2.content",
            },
        },
        position=Position(x=1025, y=80),
    )

    workflow.add_node(write_readme)
    workflow.add_node(write_main)
    workflow.add_node(list_dir)
    workflow.add_node(read_readme)
    workflow.add_node(combine)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=write_readme.id))
    workflow.add_edge(Edge.create(source_node_id=write_readme.id, target_node_id=write_main.id))
    workflow.add_edge(Edge.create(source_node_id=write_main.id, target_node_id=list_dir.id))
    workflow.add_edge(Edge.create(source_node_id=list_dir.id, target_node_id=read_readme.id))
    workflow.add_edge(Edge.create(source_node_id=list_dir.id, target_node_id=combine.id))
    workflow.add_edge(Edge.create(source_node_id=read_readme.id, target_node_id=combine.id))
    workflow.add_edge(Edge.create(source_node_id=combine.id, target_node_id=end_node_id))


def _apply_scaffold_conditional_kind(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Generate different scaffolds based on input.kind (cli vs lib) using conditional gating."""

    base_dir = f"tmp/scaffold_{workflow.id}_s16"

    conditional = Node.create(
        type=NodeType.CONDITIONAL,
        name="kind == cli ?",
        config={"condition": "input1.get('kind') == 'cli'"},
        position=Position(x=225, y=80),
    )
    write_cli = Node.create(
        type=NodeType.FILE,
        name="写CLI入口",
        config={
            "operation": "write",
            "path": f"{base_dir}/main.py",
            "encoding": "utf-8",
            "content": "print('cli')\n",
        },
        position=Position(x=425, y=40),
    )
    write_lib = Node.create(
        type=NodeType.FILE,
        name="写库入口",
        config={
            "operation": "write",
            "path": f"{base_dir}/__init__.py",
            "encoding": "utf-8",
            "content": "__all__ = []\n",
        },
        position=Position(x=425, y=140),
    )
    list_dir_cli = Node.create(
        type=NodeType.FILE,
        name="列目录(CLI)",
        config={"operation": "list", "path": base_dir},
        position=Position(x=625, y=40),
    )
    list_dir_lib = Node.create(
        type=NodeType.FILE,
        name="列目录(LIB)",
        config={"operation": "list", "path": base_dir},
        position=Position(x=625, y=140),
    )

    workflow.add_node(conditional)
    workflow.add_node(write_cli)
    workflow.add_node(write_lib)
    workflow.add_node(list_dir_cli)
    workflow.add_node(list_dir_lib)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=conditional.id))
    workflow.add_edge(
        Edge.create(
            source_node_id=conditional.id,
            target_node_id=write_cli.id,
            condition="true",
        )
    )
    workflow.add_edge(
        Edge.create(
            source_node_id=conditional.id,
            target_node_id=write_lib.id,
            condition="false",
        )
    )
    workflow.add_edge(Edge.create(source_node_id=write_cli.id, target_node_id=list_dir_cli.id))
    workflow.add_edge(Edge.create(source_node_id=write_lib.id, target_node_id=list_dir_lib.id))
    workflow.add_edge(Edge.create(source_node_id=list_dir_cli.id, target_node_id=end_node_id))
    workflow.add_edge(Edge.create(source_node_id=list_dir_lib.id, target_node_id=end_node_id))


def _apply_tool_echo(*, workflow: Workflow, start_node_id: str, end_node_id: str) -> None:
    tool_id = _extract_tool_id_from_prompt(workflow.description or "")
    if tool_id is None:
        # Fail-closed: deterministic templates must not guess tool_id.
        raise DomainValidationError(
            "Workflow validation failed",
            code="workflow_invalid",
            errors=[
                {
                    "code": "missing_tool_id_in_prompt",
                    "message": "tool_id is required to build a tool workflow template",
                    "path": "workflow",
                }
            ],
        )

    tool_node = Node.create(
        type=NodeType.TOOL,
        name="Tool(Echo)",
        config={
            "tool_id": tool_id,
            "params": {"message": f"tool_echo_{workflow.id}"},
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(tool_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=tool_node.id))
    workflow.add_edge(Edge.create(source_node_id=tool_node.id, target_node_id=end_node_id))


def _apply_file_list_read_delete(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    base_dir = f"tmp/e2e/s07_{workflow.id}"
    target_path = f"{base_dir}/target.txt"

    write_node = Node.create(
        type=NodeType.FILE,
        name="写文件",
        config={
            "operation": "write",
            "path": target_path,
            "encoding": "utf-8",
            "content": "hello",
        },
        position=Position(x=225, y=120),
    )
    list_before = Node.create(
        type=NodeType.FILE,
        name="列目录(前)",
        config={"operation": "list", "path": base_dir},
        position=Position(x=425, y=120),
    )
    read_node = Node.create(
        type=NodeType.FILE,
        name="读文件",
        config={"operation": "read", "path": target_path, "encoding": "utf-8"},
        position=Position(x=625, y=120),
    )
    delete_node = Node.create(
        type=NodeType.FILE,
        name="删文件",
        config={"operation": "delete", "path": target_path},
        position=Position(x=825, y=120),
    )
    list_after = Node.create(
        type=NodeType.FILE,
        name="列目录(后)",
        config={"operation": "list", "path": base_dir},
        position=Position(x=1025, y=120),
    )

    workflow.add_node(write_node)
    workflow.add_node(list_before)
    workflow.add_node(read_node)
    workflow.add_node(delete_node)
    workflow.add_node(list_after)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=write_node.id))
    workflow.add_edge(Edge.create(source_node_id=write_node.id, target_node_id=list_before.id))
    workflow.add_edge(Edge.create(source_node_id=list_before.id, target_node_id=read_node.id))
    workflow.add_edge(Edge.create(source_node_id=read_node.id, target_node_id=delete_node.id))
    workflow.add_edge(Edge.create(source_node_id=delete_node.id, target_node_id=list_after.id))
    workflow.add_edge(Edge.create(source_node_id=list_after.id, target_node_id=end_node_id))


def _apply_structured_output_ticket(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
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

    structured_node = Node.create(
        type=NodeType.STRUCTURED_OUTPUT,
        name="结构化抽取",
        config={
            # Optional but keeps model provider validation aligned with the UI contracts.
            "model": "openai/gpt-4",
            "schemaName": "Ticket",
            "schema": json.dumps(schema, ensure_ascii=False),
            "prompt": "Extract name/phone/issue/priority from the input.",
        },
        position=Position(x=225, y=100),
    )
    workflow.add_node(structured_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=structured_node.id))
    workflow.add_edge(Edge.create(source_node_id=structured_node.id, target_node_id=end_node_id))


def _apply_prompt_text_model_file_readback(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Prompt -> textModel (deterministic stub) -> write/read file (verifiable output)."""

    prompt_node = Node.create(
        type=NodeType.PROMPT,
        name="生成提示词",
        config={"content": "Write a short README intro for: {input1}"},
        position=Position(x=225, y=80),
    )
    llm_node = Node.create(
        type=NodeType.TEXT_MODEL,
        name="文本模型(det stub)",
        config={
            "model": "openai/gpt-4",
            # Intentionally omit prompt so it uses the incoming prompt node output.
        },
        position=Position(x=425, y=80),
    )
    write_node = Node.create(
        type=NodeType.FILE,
        name="写LLM输出",
        config={
            "operation": "write",
            "path": f"tmp/e2e/s11_llm_{workflow.id}.txt",
            "encoding": "utf-8",
            "content": "{input1}",
        },
        position=Position(x=625, y=80),
    )
    read_node = Node.create(
        type=NodeType.FILE,
        name="读LLM输出",
        config={"operation": "read", "path": "{input1.path}", "encoding": "utf-8"},
        position=Position(x=825, y=80),
    )

    workflow.add_node(prompt_node)
    workflow.add_node(llm_node)
    workflow.add_node(write_node)
    workflow.add_node(read_node)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=prompt_node.id))
    workflow.add_edge(Edge.create(source_node_id=prompt_node.id, target_node_id=llm_node.id))
    workflow.add_edge(Edge.create(source_node_id=llm_node.id, target_node_id=write_node.id))
    workflow.add_edge(Edge.create(source_node_id=write_node.id, target_node_id=read_node.id))
    workflow.add_edge(Edge.create(source_node_id=read_node.id, target_node_id=end_node_id))


def _apply_image_generation_stub(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """imageGeneration deterministic stub (no network)."""

    image_node = Node.create(
        type=NodeType.IMAGE,
        name="图像生成(det stub)",
        config={
            "model": "openai/dall-e-3",
            "aspectRatio": "1:1",
            "outputFormat": "png",
            # Use template rendering from start input.
            "prompt": "{input1}",
        },
        position=Position(x=225, y=100),
    )
    workflow.add_node(image_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=image_node.id))
    workflow.add_edge(Edge.create(source_node_id=image_node.id, target_node_id=end_node_id))


def _apply_audio_stub(*, workflow: Workflow, start_node_id: str, end_node_id: str) -> None:
    """audio deterministic stub (no network)."""

    audio_node = Node.create(
        type=NodeType.AUDIO,
        name="语音生成(det stub)",
        config={
            "model": "openai/tts-1",
            "voice": "alloy",
            "speed": 1.0,
            "text": "{input1}",
        },
        position=Position(x=225, y=100),
    )
    workflow.add_node(audio_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=audio_node.id))
    workflow.add_edge(Edge.create(source_node_id=audio_node.id, target_node_id=end_node_id))


def _apply_file_append_readback(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """file(write) -> file(append) -> file(read) (verifiable append semantics)."""

    path = f"tmp/e2e/s14_append_{workflow.id}.txt"

    write_node = Node.create(
        type=NodeType.FILE,
        name="写初始文件",
        # Use real newlines so the read-back content matches user expectations.
        config={"operation": "write", "path": path, "encoding": "utf-8", "content": "line1\n"},
        position=Position(x=225, y=100),
    )
    append_node = Node.create(
        type=NodeType.FILE,
        name="追加内容",
        config={"operation": "append", "path": path, "encoding": "utf-8", "content": "line2\n"},
        position=Position(x=425, y=100),
    )
    read_node = Node.create(
        type=NodeType.FILE,
        name="读文件",
        config={"operation": "read", "path": path, "encoding": "utf-8"},
        position=Position(x=625, y=100),
    )

    workflow.add_node(write_node)
    workflow.add_node(append_node)
    workflow.add_node(read_node)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=write_node.id))
    workflow.add_edge(Edge.create(source_node_id=write_node.id, target_node_id=append_node.id))
    workflow.add_edge(Edge.create(source_node_id=append_node.id, target_node_id=read_node.id))
    workflow.add_edge(Edge.create(source_node_id=read_node.id, target_node_id=end_node_id))


def _apply_reject_non_sqlite_db(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: database_url is not sqlite:/// (must be rejected at save time)."""

    db_node = Node.create(
        type=NodeType.DATABASE,
        name="DB(Postgres)",
        config={
            "database_url": "postgresql://example.test/db",
            "sql": "SELECT 1",
            "params": {},
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(db_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=db_node.id))
    workflow.add_edge(Edge.create(source_node_id=db_node.id, target_node_id=end_node_id))


def _apply_reject_non_openai_model(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: non-OpenAI model/provider (must be rejected at save time)."""

    model_node = Node.create(
        type=NodeType.TEXT_MODEL,
        name="TextModel(Anthropic)",
        config={
            "model": "anthropic/claude-3-5-sonnet",
            "prompt": "hello",
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(model_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=model_node.id))
    workflow.add_edge(Edge.create(source_node_id=model_node.id, target_node_id=end_node_id))


def _apply_reject_cycle_graph(*, workflow: Workflow, start_node_id: str, end_node_id: str) -> None:
    """Create an invalid workflow: graph contains a cycle (must be rejected at save time)."""

    js_node = Node.create(
        type=NodeType.JAVASCRIPT,
        name="Cycle Node",
        config={"code": "result = 1"},
        position=Position(x=225, y=100),
    )

    workflow.add_node(js_node)

    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=js_node.id))
    workflow.add_edge(Edge.create(source_node_id=js_node.id, target_node_id=end_node_id))
    # Introduce a back-edge to form a cycle: js -> end -> js.
    workflow.add_edge(Edge.create(source_node_id=end_node_id, target_node_id=js_node.id))


def _apply_reject_tool_missing_id(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: tool node missing config.tool_id (must be rejected at save time)."""

    tool_node = Node.create(
        type=NodeType.TOOL,
        name="Tool(Missing ID)",
        config={
            # Intentionally missing tool_id.
            "params": {},
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(tool_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=tool_node.id))
    workflow.add_edge(Edge.create(source_node_id=tool_node.id, target_node_id=end_node_id))


def _apply_reject_structured_missing_schema(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: structuredOutput node missing schema (must be rejected at save time)."""

    structured_node = Node.create(
        type=NodeType.STRUCTURED_OUTPUT,
        name="Structured(Missing Schema)",
        config={
            "model": "openai/gpt-4",
            "schemaName": "Ticket",
            # Intentionally missing `schema`.
            "prompt": "Extract fields.",
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(structured_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=structured_node.id))
    workflow.add_edge(Edge.create(source_node_id=structured_node.id, target_node_id=end_node_id))


def _apply_reject_structured_invalid_schema_json(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: structuredOutput schema is an invalid JSON string."""

    structured_node = Node.create(
        type=NodeType.STRUCTURED_OUTPUT,
        name="Structured(Invalid Schema JSON)",
        config={
            "model": "openai/gpt-4",
            "schemaName": "Ticket",
            # Intentionally invalid JSON (triggers SaveValidator invalid_json).
            "schema": "{",
            "prompt": "Extract fields.",
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(structured_node)
    workflow.add_edge(Edge.create(source_node_id=start_node_id, target_node_id=structured_node.id))
    workflow.add_edge(Edge.create(source_node_id=structured_node.id, target_node_id=end_node_id))


def _apply_reject_notification_missing_url(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: webhook notification missing url (must be rejected at save time)."""

    notification_node = Node.create(
        type=NodeType.NOTIFICATION,
        name="Notify(Webhook Missing URL)",
        config={
            "type": "webhook",
            # Intentionally missing `url`.
            "message": "done",
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(notification_node)
    workflow.add_edge(
        Edge.create(source_node_id=start_node_id, target_node_id=notification_node.id)
    )
    workflow.add_edge(Edge.create(source_node_id=notification_node.id, target_node_id=end_node_id))


def _apply_reject_notification_missing_webhook_url(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: slack notification missing webhook_url (must be rejected at save time)."""

    notification_node = Node.create(
        type=NodeType.NOTIFICATION,
        name="Notify(Slack Missing Webhook URL)",
        config={
            "type": "slack",
            # Intentionally missing `webhook_url`.
            "message": "done",
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(notification_node)
    workflow.add_edge(
        Edge.create(source_node_id=start_node_id, target_node_id=notification_node.id)
    )
    workflow.add_edge(Edge.create(source_node_id=notification_node.id, target_node_id=end_node_id))


def _apply_reject_notification_missing_smtp_host(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Create an invalid workflow: email notification missing smtp_host (must be rejected at save time)."""

    notification_node = Node.create(
        type=NodeType.NOTIFICATION,
        name="Notify(Email Missing SMTP Host)",
        config={
            "type": "email",
            "message": "done",
            # Intentionally missing `smtp_host` only (keep others present for stable assertions).
            "sender": "sender@example.com",
            "sender_password": "x",
            "recipients": ["recipient@example.com"],
        },
        position=Position(x=225, y=100),
    )

    workflow.add_node(notification_node)
    workflow.add_edge(
        Edge.create(source_node_id=start_node_id, target_node_id=notification_node.id)
    )
    workflow.add_edge(Edge.create(source_node_id=notification_node.id, target_node_id=end_node_id))


def _apply_reject_loop_downstream_iteration(
    *, workflow: Workflow, start_node_id: str, end_node_id: str
) -> None:
    """Reject a request that cannot be expressed in the current workflow graph semantics.

    R-07: "loop per item drives downstream nodes" is not representable, because `loop` is an
    executor-internal iteration and does not fan-out execution of subsequent nodes per item.

    We fail-closed at chat-create time with a structured validation error so the UI can
    deterministically assert the capability boundary.
    """

    raise DomainValidationError(
        "Workflow validation failed",
        code="workflow_invalid",
        errors=[
            {
                "code": "unsupported_semantics",
                "message": "loop cannot drive downstream nodes per item (not expressible in DAG)",
                "path": "workflow",
                "meta": {
                    "boundary": "loop_downstream_iteration",
                    "hint": "Use a batch API or move per-item calls outside the workflow; then pass aggregated input.",
                },
            }
        ],
    )
