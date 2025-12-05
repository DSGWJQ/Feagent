"""错误处理与恢复模块 - 第五步：异常处理与重规划

提供错误分类、恢复策略映射、用户友好消息生成等功能。
支持 RETRY/SKIP/REPLAN/ASK_USER/ABORT 等恢复动作。
"""

import random
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event

# ============================================================================
# 错误分类枚举
# ============================================================================


class ErrorCategory(str, Enum):
    """错误分类枚举

    定义所有可能的错误类别，用于分类和选择恢复策略。
    """

    DATA_MISSING = "data_missing"  # 数据缺失
    NODE_CRASH = "node_crash"  # 节点崩溃
    API_FAILURE = "api_failure"  # API调用失败
    TIMEOUT = "timeout"  # 超时
    VALIDATION_ERROR = "validation"  # 验证错误
    DEPENDENCY_ERROR = "dependency"  # 依赖错误
    RESOURCE_EXHAUSTED = "resource"  # 资源耗尽
    PERMISSION_DENIED = "permission"  # 权限不足
    RATE_LIMITED = "rate_limit"  # 限流
    UNKNOWN = "unknown"  # 未知错误

    def is_retryable(self) -> bool:
        """判断错误是否可重试"""
        retryable_categories = {
            ErrorCategory.TIMEOUT,
            ErrorCategory.API_FAILURE,
            ErrorCategory.RATE_LIMITED,
        }
        return self in retryable_categories

    def requires_user_intervention(self) -> bool:
        """判断错误是否需要用户干预"""
        user_intervention_categories = {
            ErrorCategory.DATA_MISSING,
            ErrorCategory.VALIDATION_ERROR,
            ErrorCategory.PERMISSION_DENIED,
            ErrorCategory.UNKNOWN,
        }
        return self in user_intervention_categories


# ============================================================================
# 恢复动作枚举
# ============================================================================


class RecoveryAction(str, Enum):
    """恢复动作枚举

    定义所有可能的恢复动作。
    """

    RETRY = "retry"  # 自动重试
    RETRY_WITH_BACKOFF = "retry_backoff"  # 指数退避重试
    SKIP = "skip"  # 跳过节点
    REPLAN = "replan"  # 重新规划
    ASK_USER = "ask_user"  # 询问用户
    FALLBACK = "fallback"  # 使用备选方案
    ABORT = "abort"  # 终止执行


# ============================================================================
# 异常分类器
# ============================================================================

# 异常类型到错误分类的映射
EXCEPTION_TO_CATEGORY: dict[type, ErrorCategory] = {
    TimeoutError: ErrorCategory.TIMEOUT,
    ConnectionError: ErrorCategory.API_FAILURE,
    ValueError: ErrorCategory.VALIDATION_ERROR,
    TypeError: ErrorCategory.VALIDATION_ERROR,
    KeyError: ErrorCategory.DATA_MISSING,
    AttributeError: ErrorCategory.DATA_MISSING,
    RuntimeError: ErrorCategory.NODE_CRASH,
    MemoryError: ErrorCategory.RESOURCE_EXHAUSTED,
    PermissionError: ErrorCategory.PERMISSION_DENIED,
    OSError: ErrorCategory.API_FAILURE,
}


@dataclass
class ClassificationResult:
    """分类结果"""

    category: ErrorCategory
    original_message: str
    exception_type: str


class ExceptionClassifier:
    """异常分类器

    将Python异常映射到错误分类。
    """

    def __init__(self, custom_mapping: dict[type, ErrorCategory] | None = None) -> None:
        """初始化分类器

        参数:
            custom_mapping: 自定义异常到分类的映射
        """
        self.mapping = {**EXCEPTION_TO_CATEGORY}
        if custom_mapping:
            self.mapping.update(custom_mapping)

    def classify(self, error: Exception) -> ErrorCategory:
        """分类异常

        参数:
            error: 异常实例

        返回:
            错误分类
        """
        error_type = type(error)

        # 精确匹配
        if error_type in self.mapping:
            return self.mapping[error_type]

        # 检查继承关系
        for exc_type, category in self.mapping.items():
            if isinstance(error, exc_type):
                return category

        # 检查错误消息中的关键词
        error_msg = str(error).lower()
        if "rate limit" in error_msg or "too many requests" in error_msg:
            return ErrorCategory.RATE_LIMITED
        if "timeout" in error_msg:
            return ErrorCategory.TIMEOUT
        if "connection" in error_msg or "network" in error_msg:
            return ErrorCategory.API_FAILURE

        return ErrorCategory.UNKNOWN

    def classify_with_context(self, error: Exception) -> ClassificationResult:
        """分类异常并返回上下文信息

        参数:
            error: 异常实例

        返回:
            包含分类和上下文的结果
        """
        category = self.classify(error)
        return ClassificationResult(
            category=category,
            original_message=str(error),
            exception_type=type(error).__name__,
        )


# ============================================================================
# 恢复策略映射器
# ============================================================================

# 默认的错误分类到恢复动作映射
DEFAULT_RECOVERY_MAPPING: dict[ErrorCategory, RecoveryAction] = {
    ErrorCategory.TIMEOUT: RecoveryAction.RETRY_WITH_BACKOFF,
    ErrorCategory.API_FAILURE: RecoveryAction.RETRY,
    ErrorCategory.RATE_LIMITED: RecoveryAction.RETRY_WITH_BACKOFF,
    ErrorCategory.DATA_MISSING: RecoveryAction.ASK_USER,
    ErrorCategory.VALIDATION_ERROR: RecoveryAction.ASK_USER,
    ErrorCategory.DEPENDENCY_ERROR: RecoveryAction.REPLAN,
    ErrorCategory.NODE_CRASH: RecoveryAction.SKIP,
    ErrorCategory.RESOURCE_EXHAUSTED: RecoveryAction.ABORT,
    ErrorCategory.PERMISSION_DENIED: RecoveryAction.ASK_USER,
    ErrorCategory.UNKNOWN: RecoveryAction.ASK_USER,
}


class RecoveryStrategyMapper:
    """恢复策略映射器

    将错误分类映射到恢复动作。
    """

    def __init__(self, custom_mapping: dict[ErrorCategory, RecoveryAction] | None = None) -> None:
        """初始化映射器

        参数:
            custom_mapping: 自定义映射，覆盖默认策略
        """
        self.mapping = {**DEFAULT_RECOVERY_MAPPING}
        if custom_mapping:
            self.mapping.update(custom_mapping)

    def get_recovery_action(self, category: ErrorCategory) -> RecoveryAction:
        """获取恢复动作

        参数:
            category: 错误分类

        返回:
            恢复动作
        """
        return self.mapping.get(category, RecoveryAction.ASK_USER)


# ============================================================================
# 恢复上下文和结果
# ============================================================================


@dataclass
class RecoveryContext:
    """恢复上下文

    包含执行恢复动作所需的所有信息。
    """

    node_id: str
    action: RecoveryAction
    original_error: Exception
    retry_count: int = 0
    max_retries: int = 3
    failed_dependencies: list[str] = field(default_factory=list)
    supplemental_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """恢复结果"""

    success: bool = False
    skipped: bool = False
    needs_replan: bool = False
    awaiting_user_input: bool = False
    aborted: bool = False
    exhausted_retries: bool = False
    user_prompt: str | None = None
    abort_reason: str | None = None
    failed_dependencies: list[str] = field(default_factory=list)
    result: Any = None


class RecoveryExecutor:
    """恢复执行器

    执行恢复动作。
    """

    async def execute(
        self,
        context: RecoveryContext,
        operation: Callable[[], Coroutine[Any, Any, Any]],
    ) -> RecoveryResult:
        """执行恢复动作

        参数:
            context: 恢复上下文
            operation: 要重试的操作

        返回:
            恢复结果
        """
        if context.action == RecoveryAction.RETRY:
            return await self._execute_retry(context, operation)
        elif context.action == RecoveryAction.RETRY_WITH_BACKOFF:
            return await self._execute_retry_with_backoff(context, operation)
        elif context.action == RecoveryAction.SKIP:
            return self._execute_skip(context)
        elif context.action == RecoveryAction.REPLAN:
            return self._execute_replan(context)
        elif context.action == RecoveryAction.ASK_USER:
            return self._execute_ask_user(context)
        elif context.action == RecoveryAction.ABORT:
            return self._execute_abort(context)
        else:
            return RecoveryResult(success=False)

    async def _execute_retry(
        self,
        context: RecoveryContext,
        operation: Callable[[], Coroutine[Any, Any, Any]],
    ) -> RecoveryResult:
        """执行重试"""
        if context.retry_count >= context.max_retries:
            return RecoveryResult(success=False, exhausted_retries=True)

        try:
            result = await operation()
            return RecoveryResult(success=True, result=result)
        except Exception:
            return RecoveryResult(success=False)

    async def _execute_retry_with_backoff(
        self,
        context: RecoveryContext,
        operation: Callable[[], Coroutine[Any, Any, Any]],
    ) -> RecoveryResult:
        """执行指数退避重试"""
        return await self._execute_retry(context, operation)

    def _execute_skip(self, context: RecoveryContext) -> RecoveryResult:
        """执行跳过"""
        return RecoveryResult(skipped=True)

    def _execute_replan(self, context: RecoveryContext) -> RecoveryResult:
        """执行重新规划"""
        return RecoveryResult(needs_replan=True, failed_dependencies=context.failed_dependencies)

    def _execute_ask_user(self, context: RecoveryContext) -> RecoveryResult:
        """执行询问用户"""
        error_msg = str(context.original_error)
        prompt = f"节点 {context.node_id} 执行失败: {error_msg}\n请选择如何处理？"
        return RecoveryResult(awaiting_user_input=True, user_prompt=prompt)

    def _execute_abort(self, context: RecoveryContext) -> RecoveryResult:
        """执行终止"""
        return RecoveryResult(aborted=True, abort_reason=f"严重错误: {context.original_error}")


# ============================================================================
# 指数退避计算器
# ============================================================================


class BackoffCalculator:
    """指数退避计算器"""

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        factor: float = 2.0,
        jitter: float = 0.0,
    ) -> None:
        """初始化计算器

        参数:
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            factor: 退避因子
            jitter: 抖动比例 (0.0-1.0)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """计算延迟时间

        参数:
            attempt: 尝试次数（从0开始）

        返回:
            延迟时间（秒）
        """
        delay = self.base_delay * (self.factor**attempt)
        return min(delay, self.max_delay)

    def get_delay_with_jitter(self, attempt: int) -> float:
        """计算带抖动的延迟时间

        参数:
            attempt: 尝试次数

        返回:
            带抖动的延迟时间（秒）
        """
        base = self.get_delay(attempt)
        if self.jitter <= 0:
            return base

        jitter_range = base * self.jitter
        jitter_value = random.uniform(-jitter_range, jitter_range)
        return base + jitter_value


# ============================================================================
# 用户友好消息生成器
# ============================================================================

# 错误分类到用户友好消息模板的映射
USER_FRIENDLY_TEMPLATES: dict[ErrorCategory, str] = {
    ErrorCategory.TIMEOUT: "操作超时：{details}。这可能是由于网络问题或服务繁忙导致的。",
    ErrorCategory.DATA_MISSING: "缺少必要的数据：{details}。请提供所需信息后重试。",
    ErrorCategory.API_FAILURE: "服务调用失败：{details}。外部服务可能暂时不可用。",
    ErrorCategory.VALIDATION_ERROR: "数据格式错误：{details}。请检查输入数据的格式。",
    ErrorCategory.NODE_CRASH: "处理过程中遇到错误，已跳过当前步骤继续执行。",
    ErrorCategory.DEPENDENCY_ERROR: "依赖的步骤执行失败：{details}。正在重新规划执行路径。",
    ErrorCategory.RESOURCE_EXHAUSTED: "系统资源不足：{details}。请稍后重试。",
    ErrorCategory.PERMISSION_DENIED: "权限不足：{details}。请检查访问权限。",
    ErrorCategory.RATE_LIMITED: "请求过于频繁：{details}。请稍等片刻后重试。",
    ErrorCategory.UNKNOWN: "遇到未知错误：{details}。请联系技术支持。",
}


class UserFriendlyMessageGenerator:
    """用户友好消息生成器"""

    def __init__(self, templates: dict[ErrorCategory, str] | None = None) -> None:
        """初始化生成器

        参数:
            templates: 自定义模板
        """
        self.templates = {**USER_FRIENDLY_TEMPLATES}
        if templates:
            self.templates.update(templates)

    def generate(self, category: ErrorCategory, details: str = "") -> str:
        """生成用户友好消息

        参数:
            category: 错误分类
            details: 详细信息

        返回:
            用户友好的消息
        """
        template = self.templates.get(category, USER_FRIENDLY_TEMPLATES[ErrorCategory.UNKNOWN])
        return template.format(details=details)


# ============================================================================
# 用户操作选项
# ============================================================================


@dataclass
class UserActionOption:
    """用户操作选项"""

    action: str
    label: str
    description: str = ""


# 错误分类到用户操作选项的映射
CATEGORY_OPTIONS: dict[ErrorCategory, list[UserActionOption]] = {
    ErrorCategory.TIMEOUT: [
        UserActionOption("retry", "重试", "等待后重新尝试"),
        UserActionOption("skip", "跳过", "跳过此步骤继续"),
        UserActionOption("abort", "终止", "停止整个流程"),
    ],
    ErrorCategory.DATA_MISSING: [
        UserActionOption("provide_data", "提供数据", "手动输入缺失的数据"),
        UserActionOption("skip", "跳过", "跳过此步骤"),
        UserActionOption("abort", "终止", "停止整个流程"),
    ],
    ErrorCategory.NODE_CRASH: [
        UserActionOption("retry", "重试", "重新执行此步骤"),
        UserActionOption("skip", "跳过", "跳过此步骤继续"),
        UserActionOption("abort", "终止", "停止整个流程"),
    ],
    ErrorCategory.API_FAILURE: [
        UserActionOption("retry", "重试", "重新调用服务"),
        UserActionOption("skip", "跳过", "跳过此步骤"),
        UserActionOption("abort", "终止", "停止整个流程"),
    ],
    ErrorCategory.VALIDATION_ERROR: [
        UserActionOption("provide_data", "修正数据", "提供正确格式的数据"),
        UserActionOption("skip", "跳过", "跳过此步骤"),
        UserActionOption("abort", "终止", "停止整个流程"),
    ],
}


class UserActionOptionsGenerator:
    """用户操作选项生成器"""

    def get_options(self, category: ErrorCategory) -> list[UserActionOption]:
        """获取用户操作选项

        参数:
            category: 错误分类

        返回:
            可用的操作选项列表
        """
        options = CATEGORY_OPTIONS.get(
            category,
            [
                UserActionOption("retry", "重试", "重新尝试"),
                UserActionOption("abort", "终止", "停止整个流程"),
            ],
        )

        # 确保总是有 abort 选项
        if not any(opt.action == "abort" for opt in options):
            options = list(options)  # 避免修改原列表
            options.append(UserActionOption("abort", "终止", "停止整个流程"))

        return options


# ============================================================================
# 用户决策和响应
# ============================================================================


@dataclass
class UserDecision:
    """用户决策"""

    action: str
    node_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserResponse:
    """用户响应"""

    action: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserDecisionResult:
    """用户决策处理结果"""

    action_taken: str
    should_continue: bool = True
    node_skipped: bool = False
    workflow_aborted: bool = False


@dataclass
class FormattedError:
    """格式化的错误信息"""

    message: str
    options: list[UserActionOption]
    category: ErrorCategory | None = None


# ============================================================================
# 恢复计划
# ============================================================================


@dataclass
class RecoveryPlan:
    """恢复计划"""

    node_id: str
    category: ErrorCategory
    action: RecoveryAction
    delay: float = 0.0
    awaiting_user_input: bool = False
    ready_to_retry: bool = False
    supplemental_data: dict[str, Any] = field(default_factory=dict)
    escalated: bool = False


class ErrorRecoveryHandler:
    """错误恢复处理器

    综合错误分类和恢复策略，创建恢复计划。
    """

    def __init__(
        self,
        max_retries: int = 3,
        classifier: ExceptionClassifier | None = None,
        strategy_mapper: RecoveryStrategyMapper | None = None,
        backoff_calculator: BackoffCalculator | None = None,
    ) -> None:
        """初始化处理器

        参数:
            max_retries: 最大重试次数
            classifier: 异常分类器
            strategy_mapper: 策略映射器
            backoff_calculator: 退避计算器
        """
        self.max_retries = max_retries
        self.classifier = classifier or ExceptionClassifier()
        self.strategy_mapper = strategy_mapper or RecoveryStrategyMapper()
        self.backoff_calculator = backoff_calculator or BackoffCalculator()
        self._attempt_counts: dict[str, int] = {}

    def create_recovery_plan(
        self, node_id: str, error: Exception, attempt: int = 0
    ) -> RecoveryPlan:
        """创建恢复计划

        参数:
            node_id: 节点ID
            error: 异常
            attempt: 当前尝试次数

        返回:
            恢复计划
        """
        category = self.classifier.classify(error)
        action = self.strategy_mapper.get_recovery_action(category)

        # 更新尝试次数
        self._attempt_counts[node_id] = attempt

        # 检查是否需要升级处理
        escalated = False
        if attempt >= self.max_retries and action in (
            RecoveryAction.RETRY,
            RecoveryAction.RETRY_WITH_BACKOFF,
        ):
            action = RecoveryAction.ASK_USER
            escalated = True

        # 计算延迟（如果需要）
        delay = 0.0
        if action == RecoveryAction.RETRY_WITH_BACKOFF:
            delay = self.backoff_calculator.get_delay(attempt)

        # 判断是否需要用户输入
        awaiting_user_input = action == RecoveryAction.ASK_USER

        return RecoveryPlan(
            node_id=node_id,
            category=category,
            action=action,
            delay=delay,
            awaiting_user_input=awaiting_user_input,
            escalated=escalated,
        )

    def apply_user_response(self, plan: RecoveryPlan, response: UserResponse) -> RecoveryPlan:
        """应用用户响应更新恢复计划

        参数:
            plan: 原恢复计划
            response: 用户响应

        返回:
            更新后的恢复计划
        """
        if response.action == "provide_data":
            return RecoveryPlan(
                node_id=plan.node_id,
                category=plan.category,
                action=RecoveryAction.RETRY,
                ready_to_retry=True,
                supplemental_data=response.data,
            )
        elif response.action == "retry":
            return RecoveryPlan(
                node_id=plan.node_id,
                category=plan.category,
                action=RecoveryAction.RETRY,
                ready_to_retry=True,
            )
        elif response.action == "skip":
            return RecoveryPlan(
                node_id=plan.node_id,
                category=plan.category,
                action=RecoveryAction.SKIP,
            )
        elif response.action == "abort":
            return RecoveryPlan(
                node_id=plan.node_id,
                category=plan.category,
                action=RecoveryAction.ABORT,
            )
        else:
            return plan


# ============================================================================
# 错误对话管理器
# ============================================================================


@dataclass
class DialogueState:
    """对话状态"""

    node_id: str
    node_name: str
    error_explanation: str
    awaiting_user_response: bool = False
    user_chose_retry: bool = False
    supplemental_data: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_method: str = ""


class ErrorDialogueManager:
    """错误对话管理器

    管理错误发生后与用户的对话流程。
    """

    def __init__(self, conversation_agent: Any) -> None:
        """初始化管理器

        参数:
            conversation_agent: 对话代理
        """
        self.agent = conversation_agent
        self.current_state: DialogueState | None = None
        self.classifier = ExceptionClassifier()
        self.message_generator = UserFriendlyMessageGenerator()

    async def start_error_dialogue(
        self, node_id: str, node_name: str, error: Exception
    ) -> DialogueState:
        """开始错误对话

        参数:
            node_id: 节点ID
            node_name: 节点名称
            error: 异常

        返回:
            对话状态
        """
        category = self.classifier.classify(error)
        explanation = self.message_generator.generate(category, str(error))

        self.current_state = DialogueState(
            node_id=node_id,
            node_name=node_name,
            error_explanation=explanation,
            awaiting_user_response=True,
        )

        return self.current_state

    async def process_user_response(self, decision: UserDecision) -> DialogueState:
        """处理用户响应

        参数:
            decision: 用户决策

        返回:
            更新后的对话状态
        """
        if self.current_state is None:
            raise ValueError("No active error dialogue")

        if decision.action == "retry":
            self.current_state.user_chose_retry = True
            self.current_state.awaiting_user_response = False
        elif decision.action == "provide_data":
            self.current_state.supplemental_data = decision.data
            self.current_state.awaiting_user_response = False

        return self.current_state

    async def complete_recovery(self, success: bool, result: Any = None) -> DialogueState:
        """完成恢复

        参数:
            success: 是否成功
            result: 结果

        返回:
            最终对话状态
        """
        if self.current_state is None:
            raise ValueError("No active error dialogue")

        self.current_state.resolved = success
        self.current_state.resolution_method = (
            "retry" if self.current_state.user_chose_retry else "skip"
        )

        return self.current_state


# ============================================================================
# 错误事件
# ============================================================================


@dataclass
class NodeErrorEvent(Event):
    """节点错误事件"""

    node_id: str = ""
    error_type: str = ""
    error_message: str = ""
    recovery_action: str = ""
    error_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RecoveryCompleteEvent(Event):
    """恢复完成事件"""

    node_id: str = ""
    success: bool = False
    recovery_method: str = ""
    attempts: int = 0
    recovery_timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# 错误日志
# ============================================================================


@dataclass
class ErrorLogEntry:
    """错误日志条目"""

    node_id: str
    workflow_id: str
    error_type: str
    error_message: str
    timestamp: datetime
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryLogEntry:
    """恢复日志条目"""

    node_id: str
    action: RecoveryAction
    attempt: int
    success: bool
    next_action: RecoveryAction | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class ErrorLogger:
    """错误日志记录器"""

    def __init__(self) -> None:
        """初始化日志记录器"""
        self.error_logs: list[ErrorLogEntry] = []
        self.recovery_logs: list[RecoveryLogEntry] = []

    def log_error(
        self,
        node_id: str,
        workflow_id: str,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> ErrorLogEntry:
        """记录错误

        参数:
            node_id: 节点ID
            workflow_id: 工作流ID
            error: 异常
            context: 上下文信息

        返回:
            日志条目
        """
        entry = ErrorLogEntry(
            node_id=node_id,
            workflow_id=workflow_id,
            error_type=type(error).__name__,
            error_message=str(error),
            timestamp=datetime.now(),
            context=context or {},
        )
        self.error_logs.append(entry)
        return entry

    def log_recovery_attempt(
        self,
        node_id: str,
        action: RecoveryAction,
        attempt: int,
        success: bool,
        next_action: RecoveryAction | None = None,
    ) -> RecoveryLogEntry:
        """记录恢复尝试

        参数:
            node_id: 节点ID
            action: 恢复动作
            attempt: 尝试次数
            success: 是否成功
            next_action: 下一步动作

        返回:
            日志条目
        """
        entry = RecoveryLogEntry(
            node_id=node_id,
            action=action,
            attempt=attempt,
            success=success,
            next_action=next_action,
        )
        self.recovery_logs.append(entry)
        return entry
