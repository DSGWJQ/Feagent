"""监控与知识模块联动桥接器 (Monitoring-Knowledge Bridge) - Step 9

提供监控系统与知识库之间的闭环集成：

1. MonitoringKnowledgeBridge - 监控-知识桥接器（核心组件）
2. AlertKnowledgeHandler - 告警知识处理器（告警→知识条目）
3. PerformanceKnowledgeAdapter - 性能知识适配器（瓶颈→知识）
4. MetricsKnowledgeCollector - 指标知识收集器（指标→知识）

闭环流程：
    监控指标 → 告警检测 → 知识条目创建 → 策略优化 → 任务改进

用法：
    # 创建桥接器（自动注册回调）
    bridge = MonitoringKnowledgeBridge(
        knowledge_maintainer=maintainer,
        alert_manager=alert_manager,
    )

    # 处理瓶颈
    adapter = PerformanceKnowledgeAdapter(maintainer)
    adapter.process_bottleneck(bottleneck)

    # 分析指标并记录
    collector = MetricsKnowledgeCollector(maintainer, metrics_collector)
    collector.analyze_and_record_failures(threshold=5)
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from src.domain.services.dynamic_node_monitoring import (
    Alert,
    AlertManager,
    DynamicNodeMetricsCollector,
)
from src.domain.services.knowledge_maintenance import (
    FailureCategory,
    KnowledgeMaintainer,
    MemoryCategory,
)
from src.domain.services.log_analysis import Bottleneck

# ==================== 1. AlertKnowledgeHandler 告警知识处理器 ====================


class AlertKnowledgeHandler:
    """告警知识处理器

    将告警转换为知识库条目：
    - 严重告警 → FailureCase
    - 警告告警 → LongTermMemory
    """

    # 告警类型到失败类别的映射
    ALERT_TYPE_TO_FAILURE_CATEGORY: dict[str, FailureCategory] = {
        "sandbox_failure_rate": FailureCategory.LOGIC_ERROR,
        "resource_exhausted": FailureCategory.RESOURCE_EXHAUSTED,
        "execution_timeout": FailureCategory.TIMEOUT,
        "external_dependency": FailureCategory.EXTERNAL_DEPENDENCY,
        "permission_denied": FailureCategory.PERMISSION_DENIED,
        "invalid_input": FailureCategory.INVALID_INPUT,
    }

    # 告警类型对应的预防策略
    PREVENTION_STRATEGIES: dict[str, list[str]] = {
        "sandbox_failure_rate": [
            "增加错误重试机制",
            "添加输入验证",
            "实现降级方案",
            "检查沙箱资源配置",
        ],
        "resource_exhausted": [
            "增加资源配额",
            "实现资源监控",
            "优化内存使用",
            "添加资源限制告警",
        ],
        "execution_timeout": [
            "增加超时时间",
            "优化执行逻辑",
            "实现异步处理",
            "添加进度监控",
        ],
        "external_dependency": [
            "添加重试机制",
            "实现断路器模式",
            "配置备用服务",
            "增加超时控制",
        ],
    }

    def __init__(self, knowledge_maintainer: KnowledgeMaintainer) -> None:
        self._maintainer = knowledge_maintainer
        self._processing_logs: list[dict[str, Any]] = []

    @property
    def knowledge_maintainer(self) -> KnowledgeMaintainer:
        """获取知识维护器"""
        return self._maintainer

    def handle_alert(self, alert: Alert) -> dict[str, Any]:
        """处理告警

        参数：
            alert: 告警对象

        返回：
            处理结果
        """
        log_entry = {
            "event_type": "alert_processed",
            "alert_id": alert.id,
            "alert_type": alert.type,
            "severity": alert.severity,
            "timestamp": time.time(),
        }

        try:
            if alert.severity == "critical":
                result = self._create_failure_case(alert)
                log_entry["action"] = "failure_case_created"
            else:
                result = self._create_memory(alert)
                log_entry["action"] = "memory_created"

            log_entry["success"] = True
            log_entry["result_id"] = result.get("id")

        except Exception as e:
            log_entry["success"] = False
            log_entry["error"] = str(e)
            result = {"success": True, "action": "skipped", "reason": str(e)}

        self._processing_logs.append(log_entry)
        return {"success": True, "action": log_entry.get("action", "processed")}

    def _create_failure_case(self, alert: Alert) -> dict[str, Any]:
        """从告警创建失败案例"""
        # 确定失败类别
        category = self.ALERT_TYPE_TO_FAILURE_CATEGORY.get(alert.type, FailureCategory.LOGIC_ERROR)

        # 获取预防策略
        prevention = self.PREVENTION_STRATEGIES.get(alert.type, ["进行详细分析"])

        # 生成任务类型和描述
        task_type = self._infer_task_type(alert)
        task_description = self._generate_task_description(alert)

        # 记录失败案例
        failure_id = self._maintainer.record_failure(
            task_type=task_type,
            task_description=task_description,
            workflow_id=f"alert_{alert.id}",
            failure_category=category,
            error_message=alert.message,
            root_cause=self._infer_root_cause(alert),
            lesson_learned=self._generate_lesson(alert),
            prevention_strategy=prevention,
        )

        return {"id": failure_id, "type": "failure_case"}

    def _create_memory(self, alert: Alert) -> dict[str, Any]:
        """从告警创建记忆"""
        content = f"警告记录: {alert.type} - {alert.message}"

        memory_id = self._maintainer.add_memory(
            category=MemoryCategory.CONTEXT,
            content=content,
            source=f"alert_{alert.id}",
            confidence=0.7,
            metadata={
                "alert_type": alert.type,
                "severity": alert.severity,
                "created_at": alert.created_at,
            },
        )

        return {"id": memory_id, "type": "memory"}

    def _infer_task_type(self, alert: Alert) -> str:
        """从告警推断任务类型"""
        type_mapping = {
            "sandbox_failure_rate": "sandbox_execution",
            "resource_exhausted": "resource_management",
            "execution_timeout": "task_execution",
            "external_dependency": "external_integration",
        }
        return type_mapping.get(alert.type, "monitoring_alert")

    def _generate_task_description(self, alert: Alert) -> str:
        """生成任务描述"""
        return f"处理 {alert.type} 类型的系统告警"

    def _infer_root_cause(self, alert: Alert) -> str:
        """推断根本原因"""
        cause_mapping = {
            "sandbox_failure_rate": "沙箱执行失败率过高，可能存在代码逻辑问题或资源不足",
            "resource_exhausted": "系统资源耗尽，需要优化资源使用或扩容",
            "execution_timeout": "执行超时，可能是任务过于复杂或依赖响应慢",
            "external_dependency": "外部依赖不可用或响应异常",
        }
        return cause_mapping.get(alert.type, f"告警类型 {alert.type} 触发")

    def _generate_lesson(self, alert: Alert) -> str:
        """生成经验教训"""
        lesson_mapping = {
            "sandbox_failure_rate": "需要加强沙箱执行的监控和错误处理",
            "resource_exhausted": "需要实现资源使用预警和自动扩容机制",
            "execution_timeout": "需要优化长时间运行的任务并添加超时处理",
            "external_dependency": "需要实现服务降级和断路器模式",
        }
        return lesson_mapping.get(alert.type, "需要针对此类告警建立预防机制")

    def get_processing_logs(self) -> list[dict[str, Any]]:
        """获取处理日志"""
        return self._processing_logs.copy()


# ==================== 2. PerformanceKnowledgeAdapter 性能知识适配器 ====================


class PerformanceKnowledgeAdapter:
    """性能知识适配器

    将性能瓶颈转换为知识库条目：
    - 瓶颈 → FailureCase（带优化建议）
    - 成功模式 → SuccessfulSolution
    """

    def __init__(self, knowledge_maintainer: KnowledgeMaintainer) -> None:
        self._maintainer = knowledge_maintainer
        self._processing_logs: list[dict[str, Any]] = []

    @property
    def knowledge_maintainer(self) -> KnowledgeMaintainer:
        """获取知识维护器"""
        return self._maintainer

    def process_bottleneck(self, bottleneck: Bottleneck) -> dict[str, Any]:
        """处理单个瓶颈

        参数：
            bottleneck: 瓶颈对象

        返回：
            处理结果
        """
        log_entry = {
            "event_type": "bottleneck_processed",
            "operation": bottleneck.operation,
            "service": bottleneck.service,
            "avg_duration_ms": bottleneck.avg_duration_ms,
            "timestamp": time.time(),
        }

        try:
            # 确定失败类别
            category = self._determine_failure_category(bottleneck)

            # 生成预防策略
            prevention = self._generate_prevention_strategy(bottleneck)

            # 记录失败案例
            failure_id = self._maintainer.record_failure(
                task_type="performance_bottleneck",
                task_description=f"{bottleneck.service} 服务的 {bottleneck.operation} 操作性能瓶颈",
                workflow_id=f"bottleneck_{uuid.uuid4().hex[:8]}",
                failure_category=category,
                error_message=f"平均耗时 {bottleneck.avg_duration_ms:.0f}ms，P95 耗时 {bottleneck.p95_duration_ms:.0f}ms",
                root_cause=f"操作 {bottleneck.operation} 在服务 {bottleneck.service} 中执行缓慢",
                lesson_learned=bottleneck.suggestion or "需要进行性能优化",
                prevention_strategy=prevention,
            )

            log_entry["success"] = True
            log_entry["failure_id"] = failure_id

        except Exception as e:
            log_entry["success"] = False
            log_entry["error"] = str(e)

        self._processing_logs.append(log_entry)
        return {"success": True}

    def process_bottlenecks(self, bottlenecks: list[Bottleneck]) -> list[dict[str, Any]]:
        """批量处理瓶颈

        参数：
            bottlenecks: 瓶颈列表

        返回：
            处理结果列表
        """
        return [self.process_bottleneck(b) for b in bottlenecks]

    def record_successful_pattern(self, pattern: dict[str, Any]) -> dict[str, Any]:
        """记录成功的执行模式

        参数：
            pattern: 模式信息
                - task_type: 任务类型
                - description: 描述
                - steps: 执行步骤
                - metrics: 指标
                - context: 上下文

        返回：
            记录结果
        """
        solution_id = self._maintainer.record_success(
            task_type=pattern.get("task_type", "unknown"),
            task_description=pattern.get("description", ""),
            workflow_id=f"pattern_{uuid.uuid4().hex[:8]}",
            solution_steps=pattern.get("steps", []),
            success_metrics=pattern.get("metrics", {}),
            context=pattern.get("context", {}),
        )

        return {"success": True, "solution_id": solution_id}

    def _determine_failure_category(self, bottleneck: Bottleneck) -> FailureCategory:
        """确定失败类别"""
        service_lower = bottleneck.service.lower()
        operation_lower = bottleneck.operation.lower()

        if "timeout" in operation_lower or bottleneck.p95_duration_ms > 10000:
            return FailureCategory.TIMEOUT
        elif "external" in service_lower or "api" in service_lower:
            return FailureCategory.EXTERNAL_DEPENDENCY
        elif "resource" in operation_lower or "memory" in operation_lower:
            return FailureCategory.RESOURCE_EXHAUSTED
        else:
            return FailureCategory.LOGIC_ERROR

    def _generate_prevention_strategy(self, bottleneck: Bottleneck) -> list[str]:
        """生成预防策略"""
        strategies = []

        # 基于建议生成策略
        if bottleneck.suggestion:
            strategies.append(bottleneck.suggestion)

        # 基于服务类型生成策略
        service_lower = bottleneck.service.lower()
        if "database" in service_lower:
            strategies.extend(["添加数据库索引", "优化查询语句", "考虑添加缓存"])
        elif "llm" in service_lower:
            strategies.extend(["使用更快的模型", "减少 token 数量", "实现流式处理"])
        elif "http" in service_lower or "api" in service_lower:
            strategies.extend(["添加缓存", "使用连接池", "实现请求合并"])

        # 基于耗时生成策略
        if bottleneck.avg_duration_ms > 5000:
            strategies.append("考虑异步处理")
        if bottleneck.p95_duration_ms > bottleneck.avg_duration_ms * 2:
            strategies.append("设置合理超时时间")

        return strategies if strategies else ["进行详细性能分析"]

    def get_processing_logs(self) -> list[dict[str, Any]]:
        """获取处理日志"""
        return self._processing_logs.copy()


# ==================== 3. MetricsKnowledgeCollector 指标知识收集器 ====================


class MetricsKnowledgeCollector:
    """指标知识收集器

    分析监控指标并创建知识条目：
    - 频繁失败的节点 → FailureCase
    - 成功的工作流模式 → SuccessfulSolution
    """

    def __init__(
        self,
        knowledge_maintainer: KnowledgeMaintainer,
        metrics_collector: DynamicNodeMetricsCollector,
    ) -> None:
        self._maintainer = knowledge_maintainer
        self._metrics = metrics_collector

    def analyze_and_record_failures(self, threshold: int = 5) -> dict[str, Any]:
        """分析并记录频繁失败

        参数：
            threshold: 失败次数阈值

        返回：
            分析结果
        """
        stats = self._metrics.get_statistics()
        failures_recorded = 0

        # 分析节点创建失败
        if stats.get("failed_creations", 0) >= threshold:
            self._maintainer.record_failure(
                task_type="node_creation",
                task_description="节点创建频繁失败",
                workflow_id=f"analysis_{uuid.uuid4().hex[:8]}",
                failure_category=FailureCategory.LOGIC_ERROR,
                error_message=f"节点创建失败 {stats['failed_creations']} 次",
                root_cause="节点定义或验证逻辑可能存在问题",
                lesson_learned="需要检查节点创建流程和验证规则",
                prevention_strategy=[
                    "增强节点定义验证",
                    "添加创建前检查",
                    "实现更详细的错误日志",
                ],
            )
            failures_recorded += 1

        # 分析沙箱执行失败
        if stats.get("sandbox_failures", 0) >= threshold:
            failure_rate = stats.get("sandbox_failure_rate", 0)
            self._maintainer.record_failure(
                task_type="sandbox_execution",
                task_description="沙箱执行频繁失败",
                workflow_id=f"analysis_{uuid.uuid4().hex[:8]}",
                failure_category=FailureCategory.LOGIC_ERROR,
                error_message=f"沙箱执行失败 {stats['sandbox_failures']} 次，失败率 {failure_rate:.1%}",
                root_cause="沙箱环境或执行代码可能存在问题",
                lesson_learned="需要改进沙箱稳定性和错误处理",
                prevention_strategy=[
                    "增加沙箱资源配额",
                    "改进错误捕获机制",
                    "添加执行超时控制",
                ],
            )
            failures_recorded += 1

        return {"failures_recorded": failures_recorded}

    def analyze_and_record_successes(self, min_success_count: int = 5) -> dict[str, Any]:
        """分析并记录成功模式

        参数：
            min_success_count: 最小成功次数

        返回：
            分析结果
        """
        stats = self._metrics.get_statistics()
        solutions_recorded = 0

        # 分析工作流执行成功
        if stats.get("workflow_successes", 0) >= min_success_count:
            self._maintainer.record_success(
                task_type="workflow_execution",
                task_description="工作流执行成功模式",
                workflow_id=f"pattern_{uuid.uuid4().hex[:8]}",
                solution_steps=[
                    "验证工作流配置",
                    "准备执行环境",
                    "执行节点序列",
                    "收集执行结果",
                ],
                success_metrics={
                    "success_count": stats.get("workflow_successes", 0),
                    "total_executions": stats.get("workflow_executions", 0),
                },
                context={"source": "metrics_analysis"},
            )
            solutions_recorded += 1

        return {"solutions_recorded": solutions_recorded}


# ==================== 4. MonitoringKnowledgeBridge 监控知识桥接器 ====================


class MonitoringKnowledgeBridge:
    """监控-知识桥接器

    连接监控系统与知识库，实现闭环：
    1. 自动注册告警回调
    2. 处理告警并创建知识条目
    3. 可选触发任务创建
    """

    def __init__(
        self,
        knowledge_maintainer: KnowledgeMaintainer,
        alert_manager: AlertManager,
        task_creation_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._maintainer = knowledge_maintainer
        self._alert_manager = alert_manager
        self._task_callback = task_creation_callback
        self._handler = AlertKnowledgeHandler(knowledge_maintainer)
        self._processed_alerts: set[str] = set()
        self._processing_logs: list[dict[str, Any]] = []

        # 自动注册回调
        self._alert_manager.set_notification_callback(self._on_alert)

    @property
    def knowledge_maintainer(self) -> KnowledgeMaintainer:
        """获取知识维护器"""
        return self._maintainer

    @property
    def alert_manager(self) -> AlertManager:
        """获取告警管理器"""
        return self._alert_manager

    @property
    def processed_alert_count(self) -> int:
        """已处理告警数量"""
        return len(self._processed_alerts)

    def _on_alert(self, alert: Alert) -> None:
        """告警回调处理

        参数：
            alert: 告警对象
        """
        # 避免重复处理
        if alert.id in self._processed_alerts:
            return

        self._processed_alerts.add(alert.id)

        # 记录日志
        log_entry = {
            "event_type": "alert_received",
            "alert_id": alert.id,
            "alert_type": alert.type,
            "severity": alert.severity,
            "timestamp": time.time(),
        }
        self._processing_logs.append(log_entry)

        # 处理告警
        self._handler.handle_alert(alert)

        # 如果是严重告警，触发任务创建
        if alert.severity == "critical" and self._task_callback:
            task_info = {
                "type": "alert_response",
                "alert_id": alert.id,
                "alert_type": alert.type,
                "priority": "high",
                "description": f"响应严重告警: {alert.message}",
                "created_at": time.time(),
            }
            self._task_callback(task_info)

    def get_processing_logs(self) -> list[dict[str, Any]]:
        """获取处理日志"""
        return self._processing_logs.copy()
