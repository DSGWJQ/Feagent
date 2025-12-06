"""知识库维护模块测试 (TDD - Step 8)

测试内容：
1. LongTermMemory - 长期记忆（跨会话持久化知识）
2. UserPreference - 用户偏好（个人习惯、风格偏好）
3. SuccessfulSolution - 成功解法（已验证的解决方案）
4. FailureCase - 失败案例（记录失败原因与教训）
5. KnowledgeMaintainer - 知识维护器（从事件更新知识库）
6. SolutionRetriever - 解法检索器（相似任务复用）

完成标准：
- 文档扩充"知识库维护"说明，包含 schema、更新触发条件、复用策略
- 单元测试覆盖记录添加/查询
- 示例演示 Coordinator 在类似任务中复用成功方案
"""


# ==================== 1. LongTermMemory 长期记忆测试 ====================


class TestLongTermMemory:
    """长期记忆数据结构测试"""

    def test_create_long_term_memory(self):
        """测试：创建长期记忆"""
        from src.domain.services.knowledge_maintenance import (
            LongTermMemory,
            MemoryCategory,
        )

        memory = LongTermMemory(
            memory_id="mem_001",
            category=MemoryCategory.FACT,
            content="用户喜欢简洁的代码风格",
            source="conversation_session_abc",
            confidence=0.85,
        )

        assert memory.memory_id == "mem_001"
        assert memory.category == MemoryCategory.FACT
        assert memory.content == "用户喜欢简洁的代码风格"
        assert memory.confidence == 0.85
        assert memory.access_count == 0

    def test_memory_categories(self):
        """测试：记忆类别枚举"""
        from src.domain.services.knowledge_maintenance import MemoryCategory

        assert MemoryCategory.FACT.value == "fact"
        assert MemoryCategory.PROCEDURE.value == "procedure"
        assert MemoryCategory.CONTEXT.value == "context"
        assert MemoryCategory.SKILL.value == "skill"

    def test_memory_with_metadata(self):
        """测试：带元数据的记忆"""
        from src.domain.services.knowledge_maintenance import (
            LongTermMemory,
            MemoryCategory,
        )

        memory = LongTermMemory(
            memory_id="mem_002",
            category=MemoryCategory.PROCEDURE,
            content="部署流程：先运行测试，再构建，最后部署",
            source="workflow_deploy_001",
            confidence=0.95,
            metadata={
                "domain": "devops",
                "complexity": "medium",
                "verified_times": 5,
            },
        )

        assert memory.metadata["domain"] == "devops"
        assert memory.metadata["verified_times"] == 5

    def test_memory_increment_access(self):
        """测试：增加访问计数"""
        from src.domain.services.knowledge_maintenance import (
            LongTermMemory,
            MemoryCategory,
        )

        memory = LongTermMemory(
            memory_id="mem_003",
            category=MemoryCategory.FACT,
            content="测试内容",
            source="test",
            confidence=0.8,
        )

        assert memory.access_count == 0
        memory.increment_access()
        assert memory.access_count == 1
        memory.increment_access()
        assert memory.access_count == 2

    def test_memory_update_confidence(self):
        """测试：更新置信度"""
        from src.domain.services.knowledge_maintenance import (
            LongTermMemory,
            MemoryCategory,
        )

        memory = LongTermMemory(
            memory_id="mem_004",
            category=MemoryCategory.SKILL,
            content="Python 编程技能",
            source="test",
            confidence=0.7,
        )

        memory.update_confidence(0.9)
        assert memory.confidence == 0.9

    def test_memory_to_dict(self):
        """测试：记忆转字典"""
        from src.domain.services.knowledge_maintenance import (
            LongTermMemory,
            MemoryCategory,
        )

        memory = LongTermMemory(
            memory_id="mem_005",
            category=MemoryCategory.CONTEXT,
            content="项目使用 Python 3.11",
            source="project_config",
            confidence=1.0,
        )

        data = memory.to_dict()

        assert data["memory_id"] == "mem_005"
        assert data["category"] == "context"
        assert data["content"] == "项目使用 Python 3.11"
        assert data["confidence"] == 1.0


# ==================== 2. UserPreference 用户偏好测试 ====================


class TestUserPreference:
    """用户偏好数据结构测试"""

    def test_create_user_preference(self):
        """测试：创建用户偏好"""
        from src.domain.services.knowledge_maintenance import (
            PreferenceType,
            UserPreference,
        )

        pref = UserPreference(
            preference_id="pref_001",
            user_id="user_abc",
            preference_type=PreferenceType.CODING_STYLE,
            key="indentation",
            value="4_spaces",
        )

        assert pref.preference_id == "pref_001"
        assert pref.user_id == "user_abc"
        assert pref.preference_type == PreferenceType.CODING_STYLE
        assert pref.key == "indentation"
        assert pref.value == "4_spaces"

    def test_preference_types(self):
        """测试：偏好类型枚举"""
        from src.domain.services.knowledge_maintenance import PreferenceType

        assert PreferenceType.CODING_STYLE.value == "coding_style"
        assert PreferenceType.OUTPUT_FORMAT.value == "output_format"
        assert PreferenceType.COMMUNICATION.value == "communication"
        assert PreferenceType.WORKFLOW.value == "workflow"
        assert PreferenceType.TOOL_USAGE.value == "tool_usage"

    def test_preference_with_priority(self):
        """测试：带优先级的偏好"""
        from src.domain.services.knowledge_maintenance import (
            PreferenceType,
            UserPreference,
        )

        pref = UserPreference(
            preference_id="pref_002",
            user_id="user_abc",
            preference_type=PreferenceType.OUTPUT_FORMAT,
            key="report_format",
            value="markdown",
            priority=10,  # 高优先级
        )

        assert pref.priority == 10

    def test_preference_update_value(self):
        """测试：更新偏好值"""
        from src.domain.services.knowledge_maintenance import (
            PreferenceType,
            UserPreference,
        )

        pref = UserPreference(
            preference_id="pref_003",
            user_id="user_abc",
            preference_type=PreferenceType.COMMUNICATION,
            key="language",
            value="formal",
        )

        pref.update_value("casual")
        assert pref.value == "casual"
        assert pref.updated_at is not None

    def test_preference_to_dict(self):
        """测试：偏好转字典"""
        from src.domain.services.knowledge_maintenance import (
            PreferenceType,
            UserPreference,
        )

        pref = UserPreference(
            preference_id="pref_004",
            user_id="user_xyz",
            preference_type=PreferenceType.TOOL_USAGE,
            key="preferred_llm",
            value="gpt-4",
        )

        data = pref.to_dict()

        assert data["preference_id"] == "pref_004"
        assert data["user_id"] == "user_xyz"
        assert data["preference_type"] == "tool_usage"
        assert data["key"] == "preferred_llm"
        assert data["value"] == "gpt-4"


# ==================== 3. SuccessfulSolution 成功解法测试 ====================


class TestSuccessfulSolution:
    """成功解法数据结构测试"""

    def test_create_successful_solution(self):
        """测试：创建成功解法"""
        from src.domain.services.knowledge_maintenance import SuccessfulSolution

        solution = SuccessfulSolution(
            solution_id="sol_001",
            task_type="data_analysis",
            task_description="分析销售数据并生成报表",
            workflow_id="wf_sales_001",
            solution_steps=[
                "获取数据源",
                "清洗数据",
                "统计分析",
                "生成可视化",
                "输出报表",
            ],
            success_metrics={"accuracy": 0.95, "completion_time_ms": 5000},
        )

        assert solution.solution_id == "sol_001"
        assert solution.task_type == "data_analysis"
        assert len(solution.solution_steps) == 5
        assert solution.success_metrics["accuracy"] == 0.95
        assert solution.reuse_count == 0

    def test_solution_with_context(self):
        """测试：带上下文的解法"""
        from src.domain.services.knowledge_maintenance import SuccessfulSolution

        solution = SuccessfulSolution(
            solution_id="sol_002",
            task_type="code_generation",
            task_description="生成 Python REST API",
            workflow_id="wf_codegen_001",
            solution_steps=["分析需求", "设计接口", "生成代码", "添加测试"],
            success_metrics={"code_quality": 0.9},
            context={
                "language": "python",
                "framework": "fastapi",
                "domain": "backend",
            },
        )

        assert solution.context["language"] == "python"
        assert solution.context["framework"] == "fastapi"

    def test_solution_increment_reuse(self):
        """测试：增加复用计数"""
        from src.domain.services.knowledge_maintenance import SuccessfulSolution

        solution = SuccessfulSolution(
            solution_id="sol_003",
            task_type="testing",
            task_description="编写单元测试",
            workflow_id="wf_test_001",
            solution_steps=["识别测试点", "编写测试", "运行验证"],
            success_metrics={"coverage": 0.85},
        )

        assert solution.reuse_count == 0
        solution.increment_reuse()
        assert solution.reuse_count == 1
        solution.increment_reuse()
        assert solution.reuse_count == 2

    def test_solution_calculate_similarity(self):
        """测试：计算任务相似度"""
        from src.domain.services.knowledge_maintenance import SuccessfulSolution

        solution = SuccessfulSolution(
            solution_id="sol_004",
            task_type="data_analysis",
            task_description="分析用户行为数据",
            workflow_id="wf_analysis_001",
            solution_steps=["获取数据", "处理数据", "生成报告"],
            success_metrics={"accuracy": 0.9},
            context={"domain": "analytics", "data_type": "user_behavior"},
            tags=["analytics", "user", "behavior", "report"],
        )

        # 相似任务
        similarity = solution.calculate_similarity(
            task_type="data_analysis",
            task_description="分析客户行为模式",
            context={"domain": "analytics", "data_type": "customer_behavior"},
        )

        assert similarity > 0.5  # 应该有较高相似度

    def test_solution_to_dict(self):
        """测试：解法转字典"""
        from src.domain.services.knowledge_maintenance import SuccessfulSolution

        solution = SuccessfulSolution(
            solution_id="sol_005",
            task_type="deployment",
            task_description="部署应用到生产环境",
            workflow_id="wf_deploy_001",
            solution_steps=["构建", "测试", "部署", "验证"],
            success_metrics={"deployment_time_ms": 30000},
        )

        data = solution.to_dict()

        assert data["solution_id"] == "sol_005"
        assert data["task_type"] == "deployment"
        assert len(data["solution_steps"]) == 4


# ==================== 4. FailureCase 失败案例测试 ====================


class TestFailureCase:
    """失败案例数据结构测试"""

    def test_create_failure_case(self):
        """测试：创建失败案例"""
        from src.domain.services.knowledge_maintenance import (
            FailureCase,
            FailureCategory,
        )

        failure = FailureCase(
            failure_id="fail_001",
            task_type="api_integration",
            task_description="集成第三方支付 API",
            workflow_id="wf_payment_001",
            failure_category=FailureCategory.EXTERNAL_DEPENDENCY,
            error_message="Connection timeout to payment gateway",
            root_cause="网络超时，未设置合理的重试机制",
            lesson_learned="集成外部 API 时应设置超时和重试策略",
        )

        assert failure.failure_id == "fail_001"
        assert failure.failure_category == FailureCategory.EXTERNAL_DEPENDENCY
        assert "timeout" in failure.error_message.lower()
        assert failure.lesson_learned != ""

    def test_failure_categories(self):
        """测试：失败类别枚举"""
        from src.domain.services.knowledge_maintenance import FailureCategory

        assert FailureCategory.INVALID_INPUT.value == "invalid_input"
        assert FailureCategory.RESOURCE_EXHAUSTED.value == "resource_exhausted"
        assert FailureCategory.EXTERNAL_DEPENDENCY.value == "external_dependency"
        assert FailureCategory.LOGIC_ERROR.value == "logic_error"
        assert FailureCategory.TIMEOUT.value == "timeout"
        assert FailureCategory.PERMISSION_DENIED.value == "permission_denied"

    def test_failure_with_prevention_strategy(self):
        """测试：带预防策略的失败案例"""
        from src.domain.services.knowledge_maintenance import (
            FailureCase,
            FailureCategory,
        )

        failure = FailureCase(
            failure_id="fail_002",
            task_type="data_processing",
            task_description="处理大规模数据集",
            workflow_id="wf_bigdata_001",
            failure_category=FailureCategory.RESOURCE_EXHAUSTED,
            error_message="OutOfMemoryError: Java heap space",
            root_cause="数据集过大，内存不足",
            lesson_learned="大数据处理需要分批进行",
            prevention_strategy=[
                "使用流式处理替代批量加载",
                "设置内存限制和监控",
                "实现数据分片机制",
            ],
        )

        assert len(failure.prevention_strategy) == 3
        assert "流式处理" in failure.prevention_strategy[0]

    def test_failure_is_similar_error(self):
        """测试：判断是否相似错误"""
        from src.domain.services.knowledge_maintenance import (
            FailureCase,
            FailureCategory,
        )

        failure = FailureCase(
            failure_id="fail_003",
            task_type="database_query",
            task_description="查询用户数据",
            workflow_id="wf_db_001",
            failure_category=FailureCategory.TIMEOUT,
            error_message="Query execution timeout after 30s",
            root_cause="查询未优化，全表扫描",
            lesson_learned="添加合适的索引",
        )

        # 相似错误
        is_similar = failure.is_similar_error(
            error_message="Query timeout exceeded 30 seconds",
            task_type="database_query",
        )
        assert is_similar

        # 不相似错误
        is_similar = failure.is_similar_error(
            error_message="Permission denied",
            task_type="file_access",
        )
        assert not is_similar

    def test_failure_to_dict(self):
        """测试：失败案例转字典"""
        from src.domain.services.knowledge_maintenance import (
            FailureCase,
            FailureCategory,
        )

        failure = FailureCase(
            failure_id="fail_004",
            task_type="authentication",
            task_description="用户认证",
            workflow_id="wf_auth_001",
            failure_category=FailureCategory.PERMISSION_DENIED,
            error_message="Invalid credentials",
            root_cause="密码错误",
            lesson_learned="增加错误提示友好性",
        )

        data = failure.to_dict()

        assert data["failure_id"] == "fail_004"
        assert data["failure_category"] == "permission_denied"
        assert data["task_type"] == "authentication"


# ==================== 5. KnowledgeMaintainer 知识维护器测试 ====================


class TestKnowledgeMaintainer:
    """知识维护器测试"""

    def test_maintainer_initialization(self):
        """测试：维护器初始化"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer

        maintainer = KnowledgeMaintainer()

        assert maintainer is not None
        assert maintainer.memory_count == 0
        assert maintainer.preference_count == 0
        assert maintainer.solution_count == 0
        assert maintainer.failure_count == 0

    def test_add_long_term_memory(self):
        """测试：添加长期记忆"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
        )

        maintainer = KnowledgeMaintainer()

        memory_id = maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="项目使用 Python 3.11 和 FastAPI",
            source="project_setup",
            confidence=1.0,
        )

        assert memory_id is not None
        assert maintainer.memory_count == 1

    def test_add_user_preference(self):
        """测试：添加用户偏好"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            PreferenceType,
        )

        maintainer = KnowledgeMaintainer()

        pref_id = maintainer.add_preference(
            user_id="user_001",
            preference_type=PreferenceType.CODING_STYLE,
            key="naming_convention",
            value="snake_case",
        )

        assert pref_id is not None
        assert maintainer.preference_count == 1

    def test_record_successful_solution(self):
        """测试：记录成功解法"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer

        maintainer = KnowledgeMaintainer()

        solution_id = maintainer.record_success(
            task_type="code_review",
            task_description="审查 Python 代码",
            workflow_id="wf_review_001",
            solution_steps=["静态分析", "代码规范检查", "安全检查", "生成报告"],
            success_metrics={"issues_found": 5, "time_ms": 2000},
            context={"language": "python"},
        )

        assert solution_id is not None
        assert maintainer.solution_count == 1

    def test_record_failure_case(self):
        """测试：记录失败案例"""
        from src.domain.services.knowledge_maintenance import (
            FailureCategory,
            KnowledgeMaintainer,
        )

        maintainer = KnowledgeMaintainer()

        failure_id = maintainer.record_failure(
            task_type="file_processing",
            task_description="处理 CSV 文件",
            workflow_id="wf_csv_001",
            failure_category=FailureCategory.INVALID_INPUT,
            error_message="Invalid CSV format: unexpected delimiter",
            root_cause="文件使用非标准分隔符",
            lesson_learned="处理前应检测文件格式",
        )

        assert failure_id is not None
        assert maintainer.failure_count == 1

    def test_get_memory_by_id(self):
        """测试：根据 ID 获取记忆"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
        )

        maintainer = KnowledgeMaintainer()

        memory_id = maintainer.add_memory(
            category=MemoryCategory.SKILL,
            content="熟练掌握 SQL 查询优化",
            source="skill_assessment",
            confidence=0.9,
        )

        memory = maintainer.get_memory(memory_id)

        assert memory is not None
        assert memory.content == "熟练掌握 SQL 查询优化"

    def test_get_preferences_by_user(self):
        """测试：获取用户的所有偏好"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            PreferenceType,
        )

        maintainer = KnowledgeMaintainer()

        # 添加多个偏好
        maintainer.add_preference(
            user_id="user_001",
            preference_type=PreferenceType.CODING_STYLE,
            key="indentation",
            value="4_spaces",
        )
        maintainer.add_preference(
            user_id="user_001",
            preference_type=PreferenceType.OUTPUT_FORMAT,
            key="report_format",
            value="markdown",
        )
        maintainer.add_preference(
            user_id="user_002",
            preference_type=PreferenceType.CODING_STYLE,
            key="indentation",
            value="tabs",
        )

        user1_prefs = maintainer.get_user_preferences("user_001")

        assert len(user1_prefs) == 2

    def test_search_memories(self):
        """测试：搜索记忆"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
        )

        maintainer = KnowledgeMaintainer()

        # 添加多条记忆
        maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="项目使用 PostgreSQL 数据库",
            source="config",
            confidence=1.0,
        )
        maintainer.add_memory(
            category=MemoryCategory.PROCEDURE,
            content="数据库备份流程：每日凌晨自动备份",
            source="ops_doc",
            confidence=0.95,
        )
        maintainer.add_memory(
            category=MemoryCategory.SKILL,
            content="Python 异步编程技能",
            source="skill_assessment",
            confidence=0.8,
        )

        # 搜索包含"数据库"的记忆
        results = maintainer.search_memories("数据库")

        assert len(results) == 2

    def test_on_workflow_success_event(self):
        """测试：处理工作流成功事件"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer

        maintainer = KnowledgeMaintainer()

        # 模拟工作流成功事件
        event = {
            "event_type": "workflow_success",
            "workflow_id": "wf_001",
            "task_type": "data_analysis",
            "task_description": "分析用户留存数据",
            "execution_steps": ["获取数据", "清洗", "分析", "可视化"],
            "metrics": {"accuracy": 0.92, "duration_ms": 3000},
            "context": {"domain": "analytics"},
        }

        maintainer.on_workflow_event(event)

        assert maintainer.solution_count == 1

    def test_on_workflow_failure_event(self):
        """测试：处理工作流失败事件"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer

        maintainer = KnowledgeMaintainer()

        # 模拟工作流失败事件
        event = {
            "event_type": "workflow_failure",
            "workflow_id": "wf_002",
            "task_type": "api_call",
            "task_description": "调用外部 API",
            "error_message": "Connection refused",
            "failure_category": "external_dependency",
            "root_cause": "目标服务不可用",
        }

        maintainer.on_workflow_event(event)

        assert maintainer.failure_count == 1


# ==================== 6. SolutionRetriever 解法检索器测试 ====================


class TestSolutionRetriever:
    """解法检索器测试"""

    def test_retriever_initialization(self):
        """测试：检索器初始化"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        assert retriever is not None

    def test_find_similar_solutions(self):
        """测试：查找相似解法"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()

        # 添加一些成功解法
        maintainer.record_success(
            task_type="data_analysis",
            task_description="分析销售数据趋势",
            workflow_id="wf_001",
            solution_steps=["获取数据", "清洗", "分析趋势", "生成报告"],
            success_metrics={"accuracy": 0.9},
            context={"domain": "sales"},
            tags=["sales", "analysis", "trend"],
        )

        maintainer.record_success(
            task_type="data_analysis",
            task_description="分析用户行为数据",
            workflow_id="wf_002",
            solution_steps=["获取数据", "清洗", "行为分析", "生成报告"],
            success_metrics={"accuracy": 0.88},
            context={"domain": "user_behavior"},
            tags=["user", "analysis", "behavior"],
        )

        maintainer.record_success(
            task_type="code_generation",
            task_description="生成 REST API 代码",
            workflow_id="wf_003",
            solution_steps=["分析需求", "设计接口", "生成代码"],
            success_metrics={"quality": 0.85},
            context={"language": "python"},
            tags=["code", "api", "python"],
        )

        retriever = SolutionRetriever(maintainer)

        # 查找与"分析市场数据"相似的解法
        similar = retriever.find_similar_solutions(
            task_type="data_analysis",
            task_description="分析市场数据趋势",
            context={"domain": "market"},
            top_k=2,
        )

        assert len(similar) <= 2
        # 应该返回数据分析相关的解法
        assert all(s.task_type == "data_analysis" for s in similar)

    def test_find_solutions_by_task_type(self):
        """测试：按任务类型查找解法"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()

        maintainer.record_success(
            task_type="testing",
            task_description="编写单元测试",
            workflow_id="wf_test_001",
            solution_steps=["分析代码", "设计测试", "编写测试", "运行验证"],
            success_metrics={"coverage": 0.85},
        )

        maintainer.record_success(
            task_type="testing",
            task_description="编写集成测试",
            workflow_id="wf_test_002",
            solution_steps=["准备环境", "编写测试", "运行", "清理"],
            success_metrics={"coverage": 0.75},
        )

        retriever = SolutionRetriever(maintainer)
        solutions = retriever.find_by_task_type("testing")

        assert len(solutions) == 2

    def test_get_best_solution(self):
        """测试：获取最佳解法"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()

        # 添加多个相同类型的解法，但指标不同
        maintainer.record_success(
            task_type="optimization",
            task_description="优化查询性能",
            workflow_id="wf_opt_001",
            solution_steps=["分析慢查询", "添加索引", "验证"],
            success_metrics={"improvement": 0.3},
        )

        maintainer.record_success(
            task_type="optimization",
            task_description="优化 API 性能",
            workflow_id="wf_opt_002",
            solution_steps=["性能分析", "缓存优化", "并发优化", "验证"],
            success_metrics={"improvement": 0.6},
        )

        retriever = SolutionRetriever(maintainer)

        # 获取性能提升最高的解法
        best = retriever.get_best_solution(
            task_type="optimization",
            metric_key="improvement",
        )

        assert best is not None
        assert best.success_metrics["improvement"] == 0.6

    def test_check_known_failure(self):
        """测试：检查已知失败"""
        from src.domain.services.knowledge_maintenance import (
            FailureCategory,
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()

        # 记录一个已知失败
        maintainer.record_failure(
            task_type="external_api",
            task_description="调用支付网关",
            workflow_id="wf_pay_001",
            failure_category=FailureCategory.TIMEOUT,
            error_message="Gateway timeout after 30s",
            root_cause="支付网关响应慢",
            lesson_learned="设置合理超时和重试",
            prevention_strategy=["设置 10s 超时", "添加重试机制", "实现降级方案"],
        )

        retriever = SolutionRetriever(maintainer)

        # 检查相似的失败
        warning = retriever.check_known_failure(
            task_type="external_api",
            task_description="调用支付接口",
            potential_error="Gateway timeout",
        )

        assert warning is not None
        assert len(warning.prevention_strategy) > 0


# ==================== 7. KnowledgeStore 知识存储测试 ====================


class TestKnowledgeStore:
    """知识存储测试"""

    def test_store_initialization(self):
        """测试：存储初始化"""
        from src.domain.services.knowledge_maintenance import KnowledgeStore

        store = KnowledgeStore()

        assert store is not None

    def test_persist_and_load_memories(self):
        """测试：持久化和加载记忆"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeStore,
            LongTermMemory,
            MemoryCategory,
        )

        store = KnowledgeStore()

        memory = LongTermMemory(
            memory_id="mem_persist_001",
            category=MemoryCategory.FACT,
            content="持久化测试内容",
            source="test",
            confidence=0.9,
        )

        store.save_memory(memory)
        loaded = store.load_memory("mem_persist_001")

        assert loaded is not None
        assert loaded.content == "持久化测试内容"

    def test_persist_and_load_solutions(self):
        """测试：持久化和加载解法"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeStore,
            SuccessfulSolution,
        )

        store = KnowledgeStore()

        solution = SuccessfulSolution(
            solution_id="sol_persist_001",
            task_type="test",
            task_description="测试任务",
            workflow_id="wf_test",
            solution_steps=["步骤1", "步骤2"],
            success_metrics={"score": 1.0},
        )

        store.save_solution(solution)
        loaded = store.load_solution("sol_persist_001")

        assert loaded is not None
        assert loaded.task_type == "test"

    def test_export_and_import(self):
        """测试：导出和导入知识库"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeStore,
            LongTermMemory,
            MemoryCategory,
        )

        store = KnowledgeStore()

        # 添加一些数据
        store.save_memory(
            LongTermMemory(
                memory_id="export_001",
                category=MemoryCategory.FACT,
                content="导出测试",
                source="test",
                confidence=1.0,
            )
        )

        # 导出
        exported = store.export_to_dict()

        assert "memories" in exported
        assert len(exported["memories"]) >= 1

        # 创建新存储并导入
        new_store = KnowledgeStore()
        new_store.import_from_dict(exported)

        loaded = new_store.load_memory("export_001")
        assert loaded is not None


# ==================== 8. 集成测试 ====================


class TestKnowledgeMaintenanceIntegration:
    """知识维护集成测试"""

    def test_full_knowledge_lifecycle(self):
        """测试：完整知识生命周期"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
            PreferenceType,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 1. 添加长期记忆
        maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="项目使用微服务架构",
            source="architecture_doc",
            confidence=1.0,
        )

        # 2. 添加用户偏好
        maintainer.add_preference(
            user_id="dev_001",
            preference_type=PreferenceType.CODING_STYLE,
            key="architecture_pattern",
            value="microservices",
        )

        # 3. 模拟工作流成功
        success_event = {
            "event_type": "workflow_success",
            "workflow_id": "wf_deploy_001",
            "task_type": "deployment",
            "task_description": "部署微服务到 Kubernetes",
            "execution_steps": [
                "构建镜像",
                "推送到仓库",
                "更新 K8s 配置",
                "滚动更新",
            ],
            "metrics": {"deployment_time_ms": 60000, "success": True},
            "context": {"platform": "kubernetes", "env": "production"},
        }
        maintainer.on_workflow_event(success_event)

        # 4. 检索相似解法
        similar = retriever.find_similar_solutions(
            task_type="deployment",
            task_description="部署服务到 K8s 集群",
            context={"platform": "kubernetes"},
        )

        assert len(similar) >= 1
        assert similar[0].task_type == "deployment"

    def test_coordinator_reuse_scenario(self):
        """测试：Coordinator 复用成功方案场景"""
        from src.domain.services.knowledge_maintenance import (
            FailureCategory,
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 场景：之前成功处理过类似的数据分析任务
        maintainer.record_success(
            task_type="data_analysis",
            task_description="分析用户活跃度数据",
            workflow_id="wf_analysis_001",
            solution_steps=[
                "连接数据源",
                "数据清洗",
                "计算活跃度指标",
                "生成可视化报告",
            ],
            success_metrics={"accuracy": 0.95, "execution_time_ms": 5000},
            context={"data_source": "database", "output_format": "chart"},
            tags=["user", "activity", "analysis"],
        )

        # 场景：之前处理过一个失败案例
        maintainer.record_failure(
            task_type="data_analysis",
            task_description="分析大规模日志数据",
            workflow_id="wf_analysis_002",
            failure_category=FailureCategory.RESOURCE_EXHAUSTED,
            error_message="OutOfMemory: heap space exhausted",
            root_cause="数据量过大，未分批处理",
            lesson_learned="大数据分析需要分批或流式处理",
            prevention_strategy=["分批加载数据", "使用流式处理", "增加内存限制"],
        )

        # 模拟 Coordinator 接收新任务
        new_task = {
            "task_type": "data_analysis",
            "task_description": "分析用户留存数据",
            "context": {"data_source": "database", "data_size": "large"},
        }

        # Coordinator 检查已知失败
        failure_warning = retriever.check_known_failure(
            task_type=new_task["task_type"],
            task_description=new_task["task_description"],
            potential_error="OutOfMemory",
        )

        # 应该得到警告
        assert failure_warning is not None
        assert len(failure_warning.prevention_strategy) > 0

        # Coordinator 查找可复用的解法
        reusable_solutions = retriever.find_similar_solutions(
            task_type=new_task["task_type"],
            task_description=new_task["task_description"],
            context=new_task["context"],
            top_k=3,
        )

        # 应该找到相似解法
        assert len(reusable_solutions) >= 1

        # 获取最佳解法
        best = retriever.get_best_solution(
            task_type="data_analysis",
            metric_key="accuracy",
        )

        assert best is not None
        assert best.success_metrics["accuracy"] >= 0.9

    def test_continuous_learning_scenario(self):
        """测试：持续学习场景"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 第一次执行任务 - 成功
        maintainer.on_workflow_event(
            {
                "event_type": "workflow_success",
                "workflow_id": "wf_v1",
                "task_type": "report_generation",
                "task_description": "生成月度销售报告",
                "execution_steps": ["获取数据", "分析", "生成报告"],
                "metrics": {"quality_score": 0.7, "time_ms": 10000},
                "context": {"format": "pdf"},
            }
        )

        # 第二次执行类似任务 - 改进后成功
        maintainer.on_workflow_event(
            {
                "event_type": "workflow_success",
                "workflow_id": "wf_v2",
                "task_type": "report_generation",
                "task_description": "生成月度销售报告（优化版）",
                "execution_steps": ["并行获取数据", "增量分析", "生成报告", "添加图表"],
                "metrics": {"quality_score": 0.9, "time_ms": 5000},
                "context": {"format": "pdf", "optimized": True},
            }
        )

        # 检索最佳解法应该是优化后的版本
        best = retriever.get_best_solution(
            task_type="report_generation",
            metric_key="quality_score",
        )

        assert best is not None
        assert best.success_metrics["quality_score"] == 0.9
        assert "并行获取数据" in best.solution_steps


# ==================== 9. 边界条件测试 ====================


class TestKnowledgeMaintenanceEdgeCases:
    """边界条件测试"""

    def test_empty_search_results(self):
        """测试：空搜索结果"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 空知识库搜索
        results = retriever.find_similar_solutions(
            task_type="nonexistent_type",
            task_description="不存在的任务",
            context={},
        )

        assert results == []

    def test_duplicate_memory_handling(self):
        """测试：重复记忆处理"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
        )

        maintainer = KnowledgeMaintainer()

        # 添加相同内容的记忆
        id1 = maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="相同的内容",
            source="source1",
            confidence=0.8,
        )

        id2 = maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="相同的内容",
            source="source2",
            confidence=0.9,
        )

        # 应该能够区分或合并
        assert id1 != id2 or maintainer.memory_count == 1

    def test_invalid_event_handling(self):
        """测试：无效事件处理"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer

        maintainer = KnowledgeMaintainer()

        # 无效事件类型
        invalid_event = {
            "event_type": "unknown_event",
            "workflow_id": "wf_invalid",
        }

        # 应该优雅处理，不抛异常
        maintainer.on_workflow_event(invalid_event)

        assert maintainer.solution_count == 0
        assert maintainer.failure_count == 0

    def test_confidence_bounds(self):
        """测试：置信度边界"""
        from src.domain.services.knowledge_maintenance import (
            LongTermMemory,
            MemoryCategory,
        )

        # 置信度应该在 0-1 之间
        memory = LongTermMemory(
            memory_id="bound_test",
            category=MemoryCategory.FACT,
            content="测试",
            source="test",
            confidence=0.5,
        )

        memory.update_confidence(1.5)  # 超出上限
        assert memory.confidence <= 1.0

        memory.update_confidence(-0.5)  # 低于下限
        assert memory.confidence >= 0.0
