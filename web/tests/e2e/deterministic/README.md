# Deterministic E2E Tests (模式 A)

## 测试模式

**完全确定性测试模式**

- LLM Adapter: `stub` (固定响应)
- HTTP Adapter: `mock` (本地 mock 数据)
- 运行速度: 最快
- 稳定性: 最高

## 用途

- PR 触发的 CI 测试
- 快速回归测试
- 开发过程中的验证

## 覆盖用例

- P0 用例: UX-WF-001 ~ UX-WF-005 (核心用户流程)
- P1 用例: UX-WF-101 ~ UX-WF-102 (约束防御)

## 运行方式

```bash
# 运行所有 deterministic 测试
npx playwright test --project=deterministic

# 运行特定用例
npx playwright test ux-wf-001 --project=deterministic

# 开启 UI 模式
npx playwright test --project=deterministic --headed
```

## 环境要求

- 后端需配置 `.env.test` 环境变量
- 启用 `enable_test_seed_api=true`
- 设置 `E2E_TEST_MODE=deterministic`
