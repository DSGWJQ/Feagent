"""测试 LLM 配置是否正确

这个脚本用于验证：
1. LLM 客户端是否能正确创建
2. API Key 是否配置正确
3. LLM 是否能正常调用

使用方法：
1. 确保 .env 文件中配置了 OPENAI_API_KEY
2. 运行脚本：python tests/manual/test_llm_config.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# noqa: E402 - 导入必须在 sys.path 修改之后
from src.config import settings  # noqa: E402
from src.lc import get_llm, get_llm_for_execution, get_llm_for_planning  # noqa: E402


def test_llm_config():
    """测试 LLM 配置"""
    print("=" * 60)
    print("测试 LLM 配置")
    print("=" * 60)

    # 1. 检查配置
    print("\n1. 检查配置")
    print(
        f"   API Key: {settings.openai_api_key[:10]}..."
        if settings.openai_api_key
        else "   API Key: 未配置"
    )
    print(f"   Base URL: {settings.openai_base_url}")
    print(f"   Model: {settings.openai_model}")

    if not settings.openai_api_key or settings.openai_api_key == "your-api-key-here":
        print("\n❌ 错误：OPENAI_API_KEY 未配置")
        print("   请在 .env 文件中设置 OPENAI_API_KEY")
        print("   示例：")
        print("     OPENAI_API_KEY=sk-your-kimi-api-key-here")
        print("     OPENAI_BASE_URL=https://api.moonshot.cn/v1")
        print("     OPENAI_MODEL=moonshot-v1-8k")
        return False

    # 2. 创建 LLM 客户端
    print("\n2. 创建 LLM 客户端")
    try:
        llm = get_llm()
        print("   ✅ 通用 LLM 创建成功")

        _ = get_llm_for_planning()
        print("   ✅ 计划生成 LLM 创建成功")

        _ = get_llm_for_execution()
        print("   ✅ 任务执行 LLM 创建成功")
    except Exception as e:
        print(f"   ❌ 创建失败：{e}")
        return False

    # 3. 测试 LLM 调用
    print("\n3. 测试 LLM 调用")
    print("   发送测试消息：'你好，请用一句话介绍你自己'")
    try:
        response = llm.invoke("你好，请用一句话介绍你自己")
        print("   ✅ 调用成功")
        print(f"   响应：{response.content}")
    except Exception as e:
        print(f"   ❌ 调用失败：{e}")
        return False

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！LLM 配置正确")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_llm_config()
    sys.exit(0 if success else 1)
