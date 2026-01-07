# E2E 测试数据清理策略文档

## 概述

本文档描述了 E2E 测试的完整数据清理策略，确保测试环境的稳定性和数据独立性。

## 核心特性

### 1. 自动清理（Auto Cleanup）

每个测试用例结束后自动清理其创建的 workflow 数据。

**实现机制：**
- 使用 Playwright fixture `cleanupTokens`
- Scope 为 `function`，确保每个测试独立
- 测试结束后自动调用清理 API

**示例：**
```typescript
import { test, expect } from '../fixtures/workflowFixtures';

test('should create and save workflow', async ({ seedWorkflow }) => {
  // 创建测试 workflow
  const { workflow_id } = await seedWorkflow({
    fixtureType: 'main_subgraph_only',
  });

  // 执行测试逻辑
  // ...

  // 无需手动清理，fixture 会自动清理
});
```

### 2. 失败保留（Preserve on Failure）

测试失败时可选择保留数据用于调试。

**环境变量：**
```bash
export PRESERVE_ON_FAILURE=true
```

**行为：**
- `PRESERVE_ON_FAILURE=false`（默认）：无论测试是否通过，都清理数据
- `PRESERVE_ON_FAILURE=true`：测试失败时保留数据，成功时清理

**输出示例：**
```
[Cleanup] Test failed, preserving 2 workflow(s) for debugging:
  - workflow_id: wf_abc123 (cleanup_token: cleanup_wf_abc123)
  - workflow_id: wf_def456 (cleanup_token: cleanup_wf_def456)
```

**调试失败用例：**
1. 设置环境变量：`export PRESERVE_ON_FAILURE=true`
2. 运行测试：`npx playwright test`
3. 查看日志获取保留的 workflow_id
4. 手动清理：
```bash
curl -X DELETE http://localhost:8000/api/test/workflows/cleanup \
  -H "Content-Type: application/json" \
  -H "X-Test-Mode: true" \
  -d '{"cleanup_tokens": ["cleanup_wf_abc123", "cleanup_wf_def456"]}'
```

### 3. 批量清理（Batch Cleanup）

清理所有标记为 `source='e2e_test'` 的测试数据。

**用途：**
- 测试套件开始前清理残留数据（global setup）
- 测试套件结束后最终清理（global teardown）
- 手动清理所有测试数据

**API 调用：**
```typescript
import { batchCleanupTestData } from '../fixtures/workflowFixtures';

const stats = await batchCleanupTestData();
console.log(`Deleted ${stats.deleted} workflow(s)`);
```

**命令行调用：**
```bash
# 通过 curl
curl -X DELETE http://localhost:8000/api/test/workflows/cleanup \
  -H "Content-Type: application/json" \
  -H "X-Test-Mode: true" \
  -d '{"cleanup_tokens": [], "delete_by_source": true}'
```

### 4. 清理效果验证（Cleanup Verification）

验证清理策略的有效性，确保残留率 < 5%。

**运行验证脚本：**
```bash
# 基本运行
npx tsx web/tests/e2e/scripts/verify-cleanup.ts

# 输出 JSON 报告
OUTPUT_JSON=true npx tsx web/tests/e2e/scripts/verify-cleanup.ts

# 自定义阈值
CLEANUP_THRESHOLD=3 npx tsx web/tests/e2e/scripts/verify-cleanup.ts
```

**输出示例：**
```
========================================
E2E Test Data Cleanup Verification
========================================

API Base URL: http://localhost:8000
Cleanup Threshold: 5%

[1/3] Querying test workflows...
[2/3] Performing batch cleanup...
[2/3] Deleted 3 test workflow(s)

[3/3] Verifying residual data...

========================================
Verification Result
========================================
Total Test Workflows Processed: 3
Deleted: 3
Residual: 0
Residual Rate: 0.00%
Threshold: 5%
Status: ✅ PASSED

✅ Cleanup verification passed!
```

## 架构设计

### 清理流程图

```
测试开始
    ↓
[Global Setup]
    ├─ 清理残留数据（从上次失败/中断留下的）
    ├─ 检查环境变量
    └─ 输出配置信息
    ↓
[Test Execution]
    ├─ seedWorkflow fixture 创建数据
    │   └─ 收集 cleanup_token
    ├─ 执行测试逻辑
    └─ 测试结束
        ↓
    [cleanupTokens fixture]
        ├─ 检查测试状态 (passed/failed)
        ├─ 检查 PRESERVE_ON_FAILURE
        └─ 决定是否清理
            ├─ 清理：调用 DELETE API
            └─ 保留：输出 workflow_id 日志
    ↓
[Global Teardown]
    ├─ 执行最终批量清理
    ├─ 验证残留数据
    └─ 输出清理报告
    ↓
测试结束
```

### 清理策略决策表

| 测试状态 | PRESERVE_ON_FAILURE | 清理行为 |
|---------|---------------------|---------|
| passed  | false               | ✅ 清理  |
| passed  | true                | ✅ 清理  |
| failed  | false               | ✅ 清理  |
| failed  | true                | ❌ 保留  |
| skipped | false               | ✅ 清理  |
| skipped | true                | ✅ 清理  |

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|-----|-------|------|
| `PLAYWRIGHT_API_URL` | `http://localhost:8000` | 后端 API 地址 |
| `PRESERVE_ON_FAILURE` | `false` | 是否保留失败测试的数据 |
| `CLEANUP_THRESHOLD` | `5` | 残留率阈值（百分比） |
| `OUTPUT_JSON` | `false` | 是否输出 JSON 格式报告 |

### Playwright 配置

在 `playwright.config.ts` 中配置全局 setup/teardown：

```typescript
export default defineConfig({
  globalSetup: require.resolve('./tests/e2e/global-setup.ts'),
  globalTeardown: require.resolve('./tests/e2e/global-teardown.ts'),
  // ...
});
```

## 使用示例

### 示例 1：基本用例

```typescript
import { test, expect } from '../fixtures/workflowFixtures';

test('basic workflow test', async ({ seedWorkflow, page }) => {
  // 1. 创建测试 workflow
  const { workflow_id } = await seedWorkflow({
    fixtureType: 'main_subgraph_only',
  });

  // 2. 导航到编辑器
  await page.goto(`/workflows/${workflow_id}/edit`);

  // 3. 执行测试
  await expect(page.locator('[data-testid="workflow-canvas"]')).toBeVisible();

  // 4. 无需手动清理（fixture 自动处理）
});
```

### 示例 2：创建多个 Workflow

```typescript
test('multiple workflows test', async ({ seedWorkflow, page }) => {
  // 创建多个 workflow
  const wf1 = await seedWorkflow({ fixtureType: 'main_subgraph_only' });
  const wf2 = await seedWorkflow({ fixtureType: 'side_effect_workflow' });

  // 执行测试逻辑
  // ...

  // 两个 workflow 都会自动清理
});
```

### 示例 3：自定义 Metadata

```typescript
test('workflow with custom metadata', async ({ seedWorkflow }) => {
  const { workflow_id } = await seedWorkflow({
    fixtureType: 'main_subgraph_only',
    projectId: 'my_project',
    customMetadata: {
      test_category: 'integration',
      test_author: 'developer_name',
    },
  });

  // 执行测试逻辑
  // ...
});
```

### 示例 4：调试失败用例

```bash
# 1. 启用失败保留
export PRESERVE_ON_FAILURE=true

# 2. 运行测试（假设失败）
npx playwright test ux-wf-003-run-workflow.spec.ts

# 3. 查看输出日志
# [Cleanup] Test failed, preserving 1 workflow(s) for debugging:
#   - workflow_id: wf_abc123 (cleanup_token: cleanup_wf_abc123)

# 4. 在浏览器中手动调试
# 访问: http://localhost:5173/workflows/wf_abc123/edit

# 5. 调试完成后手动清理
curl -X DELETE http://localhost:8000/api/test/workflows/cleanup \
  -H "Content-Type: application/json" \
  -H "X-Test-Mode: true" \
  -d '{"cleanup_tokens": ["cleanup_wf_abc123"]}'
```

## CI/CD 集成

### GitHub Actions 配置示例

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd web
          npm ci
          npx playwright install

      - name: Start backend
        run: |
          export enable_test_seed_api=true
          export E2E_TEST_MODE=deterministic
          uvicorn src.interfaces.api.main:app --host 0.0.0.0 --port 8000 &
          sleep 5

      - name: Run E2E tests
        run: |
          cd web
          npx playwright test --project=deterministic
        env:
          PLAYWRIGHT_API_URL: http://localhost:8000
          PRESERVE_ON_FAILURE: false

      - name: Verify cleanup
        if: always()
        run: |
          cd web
          npx tsx tests/e2e/scripts/verify-cleanup.ts
        env:
          OUTPUT_JSON: true
          CLEANUP_THRESHOLD: 5

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: web/playwright-report/
```

## 故障排查

### 问题 1：清理 API 返回 403

**原因：** 缺少 `X-Test-Mode: true` 请求头

**解决方案：**
```typescript
// 确保在所有清理请求中添加请求头
headers: {
  'X-Test-Mode': 'true',
}
```

### 问题 2：残留率超过阈值

**原因：** 清理逻辑失败或测试中断

**排查步骤：**
1. 检查清理日志：`[Cleanup] Failed to delete...`
2. 手动执行批量清理：
```bash
curl -X DELETE http://localhost:8000/api/test/workflows/cleanup \
  -H "X-Test-Mode: true" \
  -H "Content-Type: application/json" \
  -d '{"cleanup_tokens": [], "delete_by_source": true}'
```
3. 验证数据库状态：
```bash
npx tsx web/tests/e2e/scripts/verify-cleanup.ts
```

### 问题 3：Global Setup/Teardown 未执行

**原因：** Playwright 配置错误

**检查：**
```typescript
// playwright.config.ts
export default defineConfig({
  globalSetup: require.resolve('./tests/e2e/global-setup.ts'),
  globalTeardown: require.resolve('./tests/e2e/global-teardown.ts'),
  // 确保路径正确
});
```

### 问题 4：PRESERVE_ON_FAILURE 不生效

**原因：** 环境变量未正确设置

**检查：**
```bash
# 确保在运行测试前设置
export PRESERVE_ON_FAILURE=true
npx playwright test

# 或在命令行中直接设置
PRESERVE_ON_FAILURE=true npx playwright test
```

## 最佳实践

### 1. 测试独立性

- ✅ 每个测试创建自己的数据
- ✅ 不依赖其他测试的数据
- ✅ 使用 fixture 确保清理

### 2. 失败调试

- ✅ 本地调试时启用 `PRESERVE_ON_FAILURE=true`
- ✅ CI 环境禁用失败保留（避免残留）
- ✅ 记录 workflow_id 用于手动调试

### 3. 定期验证

- ✅ 每次 PR 运行清理验证脚本
- ✅ Nightly 检查残留率趋势
- ✅ 监控清理失败率

### 4. 环境隔离

- ✅ 使用独立的测试数据库
- ✅ 测试数据标记 `source='e2e_test'`
- ✅ 避免在生产环境运行清理

## 验收标准

根据 E2E_TEST_IMPLEMENTATION_GUIDE.md 步骤 3.2 的要求：

- ✅ 使用 Pytest fixture 或 Playwright fixture
- ✅ scope="function" 确保每个测试独立清理
- ✅ 测试后调用 DELETE /api/test/workflows/cleanup API
- ✅ 支持按 cleanup_tokens 批量删除
- ✅ 支持按 metadata 标记批量删除
- ✅ 自动清理：每个测试用例结束后自动清理
- ✅ 批量清理：支持按 metadata 标记批量清理
- ✅ 失败保留：测试失败时可选择保留数据
- ✅ 验证脚本：检查测试后数据库残留
- ✅ 目标：残留率 < 5%

## 参考资料

- [E2E_TEST_IMPLEMENTATION_GUIDE.md](../../../docs/testing/E2E_TEST_IMPLEMENTATION_GUIDE.md)
- [SEED_API_DESIGN.md](../../../docs/testing/SEED_API_DESIGN.md)
- [Playwright Test Fixtures](https://playwright.dev/docs/test-fixtures)

---

**文档版本**: v1.0
**最后更新**: 2026-01-06
**维护者**: Claude Sonnet 4.5
