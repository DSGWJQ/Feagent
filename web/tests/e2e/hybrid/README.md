# Hybrid E2E Tests (模式 B)

## 测试模式

**混合测试模式**

- LLM Adapter: `replay` (从录制文件回放)
- HTTP Adapter: `wiremock` (通过 WireMock 服务器)
- 运行速度: 中等
- 稳定性: 高

## 用途

- 验证真实 LLM 响应的处理逻辑
- 回放真实场景进行调试
- Nightly 回归测试

## 覆盖用例

- P1 扩展用例: 基于真实 LLM 录制数据的测试

## 运行方式

```bash
# 运行所有 hybrid 测试
npx playwright test --project=hybrid

# 运行特定用例
npx playwright test ux-wf-201 --project=hybrid
```

## 环境要求

- 后端需配置 `.env.hybrid` 环境变量
- 准备 LLM 录制文件 (recordings/*.json)
- 启动 WireMock 服务器 (可选)
