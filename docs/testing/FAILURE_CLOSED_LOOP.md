# E2E 失败闭环模板（Failure → Fix → Re-test → Doc Sync）

目标：将每次 E2E 失败固化为**可复现、可追溯、可回归**的最小闭环记录，避免“靠运气重跑”。

---

## 1) 分级与退出条件

### 分级（用于决定是否阻塞）
- **P0 阻塞**：deterministic 失败 / repeat-each 门禁未达标 / cleanup 有残留 / 引入外网依赖导致不确定性。
- **不稳定（flaky）**：偶发失败（可复现但概率性），必须给出根因与最小修复，并用 repeat-each 验证。
- **可延期**：非关键路径（P1/P2）或仅影响 fullreal/hybrid，且 deterministic 不受影响。

### 退出条件（最小硬指标）
- `deterministic`：`web` 下 `npx playwright test --project=deterministic` 全量通过。
- 稳定性门禁：`web` 下 `npx playwright test --project=deterministic --repeat-each=10` 通过率 ≥ 95%（P0 目标：100%）。
- cleanup：Global teardown 输出 `✅ No residual test data detected`（或等价证据）。
- deterministic 无外网依赖：无 OpenAI key/真实 HTTP 必要依赖（Stub/Mock 可用）。

---

## 2) 失败记录（必填）

### 2.1 复现命令
- 命令：
  - `cd web`
  - `npx playwright test --project=deterministic --grep "<用例ID>" --reporter=list`
- 环境变量（示例）：
  - `E2E_TEST_MODE=deterministic`
  - `LLM_ADAPTER=stub`
  - `HTTP_ADAPTER=mock`
  - `PLAYWRIGHT_API_URL=http://127.0.0.1:8000`

### 2.2 失败现象
- 失败用例/断言：`<spec>:<line>` / `<expect 详情>`
- 失败截图/trace：
  - `web/test-results/**/trace.zip`
  - `web/test-results/**/test-failed-1.png`
  - `web/playwright-report/`

### 2.3 初步判断（选择其一或多项）
- [ ] 选择器脆弱（非 `data-testid` / 依赖文本/结构）
- [ ] 等待条件错误（race / 瞬时状态错过 / timeout 太短）
- [ ] 后端非确定性（外网/LLM/随机性/并发）
- [ ] 数据残留（cleanup 不彻底 / run/workflow 未隔离）
- [ ] 环境差异（IPv6/端口占用/依赖版本）

---

## 3) 最小修复（KISS/YAGNI）

### 3.1 修复策略（必选 1 个主策略）
- **稳定选择器优先**：补 `data-testid`，测试仅使用其断言。
- **确定性优先**：deterministic 模式下禁用真实 LLM/真实 HTTP，必要时加 stub 分支。
- **时序优先**：引入最小 UI 展示窗口（避免“瞬时完成”导致断言错过），或改用 `toPass`/轮询属性。
- **数据隔离优先**：seed/cleanup 强一致；用 `source=e2e_test` 标记并批量清理。

### 3.2 修复范围声明
- 仅修改：`<文件列表>`（避免无关重构）
- 风险评估：`low|medium|high` + `<原因>`

---

## 4) 回归与证据（必填）

### 4.1 关联用例回归（最小）
- `npx playwright test --project=deterministic --grep "<用例ID>"`

### 4.2 全量回归（deterministic）
- `npx playwright test --project=deterministic`

### 4.3 稳定性门禁（repeat-each）
- `npx playwright test --project=deterministic --repeat-each=10`

---

## 5) 文档同步与落盘（必填）

### 5.1 CSV（issues/*.csv）
- 更新字段：`dev_state` / `review_*_state` / `git_state` / `refs` / `notes`
- `notes` 最小包含：
  - `evidence:<命令+结果>`
  - `risk:<level>`

### 5.2 文档
- 若 CI/入口/用法变化：同步 `docs/testing/E2E_TEST_IMPLEMENTATION_GUIDE.md`
- 若新增/变更规则：同步 `docs/testing/DATA_TESTID_CATALOG.md` 或相关文档

---

## 6) 演练示例（已走通）

### 示例：E2EDOC-060（deterministic flaky 修复闭环）
- 失败点（代表性）：
  - `UX-WF-005`：事件回放断言与 UI 展示不稳定（事件数/回放可见性）
  - `UX-WF-101`：chat API 偶发 10s 超时（请求超时导致 flaky）
- 最小修复策略：
  - 测试断言从“固定事件数量”改为“事件序列完整性（类型/终止条件）”
  - replay 增加最小 UI 窗口，并在编辑器渲染 replay 事件列表（`data-testid`）
  - chat API 请求 timeout 提升到 30s（避免冷启动/偶发抖动）
- 回归证据：
  - `web: npx playwright test --project=deterministic`：29/29 passed
  - `web: npx playwright test --project=deterministic --repeat-each=10`：290/290 passed
- 代码与 CSV 同步提交：
  - commit：`7a4c7d2`
