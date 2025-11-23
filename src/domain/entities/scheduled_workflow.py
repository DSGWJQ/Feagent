"""ScheduledWorkflow 实体 - 定时工作流

定义定时执行的工作流配置和状态管理
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.domain.exceptions import DomainError


@dataclass
class ScheduledWorkflow:
    """定时工作流实体

    职责：
    - 维护定时工作流的配置（workflow_id, cron_expression）
    - 管理执行状态和历史
    - 验证 cron 表达式
    - 计算下次执行时间
    """

    id: str
    workflow_id: str
    cron_expression: str
    max_retries: int
    status: str = "active"  # active, disabled, paused
    consecutive_failures: int = 0
    last_execution_at: datetime | None = None
    last_execution_status: str | None = None
    last_error_message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def create(
        workflow_id: str,
        cron_expression: str,
        max_retries: int = 3,
    ) -> "ScheduledWorkflow":
        """创建新的定时工作流

        参数：
            workflow_id: 关联的工作流ID
            cron_expression: Cron 表达式（例：'0 9 * * MON-FRI'）
            max_retries: 最大重试次数

        返回：
            ScheduledWorkflow 实例

        抛出：
            DomainError: 如果参数无效
        """
        # 验证输入
        if not workflow_id or not workflow_id.strip():
            raise DomainError("workflow_id 不能为空")

        if not cron_expression or not cron_expression.strip():
            raise DomainError("cron_expression 不能为空")

        if not ScheduledWorkflow._validate_cron_expression(cron_expression):
            raise DomainError(f"无效的 cron 表达式：{cron_expression}")

        if max_retries < 0:
            raise DomainError("max_retries 不能为负数")

        return ScheduledWorkflow(
            id=f"scheduled_{uuid4().hex[:8]}",
            workflow_id=workflow_id,
            cron_expression=cron_expression,
            max_retries=max_retries,
            status="active",
        )

    def disable(self) -> None:
        """禁用定时工作流

        抛出：
            DomainError: 如果已经禁用
        """
        if self.status == "disabled":
            raise DomainError("该定时工作流已经被禁用")

        self.status = "disabled"
        self.updated_at = datetime.now(UTC)

    def enable(self) -> None:
        """启用定时工作流

        抛出：
            DomainError: 如果已经启用
        """
        if self.status == "active":
            raise DomainError("该定时工作流已经处于启用状态")

        self.status = "active"
        self.consecutive_failures = 0
        self.updated_at = datetime.now(UTC)

    def record_execution_success(self) -> None:
        """记录成功的执行"""
        self.last_execution_at = datetime.now(UTC)
        self.last_execution_status = "success"
        self.consecutive_failures = 0
        self.last_error_message = ""
        self.updated_at = datetime.now(UTC)

    def record_execution_failure(self, error_message: str) -> None:
        """记录失败的执行

        参数：
            error_message: 错误信息

        自动禁用：当连续失败次数超过 max_retries 时自动禁用
        """
        self.last_execution_at = datetime.now(UTC)
        self.last_execution_status = "failure"
        self.consecutive_failures += 1
        self.last_error_message = error_message
        self.updated_at = datetime.now(UTC)

        # 如果超过最大重试次数，自动禁用
        if self.consecutive_failures > self.max_retries:
            self.status = "disabled"

    def get_next_execution_time(self) -> datetime:
        """计算下次执行时间

        返回：
            下次执行的时间
        """
        return self._calculate_next_cron_time()

    @staticmethod
    def _validate_cron_expression(cron_expr: str) -> bool:
        """验证 cron 表达式的有效性

        支持标准的 5 字段 cron 格式：
        minute hour day month weekday

        支持的缩写：
        - 月份: JAN, FEB, MAR, APR, MAY, JUN, JUL, AUG, SEP, OCT, NOV, DEC
        - 星期: SUN, MON, TUE, WED, THU, FRI, SAT

        参数：
            cron_expr: Cron 表达式

        返回：
            True 如果有效，False 否则
        """
        # 基础检查：5 个字段
        parts = cron_expr.split()
        if len(parts) != 5:
            return False

        minute, hour, day, month, weekday = parts

        # 先转换缩写
        month = ScheduledWorkflow._convert_month_abbr(month)
        weekday = ScheduledWorkflow._convert_weekday_abbr(weekday)

        # 验证各字段的范围
        try:
            ScheduledWorkflow._validate_cron_field(minute, 0, 59, "minute")
            ScheduledWorkflow._validate_cron_field(hour, 0, 23, "hour")
            ScheduledWorkflow._validate_cron_field(day, 1, 31, "day")
            ScheduledWorkflow._validate_cron_field(month, 1, 12, "month")
            ScheduledWorkflow._validate_cron_field(weekday, 0, 6, "weekday")
            return True
        except Exception:
            return False

    @staticmethod
    def _convert_month_abbr(month_field: str) -> str:
        """转换月份缩写为数字

        参数：
            month_field: 月份字段

        返回：
            转换后的字段
        """
        month_map = {
            "JAN": "1",
            "FEB": "2",
            "MAR": "3",
            "APR": "4",
            "MAY": "5",
            "JUN": "6",
            "JUL": "7",
            "AUG": "8",
            "SEP": "9",
            "OCT": "10",
            "NOV": "11",
            "DEC": "12",
        }

        result = month_field.upper()
        for abbr, num in month_map.items():
            result = result.replace(abbr, num)

        return result

    @staticmethod
    def _convert_weekday_abbr(weekday_field: str) -> str:
        """转换星期缩写为数字（0=Sunday, 6=Saturday）

        参数：
            weekday_field: 星期字段

        返回：
            转换后的字段
        """
        weekday_map = {
            "SUN": "0",
            "MON": "1",
            "TUE": "2",
            "WED": "3",
            "THU": "4",
            "FRI": "5",
            "SAT": "6",
        }

        result = weekday_field.upper()
        for abbr, num in weekday_map.items():
            result = result.replace(abbr, num)

        return result

    @staticmethod
    def _validate_cron_field(field: str, min_val: int, max_val: int, name: str) -> bool:
        """验证单个 cron 字段

        参数：
            field: 字段值
            min_val: 最小值
            max_val: 最大值
            name: 字段名称

        返回：
            True 如果有效

        抛出：
            ValueError: 如果无效
        """
        if field == "*":
            return True

        if field.startswith("*/"):
            try:
                step = int(field[2:])
                if step <= 0:
                    raise ValueError(f"无效的步长：{step}")
                return True
            except (ValueError, IndexError) as e:
                raise ValueError(f"无效的 {name} 字段：{field}") from e

        if "-" in field:
            try:
                parts = field.split("-")
                if len(parts) != 2:
                    raise ValueError()
                start, end = int(parts[0]), int(parts[1])
                if not (min_val <= start <= max_val and min_val <= end <= max_val):
                    raise ValueError()
                return True
            except (ValueError, IndexError) as e:
                raise ValueError(f"无效的 {name} 范围：{field}") from e

        # 逗号分隔的列表
        if "," in field:
            for part in field.split(","):
                if not part.isdigit():
                    raise ValueError(f"无效的 {name} 列表：{field}")
                val = int(part)
                if not (min_val <= val <= max_val):
                    raise ValueError(f"{name} 超出范围：{val}")
            return True

        # 单个数字
        try:
            val = int(field)
            if not (min_val <= val <= max_val):
                raise ValueError(f"{name} 超出范围：{val}")
            return True
        except ValueError as e:
            raise ValueError(f"无效的 {name} 字段：{field}") from e

    def _calculate_next_cron_time(self) -> datetime:
        """根据 cron 表达式计算下次执行时间

        简化实现：仅支持基础的 cron 模式

        返回：
            下次执行时间
        """
        parts = self.cron_expression.split()
        minute, hour, day, month, weekday = parts

        now = datetime.now(UTC)

        # 简化实现：迭代查找下一个匹配的时间
        # 这是一个基础实现，可以扩展以支持更复杂的 cron 表达式
        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # 最多搜索 1 个月内的时间
        for _ in range(60 * 24 * 31):
            if self._matches_cron_time(candidate, minute, hour, day, month, weekday):
                return candidate
            candidate += timedelta(minutes=1)

        # 如果没找到，返回 1 小时后
        return now + timedelta(hours=1)

    def _matches_cron_time(
        self,
        dt: datetime,
        minute_pattern: str,
        hour_pattern: str,
        day_pattern: str,
        month_pattern: str,
        weekday_pattern: str,
    ) -> bool:
        """检查时间是否匹配 cron 模式

        参数：
            dt: 要检查的时间
            minute_pattern: 分钟模式
            hour_pattern: 小时模式
            day_pattern: 日期模式
            month_pattern: 月份模式
            weekday_pattern: 周日期模式

        返回：
            True 如果匹配
        """
        # 转换缩写
        month_pattern = ScheduledWorkflow._convert_month_abbr(month_pattern)
        weekday_pattern = ScheduledWorkflow._convert_weekday_abbr(weekday_pattern)

        return (
            self._matches_field(dt.minute, minute_pattern, 0, 59)
            and self._matches_field(dt.hour, hour_pattern, 0, 23)
            and self._matches_field(dt.day, day_pattern, 1, 31)
            and self._matches_field(dt.month, month_pattern, 1, 12)
            and self._matches_field(dt.weekday(), weekday_pattern, 0, 6)
        )

    @staticmethod
    def _matches_field(value: int, pattern: str, min_val: int, max_val: int) -> bool:
        """检查值是否匹配 cron 字段模式

        参数：
            value: 要检查的值
            pattern: Cron 模式
            min_val: 最小值
            max_val: 最大值

        返回：
            True 如果匹配
        """
        if pattern == "*":
            return True

        if pattern.startswith("*/"):
            step = int(pattern[2:])
            return value % step == 0

        if "-" in pattern and "," not in pattern:
            start, end = map(int, pattern.split("-"))
            return start <= value <= end

        if "," in pattern:
            values = [int(v) for v in pattern.split(",")]
            return value in values

        try:
            return value == int(pattern)
        except ValueError:
            return False
