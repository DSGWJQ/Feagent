# E2E 测试实施指南（执行手册）

> **目标读者**：即将开始实施 E2E 测试的开发者
> **文档性质**：执行手册（告诉你"做什么"，而不是"为什么"）
> **预估总工作量**：9-14 天（约 2-3 周）

---

## 📖 快速开始（5 分钟了解全貌）

### 我们要做什么？

为 Feagent 工作流编辑器构建 **Playwright E2E 测试**，覆盖从"创建工作流"到"执行完成"的完整用户旅程。

### 为什么分这么多步骤？

因为 E2E 测试依赖三个基础设施：
1. **测试数据准备**（Seed API）：快速创建预定义的测试 workflow
2. **依赖隔离**（模式切换）：让测试不依赖真实 LLM/外部 API
3. **稳定选择器**（data-testid）：让 Playwright 能可靠地找到 UI 元素

### 实施路线图

```
步骤 0: 前置验证 ✅ 已完成
   └─ 验证 API 端点、SSE 事件、配置开关

步骤 1: M0 数据准备（2-3 天）
   ├─ 1.1 实现 Seed API（后端）
   └─ 1.2 添加 data-testid（前端）
   ⚠️ 可并行执行

步骤 2: M1 框架搭建（3-5 天）
   ├─ 2.1 实现模式切换机制（后端）
   ├─ 2.2 配置 Playwright 环境（前端）
   └─ 2.3 编写第一个 P0 用例

步骤 3: M2 用例实现（2-3 天）
   ├─ 3.1 完成所有 P0 用例（5 个）
   ├─ 3.2 实现清理策略
   └─ 3.3 编写 P1 用例（2 个）

步骤 4: M3 完善集成（2-3 天）
   ├─ 4.1 配置 CI Pipeline
   ├─ 4.2 添加 Full-real 模式
   └─ 4.3 编写故障排查文档
```

### 关键原则

- ✅ **一次只做一件事**：每个 checkbox 是一个独立任务
- ✅ **先验收再继续**：每个步骤都有明确的验收标准
- ✅ **遇到问题看详细文档**：主文档只告诉你做什么，详细文档告诉你怎么做

---

## 🧰 命令执行约定（bash / PowerShell）

本项目同时支持 **bash（macOS/Linux/Git Bash/WSL）** 与 **Windows PowerShell**。为避免“文档可读不可跑”，本文档对关键命令提供两种写法：

### 环境变量写法对照

```bash
# bash
export E2E_TEST_MODE=deterministic
export ENABLE_TEST_SEED_API=true
```

```powershell
# PowerShell
$env:E2E_TEST_MODE = "deterministic"
$env:ENABLE_TEST_SEED_API = "true"
```

### `curl` 多行命令说明

- bash 里用 `\` 做换行续写；PowerShell 建议用单行 `curl.exe ...`（或使用反引号 `` ` ``，但更容易出错）。

### 网络与密钥门禁（避免被 network_access 阻断）

- **Deterministic（模式 A）必须默认可跑**：不依赖外网/真实 LLM。
- **Full-real（模式 C）默认 Nightly-only**：需要 `OPENAI_API_KEY` 且需要网络访问；本地不建议频繁运行（有费用）。
- **Playwright 浏览器首次安装需要网络**：如果你的环境网络受限，请优先在允许网络的环境执行一次 `npx playwright install`，或在 CI 环境完成安装/缓存后再本地复用。

---

## 环境基线（deterministic 从零可复现）

> 目标：在 Windows PowerShell 下，从零把 deterministic E2E 跑到 “Playwright 开始执行测试”。

### 0) 版本要求（最低）

- Python：`>=3.11`（见 `pyproject.toml`）
- Node.js：建议 `>=20`（运行 `node -v`/`npm -v` 自检）
- 端口：`8000`（backend）、`5173`（web）

### 1) 后端启动（PowerShell）

> 在仓库根目录执行（新终端窗口）。

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"

$env:ENABLE_TEST_SEED_API = "true"
$env:E2E_TEST_MODE = "deterministic"
$env:LLM_ADAPTER = "stub"
$env:HTTP_ADAPTER = "mock"

python -m uvicorn src.interfaces.api.main:app --host 127.0.0.1 --port 8000
```

### 2) 前端启动（PowerShell）

> 在 `web/` 目录执行（新终端窗口）。

```powershell
Set-Location web
npm ci

# Playwright 首次安装浏览器可能需要网络；离线环境可复用已安装的浏览器缓存（默认在 %USERPROFILE%\\AppData\\Local\\ms-playwright）
npx playwright install

npm run dev -- --host 127.0.0.1 --port 5173
```

### 3) 运行 deterministic（PowerShell）

> 在 `web/` 目录执行（第三个终端窗口）。

```powershell
Set-Location web
$env:PLAYWRIGHT_API_URL = "http://127.0.0.1:8000"
$env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:5173"

# 冒烟：仅跑 UX-WF-001（验证链路跑通）
npm run test:e2e:deterministic -- --grep "UX-WF-001" --reporter=list
```

## 步骤 0: 前置验证 ✅ 已完成

### 验证结果

| 验证项 | 状态 | 说明 |
|---|---|---|
| API 端点存在性 | ✅ | 7 个关键端点均已实现 |
| SSE 事件命名 | ✅ | 前后端事件类型一致 |
| 配置开关机制 | ✅ | `disable_run_persistence` 存在 |
| 副作用识别 | ✅ | `_SIDE_EFFECT_NODE_TYPES` 完整 |

**结论**：所有前提条件满足，无阻塞性缺失，可以开始实施。

---

## 步骤 1: M0 数据准备（预估 2-3 天）

### 目标

- 后端能快速创建测试用的 workflow（Seed API）
- 前端所有关键控件都有稳定的 `data-testid`

### 前置条件

- ✅ 步骤 0 已完成

### 并行策略

步骤 1.1（后端）和步骤 1.2（前端）**可以并行执行**，互不依赖。

---

### 步骤 1.1: 实现 Seed API（后端，预估 1.5-2 天）

#### 执行清单

- [ ] **1.1.1** 创建 `WorkflowFixtureFactory`
  - 文件：`src/domain/services/workflow_fixtures.py`
  - 实现 4 个 fixture 生成函数（使用 `@register` 装饰器）
  - Fixture 类型：`main_subgraph_only` / `with_isolated_nodes` / `side_effect_workflow` / `invalid_config`

- [ ] **1.1.2** 创建 `SeedTestWorkflowUseCase`
  - 文件：`src/application/use_cases/seed_test_workflow.py`
  - 输入：`SeedTestWorkflowInput`（fixture_type, project_id, custom_metadata）
  - 输出：`SeedTestWorkflowOutput`（workflow_id, cleanup_token）

- [ ] **1.1.3** 添加 Seed API 路由
  - 文件：`src/interfaces/api/routes/test_seeds.py`
  - 端点：`POST /api/test/workflows/seed`
  - 安全控制：必须携带 `X-Test-Mode: true` 请求头

- [ ] **1.1.4** 添加清理端点
  - 端点：`DELETE /api/test/workflows/cleanup`
  - 支持按 `cleanup_tokens` 或 `metadata` 批量删除

- [ ] **1.1.5** 添加配置开关
  - 文件：`src/config.py`
  - 配置：`enable_test_seed_api: bool = False`（env: `ENABLE_TEST_SEED_API=true`）
  - 仅在测试/开发环境启用

- [ ] **1.1.6** 编写 Seed API 测试
  - 文件：`tests/integration/api/test_seed_api.py`
  - 测试 4 种 fixture 都能成功创建

#### 验收标准

运行以下命令验证：

```bash
# 1. 启动后端（测试模式）
export ENABLE_TEST_SEED_API=true
uvicorn src.interfaces.api.main:app --reload

# 2. 测试 Seed API
curl -X POST http://localhost:8000/api/test/workflows/seed \
  -H "Content-Type: application/json" \
  -H "X-Test-Mode: true" \
  -d '{"fixture_type": "main_subgraph_only", "project_id": "e2e_project"}'

# 预期响应：201 Created + workflow_id + cleanup_token
```

PowerShell 等价命令：

```powershell
# 1. 启动后端（测试模式）
$env:ENABLE_TEST_SEED_API = "true"
uvicorn src.interfaces.api.main:app --reload

# 2. 测试 Seed API（建议单行，避免 PowerShell 换行坑）
curl.exe -X POST http://localhost:8000/api/test/workflows/seed -H "Content-Type: application/json" -H "X-Test-Mode: true" -d "{\"fixture_type\":\"main_subgraph_only\",\"project_id\":\"e2e_project\"}"
```

**通过标准**：
- ✅ 返回 201 状态码
- ✅ 响应包含 `workflow_id` 和 `cleanup_token`
- ✅ 4 种 fixture_type 都能成功创建
- ✅ 缺少 `X-Test-Mode` 返回 403

#### 常见问题

- ❓ **返回 403 Forbidden**：检查是否添加了 `X-Test-Mode: true` 请求头
- ❓ **返回 400 Invalid fixture_type**：检查 `WorkflowFixtureFactory.FIXTURES` 是否注册了该类型
- ❓ **workflow 创建失败**：检查 `WorkflowRepository.save()` 是否正常工作

#### 📖 详细文档

- [SEED_API_DESIGN.md - 完整设计方案](./SEED_API_DESIGN.md)
- [SEED_API_DESIGN.md - 第 3 节：后端实现](./SEED_API_DESIGN.md#3-后端实现方案)
- [SEED_API_DESIGN.md - 第 6 节：清理策略](./SEED_API_DESIGN.md#4-清理策略)

---

### 步骤 1.2: 添加 data-testid（前端，预估 0.5-1 天）

#### 执行清单

- [ ] **1.2.1** 添加 P0 控件 testid（7 个必需）
  - `workflow-run-button`：RUN 按钮
  - `workflow-save-button`：保存按钮
  - `workflow-execution-status`：执行状态指示器
  - `workflow-canvas`：画布容器
  - `workflow-node-start`：开始节点
  - `workflow-node-end`：结束节点
  - `workflow-node-{node_id}`：动态节点（模板）

- [ ] **1.2.2** 添加副作用确认弹窗 testid（4 个必需）
  - `side-effect-confirm-modal`：确认弹窗容器
  - `confirm-allow-button`：Allow 按钮
  - `confirm-deny-button`：Deny 按钮
  - `confirm-id-hidden`：confirm_id 隐藏字段

- [ ] **1.2.3** 添加执行日志 testid（3 个推荐）
  - `execution-log-panel`：日志面板容器
  - `execution-log-entry-{index}`：日志项
  - `log-node-status-{index}`：节点状态

- [ ] **1.2.4** 添加回放相关 testid（2 个推荐）
  - `replay-run-button`：回放按钮
  - `replay-event-list`：事件列表

#### 验收标准

在浏览器开发者工具中验证：

```javascript
// 1. 打开工作流编辑器
// 2. 打开浏览器控制台，运行：

// 验证 P0 testid 存在
console.log('RUN 按钮:', document.querySelector('[data-testid="workflow-run-button"]'));
console.log('保存按钮:', document.querySelector('[data-testid="workflow-save-button"]'));
console.log('画布:', document.querySelector('[data-testid="workflow-canvas"]'));

// 验证动态 testid
console.log('开始节点:', document.querySelector('[data-testid="workflow-node-start"]'));
```

**通过标准**：
- ✅ 所有 P0 testid 都能找到对应元素
- ✅ 动态 testid 使用正确的模板格式
- ✅ 同一页面无重复 testid

#### 常见问题

- ❓ **找不到元素**：检查组件是否已渲染，可能需要等待异步加载
- ❓ **testid 重复**：使用浏览器搜索功能检查是否有重复的 `data-testid`
- ❓ **动态 ID 不生效**：检查模板字符串是否正确插值（如 `data-testid={\`workflow-node-${node.id}\`}`）

#### 📖 详细文档

- [DATA_TESTID_CATALOG.md - 完整目录](./DATA_TESTID_CATALOG.md)
- [DATA_TESTID_CATALOG.md - 第 2 节：编辑器页面](./DATA_TESTID_CATALOG.md#2-工作流编辑器页面-workflowsidedit)
- [DATA_TESTID_CATALOG.md - 第 7 节：实施建议](./DATA_TESTID_CATALOG.md#7-实施建议)

---

### 步骤 1 验收总结

完成步骤 1.1 和 1.2 后，运行以下综合验证：

```bash
# 后端验证
curl -X POST http://localhost:8000/api/test/workflows/seed \
  -H "X-Test-Mode: true" \
  -H "Content-Type: application/json" \
  -d '{"fixture_type": "main_subgraph_only"}'
# 预期：返回 workflow_id

# 前端验证
# 1. 打开浏览器访问 http://localhost:5173/workflows/{workflow_id}/edit
# 2. 打开开发者工具，验证所有 P0 testid 存在
```

PowerShell 等价命令（Seed API）：

```powershell
curl.exe -X POST http://localhost:8000/api/test/workflows/seed -H "X-Test-Mode: true" -H "Content-Type: application/json" -d "{\"fixture_type\":\"main_subgraph_only\"}"
```

**里程碑 M0 完成标志**：
- ✅ Seed API 能创建 4 种 fixture
- ✅ 前端所有 P0 testid 已添加
- ✅ 可以开始编写 Playwright 用例

---

## 步骤 2: M1 框架搭建（预估 3-5 天）

### 目标

- 实现三种测试模式切换（Deterministic/Hybrid/Full-real）
- 配置 Playwright 测试环境
- 编写并通过第一个 P0 用例

### 前置条件

- ✅ 步骤 1.1 已完成（Seed API 可用）
- ✅ 步骤 1.2 已完成（testid 已添加）

---

### 步骤 2.1: 实现模式切换机制（后端，预估 2-3 天）

#### 执行清单

- [ ] **2.1.1** 定义 Domain Ports
  - 文件：`src/domain/ports/llm_port.py`
  - 接口：`LLMPort` (Protocol) - `generate()` / `generate_streaming()`
  - 文件：`src/domain/ports/http_client_port.py`
  - 接口：`HTTPClientPort` (Protocol) - `request()`

- [ ] **2.1.2** 实现 LLM Adapters（3 种）
  - 文件：`src/infrastructure/adapters/llm_stub_adapter.py`
  - 类：`LLMStubAdapter` - 返回固定响应
  - 文件：`src/infrastructure/adapters/llm_replay_adapter.py`
  - 类：`LLMReplayAdapter` - 从录制文件回放
  - 文件：`src/infrastructure/adapters/llm_openai_adapter.py`
  - 类：`LLMOpenAIAdapter` - 真实 OpenAI 调用

- [ ] **2.1.3** 实现 HTTP Adapters（3 种）
  - 文件：`src/infrastructure/adapters/http_mock_adapter.py`
  - 类：`HTTPMockAdapter` - 本地 mock 响应
  - 文件：`src/infrastructure/adapters/http_wiremock_adapter.py`
  - 类：`HTTPWireMockAdapter` - 通过 WireMock 服务器
  - 文件：`src/infrastructure/adapters/http_httpx_adapter.py`
  - 类：`HTTPHttpxAdapter` - 真实 HTTP 请求

- [ ] **2.1.4** 实现 AdapterFactory
  - 文件：`src/interfaces/api/container.py`
  - 类：`AdapterFactory` - 根据环境变量选择 Adapter
  - 方法：`create_llm_adapter()` / `create_http_adapter()`

- [ ] **2.1.5** 添加环境变量配置
  - 文件：`src/config.py`
  - 配置：`llm_adapter: str` / `http_adapter: str`
  - 配置：`llm_replay_file: str` / `wiremock_url: str`

- [ ] **2.1.6** 创建环境配置文件
  - 文件：`.env.test` (模式 A: Deterministic)
  - 文件：`.env.hybrid` (模式 B: Hybrid)
  - 文件：`.env.fullreal` (模式 C: Full-real)

#### 验收标准

```bash
# 测试模式 A (Deterministic)
export E2E_TEST_MODE=deterministic
export LLM_ADAPTER=stub
export HTTP_ADAPTER=mock
uvicorn src.interfaces.api.main:app --reload

# 验证 LLM 返回 stub 响应
curl -X POST http://localhost:8000/api/workflows/chat-create/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "创建一个简单的工作流"}'
# 预期：返回固定的 stub 响应
```

**通过标准**：
- ✅ 使用 `.env.test` 启动，LLM 返回 stub 响应
- ✅ 使用 `.env.hybrid` 启动，LLM 返回录制响应
- ✅ 使用 `.env.fullreal` 启动，LLM 调用真实 API
- ✅ HTTP Mock 能拦截 httpbin.org 请求

#### 📖 详细文档

PowerShell 等价命令：

```powershell
$env:E2E_TEST_MODE = "deterministic"
$env:LLM_ADAPTER = "stub"
$env:HTTP_ADAPTER = "mock"
uvicorn src.interfaces.api.main:app --reload

# 验证 LLM 返回 stub 响应（建议单行，避免 PowerShell 换行坑）
curl.exe -X POST http://localhost:8000/api/workflows/chat-create/stream -H "Content-Type: application/json" -d "{\"message\":\"创建一个简单的工作流\"}"
```

- [MODE_SWITCHING_MECHANISM.md - 完整设计](./MODE_SWITCHING_MECHANISM.md)
- [MODE_SWITCHING_MECHANISM.md - 第 3 节：接口定义](./MODE_SWITCHING_MECHANISM.md#3-核心接口定义domain-layer)
- [MODE_SWITCHING_MECHANISM.md - 第 4 节：Adapters 实现](./MODE_SWITCHING_MECHANISM.md#4-实现层infrastructure-layer)

---

### 步骤 2.2: 配置 Playwright 环境（前端，预估 0.5-1 天）

#### 执行清单

- [ ] **2.2.1** 安装 Playwright
  ```bash
  cd web
  npm install -D @playwright/test
  npx playwright install
  ```

- [ ] **2.2.2** 创建 Playwright 配置
  - 文件：`web/playwright.config.ts`
  - 配置 3 个 project（deterministic/hybrid/fullreal）
  - 设置 baseURL、timeout、retries

- [ ] **2.2.3** 创建测试 fixture
  - 文件：`web/tests/e2e/fixtures/workflowFixtures.ts`
  - 实现 `seedWorkflow` fixture（调用 Seed API）
  - 实现自动清理逻辑

- [ ] **2.2.4** 创建测试目录结构
  ```
  web/tests/e2e/
  ├── fixtures/
  │   └── workflowFixtures.ts
  ├── deterministic/
  │   └── (P0 用例)
  ├── hybrid/
  │   └── (P1 用例)
  └── fullreal/
      └── (真实用例)
  ```

#### 验收标准

```bash
# 运行 Playwright 测试（空测试）
cd web
npx playwright test --project=deterministic

# 预期：测试框架正常运行（即使没有用例）
```

**通过标准**：
- ✅ Playwright 安装成功
- ✅ 配置文件无语法错误
- ✅ `seedWorkflow` fixture 能调用 Seed API
- ✅ 测试目录结构创建完成

---

### 步骤 2.3: 编写第一个 P0 用例（预估 0.5-1 天）

#### 执行清单

- [ ] **2.3.1** 编写 UX-WF-001（打开编辑器）
  - 文件：`web/tests/e2e/deterministic/ux-wf-001-open-editor.spec.ts`
  - 用例：创建 workflow → 打开编辑器 → 验证画布加载

- [ ] **2.3.2** 运行并调试用例
  ```bash
  npx playwright test ux-wf-001 --project=deterministic --headed
  ```

- [ ] **2.3.3** 修复 flaky 问题
  - 添加等待条件（`waitForSelector`）
  - 验证 testid 可访问性

#### 验收标准

```bash
# 运行第一个用例
npx playwright test ux-wf-001 --project=deterministic

# 预期：测试通过（绿色）
```

**通过标准**：
- ✅ 用例运行成功（PASSED）
- ✅ 连续运行 3 次都通过（稳定性验证）
- ✅ 失败时有截图和日志

#### 📖 详细文档

- [SEED_API_DESIGN.md - 第 6 节：Playwright 集成](./SEED_API_DESIGN.md#6-playwright-使用示例)
- [DATA_TESTID_CATALOG.md - 第 8 节：使用示例](./DATA_TESTID_CATALOG.md#73-playwright-使用示例)

---

### 步骤 2 验收总结

**里程碑 M1 完成标志**：
- ✅ 三种模式能通过环境变量切换
- ✅ Playwright 环境配置完成
- ✅ 至少 1 个 P0 用例通过
- ✅ 可以开始批量编写用例

---

## 步骤 3: M2 用例实现（预估 2-3 天）

### 目标

- 完成所有 P0 用例（5 个）
- 实现测试数据清理策略
- 编写 P1 约束防御用例（2 个）

### 前置条件

- ✅ 步骤 2.1 已完成（模式切换可用）
- ✅ 步骤 2.2 已完成（Playwright 环境就绪）
- ✅ 步骤 2.3 已完成（第一个用例通过）

---

### 步骤 3.1: 完成 P0 用例（预估 1-1.5 天）

#### 执行清单

- [ ] **3.1.1** UX-WF-002：保存工作流
  - 文件：`ux-wf-002-save-workflow.spec.ts`
  - 验证：保存成功提示 + PATCH 返回 2xx

- [ ] **3.1.2** UX-WF-003：运行工作流
  - 文件：`ux-wf-003-run-workflow.spec.ts`
  - 验证：创建 run_id + SSE 终态（completed/error）

- [ ] **3.1.3** UX-WF-004：副作用确认（deny）
  - 文件：`ux-wf-004-side-effect-deny.spec.ts`
  - 验证：弹窗出现 + deny 后明确失败

- [ ] **3.1.4** UX-WF-005：回放事件
  - 文件：`ux-wf-005-replay-events.spec.ts`
  - 验证：GET /runs/{run_id}/events 返回事件序列

#### 验收标准

```bash
# 运行所有 P0 用例
npx playwright test --project=deterministic --grep="UX-WF-00"

# 预期：5 个用例全部通过
```

**通过标准**：
- ✅ 5 个 P0 用例全部 PASSED
- ✅ 通过率 ≥ 95%（连续运行 10 次；长期目标：≥ 99%）
- ✅ 每个用例执行时间 < 30 秒

---

### 步骤 3.2: 实现清理策略（预估 0.5 天）

#### 执行清单

- [ ] **3.2.1** 实现 Playwright fixture 自动清理
  - 文件：`web/tests/e2e/fixtures/workflowFixtures.ts`
  - 策略：`cleanupTokens` fixture（function scope）在测试结束后调用 Cleanup API
  - 调试门禁：`PRESERVE_ON_FAILURE=true` 时，失败用例保留数据（输出 workflow_id/cleanup_token）

- [ ] **3.2.2** 配置全局批量清理 + 残留验证
  - 文件：`web/tests/e2e/global-teardown.ts`
  - 验证脚本：`web/tests/e2e/scripts/verify-cleanup.ts`

- [ ] **3.2.3** 验证清理效果（推荐命令）
  ```bash
  cd web
  npx playwright test --project=deterministic
  npx tsx tests/e2e/scripts/verify-cleanup.ts
  ```
  PowerShell 等价命令：
  ```powershell
  Set-Location web
  npx playwright test --project=deterministic
  npx tsx tests/e2e/scripts/verify-cleanup.ts
  ```

#### 验收标准

**通过标准**：
- ✅ 测试后残留数据 < 5%
- ✅ 清理失败时有明确日志

#### 📖 详细文档

- [P1_SUPPLEMENTS.md - P1-3：清理策略](./P1_SUPPLEMENTS.md#p1-3-db-seed-清理策略)

---

### 步骤 3.3: 编写 P1 用例（预估 0.5-1 天）

#### 执行清单

- [ ] **3.3.1** UX-WF-101：主子图约束
  - 文件：`ux-wf-101-isolated-nodes-rejected.spec.ts`
  - 验证：修改孤立节点被拒绝

- [ ] **3.3.2** UX-WF-102：保存校验失败
  - 文件：`ux-wf-102-validation-error.spec.ts`
  - 验证：返回结构化错误列表

#### 验收标准

```bash
# 运行 P1 用例
npx playwright test --project=deterministic --grep="UX-WF-10"

# 预期：2 个用例全部通过
```

**通过标准**：
- ✅ P1 用例全部 PASSED
- ✅ 错误消息可读且可定位

---

### 步骤 3 验收总结

**里程碑 M2 完成标志**：
- ✅ 所有 P0 用例通过率 ≥ 95%（连续 10 次运行；长期目标：≥ 99%）
- ✅ 清理策略有效（残留 < 5%）
- ✅ P1 约束防御用例通过
- ✅ 可以开始 CI 集成

---

## 步骤 4: M3 完善集成（预估 2-3 天）

### 目标

- 配置 CI Pipeline（PR 触发 + Nightly）
- 添加 Full-real 模式用例
- 编写故障排查文档

### 前置条件

- ✅ 步骤 3.1 已完成（P0 用例全部通过）
- ✅ 步骤 3.2 已完成（清理策略有效）

---

### 步骤 4.1: 配置 CI Pipeline（预估 1 天）

#### 执行清单

- [ ] **4.1.1** 创建 GitHub Actions 配置
  - 文件：`.github/workflows/ci.yml`（统一 CI：backend/frontend + E2E jobs）
  - 触发条件：PR/push（deterministic）+ schedule（fullreal nightly）

- [ ] **4.1.2** 配置 PR 触发（模式 A）
  ```yaml
  jobs:
    e2e-deterministic:
      runs-on: ubuntu-latest
      env:
        E2E_TEST_MODE: deterministic
        LLM_ADAPTER: stub
        HTTP_ADAPTER: mock
  ```

- [ ] **4.1.3** 配置 Nightly 触发（模式 C）
  ```yaml
  on:
    schedule:
      - cron: '0 2 * * *'  # 每天凌晨 2 点
  ```

#### 验收标准

```bash
# 本地模拟 CI 运行
cd web
export E2E_TEST_MODE=deterministic
npx playwright test --project=deterministic

# 稳定性验证（bash）：连续运行 10 次并统计通过率/产物
ITERATIONS=10 ./tests/e2e/scripts/m4-verify.sh

# 预期：所有 P0 用例通过
```

PowerShell 等价命令：

```powershell
Set-Location web
$env:E2E_TEST_MODE = "deterministic"
npx playwright test --project=deterministic

# 稳定性（PowerShell 简易版）：连续 10 次运行（结合 Playwright trace/screenshot 产物定位失败原因）
for ($i = 1; $i -le 10; $i++) {
  Write-Host ("[M4] iteration {0}/10" -f $i)
  npx playwright test --project=deterministic
  if ($LASTEXITCODE -ne 0) { break }
}
```

**通过标准**：
- ✅ PR 触发 CI 自动运行
- ✅ CI 运行时间 < 10 分钟
- ✅ 失败时有清晰的错误报告

---

### 步骤 4.2: 添加 Full-real 模式（预估 0.5-1 天）

#### 执行清单

- [ ] **4.2.1** 编写 1-2 个真实用例
  - 文件：`web/tests/e2e/fullreal/ux-wf-201-real-llm.spec.ts`
  - 用例：使用真实 LLM 创建 workflow

- [ ] **4.2.2** 配置 Nightly 运行
  - 环境变量：`OPENAI_API_KEY`（从 GitHub Secrets）
  - 超时设置：120 秒（真实 LLM 较慢）

#### 验收标准

**通过标准**：
- ✅ Full-real 用例能调用真实 LLM
- ✅ 失败时能回放（run_id + events）
- ✅ Nightly 报告可读

---

### 步骤 4.3: 编写故障排查文档（预估 0.5 天）

#### 执行清单

- [ ] **4.3.1** 整理常见问题
  - 基于步骤 1-3 遇到的实际问题
  - 补充前端/性能场景

- [ ] **4.3.2** 更新失败归因速查表
  - 文件：更新主文档附录

#### 验收标准

**通过标准**：
- ✅ 覆盖至少 15 个常见场景
- ✅ 每个场景有明确的排查步骤

---

### 步骤 4 验收总结

**里程碑 M3 完成标志**：
- ✅ CI Pipeline 正常运行
- ✅ PR 自动触发 E2E 测试
- ✅ Nightly 运行 Full-real 用例
- ✅ 故障排查文档完善

---

## 附录 A: 详细文档索引

### A.1 设计文档（实施必读）

| 文档 | 用途 | 何时阅读 |
|---|---|---|
| [SEED_API_DESIGN.md](./SEED_API_DESIGN.md) | Seed API 完整设计 | 步骤 1.1 开始前 |
| [MODE_SWITCHING_MECHANISM.md](./MODE_SWITCHING_MECHANISM.md) | 模式切换机制 | 步骤 2.1 开始前 |
| [DATA_TESTID_CATALOG.md](./DATA_TESTID_CATALOG.md) | testid 完整目录 | 步骤 1.2 开始前 |
| [P1_SUPPLEMENTS.md](./P1_SUPPLEMENTS.md) | P1 补充内容 | 步骤 3 开始前 |

### A.2 参考文档（可选阅读）

| 文档 | 用途 |
|---|---|
| [REAL_UX_E2E_TEST_PLAN.md](./REAL_UX_E2E_TEST_PLAN.md) | 原始规划文档（Codex 生成） |

---

## 附录 B: 快速故障排查

### B.1 Seed API 问题

| 现象 | 原因 | 解决方案 |
|---|---|---|
| 返回 403 Forbidden | 缺少请求头 | 添加 `X-Test-Mode: true` |
| 返回 400 Invalid fixture_type | fixture 未注册 | 检查 `WorkflowFixtureFactory.FIXTURES` |
| workflow 创建失败 | Repository 问题 | 检查 DB 连接和 `save()` 方法 |

### B.2 Playwright 问题

| 现象 | 原因 | 解决方案 |
|---|---|---|
| 找不到元素 | testid 未添加 | 检查前端组件是否有 `data-testid` |
| 测试超时 | 等待条件错误 | 使用 `waitForSelector` 而非 `waitForTimeout` |
| 测试 flaky | 竞态条件 | 添加明确的等待条件 |

### B.3 模式切换问题

| 现象 | 原因 | 解决方案 |
|---|---|---|
| LLM 返回真实响应 | 环境变量未生效 | 检查 `E2E_TEST_MODE` 和 `LLM_ADAPTER` |
| HTTP 请求未被 mock | Mock 规则缺失 | 检查 `http_mock_adapter.py` 的 `mock_responses` |
| Adapter 未找到 | Factory 配置错误 | 检查 `AdapterFactory.create_llm_adapter()` |

📖 **完整故障排查**：参见 [P1_SUPPLEMENTS.md - P1-4](./P1_SUPPLEMENTS.md#p1-4-失败归因速查表前端-性能场景补充)

🧩 **失败闭环模板**：参见 [FAILURE_CLOSED_LOOP.md](./FAILURE_CLOSED_LOOP.md)

---

## 附录 C: 验收清单总览

### P0 验收标准（必须 100% 通过）

- [ ] Seed API 返回 4 种 fixture
- [ ] Playwright 能通过 testid 定位所有 P0 控件
- [ ] 模式 A 稳定通过率 ≥ 95%（连续 10 次运行；长期目标：≥ 99%）
- [ ] 副作用确认流程：deny → 明确失败
- [ ] Replay 能回放事件序列并可见（不硬编码数量；至少包含 `node_*` + `workflow_complete/workflow_error`）

### P1 验收标准（应该通过）

- [ ] 主子图约束测试通过
- [ ] 保存校验失败返回结构化错误
- [ ] 三种模式能通过环境变量切换
- [ ] 清理策略残留率 < 5%

---

## 附录 D: 时间估算与并行策略

### 串行执行（单人）

```
步骤 0: ✅ 已完成
步骤 1: 2-3 天
步骤 2: 3-5 天
步骤 3: 2-3 天
步骤 4: 2-3 天
---
总计: 9-14 天（约 2-3 周）
```

### 并行执行（前后端分工）

```
阶段 1（并行）:
  后端: 步骤 1.1 (1.5-2 天)
  前端: 步骤 1.2 (0.5-1 天)
  实际: 2-3 天

阶段 2（串行）:
  后端: 步骤 2.1 (2-3 天)
  前端: 步骤 2.2 + 2.3 (1-2 天)
  实际: 3-5 天

阶段 3（串行）:
  步骤 3.1-3.3 (2-3 天)

阶段 4（串行）:
  步骤 4.1-4.3 (2-3 天)
---
总计: 9-14 天（约 2-3 周）
```

**关键路径**：步骤 2.1（模式切换）是最长任务，优先安排资深开发者。

---

## 更新日志

| 版本 | 日期 | 变更说明 |
|---|---|---|
| v1.0 | 2025-01-06 | 初始版本（整合 5 份文档） |

---

**文档维护者**：Claude Sonnet 4.5
**最后更新**：2025-01-06
