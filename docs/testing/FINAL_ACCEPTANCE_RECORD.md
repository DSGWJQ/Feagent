# 最终验收记录（E2E）

> **验收日期**：2026-01-07
> **验收范围**：E2E deterministic（PR 回归门禁）+ CI 入口（PR deterministic / nightly fullreal）
> **验收目标**：可复现、可追溯、可诊断（失败有产物，不靠重跑）

---

## 1) 执行命令与结果证据

### 1.1 deterministic 全量回归（本地）
- 命令：
  - `cd web`
  - `npx playwright test --project=deterministic --reporter=list`
- 结果：`29/29 passed`（用例全部通过）

### 1.2 deterministic 稳定性门禁（repeat-each）
- 命令：
  - `cd web`
  - `npx playwright test --project=deterministic --repeat-each=10 --reporter=list`
- 结果：`290/290 passed`（通过率 100% ≥ 95% 门禁）

### 1.3 失败产物与定位入口（Playwright）
- 产物目录（失败时生成）：
  - `web/test-results/`（trace/screenshot/video）
  - `web/playwright-report/`（HTML 报告）
- 典型定位命令：
  - `cd web`
  - `npx playwright show-trace <trace.zip>`

---

## 2) CI 入口核验（配置一致性）

### 2.1 GitHub Actions（统一入口）
- 文件：`.github/workflows/ci.yml`
- PR（deterministic）：job `e2e-deterministic`
- Nightly（fullreal）：job `e2e-fullreal`（`schedule` 触发）
- 失败产物：CI 失败时上传 `web/playwright-report` / `web/test-results` / `web/test-results.json`

---

## 3) 已知限制与风险

### 3.1 Full-real（nightly）依赖
- fullreal 需要 `OPENAI_API_KEY`（成本/配额/网络波动不可控）
- 本地 fullreal 手动验收（需要密钥）：
  - `cd web`
  - `E2E_TEST_MODE=fullreal LLM_ADAPTER=openai HTTP_ADAPTER=httpx OPENAI_API_KEY=... npx playwright test --project=fullreal`

### 3.2 Hybrid（中间态）未全面落地
- hybrid 模式（replay/wiremock）目前作为路线图项推进，暂未形成强门禁。

### 3.3 Windows 与 Bash 脚本差异
- `web/tests/e2e/scripts/m4-verify.sh` 适用于 Bash 环境；Windows 可使用 `npx playwright test --repeat-each=10` 替代门禁。

风险评估：`low`（deterministic 门禁已达标；CI 入口已固化并有失败产物留存）

---

## 4) 关键提交（可追溯）

- `7a4c7d2`：deterministic 全量跑通 + repeat-each 门禁达标（修复 flaky / 选择器 / 时序 / stub）
- `924c829`：CI 入口收敛（PR deterministic + nightly fullreal + artifact）
- `b92ea97`：失败闭环模板固化（Failure → Fix → Re-test → Doc Sync）
- `ea0d8ff`：Future Roadmap（M4-M7）落地化（可执行验收矩阵）
