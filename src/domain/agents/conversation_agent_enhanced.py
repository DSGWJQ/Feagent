"""
ConversationAgent 增强模块

本模块提供 ConversationAgent 的增强功能：
1. Schema 强制验证：所有决策使用 Pydantic schema 验证
2. 依赖关系分析：检测和验证工作流依赖
3. 资源约束感知：考虑时间、并发、API限制

用法：
    from src.domain.agents.conversation_agent_enhanced import (
        validate_decision_payload,
        detect_cyclic_dependencies,
        check_resource_constraints
    )
"""

import logging
from typing import Any

from pydantic import ValidationError

from src.domain.agents.decision_payload import (
    CreateWorkflowPlanPayload,
    WorkflowEdge,
    WorkflowNode,
    create_payload_from_dict,
)

logger = logging.getLogger(__name__)


# ========================================
# Schema 验证
# ========================================


def validate_decision_payload(action_type: str, payload: dict[str, Any]) -> Any:
    """验证决策 payload

    使用 Pydantic schema 验证 payload 的结构和内容。

    Args:
        action_type: 动作类型
        payload: payload 字典

    Returns:
        验证后的 Pydantic 对象

    Raises:
        ValidationError: 如果 payload 不符合 schema
    """
    try:
        # 确保 action_type 在 payload 中
        if "action_type" not in payload:
            payload["action_type"] = action_type

        # 使用工厂函数创建并验证
        validated = create_payload_from_dict(action_type, payload)

        logger.info(f"Payload 验证成功: action_type={action_type}")
        return validated

    except ValidationError as e:
        logger.error(f"Payload 验证失败: action_type={action_type}, errors={e.errors()}")
        raise


def validate_and_convert_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """验证并转换 payload（保持字典格式）

    Args:
        payload: 原始 payload 字典

    Returns:
        验证后的 payload 字典

    Raises:
        ValidationError: 如果验证失败
    """
    action_type = payload.get("action_type")
    if not action_type:
        raise ValueError("payload 缺少 action_type 字段")

    # 验证
    validated_obj = validate_decision_payload(action_type, payload)

    # 转换回字典
    return validated_obj.model_dump()


# ========================================
# 依赖关系分析
# ========================================


def detect_cyclic_dependencies(
    nodes: list[WorkflowNode], edges: list[WorkflowEdge]
) -> tuple[bool, list[str] | None]:
    """检测工作流中的循环依赖

    使用拓扑排序算法检测 DAG 中的循环。

    Args:
        nodes: 节点列表
        edges: 边列表

    Returns:
        (has_cycle, cycle_path)
        - has_cycle: 是否存在循环
        - cycle_path: 如果存在循环，返回循环路径
    """
    # 构建邻接表
    graph: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    in_degree: dict[str, int] = {node.node_id: 0 for node in nodes}

    for edge in edges:
        if edge.source not in graph:
            logger.warning(f"边的源节点 {edge.source} 不存在")
            continue
        if edge.target not in graph:
            logger.warning(f"边的目标节点 {edge.target} 不存在")
            continue

        graph[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    # Kahn 算法：拓扑排序
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    visited = []

    while queue:
        node_id = queue.pop(0)
        visited.append(node_id)

        for neighbor in graph[node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 如果访问的节点数不等于总节点数，说明有循环
    has_cycle = len(visited) != len(nodes)

    if has_cycle:
        # 找出循环路径（简化版）
        unvisited = [n.node_id for n in nodes if n.node_id not in visited]
        logger.error(f"检测到循环依赖，涉及节点: {unvisited}")
        return True, unvisited

    return False, None


def validate_workflow_dependencies(payload: CreateWorkflowPlanPayload) -> None:
    """验证工作流依赖关系

    Args:
        payload: 工作流规划 payload

    Raises:
        ValueError: 如果存在循环依赖
    """
    has_cycle, cycle_path = detect_cyclic_dependencies(payload.nodes, payload.edges)

    if has_cycle:
        error_msg = f"工作流包含循环依赖，涉及节点: {cycle_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info("工作流依赖验证通过，无循环依赖")


def analyze_parallel_opportunities(
    nodes: list[WorkflowNode], edges: list[WorkflowEdge]
) -> dict[str, Any]:
    """分析并行执行机会

    识别哪些节点可以并行执行。

    Args:
        nodes: 节点列表
        edges: 边列表

    Returns:
        并行分析结果
    """
    # 构建依赖关系
    dependencies: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    for edge in edges:
        if edge.target in dependencies:
            dependencies[edge.target].append(edge.source)

    # 按依赖层级分组
    levels: list[list[str]] = []
    processed = set()

    while len(processed) < len(nodes):
        # 找出当前层级（所有依赖都已处理的节点）
        current_level = [
            node_id
            for node_id, deps in dependencies.items()
            if node_id not in processed and all(d in processed for d in deps)
        ]

        if not current_level:
            # 如果没有可处理的节点，说明有循环或其他问题
            break

        levels.append(current_level)
        processed.update(current_level)

    return {
        "total_nodes": len(nodes),
        "parallel_levels": len(levels),
        "levels": levels,
        "max_parallel_in_level": max(len(level) for level in levels) if levels else 0,
    }


# ========================================
# 资源约束检查
# ========================================


def check_resource_constraints(
    payload: CreateWorkflowPlanPayload, constraints: dict[str, Any] | None = None
) -> dict[str, Any]:
    """检查资源约束

    验证工作流是否满足资源约束。

    Args:
        payload: 工作流规划 payload
        constraints: 资源约束配置

    Returns:
        约束检查结果
    """
    if constraints is None:
        constraints = {}

    result = {
        "constraints_met": True,
        "warnings": [],
        "violations": [],
    }

    # 检查时间约束
    time_limit = constraints.get("time_limit", 300)  # 默认 5 分钟
    global_timeout = payload.global_config.get("timeout", 0) if payload.global_config else 0

    if global_timeout > time_limit:
        result["constraints_met"] = False
        result["violations"].append(f"全局超时 ({global_timeout}s) 超过时间限制 ({time_limit}s)")

    # 检查并发限制
    max_parallel = constraints.get("max_parallel", 3)
    parallel_analysis = analyze_parallel_opportunities(payload.nodes, payload.edges)
    max_parallel_in_level = parallel_analysis["max_parallel_in_level"]

    if max_parallel_in_level > max_parallel:
        result["warnings"].append(
            f"某些并行层级有 {max_parallel_in_level} 个节点，超过限制 ({max_parallel})"
        )

    # 统计 API 调用
    api_calls = {"HTTP": 0, "LLM": 0, "DATABASE": 0}
    for node in payload.nodes:
        if node.type in api_calls:
            api_calls[node.type] += 1

    result["api_calls"] = api_calls

    # 检查 API 限制
    if api_limits := constraints.get("api_limits"):
        for api_type, limit in api_limits.items():
            if api_calls.get(api_type, 0) > limit:
                result["constraints_met"] = False
                result["violations"].append(
                    f"{api_type} 调用次数 ({api_calls[api_type]}) 超过限制 ({limit})"
                )

    logger.info(f"资源约束检查完成: {result}")
    return result


def estimate_execution_time(payload: CreateWorkflowPlanPayload) -> dict[str, Any]:
    """估算工作流执行时间

    Args:
        payload: 工作流规划 payload

    Returns:
        时间估算结果
    """
    # 简单估算：根据节点类型估算时间
    node_time_estimates = {
        "HTTP": 5,  # 5 秒
        "LLM": 10,  # 10 秒
        "DATABASE": 3,  # 3 秒
        "PYTHON": 2,  # 2 秒
        "CONDITION": 1,  # 1 秒
    }

    # 分析并行机会
    parallel_analysis = analyze_parallel_opportunities(payload.nodes, payload.edges)

    # 计算每层的执行时间
    level_times = []
    for level in parallel_analysis["levels"]:
        level_nodes = [n for n in payload.nodes if n.node_id in level]
        # 该层的时间 = 最长的节点时间
        level_time = max(node_time_estimates.get(node.type, 5) for node in level_nodes)
        level_times.append(level_time)

    total_time = sum(level_times)

    return {
        "estimated_total_time": total_time,
        "level_times": level_times,
        "parallel_levels": len(level_times),
        "sequential_time": sum(node_time_estimates.get(node.type, 5) for node in payload.nodes),
    }


# ========================================
# 综合验证函数
# ========================================


def validate_and_enhance_decision(
    action_type: str, payload: dict[str, Any], constraints: dict[str, Any] | None = None
) -> tuple[Any, dict[str, Any]]:
    """综合验证和增强决策

    Args:
        action_type: 动作类型
        payload: payload 字典
        constraints: 资源约束

    Returns:
        (validated_payload, metadata)
        - validated_payload: 验证后的 Pydantic 对象
        - metadata: 额外的元数据（依赖分析、资源检查等）
    """
    metadata: dict[str, Any] = {}

    # 1. Schema 验证
    validated = validate_decision_payload(action_type, payload)

    # 2. 特殊处理：工作流规划
    if isinstance(validated, CreateWorkflowPlanPayload):
        # 验证依赖关系
        try:
            validate_workflow_dependencies(validated)
            metadata["dependencies_valid"] = True
        except ValidationError as e:
            metadata["dependencies_valid"] = False
            metadata["dependency_errors"] = str(e)
            raise

        # 分析并行机会
        parallel_analysis = analyze_parallel_opportunities(validated.nodes, validated.edges)
        metadata["parallel_analysis"] = parallel_analysis

        # 检查资源约束
        if constraints:
            resource_check = check_resource_constraints(validated, constraints)
            metadata["resource_check"] = resource_check

            if not resource_check["constraints_met"]:
                logger.warning(f"资源约束检查未通过: {resource_check['violations']}")

        # 估算执行时间
        time_estimate = estimate_execution_time(validated)
        metadata["time_estimate"] = time_estimate

    return validated, metadata
