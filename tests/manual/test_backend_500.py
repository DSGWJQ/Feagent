"""测试后端500错误

这个脚本用于诊断后端返回500状态码的问题
"""

import json

import requests

BASE_URL = "http://localhost:8000"


def test_health():
    """测试健康检查接口"""
    print("=" * 60)
    print("测试 1: 健康检查接口")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        print("✅ 健康检查成功\n")
        return True
    except Exception as e:
        print(f"❌ 健康检查失败: {e}\n")
        return False


def test_get_agents():
    """测试获取 Agent 列表"""
    print("=" * 60)
    print("测试 2: 获取 Agent 列表")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/api/agents", timeout=5)
        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            print("✅ 获取 Agent 列表成功\n")
            return True
        else:
            print(f"响应: {response.text}")
            print("❌ 获取 Agent 列表失败\n")
            return False
    except Exception as e:
        print(f"❌ 获取 Agent 列表失败: {e}\n")
        return False


def test_create_agent():
    """测试创建 Agent"""
    print("=" * 60)
    print("测试 3: 创建 Agent")
    print("=" * 60)

    data = {
        "start": "我有一个 CSV 文件，包含过去一年的销售数据",
        "goal": "分析销售数据，找出销售趋势和热门产品，生成可视化报告",
        "name": "测试 Agent",
    }

    print(f"请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/agents",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30,  # 创建 Agent 可能需要更长时间（调用 LLM）
        )

        print(f"状态码: {response.status_code}")

        if response.status_code == 201:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("✅ 创建 Agent 成功\n")
            return True, result.get("id")
        else:
            print(f"响应: {response.text}")

            # 尝试解析错误详情
            try:
                error_detail = response.json()
                print(f"错误详情: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
            except Exception:
                pass

            print("❌ 创建 Agent 失败\n")
            return False, None
    except Exception as e:
        print(f"❌ 创建 Agent 失败: {e}\n")
        import traceback

        traceback.print_exc()
        return False, None


def main():
    """主函数"""
    print("\n🔍 开始诊断后端500错误...\n")

    # 测试 1: 健康检查
    if not test_health():
        print("⚠️ 后端服务未启动，请先启动后端服务")
        print("启动命令: uvicorn src.interfaces.api.main:app --reload --port 8000")
        return

    # 测试 2: 获取 Agent 列表
    test_get_agents()

    # 测试 3: 创建 Agent
    success, agent_id = test_create_agent()

    if success:
        print("=" * 60)
        print("🎉 所有测试通过！后端工作正常")
        print("=" * 60)
    else:
        print("=" * 60)
        print("❌ 创建 Agent 失败，这可能是500错误的原因")
        print("=" * 60)
        print("\n可能的原因：")
        print("1. 数据库未初始化（运行 alembic upgrade head）")
        print("2. LLM API Key 未配置或无效（检查 .env 文件）")
        print("3. LLM 服务不可用（检查网络连接）")
        print("4. 依赖注入配置错误（检查 routes/agents.py）")
        print("5. Use Case 实现错误（检查 application/use_cases/create_agent.py）")


if __name__ == "__main__":
    main()
