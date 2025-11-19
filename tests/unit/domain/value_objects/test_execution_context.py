"""ExecutionContext 单元测试

测试场景：
1. 创建空上下文
2. 存储任务结果
3. 获取任务结果
4. 检查任务是否存在
5. 获取所有任务名称
6. 设置共享变量
7. 获取共享变量
8. 上下文隔离（复制）
9. 合并上下文
10. 清空上下文
11. 获取不存在的任务结果（返回默认值）
12. 上下文序列化（转为字典）
"""

from src.domain.value_objects.execution_context import ExecutionContext


class TestExecutionContext:
    """ExecutionContext 测试类"""

    def test_create_empty_context(self):
        """测试场景 1: 创建空上下文"""
        # Act
        context = ExecutionContext.create()

        # Assert
        assert context is not None
        assert context.is_empty()
        assert len(context.get_all_task_names()) == 0

    def test_store_task_result(self):
        """测试场景 2: 存储任务结果"""
        # Arrange
        context = ExecutionContext.create()
        task_name = "Task 1"
        result = {"status": "success", "data": "test data"}

        # Act
        context.set_task_result(task_name, result)

        # Assert
        assert not context.is_empty()
        assert context.has_task(task_name)
        assert context.get_task_result(task_name) == result

    def test_get_task_result(self):
        """测试场景 3: 获取任务结果"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "data 1"})
        context.set_task_result("Task 2", {"result": "data 2"})

        # Act
        result1 = context.get_task_result("Task 1")
        result2 = context.get_task_result("Task 2")

        # Assert
        assert result1 == {"result": "data 1"}
        assert result2 == {"result": "data 2"}

    def test_has_task(self):
        """测试场景 4: 检查任务是否存在"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "data"})

        # Act & Assert
        assert context.has_task("Task 1")
        assert not context.has_task("Task 2")
        assert not context.has_task("Non-existent Task")

    def test_get_all_task_names(self):
        """测试场景 5: 获取所有任务名称"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "data 1"})
        context.set_task_result("Task 2", {"result": "data 2"})
        context.set_task_result("Task 3", {"result": "data 3"})

        # Act
        task_names = context.get_all_task_names()

        # Assert
        assert len(task_names) == 3
        assert "Task 1" in task_names
        assert "Task 2" in task_names
        assert "Task 3" in task_names

    def test_set_shared_variable(self):
        """测试场景 6: 设置共享变量"""
        # Arrange
        context = ExecutionContext.create()

        # Act
        context.set_variable("user_id", "12345")
        context.set_variable("session_id", "abc-def-ghi")
        context.set_variable("config", {"timeout": 30})

        # Assert
        assert context.get_variable("user_id") == "12345"
        assert context.get_variable("session_id") == "abc-def-ghi"
        assert context.get_variable("config") == {"timeout": 30}

    def test_get_shared_variable(self):
        """测试场景 7: 获取共享变量"""
        # Arrange
        context = ExecutionContext.create()
        context.set_variable("api_key", "secret-key-123")

        # Act
        api_key = context.get_variable("api_key")

        # Assert
        assert api_key == "secret-key-123"

    def test_context_isolation_copy(self):
        """测试场景 8: 上下文隔离（复制）"""
        # Arrange
        context1 = ExecutionContext.create()
        context1.set_task_result("Task 1", {"result": "data 1"})
        context1.set_variable("var1", "value1")

        # Act
        context2 = context1.copy()

        # 修改 context2
        context2.set_task_result("Task 2", {"result": "data 2"})
        context2.set_variable("var2", "value2")

        # Assert
        # context1 不应该被修改
        assert context1.has_task("Task 1")
        assert not context1.has_task("Task 2")
        assert context1.get_variable("var1") == "value1"
        assert context1.get_variable("var2") is None

        # context2 应该有两个任务
        assert context2.has_task("Task 1")
        assert context2.has_task("Task 2")
        assert context2.get_variable("var1") == "value1"
        assert context2.get_variable("var2") == "value2"

    def test_merge_contexts(self):
        """测试场景 9: 合并上下文"""
        # Arrange
        context1 = ExecutionContext.create()
        context1.set_task_result("Task 1", {"result": "data 1"})
        context1.set_variable("var1", "value1")

        context2 = ExecutionContext.create()
        context2.set_task_result("Task 2", {"result": "data 2"})
        context2.set_variable("var2", "value2")

        # Act
        context1.merge(context2)

        # Assert
        assert context1.has_task("Task 1")
        assert context1.has_task("Task 2")
        assert context1.get_variable("var1") == "value1"
        assert context1.get_variable("var2") == "value2"

    def test_clear_context(self):
        """测试场景 10: 清空上下文"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "data 1"})
        context.set_variable("var1", "value1")

        # Act
        context.clear()

        # Assert
        assert context.is_empty()
        assert len(context.get_all_task_names()) == 0
        assert context.get_variable("var1") is None

    def test_get_nonexistent_task_result_with_default(self):
        """测试场景 11: 获取不存在的任务结果（返回默认值）"""
        # Arrange
        context = ExecutionContext.create()

        # Act
        result = context.get_task_result("Non-existent Task", default={"error": "not found"})

        # Assert
        assert result == {"error": "not found"}

    def test_get_nonexistent_variable_with_default(self):
        """测试场景 11.2: 获取不存在的变量（返回默认值）"""
        # Arrange
        context = ExecutionContext.create()

        # Act
        value = context.get_variable("non_existent_var", default="default_value")

        # Assert
        assert value == "default_value"

    def test_context_to_dict(self):
        """测试场景 12: 上下文序列化（转为字典）"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "data 1"})
        context.set_task_result("Task 2", {"result": "data 2"})
        context.set_variable("var1", "value1")

        # Act
        context_dict = context.to_dict()

        # Assert
        assert "tasks" in context_dict
        assert "variables" in context_dict
        assert context_dict["tasks"]["Task 1"] == {"result": "data 1"}
        assert context_dict["tasks"]["Task 2"] == {"result": "data 2"}
        assert context_dict["variables"]["var1"] == "value1"

    def test_context_from_dict(self):
        """测试场景 13: 从字典创建上下文"""
        # Arrange
        context_dict = {
            "tasks": {
                "Task 1": {"result": "data 1"},
                "Task 2": {"result": "data 2"},
            },
            "variables": {
                "var1": "value1",
                "var2": "value2",
            },
        }

        # Act
        context = ExecutionContext.from_dict(context_dict)

        # Assert
        assert context.has_task("Task 1")
        assert context.has_task("Task 2")
        assert context.get_task_result("Task 1") == {"result": "data 1"}
        assert context.get_variable("var1") == "value1"
        assert context.get_variable("var2") == "value2"

    def test_update_task_result(self):
        """测试场景 14: 更新任务结果"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "old data"})

        # Act
        context.set_task_result("Task 1", {"result": "new data"})

        # Assert
        assert context.get_task_result("Task 1") == {"result": "new data"}

    def test_context_size(self):
        """测试场景 15: 获取上下文大小"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "data 1"})
        context.set_task_result("Task 2", {"result": "data 2"})
        context.set_task_result("Task 3", {"result": "data 3"})

        # Act
        size = context.size()

        # Assert
        assert size == 3

    def test_remove_task_result(self):
        """测试场景 16: 删除任务结果"""
        # Arrange
        context = ExecutionContext.create()
        context.set_task_result("Task 1", {"result": "data 1"})
        context.set_task_result("Task 2", {"result": "data 2"})

        # Act
        context.remove_task("Task 1")

        # Assert
        assert not context.has_task("Task 1")
        assert context.has_task("Task 2")
        assert context.size() == 1
