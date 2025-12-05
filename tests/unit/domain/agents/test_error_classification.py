"""错误分类测试 - 第五步：异常处理与重规划

测试错误分类枚举和异常到分类的映射逻辑。
遵循 TDD 流程，先编写测试，再实现功能。
"""


class TestErrorCategory:
    """测试错误分类枚举"""

    def test_error_category_should_have_data_missing(self):
        """ErrorCategory 应该包含 DATA_MISSING 分类

        场景：数据源返回空值或节点输入缺失
        期望：有明确的 DATA_MISSING 分类
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert hasattr(ErrorCategory, "DATA_MISSING")
        assert ErrorCategory.DATA_MISSING.value == "data_missing"

    def test_error_category_should_have_node_crash(self):
        """ErrorCategory 应该包含 NODE_CRASH 分类

        场景：节点执行时抛出未捕获异常导致崩溃
        期望：有明确的 NODE_CRASH 分类
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert hasattr(ErrorCategory, "NODE_CRASH")
        assert ErrorCategory.NODE_CRASH.value == "node_crash"

    def test_error_category_should_have_api_failure(self):
        """ErrorCategory 应该包含 API_FAILURE 分类

        场景：调用外部 API 返回错误状态码
        期望：有明确的 API_FAILURE 分类
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert hasattr(ErrorCategory, "API_FAILURE")
        assert ErrorCategory.API_FAILURE.value == "api_failure"

    def test_error_category_should_have_timeout(self):
        """ErrorCategory 应该包含 TIMEOUT 分类

        场景：节点执行超过配置的超时时间
        期望：有明确的 TIMEOUT 分类
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert hasattr(ErrorCategory, "TIMEOUT")
        assert ErrorCategory.TIMEOUT.value == "timeout"

    def test_error_category_should_have_validation_error(self):
        """ErrorCategory 应该包含 VALIDATION_ERROR 分类

        场景：输入数据格式或类型验证失败
        期望：有明确的 VALIDATION_ERROR 分类
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert hasattr(ErrorCategory, "VALIDATION_ERROR")
        assert ErrorCategory.VALIDATION_ERROR.value == "validation"

    def test_error_category_should_have_dependency_error(self):
        """ErrorCategory 应该包含 DEPENDENCY_ERROR 分类

        场景：依赖节点失败导致当前节点无法执行
        期望：有明确的 DEPENDENCY_ERROR 分类
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert hasattr(ErrorCategory, "DEPENDENCY_ERROR")
        assert ErrorCategory.DEPENDENCY_ERROR.value == "dependency"

    def test_error_category_should_have_rate_limited(self):
        """ErrorCategory 应该包含 RATE_LIMITED 分类

        场景：API 调用触发限流
        期望：有明确的 RATE_LIMITED 分类
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert hasattr(ErrorCategory, "RATE_LIMITED")
        assert ErrorCategory.RATE_LIMITED.value == "rate_limit"


class TestExceptionClassifier:
    """测试异常分类器"""

    def test_classify_timeout_error(self):
        """TimeoutError 应该分类为 TIMEOUT

        场景：节点执行超时抛出 TimeoutError
        期望：分类为 TIMEOUT
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()
        error = TimeoutError("Operation timed out")

        category = classifier.classify(error)

        assert category == ErrorCategory.TIMEOUT

    def test_classify_connection_error(self):
        """ConnectionError 应该分类为 API_FAILURE

        场景：网络连接失败
        期望：分类为 API_FAILURE
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()
        error = ConnectionError("Connection refused")

        category = classifier.classify(error)

        assert category == ErrorCategory.API_FAILURE

    def test_classify_value_error_as_validation(self):
        """ValueError 应该分类为 VALIDATION_ERROR

        场景：输入数据格式错误
        期望：分类为 VALIDATION_ERROR
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()
        error = ValueError("Invalid input format")

        category = classifier.classify(error)

        assert category == ErrorCategory.VALIDATION_ERROR

    def test_classify_key_error_as_data_missing(self):
        """KeyError 应该分类为 DATA_MISSING

        场景：访问不存在的字典键
        期望：分类为 DATA_MISSING
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()
        error = KeyError("missing_field")

        category = classifier.classify(error)

        assert category == ErrorCategory.DATA_MISSING

    def test_classify_runtime_error_as_node_crash(self):
        """RuntimeError 应该分类为 NODE_CRASH

        场景：运行时意外错误
        期望：分类为 NODE_CRASH
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()
        error = RuntimeError("Unexpected runtime error")

        category = classifier.classify(error)

        assert category == ErrorCategory.NODE_CRASH

    def test_classify_memory_error_as_resource_exhausted(self):
        """MemoryError 应该分类为 RESOURCE_EXHAUSTED

        场景：内存不足
        期望：分类为 RESOURCE_EXHAUSTED
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()
        error = MemoryError("Out of memory")

        category = classifier.classify(error)

        assert category == ErrorCategory.RESOURCE_EXHAUSTED

    def test_classify_permission_error(self):
        """PermissionError 应该分类为 PERMISSION_DENIED

        场景：权限不足
        期望：分类为 PERMISSION_DENIED
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()
        error = PermissionError("Access denied")

        category = classifier.classify(error)

        assert category == ErrorCategory.PERMISSION_DENIED

    def test_classify_unknown_error(self):
        """未知异常应该分类为 UNKNOWN

        场景：自定义异常或其他未映射的异常
        期望：分类为 UNKNOWN
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ExceptionClassifier,
        )

        classifier = ExceptionClassifier()

        class CustomException(Exception):
            pass

        error = CustomException("Custom error")

        category = classifier.classify(error)

        assert category == ErrorCategory.UNKNOWN

    def test_classifier_with_error_message_context(self):
        """分类器应该能根据错误消息提供额外上下文

        场景：分类时需要保留原始错误消息
        期望：返回包含分类和消息的结果
        """
        from src.domain.agents.error_handling import ExceptionClassifier

        classifier = ExceptionClassifier()
        error = TimeoutError("API call to /users timed out after 30s")

        result = classifier.classify_with_context(error)

        assert result.category is not None
        assert result.original_message == "API call to /users timed out after 30s"
        assert result.exception_type == "TimeoutError"


class TestErrorCategoryProperties:
    """测试错误分类的属性和方法"""

    def test_is_retryable_for_timeout(self):
        """TIMEOUT 应该是可重试的

        场景：超时错误通常是临时性的
        期望：is_retryable() 返回 True
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.TIMEOUT.is_retryable() is True

    def test_is_retryable_for_api_failure(self):
        """API_FAILURE 应该是可重试的

        场景：API 故障可能是暂时的
        期望：is_retryable() 返回 True
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.API_FAILURE.is_retryable() is True

    def test_is_retryable_for_rate_limited(self):
        """RATE_LIMITED 应该是可重试的

        场景：限流后等待一段时间可以重试
        期望：is_retryable() 返回 True
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.RATE_LIMITED.is_retryable() is True

    def test_is_not_retryable_for_validation_error(self):
        """VALIDATION_ERROR 不应该自动重试

        场景：数据格式错误重试也不会成功
        期望：is_retryable() 返回 False
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.VALIDATION_ERROR.is_retryable() is False

    def test_is_not_retryable_for_data_missing(self):
        """DATA_MISSING 不应该自动重试

        场景：缺失数据需要人工干预
        期望：is_retryable() 返回 False
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.DATA_MISSING.is_retryable() is False

    def test_requires_user_intervention_for_data_missing(self):
        """DATA_MISSING 需要用户干预

        场景：缺失数据需要用户提供
        期望：requires_user_intervention() 返回 True
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.DATA_MISSING.requires_user_intervention() is True

    def test_requires_user_intervention_for_validation_error(self):
        """VALIDATION_ERROR 需要用户干预

        场景：数据格式错误需要用户修正
        期望：requires_user_intervention() 返回 True
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.VALIDATION_ERROR.requires_user_intervention() is True

    def test_not_requires_user_intervention_for_timeout(self):
        """TIMEOUT 不需要用户干预

        场景：超时可以自动重试
        期望：requires_user_intervention() 返回 False
        """
        from src.domain.agents.error_handling import ErrorCategory

        assert ErrorCategory.TIMEOUT.requires_user_intervention() is False
