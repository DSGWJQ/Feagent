"""
Coordinator Runbook - Step 10

运维手册与回归测试模块，提供：
1. 模板更新操作 (TemplateUpdateOperation)
2. 版本切换操作 (VersionSwitchOperation)
3. A/B 测试操作 (ABTestOperation)
4. 上下文调试操作 (ContextDebugOperation)
5. 操作记录器 (OperationRecorder)
6. 异常案例管理器 (ExceptionCaseManager)
7. 协调者 Runbook (CoordinatorRunbook)
"""

import difflib
import random
import statistics
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# ==================== Enums ====================


class OperationType(str, Enum):
    """操作类型枚举"""

    TEMPLATE_UPDATE = "template_update"
    VERSION_SWITCH = "version_switch"
    AB_TEST = "ab_test"
    CONTEXT_DEBUG = "context_debug"


class OperationStatus(str, Enum):
    """操作状态枚举"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RollbackStrategy(str, Enum):
    """回滚策略枚举"""

    IMMEDIATE = "immediate"
    GRADUAL = "gradual"
    MANUAL = "manual"


class ABTestStrategy(str, Enum):
    """A/B 测试策略枚举"""

    RANDOM = "random"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    USER_SEGMENT = "user_segment"


class DebugLevel(str, Enum):
    """调试级别枚举"""

    BASIC = "basic"
    DETAILED = "detailed"
    VERBOSE = "verbose"
    TRACE = "trace"


# ==================== Data Classes ====================


@dataclass
class OperationRecord:
    """操作记录数据类"""

    record_id: str
    operation_type: OperationType
    operator: str
    description: str
    status: OperationStatus
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateChange:
    """模板变更数据类"""

    template_id: str
    module_name: str
    old_content: str
    new_content: str
    change_reason: str
    created_at: datetime = field(default_factory=datetime.now)

    def get_diff(self) -> list[str]:
        """获取内容差异"""
        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"{self.module_name} (old)",
                tofile=f"{self.module_name} (new)",
            )
        )
        return diff


@dataclass
class ValidationResult:
    """验证结果数据类"""

    is_valid: bool
    missing_variables: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class VersionSwitch:
    """版本切换数据类"""

    switch_id: str
    from_version: str
    to_version: str
    affected_modules: list[str]
    rollback_strategy: RollbackStrategy
    rollback_conditions: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RolloutStage:
    """发布阶段数据类"""

    stage_id: str
    percentage: float
    duration_minutes: int
    validation_checks: list[str] = field(default_factory=list)


@dataclass
class ABTestConfig:
    """A/B 测试配置数据类"""

    test_id: str
    name: str
    variant_a: dict[str, Any]
    variant_b: dict[str, Any]
    strategy: ABTestStrategy
    traffic_split: float
    weights: dict[str, float] = field(default_factory=dict)
    start_time: datetime | None = None
    end_time: datetime | None = None


@dataclass
class ABTestResult:
    """A/B 测试结果数据类"""

    test_id: str
    variant_a_metrics: dict[str, Any]
    variant_b_metrics: dict[str, Any]
    winner: str
    confidence_level: float
    concluded_at: datetime = field(default_factory=datetime.now)


@dataclass
class DebugSession:
    """调试会话数据类"""

    session_id: str
    target_session_id: str
    debug_level: DebugLevel
    breakpoints: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)


@dataclass
class DebugSnapshot:
    """调试快照数据类"""

    snapshot_id: str
    session_id: str
    checkpoint: str
    context_state: dict[str, Any]
    prompt_state: dict[str, Any]
    captured_at: datetime = field(default_factory=datetime.now)

    def compare(self, other: "DebugSnapshot") -> dict[str, Any]:
        """比较两个快照"""

        def find_diff(d1: dict, d2: dict, path: str = "") -> dict:
            diff = {}
            all_keys = set(d1.keys()) | set(d2.keys())

            for key in all_keys:
                current_path = f"{path}.{key}" if path else key
                v1 = d1.get(key)
                v2 = d2.get(key)

                if v1 != v2:
                    if isinstance(v1, dict) and isinstance(v2, dict):
                        nested_diff = find_diff(v1, v2, current_path)
                        if nested_diff:
                            diff[current_path] = nested_diff
                    else:
                        diff[current_path] = {"before": v1, "after": v2}

            return diff

        return {
            "context_state": find_diff(self.context_state, other.context_state),
            "prompt_state": find_diff(self.prompt_state, other.prompt_state),
            "checkpoint_change": {
                "from": self.checkpoint,
                "to": other.checkpoint,
            },
        }


@dataclass
class ExceptionCase:
    """异常案例数据类"""

    case_id: str
    title: str
    description: str
    symptoms: list[str]
    root_cause: str
    resolution_steps: list[str]
    prevention_measures: list[str]
    example_logs: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RunbookEntry:
    """Runbook 条目数据类"""

    entry_id: str
    title: str
    category: str
    procedure: list[str]
    estimated_duration_minutes: int
    required_permissions: list[str]
    created_at: datetime = field(default_factory=datetime.now)


# ==================== Core Classes ====================


class TemplateUpdateOperation:
    """模板更新操作类"""

    def __init__(self):
        self._changes: dict[str, TemplateChange] = {}
        self._records: dict[str, OperationRecord] = {}
        self._current_templates: dict[str, str] = {}

    def prepare_update(
        self,
        template_id: str,
        module_name: str,
        new_content: str,
        reason: str,
    ) -> TemplateChange:
        """准备模板更新"""
        old_content = self._current_templates.get(template_id, "")

        change = TemplateChange(
            template_id=template_id,
            module_name=module_name,
            old_content=old_content,
            new_content=new_content,
            change_reason=reason,
        )

        self._changes[template_id] = change
        return change

    def validate_template(
        self,
        content: str,
        required_variables: list[str],
    ) -> ValidationResult:
        """验证模板"""
        import re

        # 查找所有变量
        found_variables = set(re.findall(r"\{(\w+)\}", content))
        required_set = set(required_variables)

        missing = list(required_set - found_variables)

        return ValidationResult(
            is_valid=len(missing) == 0,
            missing_variables=missing,
            errors=[],
        )

    def execute_update(
        self,
        change: TemplateChange,
        operator: str,
    ) -> OperationRecord:
        """执行模板更新"""
        record_id = f"rec-{uuid.uuid4().hex[:8]}"

        # 更新当前模板
        self._current_templates[change.template_id] = change.new_content

        record = OperationRecord(
            record_id=record_id,
            operation_type=OperationType.TEMPLATE_UPDATE,
            operator=operator,
            description=f"Update template {change.module_name}",
            status=OperationStatus.COMPLETED,
            completed_at=datetime.now(),
            details={
                "template_id": change.template_id,
                "module_name": change.module_name,
                "change_reason": change.change_reason,
            },
            result={"success": True},
        )

        self._records[record_id] = record
        self._changes[change.template_id] = change

        return record

    def rollback(self, record_id: str, reason: str) -> OperationRecord:
        """回滚模板更新"""
        original_record = self._records.get(record_id)
        if not original_record:
            raise ValueError(f"Record {record_id} not found")

        template_id = original_record.details.get("template_id", "")
        change = self._changes.get(template_id) if template_id else None

        if change:
            # 恢复旧内容
            self._current_templates[template_id] = change.old_content

        rollback_record = OperationRecord(
            record_id=f"rollback-{uuid.uuid4().hex[:8]}",
            operation_type=OperationType.TEMPLATE_UPDATE,
            operator=original_record.operator,
            description=f"Rollback: {reason}",
            status=OperationStatus.ROLLED_BACK,
            completed_at=datetime.now(),
            details={"original_record_id": record_id},
            result={"rollback_success": True},
        )

        return rollback_record


class VersionSwitchOperation:
    """版本切换操作类"""

    def __init__(self):
        self._switches: dict[str, VersionSwitch] = {}
        self._switch_status: dict[str, OperationStatus] = {}
        self._switch_metrics: dict[str, dict[str, float]] = {}

    def plan_switch(
        self,
        from_version: str,
        to_version: str,
        modules: list[str],
        strategy: RollbackStrategy,
    ) -> VersionSwitch:
        """计划版本切换"""
        switch_id = f"sw-{uuid.uuid4().hex[:8]}"

        switch = VersionSwitch(
            switch_id=switch_id,
            from_version=from_version,
            to_version=to_version,
            affected_modules=modules,
            rollback_strategy=strategy,
        )

        self._switches[switch_id] = switch
        self._switch_status[switch_id] = OperationStatus.PENDING

        return switch

    def get_rollout_stages(self, switch: VersionSwitch) -> list[RolloutStage]:
        """获取发布阶段"""
        if switch.rollback_strategy == RollbackStrategy.IMMEDIATE:
            return [
                RolloutStage(
                    stage_id="stage-1",
                    percentage=100.0,
                    duration_minutes=0,
                    validation_checks=["basic_health"],
                )
            ]
        elif switch.rollback_strategy == RollbackStrategy.GRADUAL:
            return [
                RolloutStage(
                    stage_id="stage-1",
                    percentage=10.0,
                    duration_minutes=15,
                    validation_checks=["error_rate", "latency"],
                ),
                RolloutStage(
                    stage_id="stage-2",
                    percentage=50.0,
                    duration_minutes=30,
                    validation_checks=["error_rate", "latency", "success_rate"],
                ),
                RolloutStage(
                    stage_id="stage-3",
                    percentage=100.0,
                    duration_minutes=60,
                    validation_checks=["full_validation"],
                ),
            ]
        else:  # MANUAL
            return [
                RolloutStage(
                    stage_id="manual",
                    percentage=100.0,
                    duration_minutes=0,
                    validation_checks=["manual_approval"],
                )
            ]

    def execute_switch(
        self,
        switch: VersionSwitch,
        operator: str,
    ) -> OperationRecord:
        """执行版本切换"""
        # 保存切换配置
        self._switches[switch.switch_id] = switch
        self._switch_status[switch.switch_id] = OperationStatus.IN_PROGRESS

        # 模拟执行切换
        record_id = f"rec-{uuid.uuid4().hex[:8]}"

        self._switch_status[switch.switch_id] = OperationStatus.COMPLETED
        self._switch_metrics[switch.switch_id] = {"error_rate": 0.0, "latency_ms": 100}

        return OperationRecord(
            record_id=record_id,
            operation_type=OperationType.VERSION_SWITCH,
            operator=operator,
            description=f"Switch from {switch.from_version} to {switch.to_version}",
            status=OperationStatus.COMPLETED,
            completed_at=datetime.now(),
            details={
                "switch_id": switch.switch_id,
                "from_version": switch.from_version,
                "to_version": switch.to_version,
            },
            result={"success": True},
        )

    def report_metrics(
        self,
        switch_id: str,
        error_rate: float = 0.0,
        latency_ms: float = 100.0,
    ) -> None:
        """报告切换指标"""
        self._switch_metrics[switch_id] = {
            "error_rate": error_rate,
            "latency_ms": latency_ms,
        }

        # 检查回滚条件
        switch = self._switches.get(switch_id)
        if switch and switch.rollback_conditions:
            threshold = switch.rollback_conditions.get("error_rate_threshold", 1.0)
            if error_rate > threshold:
                self._switch_status[switch_id] = OperationStatus.ROLLED_BACK

    def get_switch_status(self, switch_id: str) -> OperationStatus:
        """获取切换状态"""
        return self._switch_status.get(switch_id, OperationStatus.PENDING)


class ABTestOperation:
    """A/B 测试操作类"""

    def __init__(self):
        self._tests: dict[str, ABTestConfig] = {}
        self._assignments: dict[str, dict[str, str]] = {}  # test_id -> session_id -> variant
        self._metrics: dict[str, dict[str, list[float]]] = {}  # test_id -> variant -> metrics
        self._round_robin_counter: dict[str, int] = {}

    def create_test(
        self,
        name: str,
        variant_a: dict[str, Any],
        variant_b: dict[str, Any],
        strategy: ABTestStrategy,
        traffic_split: float,
        weights: dict[str, float] | None = None,
    ) -> ABTestConfig:
        """创建 A/B 测试"""
        test_id = f"ab-{uuid.uuid4().hex[:8]}"

        config = ABTestConfig(
            test_id=test_id,
            name=name,
            variant_a=variant_a,
            variant_b=variant_b,
            strategy=strategy,
            traffic_split=traffic_split,
            weights=weights or {},
        )

        self._tests[test_id] = config
        return config

    def start_test(self, config: ABTestConfig) -> None:
        """启动 A/B 测试"""
        self._tests[config.test_id] = config
        config.start_time = datetime.now()
        self._assignments[config.test_id] = {}
        self._metrics[config.test_id] = {"a": [], "b": []}
        self._round_robin_counter[config.test_id] = 0

    def assign_variant(self, test_id: str, session_id: str) -> str:
        """分配变体"""
        config = self._tests.get(test_id)
        if not config:
            raise ValueError(f"Test {test_id} not found")

        # 检查是否已分配
        if test_id in self._assignments and session_id in self._assignments[test_id]:
            return self._assignments[test_id][session_id]

        # 根据策略分配
        if config.strategy == ABTestStrategy.RANDOM:
            variant = "a" if random.random() > config.traffic_split else "b"
        elif config.strategy == ABTestStrategy.ROUND_ROBIN:
            count = self._round_robin_counter.get(test_id, 0)
            variant = "a" if count % 2 == 0 else "b"
            self._round_robin_counter[test_id] = count + 1
        elif config.strategy == ABTestStrategy.WEIGHTED:
            weight_a = config.weights.get("a", 0.5)
            variant = "a" if random.random() < weight_a else "b"
        else:
            variant = "a" if random.random() > config.traffic_split else "b"

        if test_id not in self._assignments:
            self._assignments[test_id] = {}
        self._assignments[test_id][session_id] = variant

        return variant

    def record_metric(
        self,
        test_id: str,
        variant: str,
        metric_name: str,
        value: float,
    ) -> None:
        """记录指标"""
        if test_id not in self._metrics:
            self._metrics[test_id] = {"a": [], "b": []}

        self._metrics[test_id][variant].append(value)

    def get_metrics(self, test_id: str) -> dict[str, list[float]]:
        """获取指标"""
        return self._metrics.get(test_id, {"a": [], "b": []})

    def conclude_test(self, test_id: str) -> ABTestResult:
        """结束 A/B 测试"""
        config = self._tests.get(test_id)
        metrics = self._metrics.get(test_id, {"a": [], "b": []})

        # 计算统计数据
        def calc_stats(values: list[float]) -> dict[str, Any]:
            if not values:
                return {"count": 0, "mean": 0, "std": 0}
            return {
                "count": len(values),
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0,
            }

        stats_a = calc_stats(metrics["a"])
        stats_b = calc_stats(metrics["b"])

        # 确定获胜者
        if stats_a["count"] < 10 or stats_b["count"] < 10:
            winner = "inconclusive"
            confidence = 0.0
        elif stats_b["mean"] > stats_a["mean"]:
            winner = "b"
            confidence = 0.95
        elif stats_a["mean"] > stats_b["mean"]:
            winner = "a"
            confidence = 0.95
        else:
            winner = "inconclusive"
            confidence = 0.5

        if config:
            config.end_time = datetime.now()

        return ABTestResult(
            test_id=test_id,
            variant_a_metrics={
                "requests": stats_a["count"],
                "success_rate": stats_a["mean"],
                "std": stats_a["std"],
            },
            variant_b_metrics={
                "requests": stats_b["count"],
                "success_rate": stats_b["mean"],
                "std": stats_b["std"],
            },
            winner=winner,
            confidence_level=confidence,
        )


class ContextDebugOperation:
    """上下文调试操作类"""

    def __init__(self):
        self._sessions: dict[str, DebugSession] = {}
        self._snapshots: dict[str, list[DebugSnapshot]] = {}
        self._context_data: dict[str, dict[str, Any]] = {}
        self._traces: dict[str, list[dict[str, Any]]] = {}

    def start_session(
        self,
        target_session_id: str,
        debug_level: DebugLevel,
        breakpoints: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> DebugSession:
        """启动调试会话"""
        session_id = f"debug-{uuid.uuid4().hex[:8]}"

        session = DebugSession(
            session_id=session_id,
            target_session_id=target_session_id,
            debug_level=debug_level,
            breakpoints=breakpoints or [],
            filters=filters or {},
        )

        self._sessions[session_id] = session
        self._snapshots[session_id] = []
        self._traces[session_id] = []

        return session

    def capture_snapshot(
        self,
        session_id: str,
        checkpoint: str,
        context_state: dict[str, Any],
        prompt_state: dict[str, Any],
    ) -> DebugSnapshot:
        """捕获快照"""
        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"

        snapshot = DebugSnapshot(
            snapshot_id=snapshot_id,
            session_id=session_id,
            checkpoint=checkpoint,
            context_state=deepcopy(context_state),
            prompt_state=deepcopy(prompt_state),
        )

        if session_id not in self._snapshots:
            self._snapshots[session_id] = []
        self._snapshots[session_id].append(snapshot)

        return snapshot

    def set_context_data(
        self,
        session_id: str,
        data: dict[str, Any],
    ) -> None:
        """设置上下文数据"""
        self._context_data[session_id] = deepcopy(data)

    def inspect_context(self, session_id: str) -> dict[str, Any]:
        """检查上下文"""
        return self._context_data.get(session_id, {})

    def add_trace_event(
        self,
        session_id: str,
        event: str,
        data: dict[str, Any],
    ) -> None:
        """添加追踪事件"""
        if session_id not in self._traces:
            self._traces[session_id] = []

        self._traces[session_id].append(
            {
                "event": event,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_trace(self, session_id: str) -> list[dict[str, Any]]:
        """获取追踪记录"""
        return self._traces.get(session_id, [])

    def end_session(self, session_id: str) -> dict[str, Any]:
        """结束调试会话"""
        session = self._sessions.get(session_id)
        snapshots = self._snapshots.get(session_id, [])
        traces = self._traces.get(session_id, [])

        duration = datetime.now() - session.started_at if session else timedelta(0)

        return {
            "session_id": session_id,
            "target_session_id": session.target_session_id if session else None,
            "debug_level": session.debug_level.value if session else None,
            "duration": duration.total_seconds(),
            "snapshots_count": len(snapshots),
            "trace_events_count": len(traces),
            "ended_at": datetime.now().isoformat(),
        }


class OperationRecorder:
    """操作记录器类"""

    def __init__(self):
        self._records: list[OperationRecord] = []

    def record(
        self,
        operation_type: OperationType,
        operator: str,
        description: str,
        details: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> OperationRecord:
        """记录操作"""
        record = OperationRecord(
            record_id=f"rec-{uuid.uuid4().hex[:8]}",
            operation_type=operation_type,
            operator=operator,
            description=description,
            status=OperationStatus.COMPLETED,
            details=details or {},
            result=result or {},
        )

        self._records.append(record)
        return record

    def query(
        self,
        operation_type: OperationType | None = None,
        operator: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[OperationRecord]:
        """查询记录"""
        results = self._records.copy()

        if operation_type:
            results = [r for r in results if r.operation_type == operation_type]

        if operator:
            results = [r for r in results if r.operator == operator]

        if start_date:
            results = [r for r in results if r.created_at >= start_date]

        if end_date:
            results = [r for r in results if r.created_at <= end_date]

        return results

    def get_recent(self, limit: int = 10) -> list[OperationRecord]:
        """获取最近记录"""
        sorted_records = sorted(self._records, key=lambda r: r.created_at, reverse=True)
        return sorted_records[:limit]

    def generate_daily_report(self, date: datetime | None = None) -> dict[str, Any]:
        """生成日报"""
        target_date = date or datetime.now()

        # 筛选当天记录
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_records = [r for r in self._records if day_start <= r.created_at < day_end]

        # 按类型统计
        by_type: dict[str, int] = {}
        for record in day_records:
            type_name = record.operation_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        # 按操作者统计
        by_operator: dict[str, int] = {}
        for record in day_records:
            by_operator[record.operator] = by_operator.get(record.operator, 0) + 1

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "total_operations": len(day_records),
            "by_type": by_type,
            "by_operator": by_operator,
            "records": day_records,
        }


class ExceptionCaseManager:
    """异常案例管理器类"""

    def __init__(self):
        self._cases: dict[str, ExceptionCase] = {}

    def add_case(
        self,
        title: str,
        description: str,
        symptoms: list[str],
        root_cause: str,
        resolution_steps: list[str],
        prevention_measures: list[str],
        example_logs: list[dict[str, Any]] | None = None,
    ) -> ExceptionCase:
        """添加异常案例"""
        case_id = f"exc-{uuid.uuid4().hex[:8]}"

        case = ExceptionCase(
            case_id=case_id,
            title=title,
            description=description,
            symptoms=symptoms,
            root_cause=root_cause,
            resolution_steps=resolution_steps,
            prevention_measures=prevention_measures,
            example_logs=example_logs or [],
        )

        self._cases[case_id] = case
        return case

    def search_by_symptom(self, keyword: str) -> list[ExceptionCase]:
        """按症状搜索案例"""
        results = []
        keyword_lower = keyword.lower()

        for case in self._cases.values():
            for symptom in case.symptoms:
                if keyword_lower in symptom.lower():
                    results.append(case)
                    break

        return results

    def get_resolution_guide(self, case_id: str) -> dict[str, Any]:
        """获取解决指南"""
        case = self._cases.get(case_id)
        if not case:
            return {}

        return {
            "case_id": case.case_id,
            "title": case.title,
            "description": case.description,
            "root_cause": case.root_cause,
            "steps": case.resolution_steps,
            "prevention": case.prevention_measures,
        }

    def get_all_cases(self) -> list[ExceptionCase]:
        """获取所有案例"""
        return list(self._cases.values())


class CoordinatorRunbook:
    """协调者 Runbook 类"""

    def __init__(self):
        self._entries: dict[str, RunbookEntry] = {}
        self._execution_logs: list[dict[str, Any]] = []

    def add_entry(
        self,
        title: str,
        category: str,
        procedure: list[str],
        estimated_duration_minutes: int,
        required_permissions: list[str],
    ) -> RunbookEntry:
        """添加 Runbook 条目"""
        entry_id = f"rb-{uuid.uuid4().hex[:8]}"

        entry = RunbookEntry(
            entry_id=entry_id,
            title=title,
            category=category,
            procedure=procedure,
            estimated_duration_minutes=estimated_duration_minutes,
            required_permissions=required_permissions,
        )

        self._entries[entry_id] = entry
        return entry

    def get_entries_by_category(self, category: str) -> list[RunbookEntry]:
        """按类别获取条目"""
        return [e for e in self._entries.values() if e.category == category]

    def execute_procedure(
        self,
        entry_id: str,
        operator: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行操作流程"""
        entry = self._entries.get(entry_id)
        if not entry:
            return {"status": "failed", "error": "Entry not found"}

        start_time = datetime.now()
        steps_completed = []

        # 模拟执行步骤
        for i, step in enumerate(entry.procedure):
            steps_completed.append(
                {
                    "step_number": i + 1,
                    "step": step,
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        execution_log = {
            "entry_id": entry_id,
            "title": entry.title,
            "operator": operator,
            "parameters": parameters or {},
            "status": "completed",
            "steps_completed": steps_completed,
            "started_at": start_time.isoformat(),
            "ended_at": end_time.isoformat(),
            "duration_seconds": duration,
        }

        self._execution_logs.append(execution_log)

        return execution_log

    def generate_document(self) -> str:
        """生成 Runbook 文档"""
        lines = [
            "# Coordinator Runbook",
            "",
            "## Table of Contents",
            "",
        ]

        # 按类别分组
        categories: dict[str, list[RunbookEntry]] = {}
        for entry in self._entries.values():
            if entry.category not in categories:
                categories[entry.category] = []
            categories[entry.category].append(entry)

        # 生成目录
        for category in sorted(categories.keys()):
            lines.append(f"- [{category.title()}](#{category})")

        lines.append("")

        # 生成各节内容
        for category in sorted(categories.keys()):
            lines.append(f"## {category.title()}")
            lines.append("")

            for entry in categories[category]:
                lines.append(f"### {entry.title}")
                lines.append("")
                lines.append(f"**Estimated Duration:** {entry.estimated_duration_minutes} minutes")
                lines.append("")
                lines.append(f"**Required Permissions:** {', '.join(entry.required_permissions)}")
                lines.append("")
                lines.append("**Procedure:**")
                for i, step in enumerate(entry.procedure, 1):
                    lines.append(f"{i}. {step}")
                lines.append("")

        return "\n".join(lines)

    def get_all_entries(self) -> list[RunbookEntry]:
        """获取所有条目"""
        return list(self._entries.values())
