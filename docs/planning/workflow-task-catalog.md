# 可生成工作流任务库（基于已注册执行器）

## 0. 范围与口径（避免误解）

- 本文“生成工作流”指：生成可保存/可执行的 workflow DAG（编辑器工作流链路/体系 B），目标是让“可拖拽节点 = 可执行节点”。
- 不在本文范围：生成完整软件项目脚手架（例如一键生成 monorepo/CI/CD、依赖安装、命令执行）。当前节点集合**不提供**命令执行与包管理能力。
- 事实源（避免口径漂移）：
  - `docs/planning/workflow-usability-acceptance-criteria-table.md`
  - `docs/planning/workflow-capability-boundary-matrix.md`
  - `docs/planning/workflow-chat-task-boundary-samples.md`

## 1. 使用说明

- 本任务库面向“对话 → 自动生成工作流”场景：每条任务都以“节点思路 + 提示词 + 可验证完成判定”给出。
- 若任务依赖外部环境（真实 HTTP/真实 OpenAI/SMTP/Slack/tool 数据），必须标注为“条件成功”，并在提示词里要求用户补充信息（或明确降级到 deterministic 版本）。
- 默认遵循 KISS：优先生成 deterministic 可回归版本（HTTP 用 `mock_response`，模型类节点走 deterministic stub），确保保存与执行闭环先跑通。

## 2. Canonical 可执行节点清单（执行边界）

`start/end/httpRequest/textModel/conditional/javascript/python/transform/prompt/imageGeneration/audio/tool/embeddingModel/structuredOutput/database/file/notification/loop`

> 说明：`http/llm/condition` 等别名仅用于历史兼容/导入；新示例与新对话生成 **禁止** 使用别名。

## 3. 生成门禁（保证“工作流能正确生成”）

### 3.1 保存阶段必须满足（fail-closed）

- **NodeType**：只允许使用上面的 canonical 节点类型。
- **图结构**：必须是 DAG（无环），且存在 `start → end` 的主连通路径。
- **database**：`database_url` 必须以 `sqlite:///` 开头（或留空使用系统默认 sqlite）；禁止 MySQL/Postgres 等非 sqlite URL。
- **模型类节点**：`textModel/embeddingModel/imageGeneration/audio/structuredOutput` 仅允许 OpenAI provider（`openai/*` 或无前缀 OpenAI 模型名）；明显非 OpenAI 的无前缀模型（如 `claude-*`、`gemini-*`）必须拒绝。
- **structuredOutput**：必须提供 `schemaName` + `schema`（JSON object 或 JSON string）。
- **tool**：必须提供 `tool_id`，且 tool 存在且未废弃；严禁猜测 `tool_id`（缺信息应 ask_clarification）。
- **notification**：按 `type` 校验必填字段（webhook.url / slack.webhook_url / email.smtp_host 等），缺字段必须拒绝保存。

### 3.2 执行模式边界（deterministic / hybrid / fullreal）

- **deterministic**：禁止真实出网；`httpRequest` 建议配置 `mock_response`；通知节点返回 stub；模型类节点返回 deterministic stub。
- **hybrid/fullreal**：允许回放或真实调用；若缺 key/网络/SMTP 等依赖，必须给出可解释失败（或在对话侧提前提示并降级）。

### 3.3 节点写法注意（避免运行期踩坑）

- **模板渲染**：工作流执行前会对所有字符串配置做占位符渲染：
  - `{input1.xxx}`（引用当前节点的第 1 个上游输入）
  - `{initial_input.xxx}`（引用“初始输入”，不随链路变化；多节点串联/项目骨架生成时更稳）
- **python**：只能使用 SAFE_BUILTINS；不要写 `import`；用 `result = ...` 输出结果。
- **javascript**：是“少量 JS 语法替换成 Python 后 exec”的简化实现；不要依赖 JS runtime；同样用 `result = ...`，不要写 `return`。
- **conditional 分支**：分支执行依赖**边条件**（edge.condition）。若不设置边条件，两个分支都会执行；建议从 conditional 到分支节点的边分别配置 `condition="true"` / `condition="false"`。
- **loop**：是“节点内迭代”，不是图层回边；无法驱动下游节点 per-item 执行（想做逐条 HTTP/逐条 LLM：当前不可表达，见 R-07）。
- **file**：`write/append` 会自动创建父目录；建议写到 `tmp/...` 或工作区相对路径，避免绝对路径副作用。

## 4. 任务场景清单（覆盖高频 + 能力边界探索）

> 任务卡模板（每条尽量可回归/可解释）：分类（必须成功/条件成功/必须拒绝） + 节点链路 + 提示词 + 关键配置（最小可保存） + 完成判定 + 边界/降级策略。

### 4.1 必须成功（deterministic 下可回归）

#### S-01 HTTP mock 拉取 → 写文件（最小闭环）

- 节点链路：`start → httpRequest → file(write) → file(read) → end`
- 提示词：
  “请生成一个工作流：调用订单 API（使用 mock_response，deterministic 不出网），把响应保存到文件，再读回文件并输出读取结果。”
- 关键配置（最小可保存）：
  - httpRequest：`url` + `method` + `mock_response`（JSON object 或 JSON string）
  - file(write)：`operation=write` + `path` + `content="{input1}"`
  - file(read)：`operation=read` + `path="{input1.path}"`
- 完成判定：保存通过；deterministic 执行到 end；end 输出包含 file.read 的 `content/size/path` 且无 `node_error`。

#### S-02 SQLite 查询 → Transform 聚合 → 写报告

- 节点链路：`start → database(SELECT) → transform(aggregation) → file(write) → end`
- 提示词：
  “请生成一个工作流：从 sqlite 查询最近30天销售数据（可用示例 SQL），对金额字段做 sum/count/avg 聚合，生成 Markdown 报告写入文件。”
- 关键配置（最小可保存）：
  - database：`database_url=sqlite:///tmp/e2e/sales.db` + `sql`
  - transform：`type=aggregation` + `field=<数组字段路径>` + `operations=["count","sum:amount","avg:amount"]`
  - file(write)：`operation=write` + `path` + `content`（可引用 `{input1}`）
- 完成判定：保存通过；deterministic 执行成功；文件写入成功（bytes_written > 0 或可读回）。

#### S-03 SQLite 写入 → 校验 rows_affected → 通知回执

- 节点链路：`start → database(INSERT/UPDATE) → conditional → notification(webhook,stub) → end`
- 提示词：
  “请生成一个工作流：向 sqlite 写入一条数据，然后判断 rows_affected 是否大于 0；成功则发送通知（deterministic 下返回 stub）并结束。”
- 关键配置（最小可保存）：
  - database：`database_url=sqlite:///tmp/e2e/write.db` + `sql`（写入语句）
  - conditional：`condition="input1['rows_affected'] > 0"`
  - edge：`conditional → notification` 配置 `condition="true"`；`conditional → end` 配置 `condition="false"`（保证失败分支仍可结束）
  - notification：`type=webhook` + `url` + `message`
- 完成判定：保存通过；deterministic 执行成功；rows_affected>0 时 notification 执行并返回 stub；否则 notification 被 `node_skipped` 且仍能到 end。

#### S-04 条件分支 gating（只执行一个分支）

- 节点链路：`start → conditional → javascript(A)/javascript(B) → end`
- 提示词：
  “请生成一个工作流：输入字符串，若等于 test 走 A 分支输出 'A'，否则走 B 分支输出 'B'，并保证只执行一个分支。”
- 关键配置（最小可保存）：
  - conditional：`condition="input1 == 'test'"`
  - edge：`conditional → javascript(A)` 配置 `condition="true"`；`conditional → javascript(B)` 配置 `condition="false"`
  - javascript(A)：`code="result = 'A'"`
  - javascript(B)：`code="result = 'B'"`
- 完成判定：不同输入只命中对应分支；未命中分支应产生 `node_skipped`（可解释）。

#### S-05 loop(range) 生成列表 → 写文件（loop 是节点内迭代）

- 节点链路：`start → loop(range) → file(write) → end`
- 提示词：
  “请生成一个工作流：用 loop(range) 从 0 到 4 生成对象列表（包含 i 和 i*i），把列表写入文件。”
- 关键配置（最小可保存）：
  - loop：`type=range` + `start/end/step` + `code="result = {'i': i, 'square': i*i}"`
  - file(write)：`operation=write` + `content="{input1}"`（input1 为 loop 输出数组）
- 完成判定：保存通过；deterministic 执行成功；文件内容为数组 JSON 串（可读回检查长度）。

#### S-06 Transform(field_mapping) 字段重组（无需写代码）

- 节点链路：`start → transform(field_mapping) → end`
- 提示词：
  “请生成一个工作流：输入是一个 JSON（含 user.profile.name 与 user.id），用 transform 做字段映射输出 {id, name}。”
- 关键配置（最小可保存）：
  - transform：`type=field_mapping` + `mapping={"id":"input1.user.id","name":"input1.user.profile.name"}`
- 完成判定：保存通过；执行输出为含 `id/name` 的对象。

#### S-07 文件操作边界：list → read → delete（可解释失败）

- 节点链路：`start → file(list) → file(read) → file(delete) → end`
- 提示词：
  “请生成一个工作流：列出 tmp 目录内容；读取指定文件；然后删除该文件并返回删除结果（路径用模板引用上游输出）。”
- 关键配置（最小可保存）：
  - file(list)：`operation=list` + `path="tmp"`
  - file(read)：`operation=read` + `path="<一个确定存在的文件>"`（若不确定必须 ask_clarification）
  - file(delete)：`operation=delete` + `path="{input1.path}"`
- 完成判定：存在文件时执行成功；文件不存在时应 `node_error` 且错误信息包含 path（可定位）。

#### S-08 structuredOutput(schema) 抽取（schema 校验边界）

- 节点链路：`start → structuredOutput → end`
- 提示词：
  “请生成一个工作流：输入工单文本，抽取 name/phone/issue/priority，使用 structuredOutput 且提供 schemaName+schema。”
- 关键配置（最小可保存）：
  - structuredOutput：`schemaName` + `schema`（JSON object 或 JSON string）
- 完成判定：保存通过；deterministic 执行返回 stub JSON（结构可序列化）；fullreal 下可返回真实抽取结果（见 C-03）。

#### S-09 embeddingModel 向量化 → 写入文件/DB（deterministic stub）

- 节点链路：`start → embeddingModel → file(write) → end`
- 提示词：
  “请生成一个工作流：对输入文本生成 embedding（deterministic 下 stub），把向量结果写入文件。”
- 关键配置（最小可保存）：
  - embeddingModel：`model="openai/text-embedding-3-small"`（或无前缀 OpenAI embedding 模型名）
  - file(write)：`operation=write` + `content="{input1}"`
- 完成判定：保存通过；deterministic 执行成功；文件写入成功。

#### S-10 “项目生成”最小骨架（多文件写入，无命令执行）

- 节点链路：`start → file(write README) → file(write main) → file(list) → end`
- 提示词：
  “请生成一个工作流：在 tmp/scaffold/ 下生成一个最小项目骨架：README.md 与 main.py（内容可用模板/固定文本），最后 list 目录并输出清单。注意：不需要执行任何命令。”
- 关键配置（最小可保存）：
  - file(write)：`operation=write` + `path="tmp/scaffold/README.md"` + `content="..."`（可引用 `{initial_input}`）
  - file(write)：`operation=write` + `path="tmp/scaffold/main.py"` + `content="print('hello')"`
  - file(list)：`operation=list` + `path="tmp/scaffold"`
- 完成判定：保存通过；deterministic 执行成功；list 输出 items 包含上述文件。

#### S-11 Prompt → textModel → 写文件/读回（覆盖 prompt/textModel）

- 节点链路：`start → prompt → textModel → file(write) → file(read) → end`
- 提示词：
  “请生成一个工作流：用 prompt 节点把输入拼成提示词，交给 textModel 生成文本（deterministic 下 stub），把输出写入文件并读回，最后输出读回内容。”
- 关键配置（最小可保存）：
  - prompt：`content`（可含 `{input1}`）
  - textModel：`model="openai/gpt-4"`（prompt 可留空以使用上游输入）
  - file(write)：`operation=write` + `path` + `content="{input1}"`
  - file(read)：`operation=read` + `path="{input1.path}"`
- 完成判定：保存通过；deterministic 执行成功；file.read 的 `content` 包含 `[deterministic stub:openai/gpt-4]`。

#### S-12 imageGeneration（deterministic stub，不出网）

- 节点链路：`start → imageGeneration → end`
- 提示词：
  “请生成一个工作流：使用 imageGeneration 生成图片；deterministic 下不出网并返回 stub；输出结果。”
- 关键配置（最小可保存）：
  - imageGeneration：`model="openai/dall-e-3"` +（可选）`aspectRatio/outputFormat` + `prompt="{input1}"`
- 完成判定：保存通过；deterministic 执行成功；输出为对象且 `stub=true`、`mode=deterministic`、`image_b64=""`。

#### S-13 audio（deterministic stub，不出网）

- 节点链路：`start → audio → end`
- 提示词：
  “请生成一个工作流：使用 audio 生成语音；deterministic 下不出网并返回 stub；输出结果。”
- 关键配置（最小可保存）：
  - audio：`model="openai/tts-1"` + `voice="alloy"` + `text="{input1}"`
- 完成判定：保存通过；deterministic 执行成功；输出为对象且 `stub=true`、`mode=deterministic`、`audio_b64=""`。

#### S-14 file(write) → file(append) → file(read)（追加语义验证）

- 节点链路：`start → file(write) → file(append) → file(read) → end`
- 提示词：
  “请生成一个工作流：先写文件 line1\\n，再 append line2\\n，然后 read 并输出最终内容。”
- 关键配置（最小可保存）：
  - file(write)：`operation=write` + `path` + `content="line1\\n"`
  - file(append)：`operation=append` + `path` + `content="line2\\n"`
  - file(read)：`operation=read` + `path`
- 完成判定：保存通过；deterministic 执行成功；file.read 的 `content == "line1\\nline2\\n"`。

#### S-15 参数化项目骨架（路径/内容模板渲染 + 可验证读回）

- 节点链路：`start → file(write README) → file(write main) → file(list) → file(read README) → transform(merge) → end`
  - 说明：`transform(merge)` 需要同时接收 `file(list)` 与 `file(read)` 两个输入（多入边），用于把“文件清单 + README 内容”合并成一个最终输出对象（便于断言）。
- 提示词：
  “请生成一个工作流：输入包含 project.name；在 tmp 目录下按 project.name 创建项目目录并生成 README.md 与 main.py；最后输出目录清单和 README 内容用于验证模板渲染。注意：不需要执行任何命令。”
- 关键配置（最小可保存）：
  - file(write README)：`operation=write` + `path="tmp/scaffold_x/{initial_input.project.name}/README.md"` + `content="# {initial_input.project.name}..."`
  - file(write main)：`operation=write` + `path="tmp/scaffold_x/{initial_input.project.name}/main.py"`
  - file(list)：`operation=list` + `path="tmp/scaffold_x/{initial_input.project.name}"`
  - file(read README)：`operation=read` + `path="tmp/scaffold_x/{initial_input.project.name}/README.md"`
  - transform(merge)：`type=field_mapping` + `mapping={project_dir:"input1.path",files:"input1.items",readme:"input2.content"}`
- 完成判定：保存通过；deterministic 执行成功；输出对象包含：
  - `project_dir` 包含 project.name
  - `files` 列表包含 `README.md` 与 `main.py`
  - `readme` 内容包含 `# <project.name>`

#### S-16 条件分支项目骨架（CLI vs Library）

- 节点链路：`start → conditional → file(write cli)/file(write lib) → file(list) → end`
- 提示词：
  “请生成一个工作流：根据输入 input.kind 选择生成 CLI(main.py) 或 Library(__init__.py) 骨架，并输出目录清单；要求 conditional 分支只执行一个分支。”
- 关键配置（最小可保存）：
  - conditional：`condition="input1.get('kind') == 'cli'"`（输入为 JSON 对象）
  - edge：`conditional → cli` 配置 `condition="true"`；`conditional → lib` 配置 `condition="false"`
  - file(write)：分别写入 `main.py` 或 `__init__.py`
  - file(list)：对生成目录 `operation=list`
- 完成判定：kind=cli 时 list 仅包含 `main.py`；否则仅包含 `__init__.py`（另一个文件不存在）。

#### S-17 tool(echo) 回显（tool_id 由用户提供，deterministic 可回归）

- 节点链路：`start → tool(echo) → end`
- 前置条件：
  - 用户必须提供 `tool_id`，且该 tool 存在且未废弃（保存门禁会校验）。
  - 可先通过 `POST /api/tools` 创建一个 `implementation_config.handler="echo"` 的 builtin tool，拿到返回的 `id` 作为 `tool_id`。
- 提示词：
  “S-17 tool_id=<tool_xxx> 请生成一个工作流：调用该 tool 回显 message，并输出 echoed 字段用于验证。”
- 关键配置（最小可保存）：
  - tool：`tool_id=<用户提供>`；`params={message:"tool_echo_<workflow_id>"}`
- 完成判定：保存通过；deterministic 执行成功；最终输出满足：`echoed == "tool_echo_<workflow_id>"`。

### 4.2 条件成功（依赖环境/数据/用户补充信息）

#### C-01 真实 HTTP 出网（fullreal）+ deterministic 降级

- 节点链路：`start → httpRequest → end`
- 提示词：
  “请生成一个工作流：调用真实第三方 API 拉取数据并返回；若在 deterministic 模式请使用 mock_response 保证不出网。”
- 关键配置（最小可保存）：
  - httpRequest：`url` + `method`；deterministic：补 `mock_response`
- 完成判定：fullreal 下真实请求成功；deterministic 下返回 mock/stub，且不触网。

#### C-02 真实 OpenAI 文本生成（fullreal）

- 节点链路：`start → prompt → textModel → file(write) → end`
- 提示词：
  “请生成一个工作流：根据输入生成摘要并写入文件。fullreal 下使用 OpenAI；其他模式下允许 stub/replay。”
- 关键配置（最小可保存）：
  - textModel：`model="openai/gpt-4"`（或无前缀 OpenAI 模型名）；如有多入边且未配置 prompt，必须提供 `promptSourceNodeId`
- 完成判定：fullreal 下需环境具备 OpenAI key/可用网络；否则必须给出可解释失败或降级策略。

#### C-03 structuredOutput 真实抽取（fullreal）

- 节点链路：`start → structuredOutput → end`
- 提示词：
  “请生成一个工作流：对输入文本做结构化抽取（schemaName+schema），fullreal 下返回真实 JSON。”
- 关键配置（最小可保存）：structuredOutput 的 `schemaName` + `schema` +（可选）`model`
- 完成判定：fullreal 下返回 JSON 且可解析；依赖 OpenAI key/网络。

#### C-04 图片生成 / 音频生成（fullreal）

- 节点链路（图片）：`start → imageGeneration → file(write) → end`
- 节点链路（音频）：`start → audio → file(write) → end`
- 提示词：
  “请生成一个工作流：根据输入生成图片/语音并保存。deterministic 下允许 stub，fullreal 下真实调用 OpenAI。”
- 关键配置（最小可保存）：`imageGeneration.model` / `audio.model`（OpenAI-only）+ file(write)
- 完成判定：fullreal 下生成 payload 并写入文件；依赖 OpenAI key/网络。

#### C-05 通知（webhook/slack/email）

- 节点链路：`start → notification → end`
- 提示词：
  “请生成一个工作流：当流程完成后发送通知。deterministic 下返回 stub；fullreal 下按配置真实发送。”
- 关键配置（最小可保存）：
  - webhook：`type=webhook` + `url` + `message`
  - slack：`type=slack` + `webhook_url` + `message`
  - email：`type=email` + `smtp_host/smtp_port/sender/sender_password/recipients` + `subject/message`
- 完成判定：fullreal 下依赖出网/SMTP/Slack webhook；缺失必须可解释失败。

#### C-06 tool 节点（必须提供 tool_id，且 tool 存在）

- 节点链路：`start → tool → end`
- 提示词：
  “请生成一个工作流：调用指定工具完成任务。请先让我提供 tool_id（不要猜测），并把 params 作为对象传入。”
- 关键配置（最小可保存）：`tool.tool_id` +（可选）`tool.params`
- 完成判定：tool_id 存在且未废弃才可成功；否则必须 fail-closed（保存拒绝或执行报错可解释）。

### 4.3 必须拒绝（硬约束 / 不可表达 / 必然失败）

#### R-01 非 sqlite 数据库（必须拒绝）

- 需求示例：
  “请生成一个工作流：连接 MySQL/Postgres 查询数据并写回。”
- 处理策略：必须拒绝或改写为 sqlite-only 并明确告知限制。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=unsupported_database_url`
  - `path` 包含 `config.database_url`

#### R-02 非 OpenAI provider / 明显非 OpenAI 模型（必须拒绝）

- 需求示例：
  “请用 Claude/Gemini 生成文案/向量/图片/语音。”
- 处理策略：必须拒绝或改写为 OpenAI-only，并提示当前承诺范围。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=unsupported_model_provider`（或 `unsupported_model`）
  - `path` 包含 `config.model`

#### R-03 请求回边/环形工作流（必须拒绝）

- 需求示例：
  “请生成一个会一直循环执行直到成功的工作流（用边回到前面节点）。”
- 处理策略：必须拒绝“图层回边/环”；可建议用 `loop` 节点做**节点内**迭代（range/while），并设置上限。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=cycle_detected`
  - `path=edges`（或包含 `edges`）

#### R-04 tool 节点缺 tool_id（必须拒绝）

- 需求示例：
  “请调用天气工具查询天气”（未提供 tool_id）。
- 处理策略：必须 ask_clarification 让用户提供 tool_id；严禁凭空猜测。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=missing_tool_id`
  - `path` 包含 `config.tool_id`

#### R-05 structuredOutput 缺 schema（必须拒绝）

- 需求示例：
  “请抽取字段并输出 JSON”（但未提供 schema）。
- 处理策略：必须要求补齐 `schemaName + schema`；若 schema 非法 JSON string，见 R-08。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=missing_schema` 且 `path` 包含 `config.schema`

#### R-06 notification(webhook) 缺 url（必须拒绝）

- 需求示例：
  “请在流程结束后发送 webhook 通知”（但未提供 url）。
- 处理策略：必须要求补齐 `url`；否则保存必拒绝（避免执行期必失败）。Slack/email 见 R-09/R-10。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=missing_url` 且 `path` 包含 `config.url`

#### R-07 “逐条调用 API/LLM（按列表循环驱动下游节点）”（当前不可表达）

- 需求示例：
  “遍历用户列表，逐个调用画像接口并汇总结果。”
- 处理策略：必须明确告知：`loop` 是节点内迭代，无法驱动下游节点 per-item 执行；可选降级：
  1) 让上游一次性提供批量接口（单次 `httpRequest` 处理所有用户），或
  2) 将逐条调用放在工作流外部系统处理后，把汇总结果作为 `start` 输入再进入工作流。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=unsupported_semantics`
  - `path` 包含 `workflow`

#### R-08 structuredOutput 的 schema 为非法 JSON string（必须拒绝）

- 需求示例：
  “请做结构化抽取（schemaName=Ticket，schema='{'）”（schema 是字符串但不可解析）。
- 处理策略：schema 为 string 时必须是可解析 JSON；否则拒绝保存（fail-closed）。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=invalid_json`
  - `path` 包含 `config.schema`

#### R-09 notification(slack) 缺 webhook_url（必须拒绝）

- 需求示例：
  “请在流程结束后发 Slack 通知”（但未提供 webhook_url）。
- 处理策略：必须要求补齐 webhook_url；否则保存必拒绝（fail-closed）。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 包含：
  - `code=missing_webhook_url`
  - `path` 包含 `config.webhook_url`

#### R-10 notification(email) 缺 smtp_host（必须拒绝）

- 需求示例：
  “请在流程结束后发邮件通知”（但未提供 smtp_host）。
- 处理策略：必须要求补齐 `smtp_host/sender/sender_password/recipients` 等字段；否则保存必拒绝（fail-closed）。
- 拒绝判定（可回归断言）：HTTP 400；`detail.code=workflow_invalid`；`detail.errors[]` 至少包含：
  - `code=missing_smtp_host`
  - `path` 包含 `config.smtp_host`

## 5. 通用提示词模板（面向对话生成）

- “请生成一个工作流。输入是：<输入类型/样例>；输出是：<输出类型>；必须包含节点：<节点链路>；并给出每个节点的最小可保存配置。若存在外部依赖（HTTP/LLM/tool/通知），请给出 deterministic 降级方案与完成判定。”

## 6. 完成评估 Checklist（评估是否完成任务）

### 6.1 生成正确性（保存前/保存时）

- 仅使用 canonical node types；不出现别名节点（`http/llm/condition` 等）。
- `start/end` 存在且主连通：`start → end` 路径可达；无环（DAG）。
- 满足硬约束：sqlite-only；OpenAI-only；structuredOutput schema 必填；tool_id 必填且存在；notification 字段完整。

### 6.2 执行正确性（deterministic 可回归）

- deterministic 模式下不出网：HTTP 有 `mock_response`（或接受 stub）；通知为 stub；模型类节点为 deterministic stub。
- 执行到 end 且无 `node_error`；分支/跳过必须可解释（`node_skipped` 有 reason）。
- 对副作用任务（写文件/写 DB）：能通过“读回/二次查询/输出字段”验证（例如 S-01/S-03 的验证链路）。

### 6.3 真实完成（fullreal 可选）

- 若用户要求真实调用：必须明确列出所需依赖（API key/出网/SMTP/tool 数据），并在缺失时 fail-closed 且错误可定位。

## 7. 自动化回归覆盖（deterministic E2E）

> 口径：下述用例均通过“对话 chat-create → 进入编辑器 → 保存 → 执行（或拒绝）”模拟真实用户操作，作为任务完成判定的回归基线。

- deterministic 模板实现：`src/domain/services/deterministic_chat_create_templates.py`
- Playwright 用例（可直接定位任务覆盖）：
  - S-01/S-05/S-08：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog.spec.ts`
  - S-03/S-04/S-06：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog-2.spec.ts`
  - S-02/S-09/S-10：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog-3.spec.ts`
  - S-07：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog-4.spec.ts`
  - S-11~S-14：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog-5.spec.ts`
  - S-15/S-16：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog-6.spec.ts`
  - S-17：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog-7.spec.ts`
  - R-01~R-10：`web/tests/e2e/deterministic/workflow-chat-create-task-catalog-reject.spec.ts`
- 建议回归命令：
  - `pnpm -C web test:e2e:deterministic -- workflow-chat-create-task-catalog`
