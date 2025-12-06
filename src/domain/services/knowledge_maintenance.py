"""知识库维护模块 (Knowledge Maintenance) - Step 8

提供知识库维护的完整实现，包括：

1. LongTermMemory - 长期记忆（跨会话持久化知识）
2. UserPreference - 用户偏好（个人习惯、风格偏好）
3. SuccessfulSolution - 成功解法（已验证的解决方案）
4. FailureCase - 失败案例（记录失败原因与教训）
5. KnowledgeMaintainer - 知识维护器（从事件更新知识库）
6. SolutionRetriever - 解法检索器（相似任务复用）
7. KnowledgeStore - 知识存储（持久化）

Schema 定义：
    LongTermMemory:
        - memory_id: 唯一标识
        - category: 类别 (fact/procedure/context/skill)
        - content: 内容
        - source: 来源
        - confidence: 置信度 (0-1)
        - access_count: 访问次数
        - metadata: 元数据

    UserPreference:
        - preference_id: 唯一标识
        - user_id: 用户 ID
        - preference_type: 类型 (coding_style/output_format/communication/workflow/tool_usage)
        - key: 偏好键
        - value: 偏好值
        - priority: 优先级

    SuccessfulSolution:
        - solution_id: 唯一标识
        - task_type: 任务类型
        - task_description: 任务描述
        - workflow_id: 工作流 ID
        - solution_steps: 解决步骤
        - success_metrics: 成功指标
        - context: 上下文
        - tags: 标签
        - reuse_count: 复用次数

    FailureCase:
        - failure_id: 唯一标识
        - task_type: 任务类型
        - task_description: 任务描述
        - workflow_id: 工作流 ID
        - failure_category: 失败类别
        - error_message: 错误消息
        - root_cause: 根本原因
        - lesson_learned: 经验教训
        - prevention_strategy: 预防策略

更新触发条件：
    - workflow_success 事件 → 记录 SuccessfulSolution
    - workflow_failure 事件 → 记录 FailureCase
    - 用户反馈 → 更新 UserPreference
    - 会话结论 → 添加 LongTermMemory

复用策略：
    1. 相似度匹配：基于 task_type、description、context、tags 计算相似度
    2. 最佳解法选择：按 success_metrics 指标排序
    3. 失败预警：检查是否有类似的历史失败案例
    4. 置信度衰减：长期未使用的记忆置信度逐渐降低

用法：
    # 知识维护
    maintainer = KnowledgeMaintainer()
    maintainer.add_memory(MemoryCategory.FACT, "项目使用 Python 3.11", "config", 1.0)
    maintainer.on_workflow_event(success_event)

    # 解法检索
    retriever = SolutionRetriever(maintainer)
    similar = retriever.find_similar_solutions(task_type, description, context)
    best = retriever.get_best_solution(task_type, "accuracy")
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

# ==================== 1. 记忆类别枚举 ====================


class MemoryCategory(str, Enum):
    """记忆类别枚举

    - FACT: 事实性知识（如项目配置、环境信息）
    - PROCEDURE: 过程性知识（如操作流程、部署步骤）
    - CONTEXT: 上下文知识（如项目背景、业务规则）
    - SKILL: 技能性知识（如编程技能、工具使用）
    """

    FACT = "fact"
    PROCEDURE = "procedure"
    CONTEXT = "context"
    SKILL = "skill"


# ==================== 2. LongTermMemory 长期记忆 ====================


@dataclass
class LongTermMemory:
    """长期记忆

    跨会话持久化的知识单元，用于存储事实、流程、上下文和技能。

    属性：
        memory_id: 唯一标识
        category: 记忆类别
        content: 内容
        source: 来源（会话 ID、文档等）
        confidence: 置信度 (0-1)
        access_count: 访问次数
        metadata: 附加元数据
        created_at: 创建时间
        last_accessed_at: 最后访问时间
    """

    memory_id: str
    category: MemoryCategory
    content: str
    source: str
    confidence: float
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: datetime | None = None

    def increment_access(self) -> None:
        """增加访问计数"""
        self.access_count += 1
        self.last_accessed_at = datetime.now()

    def update_confidence(self, new_confidence: float) -> None:
        """更新置信度（限制在 0-1 范围内）"""
        self.confidence = max(0.0, min(1.0, new_confidence))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "memory_id": self.memory_id,
            "category": self.category.value,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "access_count": self.access_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LongTermMemory:
        """从字典创建"""
        return cls(
            memory_id=data["memory_id"],
            category=MemoryCategory(data["category"]),
            content=data["content"],
            source=data["source"],
            confidence=data["confidence"],
            access_count=data.get("access_count", 0),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
            last_accessed_at=(
                datetime.fromisoformat(data["last_accessed_at"])
                if data.get("last_accessed_at")
                else None
            ),
        )


# ==================== 3. 偏好类型枚举 ====================


class PreferenceType(str, Enum):
    """偏好类型枚举

    - CODING_STYLE: 编码风格（缩进、命名等）
    - OUTPUT_FORMAT: 输出格式（markdown、table 等）
    - COMMUNICATION: 沟通风格（正式、简洁等）
    - WORKFLOW: 工作流偏好（自动化级别等）
    - TOOL_USAGE: 工具使用偏好（首选 LLM 等）
    """

    CODING_STYLE = "coding_style"
    OUTPUT_FORMAT = "output_format"
    COMMUNICATION = "communication"
    WORKFLOW = "workflow"
    TOOL_USAGE = "tool_usage"


# ==================== 4. UserPreference 用户偏好 ====================


@dataclass
class UserPreference:
    """用户偏好

    记录用户的个人习惯和风格偏好。

    属性：
        preference_id: 唯一标识
        user_id: 用户 ID
        preference_type: 偏好类型
        key: 偏好键（如 "indentation"）
        value: 偏好值（如 "4_spaces"）
        priority: 优先级（数字越大优先级越高）
        created_at: 创建时间
        updated_at: 更新时间
    """

    preference_id: str
    user_id: str
    preference_type: PreferenceType
    key: str
    value: str
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None

    def update_value(self, new_value: str) -> None:
        """更新偏好值"""
        self.value = new_value
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "preference_id": self.preference_id,
            "user_id": self.user_id,
            "preference_type": self.preference_type.value,
            "key": self.key,
            "value": self.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserPreference:
        """从字典创建"""
        return cls(
            preference_id=data["preference_id"],
            user_id=data["user_id"],
            preference_type=PreferenceType(data["preference_type"]),
            key=data["key"],
            value=data["value"],
            priority=data.get("priority", 0),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
            ),
        )


# ==================== 5. SuccessfulSolution 成功解法 ====================


@dataclass
class SuccessfulSolution:
    """成功解法

    记录已验证的解决方案，用于相似任务复用。

    属性：
        solution_id: 唯一标识
        task_type: 任务类型
        task_description: 任务描述
        workflow_id: 关联的工作流 ID
        solution_steps: 解决步骤列表
        success_metrics: 成功指标（如 accuracy、duration 等）
        context: 执行上下文
        tags: 标签（用于检索）
        reuse_count: 复用次数
        created_at: 创建时间
        last_reused_at: 最后复用时间
    """

    solution_id: str
    task_type: str
    task_description: str
    workflow_id: str
    solution_steps: list[str]
    success_metrics: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    reuse_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_reused_at: datetime | None = None

    def increment_reuse(self) -> None:
        """增加复用计数"""
        self.reuse_count += 1
        self.last_reused_at = datetime.now()

    def calculate_similarity(
        self,
        task_type: str,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> float:
        """计算与给定任务的相似度

        参数：
            task_type: 目标任务类型
            task_description: 目标任务描述
            context: 目标任务上下文

        返回：
            相似度分数 (0-1)
        """
        score = 0.0
        weights = {"type": 0.3, "description": 0.4, "context": 0.3}

        # 任务类型匹配
        if self.task_type == task_type:
            score += weights["type"]
        elif self.task_type.lower() in task_type.lower():
            score += weights["type"] * 0.5

        # 描述相似度（使用 SequenceMatcher）
        desc_similarity = SequenceMatcher(
            None,
            self.task_description.lower(),
            task_description.lower(),
        ).ratio()
        score += weights["description"] * desc_similarity

        # 上下文匹配
        if context and self.context:
            matching_keys = set(self.context.keys()) & set(context.keys())
            if matching_keys:
                context_score = sum(
                    1 for k in matching_keys if self.context.get(k) == context.get(k)
                ) / len(matching_keys)
                score += weights["context"] * context_score

        return score

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "solution_id": self.solution_id,
            "task_type": self.task_type,
            "task_description": self.task_description,
            "workflow_id": self.workflow_id,
            "solution_steps": self.solution_steps,
            "success_metrics": self.success_metrics,
            "context": self.context,
            "tags": self.tags,
            "reuse_count": self.reuse_count,
            "created_at": self.created_at.isoformat(),
            "last_reused_at": (self.last_reused_at.isoformat() if self.last_reused_at else None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SuccessfulSolution:
        """从字典创建"""
        return cls(
            solution_id=data["solution_id"],
            task_type=data["task_type"],
            task_description=data["task_description"],
            workflow_id=data["workflow_id"],
            solution_steps=data["solution_steps"],
            success_metrics=data["success_metrics"],
            context=data.get("context", {}),
            tags=data.get("tags", []),
            reuse_count=data.get("reuse_count", 0),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
            last_reused_at=(
                datetime.fromisoformat(data["last_reused_at"])
                if data.get("last_reused_at")
                else None
            ),
        )


# ==================== 6. 失败类别枚举 ====================


class FailureCategory(str, Enum):
    """失败类别枚举

    - INVALID_INPUT: 无效输入
    - RESOURCE_EXHAUSTED: 资源耗尽
    - EXTERNAL_DEPENDENCY: 外部依赖问题
    - LOGIC_ERROR: 逻辑错误
    - TIMEOUT: 超时
    - PERMISSION_DENIED: 权限不足
    """

    INVALID_INPUT = "invalid_input"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    EXTERNAL_DEPENDENCY = "external_dependency"
    LOGIC_ERROR = "logic_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"


# ==================== 7. FailureCase 失败案例 ====================


@dataclass
class FailureCase:
    """失败案例

    记录失败原因与教训，用于预防类似错误。

    属性：
        failure_id: 唯一标识
        task_type: 任务类型
        task_description: 任务描述
        workflow_id: 关联的工作流 ID
        failure_category: 失败类别
        error_message: 错误消息
        root_cause: 根本原因
        lesson_learned: 经验教训
        prevention_strategy: 预防策略列表
        created_at: 创建时间
    """

    failure_id: str
    task_type: str
    task_description: str
    workflow_id: str
    failure_category: FailureCategory
    error_message: str
    root_cause: str
    lesson_learned: str
    prevention_strategy: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def is_similar_error(
        self,
        error_message: str,
        task_type: str | None = None,
    ) -> bool:
        """判断是否相似错误

        参数：
            error_message: 目标错误消息
            task_type: 目标任务类型

        返回：
            是否相似
        """
        # 任务类型不匹配则不相似
        if task_type and self.task_type != task_type:
            return False

        self_error_lower = self.error_message.lower()
        target_error_lower = error_message.lower()

        # 子串包含检查（一个错误消息包含另一个）
        if target_error_lower in self_error_lower or self_error_lower in target_error_lower:
            return True

        # 错误消息相似度检查
        error_similarity = SequenceMatcher(
            None,
            self_error_lower,
            target_error_lower,
        ).ratio()

        return error_similarity >= 0.5

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "failure_id": self.failure_id,
            "task_type": self.task_type,
            "task_description": self.task_description,
            "workflow_id": self.workflow_id,
            "failure_category": self.failure_category.value,
            "error_message": self.error_message,
            "root_cause": self.root_cause,
            "lesson_learned": self.lesson_learned,
            "prevention_strategy": self.prevention_strategy,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureCase:
        """从字典创建"""
        return cls(
            failure_id=data["failure_id"],
            task_type=data["task_type"],
            task_description=data["task_description"],
            workflow_id=data["workflow_id"],
            failure_category=FailureCategory(data["failure_category"]),
            error_message=data["error_message"],
            root_cause=data["root_cause"],
            lesson_learned=data["lesson_learned"],
            prevention_strategy=data.get("prevention_strategy", []),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
        )


# ==================== 8. KnowledgeMaintainer 知识维护器 ====================


class KnowledgeMaintainer:
    """知识维护器

    负责管理知识库的增删改查，以及处理工作流事件。

    功能：
        - 添加/获取/搜索长期记忆
        - 添加/获取用户偏好
        - 记录成功解法和失败案例
        - 处理工作流成功/失败事件
    """

    def __init__(self) -> None:
        self._memories: dict[str, LongTermMemory] = {}
        self._preferences: dict[str, UserPreference] = {}
        self._solutions: dict[str, SuccessfulSolution] = {}
        self._failures: dict[str, FailureCase] = {}

    @property
    def memory_count(self) -> int:
        """记忆总数"""
        return len(self._memories)

    @property
    def preference_count(self) -> int:
        """偏好总数"""
        return len(self._preferences)

    @property
    def solution_count(self) -> int:
        """解法总数"""
        return len(self._solutions)

    @property
    def failure_count(self) -> int:
        """失败案例总数"""
        return len(self._failures)

    # ========== 长期记忆管理 ==========

    def add_memory(
        self,
        category: MemoryCategory,
        content: str,
        source: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """添加长期记忆

        参数：
            category: 记忆类别
            content: 内容
            source: 来源
            confidence: 置信度
            metadata: 元数据

        返回：
            记忆 ID
        """
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        memory = LongTermMemory(
            memory_id=memory_id,
            category=category,
            content=content,
            source=source,
            confidence=confidence,
            metadata=metadata or {},
        )
        self._memories[memory_id] = memory
        return memory_id

    def get_memory(self, memory_id: str) -> LongTermMemory | None:
        """获取记忆

        参数：
            memory_id: 记忆 ID

        返回：
            LongTermMemory 或 None
        """
        memory = self._memories.get(memory_id)
        if memory:
            memory.increment_access()
        return memory

    def search_memories(
        self,
        keyword: str,
        category: MemoryCategory | None = None,
    ) -> list[LongTermMemory]:
        """搜索记忆

        参数：
            keyword: 关键词
            category: 可选的类别过滤

        返回：
            匹配的记忆列表
        """
        results = []
        keyword_lower = keyword.lower()

        for memory in self._memories.values():
            if category and memory.category != category:
                continue
            if keyword_lower in memory.content.lower():
                results.append(memory)

        return results

    # ========== 用户偏好管理 ==========

    def add_preference(
        self,
        user_id: str,
        preference_type: PreferenceType,
        key: str,
        value: str,
        priority: int = 0,
    ) -> str:
        """添加用户偏好

        参数：
            user_id: 用户 ID
            preference_type: 偏好类型
            key: 偏好键
            value: 偏好值
            priority: 优先级

        返回：
            偏好 ID
        """
        pref_id = f"pref_{uuid.uuid4().hex[:8]}"
        preference = UserPreference(
            preference_id=pref_id,
            user_id=user_id,
            preference_type=preference_type,
            key=key,
            value=value,
            priority=priority,
        )
        self._preferences[pref_id] = preference
        return pref_id

    def get_user_preferences(self, user_id: str) -> list[UserPreference]:
        """获取用户的所有偏好

        参数：
            user_id: 用户 ID

        返回：
            偏好列表
        """
        return [p for p in self._preferences.values() if p.user_id == user_id]

    # ========== 成功解法管理 ==========

    def record_success(
        self,
        task_type: str,
        task_description: str,
        workflow_id: str,
        solution_steps: list[str],
        success_metrics: dict[str, Any],
        context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """记录成功解法

        参数：
            task_type: 任务类型
            task_description: 任务描述
            workflow_id: 工作流 ID
            solution_steps: 解决步骤
            success_metrics: 成功指标
            context: 上下文
            tags: 标签

        返回：
            解法 ID
        """
        solution_id = f"sol_{uuid.uuid4().hex[:8]}"
        solution = SuccessfulSolution(
            solution_id=solution_id,
            task_type=task_type,
            task_description=task_description,
            workflow_id=workflow_id,
            solution_steps=solution_steps,
            success_metrics=success_metrics,
            context=context or {},
            tags=tags or [],
        )
        self._solutions[solution_id] = solution
        return solution_id

    def get_solutions(self) -> list[SuccessfulSolution]:
        """获取所有解法"""
        return list(self._solutions.values())

    # ========== 失败案例管理 ==========

    def record_failure(
        self,
        task_type: str,
        task_description: str,
        workflow_id: str,
        failure_category: FailureCategory,
        error_message: str,
        root_cause: str,
        lesson_learned: str,
        prevention_strategy: list[str] | None = None,
    ) -> str:
        """记录失败案例

        参数：
            task_type: 任务类型
            task_description: 任务描述
            workflow_id: 工作流 ID
            failure_category: 失败类别
            error_message: 错误消息
            root_cause: 根本原因
            lesson_learned: 经验教训
            prevention_strategy: 预防策略

        返回：
            失败案例 ID
        """
        failure_id = f"fail_{uuid.uuid4().hex[:8]}"
        failure = FailureCase(
            failure_id=failure_id,
            task_type=task_type,
            task_description=task_description,
            workflow_id=workflow_id,
            failure_category=failure_category,
            error_message=error_message,
            root_cause=root_cause,
            lesson_learned=lesson_learned,
            prevention_strategy=prevention_strategy or [],
        )
        self._failures[failure_id] = failure
        return failure_id

    def get_failures(self) -> list[FailureCase]:
        """获取所有失败案例"""
        return list(self._failures.values())

    # ========== 工作流事件处理 ==========

    def on_workflow_event(self, event: dict[str, Any]) -> None:
        """处理工作流事件

        参数：
            event: 工作流事件
                - event_type: "workflow_success" 或 "workflow_failure"
                - workflow_id: 工作流 ID
                - task_type: 任务类型
                - task_description: 任务描述
                - 其他字段根据事件类型不同
        """
        event_type = event.get("event_type")

        if event_type == "workflow_success":
            self._handle_success_event(event)
        elif event_type == "workflow_failure":
            self._handle_failure_event(event)
        # 未知事件类型忽略

    def _handle_success_event(self, event: dict[str, Any]) -> None:
        """处理成功事件"""
        self.record_success(
            task_type=event.get("task_type", ""),
            task_description=event.get("task_description", ""),
            workflow_id=event.get("workflow_id", ""),
            solution_steps=event.get("execution_steps", []),
            success_metrics=event.get("metrics", {}),
            context=event.get("context"),
            tags=event.get("tags"),
        )

    def _handle_failure_event(self, event: dict[str, Any]) -> None:
        """处理失败事件"""
        category_str = event.get("failure_category", "logic_error")
        try:
            category = FailureCategory(category_str)
        except ValueError:
            category = FailureCategory.LOGIC_ERROR

        self.record_failure(
            task_type=event.get("task_type", ""),
            task_description=event.get("task_description", ""),
            workflow_id=event.get("workflow_id", ""),
            failure_category=category,
            error_message=event.get("error_message", ""),
            root_cause=event.get("root_cause", ""),
            lesson_learned=event.get("lesson_learned", ""),
            prevention_strategy=event.get("prevention_strategy"),
        )


# ==================== 9. SolutionRetriever 解法检索器 ====================


class SolutionRetriever:
    """解法检索器

    提供相似解法检索、最佳解法选择、失败预警等功能。
    """

    def __init__(self, maintainer: KnowledgeMaintainer) -> None:
        self._maintainer = maintainer

    def find_similar_solutions(
        self,
        task_type: str,
        task_description: str,
        context: dict[str, Any] | None = None,
        top_k: int = 5,
        min_similarity: float = 0.3,
    ) -> list[SuccessfulSolution]:
        """查找相似解法

        参数：
            task_type: 任务类型
            task_description: 任务描述
            context: 上下文
            top_k: 返回前 k 个结果
            min_similarity: 最小相似度阈值

        返回：
            相似解法列表（按相似度降序）
        """
        solutions = self._maintainer.get_solutions()
        if not solutions:
            return []

        # 计算相似度并排序
        scored = []
        for solution in solutions:
            similarity = solution.calculate_similarity(task_type, task_description, context)
            if similarity >= min_similarity:
                scored.append((similarity, solution))

        # 按相似度降序排序
        scored.sort(key=lambda x: x[0], reverse=True)

        return [solution for _, solution in scored[:top_k]]

    def find_by_task_type(self, task_type: str) -> list[SuccessfulSolution]:
        """按任务类型查找解法

        参数：
            task_type: 任务类型

        返回：
            匹配的解法列表
        """
        return [s for s in self._maintainer.get_solutions() if s.task_type == task_type]

    def get_best_solution(
        self,
        task_type: str,
        metric_key: str,
    ) -> SuccessfulSolution | None:
        """获取最佳解法

        参数：
            task_type: 任务类型
            metric_key: 用于比较的指标键

        返回：
            最佳解法或 None
        """
        solutions = self.find_by_task_type(task_type)
        if not solutions:
            return None

        # 按指标值排序（降序）
        valid_solutions = [s for s in solutions if metric_key in s.success_metrics]
        if not valid_solutions:
            return solutions[0]  # 如果没有该指标，返回第一个

        return max(valid_solutions, key=lambda s: s.success_metrics[metric_key])

    def check_known_failure(
        self,
        task_type: str,
        task_description: str,
        potential_error: str | None = None,
    ) -> FailureCase | None:
        """检查已知失败

        参数：
            task_type: 任务类型
            task_description: 任务描述
            potential_error: 可能的错误消息

        返回：
            匹配的失败案例或 None
        """
        failures = self._maintainer.get_failures()

        for failure in failures:
            # 任务类型匹配
            if failure.task_type != task_type:
                continue

            # 如果有潜在错误，检查相似性
            if potential_error:
                if failure.is_similar_error(potential_error, task_type):
                    return failure

            # 任务描述相似度
            desc_similarity = SequenceMatcher(
                None,
                failure.task_description.lower(),
                task_description.lower(),
            ).ratio()
            if desc_similarity > 0.5:
                return failure

        return None


# ==================== 10. KnowledgeStore 知识存储 ====================


class KnowledgeStore:
    """知识存储

    提供知识的持久化和加载功能。
    """

    def __init__(self) -> None:
        self._memories: dict[str, LongTermMemory] = {}
        self._preferences: dict[str, UserPreference] = {}
        self._solutions: dict[str, SuccessfulSolution] = {}
        self._failures: dict[str, FailureCase] = {}

    def save_memory(self, memory: LongTermMemory) -> None:
        """保存记忆"""
        self._memories[memory.memory_id] = memory

    def load_memory(self, memory_id: str) -> LongTermMemory | None:
        """加载记忆"""
        return self._memories.get(memory_id)

    def save_preference(self, preference: UserPreference) -> None:
        """保存偏好"""
        self._preferences[preference.preference_id] = preference

    def load_preference(self, preference_id: str) -> UserPreference | None:
        """加载偏好"""
        return self._preferences.get(preference_id)

    def save_solution(self, solution: SuccessfulSolution) -> None:
        """保存解法"""
        self._solutions[solution.solution_id] = solution

    def load_solution(self, solution_id: str) -> SuccessfulSolution | None:
        """加载解法"""
        return self._solutions.get(solution_id)

    def save_failure(self, failure: FailureCase) -> None:
        """保存失败案例"""
        self._failures[failure.failure_id] = failure

    def load_failure(self, failure_id: str) -> FailureCase | None:
        """加载失败案例"""
        return self._failures.get(failure_id)

    def export_to_dict(self) -> dict[str, Any]:
        """导出为字典

        返回：
            包含所有知识的字典
        """
        return {
            "memories": [m.to_dict() for m in self._memories.values()],
            "preferences": [p.to_dict() for p in self._preferences.values()],
            "solutions": [s.to_dict() for s in self._solutions.values()],
            "failures": [f.to_dict() for f in self._failures.values()],
            "exported_at": datetime.now().isoformat(),
        }

    def import_from_dict(self, data: dict[str, Any]) -> None:
        """从字典导入

        参数：
            data: 知识数据字典
        """
        for mem_data in data.get("memories", []):
            memory = LongTermMemory.from_dict(mem_data)
            self._memories[memory.memory_id] = memory

        for pref_data in data.get("preferences", []):
            preference = UserPreference.from_dict(pref_data)
            self._preferences[preference.preference_id] = preference

        for sol_data in data.get("solutions", []):
            solution = SuccessfulSolution.from_dict(sol_data)
            self._solutions[solution.solution_id] = solution

        for fail_data in data.get("failures", []):
            failure = FailureCase.from_dict(fail_data)
            self._failures[failure.failure_id] = failure

    def export_to_json(self) -> str:
        """导出为 JSON 字符串"""
        return json.dumps(self.export_to_dict(), ensure_ascii=False, indent=2)

    def import_from_json(self, json_str: str) -> None:
        """从 JSON 字符串导入"""
        data = json.loads(json_str)
        self.import_from_dict(data)
