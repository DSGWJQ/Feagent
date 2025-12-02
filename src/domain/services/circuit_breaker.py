"""熔断器 (Circuit Breaker) - 阶段 5

业务定义：
- 保护系统免受级联故障影响
- 当失败率过高时自动熔断
- 支持半开状态的自动恢复

状态机：
- CLOSED: 正常状态，请求正常通过
- OPEN: 熔断状态，请求被拒绝
- HALF_OPEN: 半开状态，允许有限请求测试恢复

设计原则：
- 故障隔离：快速失败避免资源浪费
- 自动恢复：超时后自动尝试恢复
- 可观测性：提供状态查询和事件通知
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class CircuitState(str, Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 关闭（正常）
    OPEN = "open"  # 打开（熔断）
    HALF_OPEN = "half_open"  # 半开（恢复测试）


class CircuitBreakerOpenError(Exception):
    """熔断器已打开异常"""

    pass


@dataclass
class CircuitBreakerConfig:
    """熔断器配置

    属性：
    - failure_threshold: 连续失败次数阈值
    - recovery_timeout: 恢复超时时间（秒）
    - half_open_requests: 半开状态允许的请求数
    - success_threshold: 半开状态成功次数阈值（恢复到关闭）
    """

    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_requests: int = 3
    success_threshold: int = 2


@dataclass
class CircuitBreakerMetrics:
    """熔断器指标

    记录熔断器的运行状态。
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    state_changes: list[dict[str, Any]] = field(default_factory=list)


class CircuitBreaker:
    """熔断器

    职责：
    1. 跟踪请求成功/失败
    2. 根据阈值切换状态
    3. 在熔断状态下拒绝请求
    4. 自动恢复机制

    使用示例：
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config)

        try:
            breaker.check_state()
            # 执行操作
            breaker.record_success()
        except CircuitBreakerOpenError:
            # 熔断器打开，快速失败
            pass
        except Exception:
            breaker.record_failure()
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """初始化熔断器

        参数：
            config: 熔断器配置
        """
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._last_failure_time: datetime | None = None
        self._metrics = CircuitBreakerMetrics()

    @property
    def state(self) -> str:
        """获取当前状态

        如果是 OPEN 状态且已过恢复时间，自动转为 HALF_OPEN。
        """
        if self._state == CircuitState.OPEN and self._should_attempt_recovery():
            self._transition_to(CircuitState.HALF_OPEN)

        return self._state.value

    @property
    def is_open(self) -> bool:
        """检查熔断器是否打开"""
        # 触发状态检查（可能转为 HALF_OPEN）
        current_state = self.state
        return current_state == CircuitState.OPEN.value

    def check_state(self) -> None:
        """检查状态，如果熔断则抛出异常

        异常：
            CircuitBreakerOpenError: 熔断器已打开
        """
        current_state = self.state

        if current_state == CircuitState.OPEN.value:
            self._metrics.rejected_requests += 1
            raise CircuitBreakerOpenError("熔断器已打开，请求被拒绝")

        if current_state == CircuitState.HALF_OPEN.value:
            # 半开状态，限制请求数
            if self._half_open_requests >= self.config.half_open_requests:
                self._metrics.rejected_requests += 1
                raise CircuitBreakerOpenError("熔断器半开状态，超过允许的请求数")
            self._half_open_requests += 1

        self._metrics.total_requests += 1

    def record_success(self) -> None:
        """记录成功请求"""
        self._metrics.successful_requests += 1

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        else:
            # 重置失败计数
            self._failure_count = 0

    def record_failure(self) -> None:
        """记录失败请求"""
        self._metrics.failed_requests += 1
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._state == CircuitState.HALF_OPEN:
            # 半开状态下失败，立即打开
            self._transition_to(CircuitState.OPEN)
        elif self._failure_count >= self.config.failure_threshold:
            # 达到阈值，打开熔断器
            self._transition_to(CircuitState.OPEN)

    def reset(self) -> None:
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._last_failure_time = None

    def get_metrics(self) -> dict[str, Any]:
        """获取指标"""
        return {
            "state": self.state,
            "total_requests": self._metrics.total_requests,
            "successful_requests": self._metrics.successful_requests,
            "failed_requests": self._metrics.failed_requests,
            "rejected_requests": self._metrics.rejected_requests,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
        }

    def _should_attempt_recovery(self) -> bool:
        """检查是否应该尝试恢复"""
        if self._last_failure_time is None:
            return True

        recovery_time = self._last_failure_time + timedelta(seconds=self.config.recovery_timeout)
        return datetime.now() >= recovery_time

    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转换"""
        old_state = self._state
        self._state = new_state

        # 记录状态变化
        self._metrics.state_changes.append(
            {
                "from": old_state.value,
                "to": new_state.value,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # 重置计数器
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_requests = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._half_open_requests = 0
        elif new_state == CircuitState.OPEN:
            self._last_failure_time = datetime.now()


# 导出
__all__ = [
    "CircuitState",
    "CircuitBreakerOpenError",
    "CircuitBreakerConfig",
    "CircuitBreakerMetrics",
    "CircuitBreaker",
]
