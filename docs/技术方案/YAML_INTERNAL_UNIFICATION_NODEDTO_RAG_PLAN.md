# YAML 内部统一 + YAML→NodeDTO + RAG 索引（规划文档）

## 0. 背景与结论（基于现状审计）

当前仓库同时存在两套“节点/工作流”表达：

1) **编辑器工作流（DB Node/Edge + NodeType + ExecutorRegistry）**
用于前端画布拖拽、保存与执行；可执行能力以 `src/infrastructure/executors/__init__.py` 注册的执行器集合为事实源，并由 `src/domain/services/workflow_save_validator.py` 做“保存前强校验”。

2) **YAML 能力定义（definitions/nodes/*.yaml + schema/validator/catalog）**
用于能力目录/模板/自描述；启动时会加载为 `capability_definitions`（`src/interfaces/api/main.py`），并存在独立的 YAML 校验器与 JSON Schema。

现状存在三个关键问题（会直接影响可扩展性与可验收性）：
- **“校验口径不一致”**：JSON Schema / NodeYamlValidator / CapabilityCatalogService 的 `executor_type` 允许集合不同，导致同一 YAML 在不同环节得到不同结论（文档漂移）。
- **“对话规划不识别 YAML”**：Workflow chat 规划仅使用“当前 workflow 图 + tool 列表 +（可选）RAG 文本”，并不会把 YAML 当作可用节点库直接注入 system prompt。
- **“模板工作流 YAML 与执行语义不一致（历史问题）”**：`kind: workflow` 的模板中常使用 `edge.condition`；本方案已通过“执行引擎支持 edge.condition + fail-closed 语义”消除核心漂移风险，但 `definitions/nodes` 中仍存在 `kind: workflow` 文件，建议后续迁移/删除以避免误导。

因此，本方案采用**确定性编译（YAML→NodeDTO）作为主线**，并把 RAG 作为“推荐/解释”的辅线：
**主线负责“落库可用、稳定可回归”；辅线负责“让对话更懂模板/参数含义”。**

---

## 0.1 状态更新（2026-01-08）

已落地（有测试回归）：
- `edge.condition` gating（跳过节点 + 过滤 inputs，fail-closed）
- chat 增量编辑：`nodes_to_update / edges_to_update`（越界拒绝 + 白名单字段）
- config 模板渲染：执行前渲染 `node.config`（递归替换 + fail-soft）

未落地（仍是规划项）：
- YAML 内部统一（Schema/Validator/Catalog 统一口径）
- YAML→NodeDTO 编译与前端拖拽映射
- RAG 索引写入与对话规划注入
- `kind: workflow` 模板 YAML 的迁移/删除（当前仍存在）

## 1. 目标（Must）与非目标（Out）

### 1.1 Must（本次要交付）
1. **YAML 内部统一**：使 JSON Schema、NodeYamlValidator、CapabilityCatalogService 对 `executor_type` 与 `on_failure` 的允许集合一致；`scripts/validate_node_definitions.py` 成为可信验收入口。
2. **实现 YAML→NodeDTO**：从 `kind: node` YAML 生成可用于编辑器画布的 NodeDTO 模板（可直接用于拖拽创建节点实例），并确保：
   - 生成的节点类型与配置满足 `WorkflowSaveValidator` 的硬约束（fail-closed）。
   - 不依赖外部网络/真实 LLM 才能生成模板。
   - 不破坏现有测试（包含现有 YAML 相关测试）。
3. **删除“工作流模板相关内容”（kind: workflow）**：移除 `definitions/nodes/` 下的模板工作流 YAML，并保证删除不会破坏现有测试与启动加载。
4. **把 YAML 写入 RAG（索引）**：将 YAML 的“规范化摘要”写入知识库，供对话规划阶段通过 RAG 检索到（可控、可追溯、可回滚）。
5. **补齐三项真实缺口（执行/对话/模板化）**：
   - 执行引擎支持 `edge.condition`（DAG 内“按条件跳转/跳过节点”）
   - chat 增量编辑支持 “改配置/改边条件”（nodes_to_update / edges_to_update）
   - 节点 config 支持 `{input1.xxx}` 这类安全模板替换（HTTP/DB 等也可用）

### 1.2 Out（本次明确不做）
- 不把 YAML 直接变成“可执行 workflow DAG”（因为已移除 `definitions/nodes` 下的 `kind: workflow` 模板；YAML 的主职责是能力/模板，而不是运行时编排事实源）。
- 不实现“带环的 while/for 跳转”类控制流（当前保存校验仍要求无环；Loop 继续作为“数据处理节点”使用）。

---

## 2. 现状清单（用于取舍）

### 2.1 `definitions/nodes/*.yaml` 的构成（当前）
- 总数：20
- `kind: node`：15（能力定义）
- `kind: workflow`：5（仍存在；当前 validator 兼容，但建议迁移/删除以减少语义误导）

### 2.2 立即可作为 NodeDTO 模板候选的 YAML（建议保留并优先映射）
以“可映射到编辑器 NodeType + 可提供最小可运行默认 config”为筛选标准：
- `api.yaml`（`executor_type: api` → NodeType `httpRequest`）
- `file.yaml`（`executor_type: file` → NodeType `file`）
- `data_process.yaml`（`executor_type: transform/data_process` → NodeType `transform`）
- `data_collection.yaml`（`executor_type: database` → NodeType `database`）
- `llm.yaml`、`llm_analysis.yaml`（`executor_type: llm` → NodeType `textModel/llm`）
- `code.yaml`（`executor_type: code/python` → NodeType `python`；JS 不建议做可运行默认）

### 2.3 不适合直接映射为编辑器 NodeDTO 的 YAML（建议保留但标记“不可映射/仅文档或 Agent 子系统用”）
典型：`executor_type: sequential/generic/parallel/human` 这一类要么缺少编辑器运行语义，要么需要“宏节点/子图编排”能力。
方案：保留 YAML 作为“能力/模板说明”，但在 NodeDTO 生成器中 **fail-closed 排除**，并给出可观测的 skip reason。

### 2.4 需要删除的 `kind: workflow` 模板（本方案直接删）
（以仓库当前清单为准，删除前需再次 grep 确认无引用）
- `definitions/nodes/conditional_data_quality_pipeline.yaml`
- `definitions/nodes/filter_high_value_orders.yaml`
- `definitions/nodes/loop_batch_user_processing.yaml`
- `definitions/nodes/map_price_discount.yaml`
- `definitions/nodes/smart_order_processing_system.yaml`
（现已删除；任何新引入的 `kind: workflow` 将被 startup 校验 fail-fast 拒绝）

---

## 3. 路线选择：RAG vs YAML→NodeDTO（可扩展/可复用对比）

### 3.1 仅靠 RAG 的问题（不作为主线）
- **非确定性**：RAG 命中与否、LLM 是否采纳，无法形成稳定回归；难以做到“同输入必出同图”。
- **不可 fail-closed**：即使检索到了 YAML，LLM 仍可能生成不满足 SaveValidator 的 NodeDTO。
- **运维复杂**：知识库内容漂移/重复/版本冲突难追溯，出现错误难定位到具体 YAML 版本。

### 3.2 YAML→NodeDTO 的优势（推荐主线）
- **确定性**：同一份 YAML 同一版本的输出稳定；可加快照测试。
- **复用性**：前端节点面板、对话规划、文档都围绕 YAML 作为事实源（DRY）。
- **安全性（fail-closed）**：编译器能对照 `WorkflowSaveValidator` 的硬约束生成最小合法 config；不合法则拒绝导入并给出结构化错误。

### 3.3 最佳实践：主线编译 + 辅线 RAG
最终形态：
- 用户拖拽/对话生成落库：走 **YAML→NodeDTO**（强约束、可回归）
- 对话理解/推荐/解释参数：走 **RAG**（改善体验但不承担正确性）

---

## 4. 总体实施计划（分阶段、可回滚）

### Phase A：YAML 内部统一（Schema/Validator/Catalog 三方一致）

**目标**：任何 YAML 的“合法性”只存在一套权威口径；`validate_node_definitions.py` 的结果与启动加载一致。

**设计原则（SOLID/KISS）**：
- SRP：Schema 负责“结构契约”；Validator 负责“补充语义校验（如 dynamic_code 语法）”；Catalog 只做启动 fail-fast，不做第二份“白名单逻辑”。
- DRY：`executor_type` 允许集合必须只维护一处（建议在 Domain 层常量/或直接从 Schema 读取）。

**执行步骤**：
1. 选定单一事实源（推荐：**Schema** 作为最终权威，Validator/Catalog 均从 Schema 读取允许集合）。
2. 更新 `definitions/schemas/node_definition_schema.json`：
   - `executor_type.enum` 覆盖仓库实际使用的类型（至少包含：`api, code, database, file, llm, python, transform, data_process, human, parallel, condition, loop, sequential, generic, workflow, http, container`）。
   - `error_strategy.on_failure.enum` 与 Validator 允许集合一致（例如 `retry/skip/abort/replan/fallback`）。
3. 更新 `NodeYamlValidator`：
   - 去掉硬编码 `VALID_EXECUTOR_TYPES` / `VALID_ON_FAILURE_ACTIONS`（或改为从 schema 动态加载）。
4. 更新 `CapabilityCatalogService.SUPPORTED_NODE_EXECUTOR_TYPES`：
   - 改为从 schema 的 `executor_type.enum` 读取，避免维护两份集合。
5. 更新/补齐测试：
   - 新增一个“schema 与 validator 一致性”单测：断言 `schema.executor_type.enum == validator.executor_types()`。
6. 验证：
   - `python scripts/validate_node_definitions.py --strict` 必须可作为验收入口（删除 workflow 模板后应全通过）。

**回滚策略**：
- schema 与 validator/catelog 的读取逻辑保持向后兼容：读取失败时 fail-closed（启动报错）而不是悄悄放行。

---

### Phase B：删除 `kind: workflow` 模板工作流 YAML

**目标**：`definitions/nodes/` 只保留“节点能力定义（node/template）”，不再出现“workflow 蓝图”造成执行语义误导。

**执行步骤**：
1. 全仓库 grep 这 5 个 YAML 文件名/`name:` 是否被引用（docs/tests/src）。
2. 删除上述 5 个文件。
3. 新增一个回归测试/脚本检查：
   - `definitions/nodes/` 下不得存在 `kind: workflow`。
4. 再次跑 `python scripts/validate_node_definitions.py --strict`。

**注意**：本阶段只删除 workflow 模板文件；若后续确认 sequential/generic 也不需要，再另起迁移 PR（避免 scope creep）。

---

### Phase C：实现 YAML→NodeDTO（确定性编译器）

**目标**：把 `kind: node` YAML 编译为可被编辑器使用的 NodeDTO 模板；并确保输出满足保存校验的硬约束。

**核心约束（fail-closed）**：
- 只对“可映射到编辑器 NodeType 并在 executor_registry 中存在执行器”的 YAML 生成 NodeDTO。
- 对于以下情况必须拒绝（返回结构化错误/或标记 skipped）：
  - executor_type 无法映射到 NodeType
  - 需要强依赖外部系统但无法提供安全默认（例如 tool 节点但 tool_id 不存在）
  - 生成后的默认 config 无法通过 `WorkflowSaveValidator` 的硬约束（例如 http 缺 url/method，python 缺 code）

**建议落地点（架构）**：
1. 新增 `YamlNodeTemplateCompiler`（Application 层）：
   - 输入：`CapabilityDefinition`（加载自 YAML）
   - 输出：`NodeDTO`（`id/type/name/data/position`）
2. 映射表（示例）：
   - `executor_type: api/http` → NodeDTO.type=`httpRequest`，data 默认包含 `url/method/headers/body`
   - `executor_type: file` → type=`file`，data 默认 `operation/path/encoding`
   - `executor_type: llm` → type=`textModel`，data 默认 `model/temperature/maxTokens/prompt`（或要求上游 Prompt 节点供输入）
   - `executor_type: python/code` → type=`python`，data 默认 `code="result = input1"`
   - `executor_type: database` → type=`database`，data 默认 `database_url/sql="SELECT 1"`
   - `executor_type: transform/data_process` → type=`transform`，data 默认最小可运行配置（如 `type=field_mapping` + 空 mapping 需谨慎；建议用 `custom` + `function=len` 或提供最小合法 mapping）
3. 提供一个 API（供前端面板/对话规划使用）：
   - `GET /api/workflows/node-templates`（返回 NodeDTO 列表 + skipped 列表 + 版本信息）

**测试策略（不破坏原测试）**：
- 单测：对每个支持映射的 YAML，编译出的 NodeDTO 必须满足：
  - `NodeDTO.to_entity()` 不抛异常（NodeType 存在）
  - 放入一个最小 workflow（start→template→end）后 `WorkflowSaveValidator.validate_or_raise()` 通过
- 集成：启动后 API 返回稳定排序（按 name），且在 deterministic 环境下不访问网络。

---

### Phase D：将 YAML 索引进 RAG（辅线）

**目标**：让 Workflow chat 在规划阶段能检索到 YAML 的摘要文本，提高“识别节点能力/参数”的命中率；但不让 RAG 成为正确性的唯一来源。

**写入内容建议（可追溯）**：
- title：`node_def:{name}@{version}`
- content：标准化摘要（name/description/executor_type/parameters/returns/示例片段）
- metadata：
  - `kind=node_definition`
  - `source_path=definitions/nodes/xxx.yaml`
  - `executor_type=...`
  - `version=...`
  - `content_hash=...`（用于幂等与增量更新）

**触发方式（避免破坏测试）**：
1. 首选：提供脚本 `scripts/index_node_definitions_to_rag.py`（手动执行，CI 不跑）。
2. 可选：启动时自动索引（必须加 feature flag，默认关闭；且 deterministic/test 环境必须禁用）。

**验收要点**：
- 索引是幂等的：同 hash 不重复写入；变更时可更新/重建。
- RAG 不可用时 fail-soft：不影响主链路（仅记录告警/指标）。

---

### Phase E：前端 UI 映射（不新增页面，复用现有节点面板/画布）

**目标**：将 Phase C 产出的“可映射模板”接入现有工作流编辑器 UI，满足：
- 不新增路由/页面（禁止新建独立页面）
- 复用现有 `NodePalette` 与既有节点 renderer（ReactFlow `nodeTypes`）
- 模板创建的节点 **type 必须是既有的 node type**（例如 `httpRequest/file/database/textModel/python/transform/loop/conditional`），不能引入新的 ReactFlow 节点类型

**现状约束（必须遵守）**：
- 节点面板静态来源：`web/src/features/workflows/utils/nodeUtils.ts` 的 `nodeTypeConfigs`
- 默认配置来源：`getDefaultNodeData(type)`（同文件）
- 拖拽协议：DataTransfer key 为 `application/reactflow`（只传 type），画布 drop 时用 `getDefaultNodeData(type)` 生成 data（`web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`）

**设计方案（KISS + 兼容）**：
1. 后端提供模板 API（来自 Phase C 编译器）：
   - `GET /api/workflows/node-templates`
   - 返回：`templates[]`（每个模板包含：`template_id`, `node_type`, `label`, `description`, `default_data`, `source_path`, `version`）+ `skipped[]`
2. 前端不新建页面，仅增强现有编辑器：
   - 在 `WorkflowEditorPageWithMutex` 拉取 `node-templates`（建议 React Query），并传入 `NodePalette`
   - `NodePalette` 在同一组件内新增“Templates”分组（不新增页面）
3. Template 创建节点保持既有 node type：
   - Template 条目使用 `template.node_type` 作为 ReactFlow node type（必须已存在于 `nodeTypeConfigs`/`nodeTypes`）
4. 拖拽协议升级（向后兼容）：
   - Built-in 节点：仅设置 `application/reactflow = type`
   - Template 节点：额外设置 `application/x-feagent-node-template = <json>`，json 内至少包含 `node_type` 与 `default_data`
   - 画布 drop：优先读取模板 payload；没有则 fallback 旧逻辑
5. 点击添加兼容：
   - `onAddNode` 扩展为 `(type: string, defaultDataOverride?: object, labelOverride?: string)`（或等价方案）
   - Built-in 仍只传 type，Template 传 `default_data` 覆盖

**验收标准（Phase E）**：
1. 不新增页面/路由：仅修改现有工作流编辑器相关文件（NodePalette/EditorPage/api hooks），不引入新的页面入口。
2. 模板节点创建后：
   - node.type 等于模板声明的 `node_type`，且属于现有 node type 集合
   - node.data 等于模板 `default_data`（必要时合并 name/label 字段，保持配置面板可用）
3. 旧功能不回归：
   - Built-in 节点拖拽/点击添加行为不变
   - 现有前端测试（vitest/playwright 门禁）全部通过

---

### Phase F：逐模板“真实可用”验证（自动化测试 + 可复现脚本）

**目标**：对 Phase C 输出的每一个模板做“编译→保存校验→执行成功”的自动化验证；对外部依赖节点（HTTP/LLM 等）使用测试内 stub，确保 deterministic/CI 环境稳定。

**验证维度（每个模板必须全部通过）**：
1. 编译正确：YAML → template 不报错；无法映射者必须进入 `skipped` 且原因可解释
2. 可保存：组装 `start→template→end` 后 `WorkflowSaveValidator.validate_or_raise()` 必须通过
3. 可执行：执行引擎跑完且无 DomainError（外部依赖均被 stub，禁止外网）

**测试策略（按节点类型）**：
- `file`：使用 `tmp_path`，以 `write/append/read/list` 组合验证 I/O（不触碰仓库文件）
- `database`：使用临时 sqlite 文件，默认 SQL 用 `SELECT 1`（不依赖真实业务库）
- `python`：默认代码 `result = input1`，验证输入输出一致
- `transform`：选择确定性的最小配置（建议 `custom+len` 或固定 mapping），验证输出稳定
- `httpRequest`：monkeypatch `httpx.AsyncClient`（或其 `request`）返回固定响应，验证 JSON 解析路径
- `textModel`：通过 `sys.modules['openai']` 注入 fake AsyncOpenAI（或 monkeypatch），验证返回 content 解析路径

**验收标准（Phase F）**：
1. 新增后端集成测试：自动遍历编译器输出（或 `node-templates` API 的 `templates[]`），逐一验证（保存+执行）。
2. 外部依赖零泄露：测试执行期间不得产生真实网络请求（对 httpx/openai 均 stub）。
3. 全量门禁：
   - 后端：`pytest` 全通过
   - 前端：`pnpm test`/`pnpm vitest` 全通过
4. 提供本地验收入口：
   - `pytest -q tests/integration/test_node_templates_runtime.py`

## 5. 详细验收标准（可操作、可回归）

### 5.1 YAML 内部统一（Phase A）验收
1. `python scripts/validate_node_definitions.py --strict` 退出码为 0。
2. 启动应用时 `CapabilityCatalogService.load_and_validate_startup()` 不报错。
3. 单测：schema 与 validator/catelog 的允许集合一致（新增测试用例）。

### 5.2 删除 workflow 模板（Phase B）验收
1. `definitions/nodes/` 目录下不存在 `kind: workflow` 文件。
2. 全量测试通过：`pytest`（至少包含现有 YAML 相关测试集）。
3. `python scripts/validate_node_definitions.py --strict` 仍为 0。

### 5.3 YAML→NodeDTO（Phase C）验收
1. 新 API `GET /api/workflows/node-templates`：
   - 返回列表包含可映射节点（至少覆盖 api/file/llm/python/database/transform）。
   - 返回结构包含 `skipped` 列表与原因（例如 sequential/generic/human/parallel 等）。
2. 对每个“可映射 YAML”，生成的 NodeDTO 满足：
   - `NodeDTO.to_entity()` 成功
   - 组装 `start→node→end` workflow 后，`WorkflowSaveValidator.validate_or_raise()` 成功
3. 兼容性：
   - 不改变现有 `/api/workflows/chat-create/stream`、`/api/workflows/{id}/chat-stream` 行为（除非另有 PR 明确修复 chat-create 的 base-workflow 阻断点）。
4. 测试：
   - 现有测试全通过
   - 新增的编译器测试全通过

### 5.4 YAML 写入 RAG（Phase D）验收
1. 运行脚本后，`/api/knowledge/upload`/repository 中能看到对应文档记录（数量与 YAML 节点定义一致或可解释）。
2. RAG 不可用/检索为空时：
   - workflow chat 仍可工作（fail-soft）
   - 日志/指标可观测（至少能定位索引失败原因）

---

### 5.5 前端 UI 映射（Phase E）验收
1. 编辑器 UI 未新增页面/路由，仅增强现有节点面板与创建逻辑。
2. 模板节点在 UI 中创建后：
   - node.type 与既有 node types 匹配（不新增 ReactFlow nodeTypes）
   - node.data 采用模板 default_data，并可在配置面板中查看/保存
3. 前端测试不回归：`web` 的 vitest/playwright（若有门禁）全部通过。

### 5.6 逐模板运行验证（Phase F）验收
1. 后端新增集成测试会遍历所有 `templates[]` 并逐一验证保存+执行成功。
2. 测试中对 HTTP/LLM 等外部依赖全部 stub，确保 deterministic 环境稳定。
3. 全量测试门禁：`pytest` 与 `pnpm test`（或 `pnpm vitest`）均为 0 退出码。

### 5.7 条件分支语义（edge.condition）验收
1. 执行引擎按入边 `edge.condition` 决定是否执行节点：不满足则跳过，不产生 output。
2. 单测覆盖：`tests/unit/domain/services/test_workflow_executor.py`（仅执行满足条件的分支）。

### 5.8 配置模板化（{input1.xxx}）验收
1. 任何节点的 config 字符串字段支持 `{input1}` / `{input1.key}` / `{input1.arr[0]}` 等安全替换。
2. 单测覆盖：`tests/unit/domain/services/test_workflow_engine_templating.py`。

### 5.9 Chat 改配置/改边条件验收
1. 对话增量编辑支持：
   - `nodes_to_update[].config_patch`（浅合并更新配置）
   - `edges_to_update[].condition`（更新边条件）
2. 单测覆盖：`tests/unit/domain/services/test_workflow_chat_service_enhanced_modifications.py`。

---

## 6. 风险清单与对策（红队）

1) **“统一口径”改动可能触发启动 fail-fast**
对策：分阶段提交；先补齐 schema/validator 的允许集合，再收紧；并为读取 schema 失败提供清晰错误。

2) **YAML→NodeDTO 默认 config 可能导致保存通过但执行失败**
对策：编译器除满足 SaveValidator 外，还应为关键节点（http/python/file/database/loop/conditional）补齐运行时必需字段；并提供最小执行回归用例（本地执行 stream）。

3) **RAG 索引引入外部依赖导致测试不稳定**
对策：默认关闭自动索引；测试环境只允许手动脚本或禁用；索引失败不影响主流程。

---

## 7. 交付物列表（最终 PR 应包含）
- `definitions/schemas/node_definition_schema.json`（统一后的 enum）
- `src/domain/services/node_definition_spec.py`（统一枚举事实源）
- `src/domain/services/node_yaml_validator.py`（去硬编码/与 schema 一致）
- `src/application/services/capability_catalog_service.py`（从 schema 读取允许集合，或引用统一常量）
- 删除 5 个 `kind: workflow` YAML
- `src/application/services/yaml_node_template_compiler.py`（或同类命名）
- `src/interfaces/api/dto/node_templates_dto.py`（模板 DTO）
- `src/interfaces/api/routes/workflows.py`（新 API：`GET /api/workflows/node-templates`）
- `scripts/index_node_definitions_to_rag.py`（可选，强建议）
- 新增单测与集成测试（覆盖编译器与“无 workflow 模板”约束）
