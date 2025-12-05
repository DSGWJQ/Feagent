"""工具配置集成测试 - 阶段 1

测试目标：
1. 验证 tools/ 目录中所有 YAML 文件可被正确解析
2. 验证解析后的配置可以转换为 Tool 实体
3. 作为 CI 检查的一部分确保工具配置有效
"""

from pathlib import Path

import pytest

from src.domain.entities.tool import Tool
from src.domain.services.tool_config_loader import (
    ToolConfigLoader,
)
from src.domain.value_objects.tool_category import ToolCategory

# =============================================================================
# 配置
# =============================================================================

# 工具配置目录（相对于项目根目录）
TOOLS_DIR = Path(__file__).parent.parent.parent / "tools"


# =============================================================================
# 测试类
# =============================================================================


class TestToolConfigsIntegration:
    """工具配置集成测试"""

    @pytest.fixture
    def loader(self):
        """创建加载器实例"""
        return ToolConfigLoader()

    def test_tools_directory_exists(self):
        """测试：tools 目录应该存在"""
        assert TOOLS_DIR.exists(), f"工具目录不存在: {TOOLS_DIR}"
        assert TOOLS_DIR.is_dir(), f"不是目录: {TOOLS_DIR}"

    def test_tools_directory_has_yaml_files(self):
        """测试：tools 目录应该包含 YAML 文件"""
        yaml_files = list(TOOLS_DIR.glob("*.yaml")) + list(TOOLS_DIR.glob("*.yml"))
        assert len(yaml_files) > 0, "tools 目录中没有 YAML 文件"

    def test_all_yaml_files_are_valid(self, loader):
        """测试：所有 YAML 文件应该能被成功解析"""
        configs, errors = loader.load_from_directory_with_errors(str(TOOLS_DIR))

        # 如果有错误，详细报告
        if errors:
            error_messages = [f"{name}: {err}" for name, err in errors]
            pytest.fail("以下配置文件验证失败:\n" + "\n".join(error_messages))

        assert len(configs) > 0, "没有成功加载任何配置"

    def test_all_configs_can_be_converted_to_entities(self, loader):
        """测试：所有配置应该能转换为 Tool 实体"""
        configs = loader.load_from_directory(str(TOOLS_DIR))

        for config in configs:
            tool = loader.to_tool_entity(config)

            # 验证基本属性
            assert isinstance(tool, Tool)
            assert tool.id is not None
            assert tool.name == config.name
            assert tool.description == config.description
            assert isinstance(tool.category, ToolCategory)

    def test_http_request_tool_exists(self, loader):
        """测试：http_request 工具应该存在"""
        configs = loader.load_from_directory(str(TOOLS_DIR))
        names = [c.name for c in configs]

        assert "http_request" in names, "缺少 http_request 工具"

    def test_http_request_tool_has_required_parameters(self, loader):
        """测试：http_request 工具应该有必需的参数"""
        config = loader.load_from_file(str(TOOLS_DIR / "http_request.yaml"))

        param_names = [p.name for p in config.parameters]
        required_params = ["url", "method"]

        for param in required_params:
            assert param in param_names, f"http_request 缺少参数: {param}"

    def test_llm_call_tool_exists(self, loader):
        """测试：llm_call 工具应该存在"""
        configs = loader.load_from_directory(str(TOOLS_DIR))
        names = [c.name for c in configs]

        assert "llm_call" in names, "缺少 llm_call 工具"

    def test_llm_call_tool_has_required_parameters(self, loader):
        """测试：llm_call 工具应该有必需的参数"""
        config = loader.load_from_file(str(TOOLS_DIR / "llm_call.yaml"))

        param_names = [p.name for p in config.parameters]
        required_params = ["provider", "model", "messages"]

        for param in required_params:
            assert param in param_names, f"llm_call 缺少参数: {param}"

    def test_all_tools_have_valid_categories(self, loader):
        """测试：所有工具应该有有效的分类"""
        configs = loader.load_from_directory(str(TOOLS_DIR))
        valid_categories = {c.value for c in ToolCategory}

        for config in configs:
            assert (
                config.category in valid_categories
            ), f"工具 '{config.name}' 的分类 '{config.category}' 无效"

    def test_all_tools_have_entry_type(self, loader):
        """测试：所有工具应该有入口类型"""
        configs = loader.load_from_directory(str(TOOLS_DIR))

        for config in configs:
            assert "type" in config.entry, f"工具 '{config.name}' 缺少 entry.type"

    def test_javascript_tool_has_code(self, loader):
        """测试：JavaScript 工具应该包含代码"""
        # 查找 JavaScript 类型的工具
        configs = loader.load_from_directory(str(TOOLS_DIR))

        for config in configs:
            if config.entry.get("type") == "javascript":
                assert "code" in config.entry, f"JavaScript 工具 '{config.name}' 缺少 code"
                assert (
                    len(config.entry["code"]) > 0
                ), f"JavaScript 工具 '{config.name}' 的 code 为空"

    def test_python_tool_has_module_and_function(self, loader):
        """测试：Python 工具应该有模块和函数"""
        configs = loader.load_from_directory(str(TOOLS_DIR))

        for config in configs:
            if config.entry.get("type") == "python":
                assert "module" in config.entry, f"Python 工具 '{config.name}' 缺少 module"
                assert "function" in config.entry, f"Python 工具 '{config.name}' 缺少 function"

    def test_export_and_reimport_all_tools(self, loader):
        """测试：所有工具导出再导入应该保持一致"""
        configs = loader.load_from_directory(str(TOOLS_DIR))

        for config in configs:
            # 转换为实体
            tool = loader.to_tool_entity(config)

            # 导出为 YAML
            yaml_output = loader.export_to_yaml(tool)

            # 再导入
            reimported_config = loader.parse_yaml(yaml_output)

            # 验证关键字段一致
            assert reimported_config.name == config.name
            assert reimported_config.description == config.description
            assert reimported_config.category == config.category
            assert len(reimported_config.parameters) == len(config.parameters)


class TestToolConfigValidationCI:
    """CI 验证测试"""

    def test_ci_validation_passes(self):
        """测试：CI 验证应该通过（无错误配置）"""
        from scripts.validate_tool_configs import validate_tool_configs

        success, fail, errors = validate_tool_configs(
            directory=str(TOOLS_DIR),
            verbose=False,
        )

        assert fail == 0, f"CI 验证失败: {errors}"
        assert success > 0, "没有找到任何工具配置"
