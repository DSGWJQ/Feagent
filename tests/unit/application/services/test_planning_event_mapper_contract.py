"""契约测试：PlanningEventMapper 初始事件（workflow_id 注入）

目的：
- 固化 SSE 的“早期可用 workflow_id”约束：router 可在第一条事件中提供 metadata.workflow_id
- 保持向后兼容：未提供 metadata 时不输出 metadata 字段
"""

from unittest.mock import MagicMock

from src.application.services.planning_event_mapper import PlanningEventMapper


class TestPlanningEventMapperContract:
    def test_create_initial_event_includes_metadata_when_provided(self) -> None:
        mapper = PlanningEventMapper(workflow_mapper=MagicMock())

        event = mapper.create_initial_event(
            "AI is analyzing the request.",
            metadata={"workflow_id": "wf_123"},
        )

        assert event.metadata == {"workflow_id": "wf_123"}
        assert event.to_sse_dict()["metadata"]["workflow_id"] == "wf_123"

    def test_create_initial_event_omits_metadata_when_not_provided(self) -> None:
        mapper = PlanningEventMapper(workflow_mapper=MagicMock())

        event = mapper.create_initial_event()

        assert event.metadata == {}
        assert "metadata" not in event.to_sse_dict()
