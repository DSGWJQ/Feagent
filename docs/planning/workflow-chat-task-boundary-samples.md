# 对话任务边界样例集（V0）

> 日期：2026-02-01
> 依据：`docs/planning/workflow-usability-capability-plan.md` §5.2-§5.3
> 口径：本样例集仅覆盖“编辑器工作流”支持的 canonical 节点类型；别名仅用于历史兼容。
> 当前约束：**仅支持 sqlite**；模型类节点仅承诺 **OpenAI provider**（fail-closed）。

## 0. 结构模板（每条样例必须包含）

- 分类：必须成功 / 必须拒绝 / 条件成功
- 需求描述（用户原话）
- 期望节点组合（canonical node types）
- 关键配置（最小可执行/最小可保存）
- 成功判定 / 失败判定（可回归、可解释）
- 备注（风险/依赖/需要澄清点）

## 1. 必须成功（deterministic 下可回归）

### S-01 HTTP mock 拉取 + 写文件

- 分类：必须成功
- 需求描述：
  “请生成一个工作流：调用订单 API 获取订单列表（可以用 mock_response），把结果保存到本地文件。”
- 期望节点组合：`start → httpRequest → file → end`
- 关键配置：
  - httpRequest.config：`url/method/mock_response`
  - file.config：`operation=write/path/content`（content 可用 `{input1}` 模板引用）
- 成功判定：deterministic 执行完成，文件写入成功，end 输出为 httpResponse 或 file result
- 失败判定：保存阶段缺 url/method/path 等必填字段；应返回可定位错误 path

### S-02 SQLite 查询 + Python 统计 + 写文件

- 分类：必须成功
- 需求描述：
  “请生成一个工作流：从 sqlite 查询销售数据，计算总销售额，输出 Markdown 报告并写入文件。”
- 期望节点组合：`start → database → python → file → end`
- 关键配置：
  - database.config：`database_url=sqlite:///...` + `sql`
  - python.config：对 rows 进行聚合并输出 `result`
  - file.config：write
- 成功判定：deterministic 执行完成，end 输出包含统计结果
- 失败判定：database_url 非 sqlite 必须在保存阶段拒绝（unsupported_database_url）

### S-03 条件分支（true/false gating）+ 只执行一个分支

- 分类：必须成功
- 需求描述：
  “输入是一个字符串，如果等于 test 就走 A 分支，否则走 B 分支，最后输出分支结果。”
- 期望节点组合：`start → conditional → javascript(A) / javascript(B) → end`
- 关键配置：
  - conditional.config：`condition: "input1 == 'test'"`
  - edge.condition：`"true"` / `"false"`
- 成功判定：不同输入只执行对应分支；执行日志可证明另一分支未执行
- 失败判定：edge.condition 不满足时被跳过必须发出 node_skipped 事件（可解释）

### S-04 range loop 生成列表

- 分类：必须成功
- 需求描述：
  “请生成一个工作流：从 0 到 4 循环，把每次 i 计算成对象并汇总返回。”
- 期望节点组合：`start → loop(range) → end`
- 关键配置：
  - loop.config：`type=range/start/end/step/code`
- 成功判定：输出为数组（长度与 end-start 一致）
- 失败判定：缺 end 或 code 必须在保存阶段拒绝（missing_end/missing_code）

### S-05 structuredOutput 抽取（schema 必填）

- 分类：必须成功
- 需求描述：
  “输入一段工单文本，请抽取 name/phone/issue/priority，输出 JSON（需要 schema）。”
- 期望节点组合：`start → structuredOutput → end`
- 关键配置：
  - structuredOutput.config：`schemaName` + `schema`（JSON object 或 JSON string）
- 成功判定：deterministic 执行返回 JSON（可为 stub），但结构合法、可序列化
- 失败判定：缺 schema/schemaName 必须保存阶段拒绝并定位字段

## 2. 必须拒绝（硬约束 / 必然执行失败）

### R-01 非 sqlite 数据库

- 分类：必须拒绝
- 需求描述：
  “请生成一个工作流：连接 MySQL 查询数据并写回 MySQL。”
- 期望节点组合：无（必须拒绝或改写为 sqlite-only 并提示）
- 关键配置：无
- 成功判定：对话侧明确提示“仅支持 sqlite”；若仍生成 database 节点，保存阶段必须拒绝（unsupported_database_url）
- 失败判定：保存通过但执行失败（禁止）

### R-02 使用 Anthropic/Claude 或 Google/Gemini provider

- 分类：必须拒绝
- 需求描述：
  “请用 Claude 3.5 Sonnet 生成营销文案，并保存到文件。”
- 期望节点组合：必须改写为 OpenAI-only（或拒绝）
- 关键配置：无
- 成功判定：对话侧提示“当前仅支持 OpenAI provider”；保存阶段必须拒绝非 openai provider（unsupported_model_provider）
- 失败判定：保存通过但执行必失败（禁止）

### R-03 请求“回边/环形”工作流

- 分类：必须拒绝
- 需求描述：
  “请生成一个会一直循环执行直到成功的工作流（用边回到前面节点）。”
- 期望节点组合：必须拒绝图层回边；可建议使用 `loop` 节点替代
- 成功判定：对话侧明确说明“workflow 是 DAG 无环”；如用户坚持回边，保存阶段应报 cycle_detected
- 失败判定：允许有环图进入系统（禁止）

## 3. 条件成功（依赖环境/数据/用户补充信息）

### C-01 tool 节点（必须提供 tool_id）

- 分类：条件成功
- 需求描述：
  “请调用天气工具查询上海天气，再把结果发到 webhook。”
- 期望节点组合：`start → tool → notification(webhook) → end`
- 关键配置：
  - tool.config：`tool_id`（必须来自允许工具列表）
  - notification.config：webhook url/message
- 成功判定：用户提供 tool_id 且 tool 存在且未废弃；否则对话侧必须 ask_clarification
- 失败判定：AI 猜测 tool_id 或保存一个缺 tool_id 的 tool 节点（禁止）

### C-02 真实 HTTP 出网

- 分类：条件成功
- 需求描述：
  “请调用真实的第三方 API 拉取数据并入库。”
- 期望节点组合：`start → httpRequest → database → end`
- 关键配置：
  - deterministic：必须用 mock_response 或 HTTP mock
  - fullreal：依赖出网与对方 API 可用性
- 成功判定：在 fullreal 下真实请求成功；在 deterministic 下可用 mock 跑通
- 失败判定：deterministic 下试图出网（违反模式门禁）

### C-03 真实 OpenAI 调用

- 分类：条件成功
- 需求描述：
  “请用 LLM 生成一份总结并保存到文件（真实调用）。"
- 期望节点组合：`start → prompt → textModel → file → end`
- 关键配置：
  - fullreal：要求 `E2E_TEST_MODE=fullreal` 且 `LLM_ADAPTER=openai` 且 `OPENAI_API_KEY` 存在
  - deterministic/hybrid：走 stub/replay
- 成功判定：fullreal 下真实返回；其他模式下 stub/replay 也可回归
- 失败判定：fullreal 配置缺失但未给出清晰错误提示（禁止）

### C-04 通知（email/slack/webhook）

- 分类：条件成功
- 需求描述：
  “当检测到异常时发送 email 给我，并附上报告。”
- 期望节点组合：`start → conditional → notification(email) → end`
- 关键配置：email 所需字段（smtp_host/sender/sender_password/recipients 等）
- 成功判定：保存阶段字段校验通过；fullreal 下依赖 SMTP/出网
- 失败判定：缺字段保存通过但执行失败（禁止）
