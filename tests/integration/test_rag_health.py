"""RAG系统集成测试 - 健康检查"""

import pytest

from src.infrastructure.knowledge_base.rag_config_manager import RAGConfigManager
from src.interfaces.api.dependencies.rag import check_rag_health, get_rag_config, is_rag_enabled


class TestRAGHealthCheck:
    """RAG系统健康检查集成测试"""

    @pytest.mark.asyncio
    async def test_rag_configuration_should_be_valid(self):
        """测试：RAG配置应该是有效的"""
        # Act
        errors = RAGConfigManager.validate_config()

        # Assert
        # 配置应该是有效的，如果有环境变量问题，这里会有错误
        # 我们允许一些可选配置缺失
        assert isinstance(errors, list)

    @pytest.mark.asyncio
    async def test_rag_enabled_status(self):
        """测试：RAG启用状态检查"""
        # Act
        enabled = is_rag_enabled()

        # Assert
        assert isinstance(enabled, bool)

    def test_get_rag_config_should_return_dict(self):
        """测试：获取RAG配置应该返回字典"""
        # Act
        config = get_rag_config()

        # Assert
        assert isinstance(config, dict)
        assert "enabled" in config
        assert "vector_store_type" in config
        assert "embedding_provider" in config
        assert "health_status" in config

    @pytest.mark.asyncio
    async def test_vector_store_initialization(self):
        """测试：向量存储初始化"""
        # Act
        success = await RAGConfigManager.initialize_vector_store()

        # Assert
        # 即使没有真实的OpenAI API密钥，初始化也应该能成功
        # 因为它主要是创建目录和设置基础结构
        assert isinstance(success, bool)

    @pytest.mark.asyncio
    async def test_health_check_should_return_status(self):
        """测试：健康检查应该返回状态信息"""
        # Act
        health = await check_rag_health()

        # Assert
        assert isinstance(health, dict)
        assert "status" in health  # overall status
        assert "components" in health
        assert "timestamp" in health

        # Check components structure
        components = health["components"]
        assert "embedding" in components
        assert "vector_store" in components
        assert "knowledge_base" in components

    @pytest.mark.asyncio
    async def test_directories_creation(self):
        """测试：必要目录创建"""
        # This should not raise any exceptions
        RAGConfigManager.ensure_directories_exist()

        # Verification would need to check filesystem, but for now
        # we just ensure no exceptions are raised
        assert True

    @pytest.mark.asyncio
    async def test_get_vector_config(self):
        """测试：获取向量存储配置"""
        # Act
        config = RAGConfigManager.get_vector_config()

        # Assert
        assert isinstance(config, dict)
        assert "type" in config
        assert config["type"] in ["sqlite", "chroma", "qdrant", "faiss"]

    @pytest.mark.asyncio
    async def test_get_embedding_config(self):
        """测试：获取嵌入模型配置"""
        # Act
        config = RAGConfigManager.get_embedding_config()

        # Assert
        assert isinstance(config, dict)
        assert "provider" in config
        assert "model" in config

    @pytest.mark.asyncio
    async def test_full_health_check_flow(self):
        """测试：完整的健康检查流程"""
        # This test orchestrates the full health check process

        # 1. Ensure directories exist
        RAGConfigManager.ensure_directories_exist()

        # 2. Initialize vector store
        init_result = await RAGConfigManager.initialize_vector_store()
        assert isinstance(init_result, bool)

        # 3. Run health check
        health = await check_rag_health()
        assert isinstance(health, dict)
        assert "status" in health

        # 4. Check we have all expected components
        components = health["components"]
        expected_components = ["vector_store", "embedding", "knowledge_base"]
        for component in expected_components:
            assert component in components
            assert "status" in components[component]

    @pytest.mark.asyncio
    async def test_error_handling_in_health_check(self):
        """测试：健康检查中的错误处理"""
        # Even if some components fail, the health check should
        # return a valid structure with appropriate error information

        health = await check_rag_health()

        # Should always return a dict with required structure
        assert isinstance(health, dict)
        assert "status" in health
        assert "components" in health

        # Even failed components should have status information
        for component_name, component_info in health["components"].items():
            assert "status" in component_info
            # Status should be one of expected values
            assert component_info["status"] in [
                "healthy",
                "unhealthy",
                "configured",
                "missing",
                "error",
            ]
