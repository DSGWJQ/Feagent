"""ToolEngine 测试 - 阶段 2

测试目标：
1. 验证启动时扫描工具目录并加载
2. 验证工具注册到索引
3. 验证按名称/标签查找工具
4. 验证热更新机制（新增/修改/删除 YAML）
5. 验证并发安全性
"""

import asyncio

import pytest

from src.domain.entities.tool import Tool
from src.domain.services.tool_engine import (
    ToolEngine,
    ToolEngineConfig,
    ToolEngineEvent,
    ToolEngineEventType,
    ToolIndex,
    ToolNotFoundError,
)
from src.domain.value_objects.tool_category import ToolCategory

# =============================================================================
# 第一部分：ToolEngineConfig 测试
# =============================================================================


class TestToolEngineConfig:
    """ToolEngine 配置测试"""

    def test_default_config(self):
        """测试：默认配置"""
        config = ToolEngineConfig()

        assert config.tools_directory == "tools"
        assert config.auto_reload is True
        assert config.reload_interval == 5.0
        assert config.watch_for_changes is False

    def test_custom_config(self):
        """测试：自定义配置"""
        config = ToolEngineConfig(
            tools_directory="/custom/tools",
            auto_reload=False,
            reload_interval=10.0,
            watch_for_changes=True,
        )

        assert config.tools_directory == "/custom/tools"
        assert config.auto_reload is False
        assert config.reload_interval == 10.0
        assert config.watch_for_changes is True


# =============================================================================
# 第二部分：ToolIndex 测试
# =============================================================================


class TestToolIndex:
    """工具索引测试"""

    @pytest.fixture
    def sample_tool(self):
        """创建示例工具"""
        return Tool(
            id="tool_abc123",
            name="http_request",
            description="发送HTTP请求",
            category=ToolCategory.HTTP,
            status="draft",
            version="1.0.0",
            tags=["http", "network", "api"],
            author="system",
        )

    @pytest.fixture
    def sample_tool2(self):
        """创建第二个示例工具"""
        return Tool(
            id="tool_def456",
            name="llm_call",
            description="调用LLM",
            category=ToolCategory.AI,
            status="draft",
            version="1.0.0",
            tags=["ai", "llm", "chat"],
            author="system",
        )

    def test_add_tool(self, sample_tool):
        """测试：添加工具到索引"""
        index = ToolIndex()
        index.add(sample_tool)

        assert index.count == 1
        assert "http_request" in index

    def test_get_tool_by_name(self, sample_tool):
        """测试：按名称获取工具"""
        index = ToolIndex()
        index.add(sample_tool)

        tool = index.get("http_request")
        assert tool is not None
        assert tool.name == "http_request"

    def test_get_nonexistent_tool(self):
        """测试：获取不存在的工具返回 None"""
        index = ToolIndex()
        tool = index.get("nonexistent")
        assert tool is None

    def test_remove_tool(self, sample_tool):
        """测试：从索引移除工具"""
        index = ToolIndex()
        index.add(sample_tool)
        index.remove("http_request")

        assert index.count == 0
        assert "http_request" not in index

    def test_update_tool(self, sample_tool):
        """测试：更新工具"""
        index = ToolIndex()
        index.add(sample_tool)

        # 更新版本
        updated_tool = Tool(
            id=sample_tool.id,
            name=sample_tool.name,
            description="更新后的描述",
            category=sample_tool.category,
            status=sample_tool.status,
            version="2.0.0",
            tags=sample_tool.tags,
            author=sample_tool.author,
        )
        index.update(updated_tool)

        tool = index.get("http_request")
        assert tool.version == "2.0.0"
        assert tool.description == "更新后的描述"

    def test_find_by_tag(self, sample_tool, sample_tool2):
        """测试：按标签查找工具"""
        index = ToolIndex()
        index.add(sample_tool)
        index.add(sample_tool2)

        # 查找 http 标签
        http_tools = index.find_by_tag("http")
        assert len(http_tools) == 1
        assert http_tools[0].name == "http_request"

        # 查找 ai 标签
        ai_tools = index.find_by_tag("ai")
        assert len(ai_tools) == 1
        assert ai_tools[0].name == "llm_call"

    def test_find_by_multiple_tags(self, sample_tool, sample_tool2):
        """测试：按多个标签查找（AND 逻辑）"""
        index = ToolIndex()
        index.add(sample_tool)
        index.add(sample_tool2)

        # http AND network
        tools = index.find_by_tags(["http", "network"])
        assert len(tools) == 1
        assert tools[0].name == "http_request"

        # ai AND llm
        tools = index.find_by_tags(["ai", "llm"])
        assert len(tools) == 1
        assert tools[0].name == "llm_call"

        # 不匹配的组合
        tools = index.find_by_tags(["http", "ai"])
        assert len(tools) == 0

    def test_find_by_any_tag(self, sample_tool, sample_tool2):
        """测试：按任意标签查找（OR 逻辑）"""
        index = ToolIndex()
        index.add(sample_tool)
        index.add(sample_tool2)

        # http OR ai
        tools = index.find_by_any_tag(["http", "ai"])
        assert len(tools) == 2

    def test_find_by_category(self, sample_tool, sample_tool2):
        """测试：按分类查找"""
        index = ToolIndex()
        index.add(sample_tool)
        index.add(sample_tool2)

        http_tools = index.find_by_category(ToolCategory.HTTP)
        assert len(http_tools) == 1
        assert http_tools[0].name == "http_request"

        ai_tools = index.find_by_category(ToolCategory.AI)
        assert len(ai_tools) == 1
        assert ai_tools[0].name == "llm_call"

    def test_list_all(self, sample_tool, sample_tool2):
        """测试：列出所有工具"""
        index = ToolIndex()
        index.add(sample_tool)
        index.add(sample_tool2)

        all_tools = index.list_all()
        assert len(all_tools) == 2

    def test_clear(self, sample_tool, sample_tool2):
        """测试：清空索引"""
        index = ToolIndex()
        index.add(sample_tool)
        index.add(sample_tool2)
        index.clear()

        assert index.count == 0


# =============================================================================
# 第三部分：ToolEngine 初始化测试
# =============================================================================


class TestToolEngineInitialization:
    """ToolEngine 初始化测试"""

    def test_create_engine_with_default_config(self):
        """测试：使用默认配置创建引擎"""
        engine = ToolEngine()

        assert engine.config.tools_directory == "tools"
        assert engine.is_loaded is False

    def test_create_engine_with_custom_config(self):
        """测试：使用自定义配置创建引擎"""
        config = ToolEngineConfig(
            tools_directory="/custom/tools",
            auto_reload=False,
        )
        engine = ToolEngine(config=config)

        assert engine.config.tools_directory == "/custom/tools"
        assert engine.config.auto_reload is False

    @pytest.mark.asyncio
    async def test_load_tools_from_directory(self, tmp_path):
        """测试：从目录加载工具"""
        # 创建测试工具文件
        tool_yaml = """
name: test_tool
description: 测试工具
category: custom
entry:
  type: builtin
  handler: test_handler
tags:
  - test
"""
        (tmp_path / "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)

        await engine.load()

        assert engine.is_loaded is True
        assert engine.tool_count == 1

        tool = engine.get("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

    @pytest.mark.asyncio
    async def test_load_multiple_tools(self, tmp_path):
        """测试：加载多个工具"""
        tool1 = """
name: tool_1
description: 工具1
category: http
entry:
  type: builtin
  handler: handler1
"""
        tool2 = """
name: tool_2
description: 工具2
category: ai
entry:
  type: builtin
  handler: handler2
"""
        (tmp_path / "tool_1.yaml").write_text(tool1, encoding="utf-8")
        (tmp_path / "tool_2.yaml").write_text(tool2, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)

        await engine.load()

        assert engine.tool_count == 2
        assert engine.get("tool_1") is not None
        assert engine.get("tool_2") is not None

    @pytest.mark.asyncio
    async def test_load_skip_invalid_files(self, tmp_path):
        """测试：跳过无效文件"""
        valid = """
name: valid_tool
description: 有效工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        invalid = """
name: invalid_tool
# 缺少必需字段
"""
        (tmp_path / "valid.yaml").write_text(valid, encoding="utf-8")
        (tmp_path / "invalid.yaml").write_text(invalid, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)

        await engine.load()

        assert engine.tool_count == 1
        assert engine.get("valid_tool") is not None
        assert len(engine.load_errors) == 1


# =============================================================================
# 第四部分：工具查找测试
# =============================================================================


class TestToolEngineLookup:
    """ToolEngine 查找功能测试"""

    @pytest.fixture
    async def loaded_engine(self, tmp_path):
        """创建已加载工具的引擎"""
        tools = [
            """
name: http_request
description: HTTP请求工具
category: http
tags:
  - http
  - network
  - api
entry:
  type: builtin
  handler: http_request
""",
            """
name: llm_call
description: LLM调用工具
category: ai
tags:
  - ai
  - llm
  - chat
entry:
  type: builtin
  handler: llm_call
""",
            """
name: file_reader
description: 文件读取工具
category: file
tags:
  - file
  - read
entry:
  type: builtin
  handler: file_reader
""",
        ]

        for i, content in enumerate(tools):
            (tmp_path / f"tool_{i}.yaml").write_text(content, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()
        return engine

    @pytest.mark.asyncio
    async def test_get_by_name(self, loaded_engine):
        """测试：按名称获取工具"""
        tool = loaded_engine.get("http_request")
        assert tool is not None
        assert tool.name == "http_request"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, loaded_engine):
        """测试：获取不存在的工具返回 None"""
        tool = loaded_engine.get("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_get_or_raise(self, loaded_engine):
        """测试：get_or_raise 找不到时抛出异常"""
        tool = loaded_engine.get_or_raise("http_request")
        assert tool.name == "http_request"

        with pytest.raises(ToolNotFoundError):
            loaded_engine.get_or_raise("nonexistent")

    @pytest.mark.asyncio
    async def test_find_by_tag(self, loaded_engine):
        """测试：按标签查找"""
        tools = loaded_engine.find_by_tag("http")
        assert len(tools) == 1
        assert tools[0].name == "http_request"

        tools = loaded_engine.find_by_tag("ai")
        assert len(tools) == 1
        assert tools[0].name == "llm_call"

    @pytest.mark.asyncio
    async def test_find_by_tags(self, loaded_engine):
        """测试：按多个标签查找（AND）"""
        tools = loaded_engine.find_by_tags(["http", "network"])
        assert len(tools) == 1
        assert tools[0].name == "http_request"

    @pytest.mark.asyncio
    async def test_find_by_any_tag(self, loaded_engine):
        """测试：按任意标签查找（OR）"""
        tools = loaded_engine.find_by_any_tag(["http", "ai"])
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_find_by_category(self, loaded_engine):
        """测试：按分类查找"""
        tools = loaded_engine.find_by_category(ToolCategory.HTTP)
        assert len(tools) == 1

        tools = loaded_engine.find_by_category(ToolCategory.AI)
        assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_list_all_tools(self, loaded_engine):
        """测试：列出所有工具"""
        tools = loaded_engine.list_all()
        assert len(tools) == 3

    @pytest.mark.asyncio
    async def test_list_tool_names(self, loaded_engine):
        """测试：列出所有工具名称"""
        names = loaded_engine.list_names()
        assert len(names) == 3
        assert "http_request" in names
        assert "llm_call" in names
        assert "file_reader" in names

    @pytest.mark.asyncio
    async def test_search_tools(self, loaded_engine):
        """测试：搜索工具（名称/描述模糊匹配）"""
        # 搜索名称
        tools = loaded_engine.search("http")
        assert len(tools) >= 1

        # 搜索描述
        tools = loaded_engine.search("LLM")
        assert len(tools) >= 1


# =============================================================================
# 第五部分：热更新测试
# =============================================================================


class TestToolEngineHotReload:
    """ToolEngine 热更新测试"""

    @pytest.mark.asyncio
    async def test_reload_detects_new_file(self, tmp_path):
        """测试：重载检测新增文件"""
        # 初始只有一个工具
        tool1 = """
name: tool_1
description: 工具1
category: custom
entry:
  type: builtin
  handler: handler1
"""
        (tmp_path / "tool_1.yaml").write_text(tool1, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        assert engine.tool_count == 1

        # 添加新工具
        tool2 = """
name: tool_2
description: 工具2
category: custom
entry:
  type: builtin
  handler: handler2
"""
        (tmp_path / "tool_2.yaml").write_text(tool2, encoding="utf-8")

        # 重载
        await engine.reload()

        assert engine.tool_count == 2
        assert engine.get("tool_2") is not None

    @pytest.mark.asyncio
    async def test_reload_detects_modified_file(self, tmp_path):
        """测试：重载检测修改的文件"""
        tool_yaml = """
name: test_tool
description: 原始描述
category: custom
version: "1.0.0"
entry:
  type: builtin
  handler: handler
"""
        tool_path = tmp_path / "test_tool.yaml"
        tool_path.write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        tool = engine.get("test_tool")
        assert tool.description == "原始描述"
        assert tool.version == "1.0.0"

        # 修改工具
        modified_yaml = """
name: test_tool
description: 修改后的描述
category: custom
version: "2.0.0"
entry:
  type: builtin
  handler: handler
"""
        tool_path.write_text(modified_yaml, encoding="utf-8")

        # 重载
        await engine.reload()

        tool = engine.get("test_tool")
        assert tool.description == "修改后的描述"
        assert tool.version == "2.0.0"

    @pytest.mark.asyncio
    async def test_reload_detects_deleted_file(self, tmp_path):
        """测试：重载检测删除的文件"""
        tool1 = """
name: tool_1
description: 工具1
category: custom
entry:
  type: builtin
  handler: handler1
"""
        tool2 = """
name: tool_2
description: 工具2
category: custom
entry:
  type: builtin
  handler: handler2
"""
        tool1_path = tmp_path / "tool_1.yaml"
        tool2_path = tmp_path / "tool_2.yaml"
        tool1_path.write_text(tool1, encoding="utf-8")
        tool2_path.write_text(tool2, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        assert engine.tool_count == 2

        # 删除一个工具
        tool2_path.unlink()

        # 重载
        await engine.reload()

        assert engine.tool_count == 1
        assert engine.get("tool_1") is not None
        assert engine.get("tool_2") is None

    @pytest.mark.asyncio
    async def test_reload_returns_changes(self, tmp_path):
        """测试：重载返回变更信息"""
        tool1 = """
name: tool_1
description: 工具1
category: custom
entry:
  type: builtin
  handler: handler1
"""
        (tmp_path / "tool_1.yaml").write_text(tool1, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 添加新工具
        tool2 = """
name: tool_2
description: 工具2
category: custom
entry:
  type: builtin
  handler: handler2
"""
        (tmp_path / "tool_2.yaml").write_text(tool2, encoding="utf-8")

        # 修改现有工具
        modified = """
name: tool_1
description: 修改后
category: custom
version: "2.0.0"
entry:
  type: builtin
  handler: handler1
"""
        (tmp_path / "tool_1.yaml").write_text(modified, encoding="utf-8")

        changes = await engine.reload()

        assert "added" in changes
        assert "modified" in changes
        assert "tool_2" in changes["added"]
        assert "tool_1" in changes["modified"]

    @pytest.mark.asyncio
    async def test_register_tool_manually(self, tmp_path):
        """测试：手动注册工具"""
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        assert engine.tool_count == 0

        # 手动注册工具
        tool = Tool(
            id="tool_manual",
            name="manual_tool",
            description="手动注册的工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
        )
        engine.register(tool)

        assert engine.tool_count == 1
        assert engine.get("manual_tool") is not None

    @pytest.mark.asyncio
    async def test_unregister_tool(self, tmp_path):
        """测试：注销工具"""
        tool1 = """
name: tool_1
description: 工具1
category: custom
entry:
  type: builtin
  handler: handler1
"""
        (tmp_path / "tool_1.yaml").write_text(tool1, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        assert engine.tool_count == 1

        engine.unregister("tool_1")

        assert engine.tool_count == 0
        assert engine.get("tool_1") is None


# =============================================================================
# 第六部分：事件系统测试
# =============================================================================


class TestToolEngineEvents:
    """ToolEngine 事件系统测试"""

    @pytest.mark.asyncio
    async def test_on_tool_loaded_event(self, tmp_path):
        """测试：工具加载事件"""
        tool_yaml = """
name: test_tool
description: 测试工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        (tmp_path / "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)

        events = []

        def on_event(event: ToolEngineEvent):
            events.append(event)

        engine.subscribe(on_event)
        await engine.load()

        # 检查是否收到事件
        loaded_events = [e for e in events if e.event_type == ToolEngineEventType.TOOL_LOADED]
        assert len(loaded_events) >= 1

    @pytest.mark.asyncio
    async def test_on_tool_added_event(self, tmp_path):
        """测试：工具添加事件"""
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        events = []

        def on_event(event: ToolEngineEvent):
            events.append(event)

        engine.subscribe(on_event)

        # 手动注册工具
        tool = Tool(
            id="tool_new",
            name="new_tool",
            description="新工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
        )
        engine.register(tool)

        added_events = [e for e in events if e.event_type == ToolEngineEventType.TOOL_ADDED]
        assert len(added_events) == 1
        assert added_events[0].tool_name == "new_tool"

    @pytest.mark.asyncio
    async def test_on_tool_removed_event(self, tmp_path):
        """测试：工具移除事件"""
        tool_yaml = """
name: test_tool
description: 测试工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        (tmp_path / "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        events = []

        def on_event(event: ToolEngineEvent):
            events.append(event)

        engine.subscribe(on_event)
        engine.unregister("test_tool")

        removed_events = [e for e in events if e.event_type == ToolEngineEventType.TOOL_REMOVED]
        assert len(removed_events) == 1
        assert removed_events[0].tool_name == "test_tool"

    @pytest.mark.asyncio
    async def test_unsubscribe(self, tmp_path):
        """测试：取消订阅"""
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)

        events = []

        def on_event(event: ToolEngineEvent):
            events.append(event)

        engine.subscribe(on_event)
        engine.unsubscribe(on_event)

        await engine.load()

        # 取消订阅后不应收到事件
        assert len(events) == 0


# =============================================================================
# 第七部分：并发安全测试
# =============================================================================


class TestToolEngineConcurrency:
    """ToolEngine 并发安全测试"""

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, tmp_path):
        """测试：并发读取"""
        tools = [
            f"""
name: tool_{i}
description: 工具{i}
category: custom
entry:
  type: builtin
  handler: handler{i}
"""
            for i in range(10)
        ]

        for i, content in enumerate(tools):
            (tmp_path / f"tool_{i}.yaml").write_text(content, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        async def read_tool(name: str):
            for _ in range(100):
                tool = engine.get(name)
                assert tool is not None
                await asyncio.sleep(0.001)

        # 并发读取
        tasks = [read_tool(f"tool_{i}") for i in range(10)]
        await asyncio.gather(*tasks)

    @pytest.mark.asyncio
    async def test_concurrent_read_write(self, tmp_path):
        """测试：并发读写"""
        tool_yaml = """
name: test_tool
description: 测试工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        (tmp_path / "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        read_count = 0
        write_count = 0

        async def reader():
            nonlocal read_count
            for _ in range(50):
                tool = engine.get("test_tool")
                if tool:
                    read_count += 1
                await asyncio.sleep(0.001)

        async def writer():
            nonlocal write_count
            for i in range(10):
                tool = Tool(
                    id=f"tool_new_{i}",
                    name=f"new_tool_{i}",
                    description=f"新工具{i}",
                    category=ToolCategory.CUSTOM,
                    status="draft",
                    version="1.0.0",
                )
                engine.register(tool)
                write_count += 1
                await asyncio.sleep(0.005)

        await asyncio.gather(reader(), reader(), writer())

        assert read_count > 0
        assert write_count == 10


# =============================================================================
# 第八部分：统计信息测试
# =============================================================================


class TestToolEngineStatistics:
    """ToolEngine 统计信息测试"""

    @pytest.mark.asyncio
    async def test_get_statistics(self, tmp_path):
        """测试：获取统计信息"""
        tools = [
            """
name: http_tool
description: HTTP工具
category: http
tags: [http]
entry:
  type: builtin
  handler: http
""",
            """
name: ai_tool
description: AI工具
category: ai
tags: [ai]
entry:
  type: builtin
  handler: ai
""",
            """
name: custom_tool
description: 自定义工具
category: custom
tags: [custom]
entry:
  type: builtin
  handler: custom
""",
        ]

        for i, content in enumerate(tools):
            (tmp_path / f"tool_{i}.yaml").write_text(content, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        stats = engine.get_statistics()

        assert stats["total_tools"] == 3
        assert stats["by_category"]["http"] == 1
        assert stats["by_category"]["ai"] == 1
        assert stats["by_category"]["custom"] == 1
        assert "load_errors" in stats
        assert "last_reload_at" in stats


# =============================================================================
# 第九部分：参数验证集成测试
# =============================================================================


class TestToolEngineParameterValidation:
    """ToolEngine 参数验证集成测试"""

    @pytest.fixture
    def tool_with_params(self, tmp_path):
        """创建带参数的工具"""
        tool_yaml = """
name: http_request
description: 发送HTTP请求
category: http
version: "1.0.0"
parameters:
  - name: url
    type: string
    required: true
    description: 请求URL
  - name: method
    type: string
    required: true
    enum: [GET, POST, PUT, DELETE]
    default: GET
    description: HTTP方法
  - name: timeout
    type: number
    required: false
    default: 30
    description: 超时时间（秒）
  - name: headers
    type: object
    required: false
    description: 请求头
entry:
  type: builtin
  handler: http_request
"""
        tool_path = tmp_path / "http_request.yaml"
        tool_path.write_text(tool_yaml, encoding="utf-8")
        return tmp_path

    @pytest.mark.asyncio
    async def test_validate_params_valid_input(self, tool_with_params):
        """测试：验证有效的参数"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {"url": "https://example.com", "method": "GET"},
        )

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.validated_params["url"] == "https://example.com"
        assert result.validated_params["method"] == "GET"
        assert result.validated_params["timeout"] == 30  # 默认值

    @pytest.mark.asyncio
    async def test_validate_params_missing_required(self, tool_with_params):
        """测试：验证缺少必填参数"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {"method": "GET"},  # 缺少 url
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type.value == "missing_required"
        assert result.errors[0].parameter_name == "url"

    @pytest.mark.asyncio
    async def test_validate_params_type_mismatch(self, tool_with_params):
        """测试：验证类型不匹配"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {"url": "https://example.com", "method": "GET", "timeout": "abc"},
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type.value == "type_mismatch"
        assert result.errors[0].parameter_name == "timeout"

    @pytest.mark.asyncio
    async def test_validate_params_invalid_enum(self, tool_with_params):
        """测试：验证无效的枚举值"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {"url": "https://example.com", "method": "INVALID"},
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type.value == "invalid_enum"
        assert result.errors[0].parameter_name == "method"

    @pytest.mark.asyncio
    async def test_validate_params_extra_params_lenient(self, tool_with_params):
        """测试：宽松模式允许多余参数"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {"url": "https://example.com", "method": "GET", "extra_param": "value"},
        )

        # 宽松模式下应该通过
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_params_extra_params_strict(self, tool_with_params):
        """测试：严格模式拒绝多余参数"""
        config = ToolEngineConfig(
            tools_directory=str(tool_with_params),
            strict_validation=True,
        )
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {"url": "https://example.com", "method": "GET", "extra_param": "value"},
        )

        assert result.is_valid is False
        assert any(e.error_type.value == "extra_parameter" for e in result.errors)

    @pytest.mark.asyncio
    async def test_validate_params_or_raise_valid(self, tool_with_params):
        """测试：validate_params_or_raise 有效参数"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        validated = engine.validate_params_or_raise(
            "http_request",
            {"url": "https://example.com", "method": "GET"},
        )

        assert validated["url"] == "https://example.com"
        assert validated["method"] == "GET"
        assert validated["timeout"] == 30

    @pytest.mark.asyncio
    async def test_validate_params_or_raise_invalid(self, tool_with_params):
        """测试：validate_params_or_raise 无效参数抛出异常"""
        from src.domain.services.tool_parameter_validator import ToolValidationError

        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        with pytest.raises(ToolValidationError) as exc_info:
            engine.validate_params_or_raise(
                "http_request",
                {"method": "GET"},  # 缺少 url
            )

        assert exc_info.value.tool_name == "http_request"
        assert len(exc_info.value.errors) == 1

    @pytest.mark.asyncio
    async def test_validate_params_tool_not_found(self, tool_with_params):
        """测试：验证不存在的工具"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        with pytest.raises(ToolNotFoundError):
            engine.validate_params("nonexistent_tool", {"param": "value"})

    @pytest.mark.asyncio
    async def test_validate_params_with_defaults(self, tool_with_params):
        """测试：验证参数时填充默认值"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {"url": "https://example.com"},  # 只提供 url，其他使用默认
        )

        assert result.is_valid is True
        assert result.validated_params["method"] == "GET"  # 默认值
        assert result.validated_params["timeout"] == 30  # 默认值

    @pytest.mark.asyncio
    async def test_validate_params_multiple_errors(self, tool_with_params):
        """测试：多个验证错误"""
        config = ToolEngineConfig(
            tools_directory=str(tool_with_params),
            strict_validation=True,
        )
        engine = ToolEngine(config=config)
        await engine.load()

        result = engine.validate_params(
            "http_request",
            {
                "method": "INVALID",  # 无效枚举
                "timeout": "abc",  # 类型错误
                "extra": "value",  # 多余参数
            },  # 缺少 url
        )

        assert result.is_valid is False
        assert len(result.errors) >= 3  # 至少有3个错误

    @pytest.mark.asyncio
    async def test_validation_event_on_error(self, tool_with_params):
        """测试：验证错误时发送事件"""
        config = ToolEngineConfig(tools_directory=str(tool_with_params))
        engine = ToolEngine(config=config)
        await engine.load()

        events = []

        def on_event(event: ToolEngineEvent):
            events.append(event)

        engine.subscribe(on_event)

        # 触发验证错误
        engine.validate_params(
            "http_request",
            {"method": "GET"},  # 缺少 url
        )

        # 检查是否有验证错误事件
        validation_events = [
            e for e in events if e.event_type == ToolEngineEventType.VALIDATION_ERROR
        ]
        assert len(validation_events) == 1
        assert validation_events[0].tool_name == "http_request"
