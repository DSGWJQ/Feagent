# Workflow 可用性修复与能力边界探索规划

> 本文为“可用性修复 + 测试盲区补测 + 能力边界探索”的完整规划文档，仅规划，不包含执行记录。
> 目标：在确保两套体系统一的前提下，建立可用性闭环与能力边界验证体系。

## 0. 术语与范围

- **两套体系**：
  - 体系 A：`docs/planning/workflow-task-catalog.md` 任务库与节点清单（面向用户/对话）。
  - 体系 B：真实可执行能力（执行引擎/保存校验/执行器注册/API/前端可拖拽节点）。
    - **体系 B 的事实源（Source of Truth，真实项目口径）**：
      - 节点类型（含兼容别名）：`src/domain/value_objects/node_type.py`
      - 执行器注册（node_type → executor）：`src/infrastructure/executors/__init__.py:create_executor_registry`
      - 保存前强校验（fail-closed）：`src/domain/services/workflow_save_validator.py`
      - 执行语义（DAG/edge.condition/config 模板渲染/事件）：`src/domain/services/workflow_engine.py`
      - 前端节点白名单与配置面板：`web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx` + `web/src/features/workflows/components/NodeConfigPanel.tsx`
      - 对话侧“节点类型映射/容错”（测试替身/离线可复现）：`src/infrastructure/llm/deterministic_workflow_chat_llm.py`
    - **说明（避免口径漂移）**：`src/domain/services/node_registry.py` + `src/domain/services/node_schema.py` 属于 WorkflowAgent/扩展定义体系，与“编辑器工作流(NodeType/ExecutorRegistry)”并存；本规划的“可用性验收口径”以编辑器工作流为准，必要时再补齐两者映射。
- **可用性闭环**：可表达（对话） → 可生成（节点） → 可校验（配置） → 可执行（运行） → 可解释（错误/输出）。
- **边界探索**：识别“必须成功 / 必须失败 / 依赖条件下成功”的任务边界。

## 1. 项目理解与信息补全清单（必须先完成）

### 1.1 已确认依据（已读）
- 任务库与节点清单：`docs/planning/workflow-task-catalog.md`
- 节点类型（含别名与向后兼容）：`src/domain/value_objects/node_type.py`
- 执行器注册（事实源）：`src/infrastructure/executors/__init__.py:create_executor_registry`
- 保存前强校验（事实源）：`src/domain/services/workflow_save_validator.py`
- 执行引擎（事实源）：`src/domain/services/workflow_engine.py`
- 前端节点类型映射（可拖拽节点集合）：`web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`

### 1.2 待补全信息（阻塞可用性结论的缺口）
> 未补齐前，所有结论需标注“不确定性”。

- **能力开关/依赖注入与“可执行”边界**：
  - `tool` 节点是否可执行取决于 `create_executor_registry(session_factory=...)` 是否注入；需明确各环境（dev/test/prod）的启用策略与 UI 行为（隐藏/禁用/报错）。
  - `textModel/embeddingModel/imageGeneration/audio/structuredOutput` 依赖 OpenAI Key（或替身）；需明确 deterministic/stub 策略与生产配置。
- **API 对外节点类型口径**：
  - `src/interfaces/api/routes/workflows.py` 的（deprecated）生成 prompt 已扩展到 UI 支持节点（`prompt/embeddingModel/imageGeneration/audio/structuredOutput/javascript` 等），并在 prompt 规则中明确：`tool` 受环境依赖（`session_factory` 注入/feature flag），避免生成“保存必失败”的节点。
- **前端可见性与对话可用节点**：
  - 需导出 UI palette 节点列表并与 executor registry 对齐（哪些节点隐藏/限制/实验）。
  - 需确认对话生成（真实 LLM 链路）是否与 `deterministic_workflow_chat_llm.py` 的 node types/别名映射一致。
- **“校验口径一致性”核对（P0，可用性硬门槛）**：
  - `WorkflowSaveValidator` 的规则必须与对应 executor 的硬约束一致，避免“保存通过但必然执行失败”的漂移。
    - 例：`WorkflowSaveValidator` 允许 http 节点仅提供 `path`，但 `HttpExecutor` 仅使用 `url`（需统一）。
    - 例：Loop 节点类型 `for`/`iterations`（旧 UI 口径）与 runtime `range`/`end`（执行器口径）不一致会导致执行必失败（需 normalize + 双端对齐）。
- 既有测试清单（你之前已测的场景、节点、依赖）。

**输出物**：
- 《体系对齐矩阵（草案）》
- 《信息缺口与阻塞项列表》

## 2. 可用性统一定义与验收标准

### 2.1 可用性闭环定义
1) **可表达**：用户可用自然语言清晰表达目标与约束。
2) **可生成**：系统可生成与目标一致的节点结构与配置。
3) **可校验**：节点配置通过前端表单校验 + 保存前强校验（`WorkflowSaveValidator`）+ 必要的业务校验。
4) **可执行**：执行器在依赖满足条件下运行成功。
5) **可解释**：失败时能清晰定位节点与原因；成功时有可观察结果。

### 2.2 统一验收标准（必须同时满足）
- **最小配置可跑通（可回归）**：对每个对外节点类型，至少存在一份“最小可执行配置”样例，并满足：
  - 组装 `start → node → end` 后，`WorkflowSaveValidator.validate_or_raise()` 通过；
  - 在 deterministic 环境中可执行（不触发真实外部副作用，必要时使用 stub/mock_response）。
- **失败可解释（结构化）**：
  - 保存前失败：必须返回结构化错误（`code/message/path`），且能定位到具体节点字段；
  - 执行时失败：必须可定位到 `node_id/node_type`（`WorkflowEngine` 事件：`node_start/node_error/node_complete/node_skipped`）。
- **输出可观察（可追踪）**：执行结果能通过 UI/日志/事件流观察到（至少可追溯到每个节点的输出或错误）。

**输出物**：
- 《可用性验收标准表》

## 3. 两套体系统一方案（差异修复规划）

### 3.1 差异分类
- **节点清单差异**：文档列出但系统缺失 / 系统存在但文档缺失。
- **节点配置差异**：文档示例与 SaveValidator/执行器/前端配置字段不一致。
- **节点可见性差异**：系统隐藏节点 vs 文档暴露。
- **执行器差异**：对外节点类型存在但无执行器 / 执行器存在但 UI/API/chat 未暴露或被限制。

### 3.2 统一策略（先定主方案）
- **主策略（强制）**：以体系 B 的事实源为权威，体系 A 只描述“当前版本可保存且可执行（或可解释失败）”的能力；禁止出现“文档承诺但系统不可执行”的节点/示例。
- **对外口径（强制统一）**：文档/对话/前端统一使用 `NodeType` 的 V0 名称（如 `httpRequest/textModel/conditional/...`）；兼容别名（如 `http/llm/condition`）仅用于历史兼容，不进入新示例与新文档。
- **双轨标注（用于渐进演进）**：当节点在 runtime 存在但未在 UI/API/chat 放开时，必须标注为 `EXPERIMENTAL`，并写清启用条件（feature flag / 依赖注入 / 环境变量）。

### 3.3 最小变更路径
1) 建立对齐矩阵（任务库 ↔ NodeType ↔ 执行器 ↔ SaveValidator ↔ API ↔ UI ↔ 对话映射）。
2) 以最小代价修复“阻塞可用性”的差异（P0）。
3) 更新任务库与对话模板，确保示例可执行。

**输出物**：
- 《节点对齐矩阵》
- 《差异修复清单（P0/P1/P2）》

## 4. 测试盲区与补测计划

### 4.1 盲区分类
- **节点覆盖盲区**：未测节点/隐藏节点。
- **配置边界盲区**：必填字段/枚举范围/Schema 约束。
- **控制流盲区**：`edge.condition` 跳过语义、`conditional` 表达式、`loop` 的空输入/上限等极限情况。
- **依赖盲区**：DB/HTTP/LLM/MCP/通知不可用或权限不足。
- **异常可解释盲区**：错误提示缺失或不可定位。

### 4.2 补测优先级规则
- 影响面（高/中/低） × 失败概率 × 可恢复性

### 4.3 补测矩阵（示例结构）
| 维度 | 场景 | 期望 | 失败模式 | 可解释性要求 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| 节点 | structuredOutput | schema 必填 | 缺 schema | 明确提示缺字段 | P0 |
| 依赖 | database | 仅 sqlite 支持 | mysql 连接 | 明确提示不支持 | P0 |
| 控制 | loop | 空集合 | 无迭代 | 输出为空但成功 | P1 |
| 控制 | edge.condition | 条件不满足 | 节点被跳过 | 事件 `node_skipped` 可定位原因 | P0 |

**输出物**：
- 《补测矩阵（P0/P1/P2）》
- 《可用性失败提示规范》

## 5. 能力边界探索方案（对话任务边界）

### 5.1 边界维度矩阵
- 输入维度：文本 / 结构化 / 文件 / 数据库 / 网络
- 控制维度：条件 / 循环 / 组合嵌套（当前是 **DAG 无环**；`loop` 为“节点内迭代”，不是图层面的回边）
- 依赖维度：模型可用性 / 密钥 / 权限 / 配额
- 负载维度：大输入 / 长链路 / 高并发

### 5.2 对话任务边界分类
- **必须成功**：系统承诺支持的高频场景。
- **必须拒绝**：超出节点能力或缺关键依赖。
- **条件成功**：依赖配置正确时可执行。

### 5.3 边界探索任务库结构
- 场景 → 需求描述 → 期望节点组合 → 关键配置 → 成功/失败判定

**输出物**：
- 《对话任务边界样例集》
- 《能力边界矩阵》

## 6. 最终交付文档结构（建议目录）

1) 项目能力综述与对齐矩阵
2) 可用性定义与验收标准
3) 差异清单与修复策略
4) 测试盲区与补测矩阵
5) 能力边界探索矩阵
6) 对话任务边界样例集
7) 风险、依赖与里程碑

## 7. 风险与假设（红队视角）

- **假设 1**：文档节点即执行器节点 —— 需验证。
- **假设 2**：保存校验（SaveValidator）与执行器硬约束一致 —— 需验证（避免“保存通过但必然执行失败”）。
- **假设 3**：对话生成映射与 UI 节点一致 —— 需验证。

对应控制措施：对齐矩阵与最小可执行配置校验。

## 8. 里程碑与验收（仅规划）

> 执行级三里程碑（能力事实源统一 / textModel 多入边可用性 / deterministic Playwright e2e 回归门禁）详见：`docs/planning/workflow-capability-unification-milestones.md`。
> 本文仍保留为“全景规划”，用于补齐信息缺口、定义可用性口径与测试矩阵。

- M1：信息补全与对齐矩阵完成（阻塞项清零）
- M2：P0 盲区补测完成（覆盖可用性闭环）
- M3：能力边界矩阵与对话任务库完成
- M4：统一文档发布与验证

验收条件：
- 关键节点最小配置全部可执行或可解释失败
- 盲区矩阵 P0/P1 覆盖率 >= 90%
- 对话任务边界样例全部可复现

## 9. 需要你提供的信息（以便补全规划）

- 已测试场景/节点清单（按任务/节点/依赖）
- 当前环境可用依赖（LLM/DB/HTTP/通知/MCP/知识库）
- 对话成功标准（生成即可 / 必须执行成功 / 必须产出）

---

> 备注：本规划文档将在信息补全后转为“可执行版本”，并给出逐项实施清单。
