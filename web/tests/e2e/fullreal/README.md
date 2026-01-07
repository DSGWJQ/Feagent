# Full-Real E2E Tests (模式 C)

## 测试模式

**真实端到端测试模式**

- LLM Adapter: `openai` (真实 OpenAI API 调用)
- HTTP Adapter: `httpx` (真实 HTTP 请求)
- 运行速度: 最慢
- 稳定性: 依赖外部服务

## 用途

- Nightly 真实场景验证
- 发布前的完整集成测试
- 验证真实 LLM 响应质量

## 覆盖用例

- 真实 LLM 工作流创建测试
- 完整用户旅程验证

## 运行方式

```bash
# 运行所有 fullreal 测试 (需要 API Key)
npx playwright test --project=fullreal

# 运行特定用例
npx playwright test ux-wf-301 --project=fullreal
```

## 环境要求

- 后端需配置 `.env.fullreal` 环境变量
- 设置 `OPENAI_API_KEY` 环境变量
- 确保外部 API 可访问
- 超时设置: 120 秒 (真实 LLM 调用较慢)

## 注意事项

- 不建议在本地频繁运行 (会产生 API 费用)
- 失败时会保留 run_id 和 events 用于回放调试
- 不自动重试 (避免多次调用 API)
