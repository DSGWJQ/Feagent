# Workflow 能力边界矩阵（V0）

> 日期：2026-02-01
> 依据：`docs/planning/workflow-usability-capability-plan.md` §5
> 口径：以“编辑器工作流链路（体系 B）”为事实源：`NodeType + ExecutorRegistry + WorkflowSaveValidator + WorkflowEngine + UI`。
> 当前约束：**仅支持 sqlite**；模型类节点仅承诺 **OpenAI provider**（fail-closed）。

## 0. E2E 模式与依赖边界（能力 = 节点能力 × 环境能力）

系统通过 E2E 模式切换将“可执行能力”划分为三档（避免测试环境误走真实依赖）：

| 模式 | `E2E_TEST_MODE` | LLM | HTTP | 典型用途 |
| --- | --- | --- | --- | --- |
| A | deterministic | `LLM_ADAPTER=stub`（不出网） | `HTTP_ADAPTER=mock`（不出网） | CI / 回归门禁 |
| B | hybrid | `LLM_ADAPTER=replay`（回放） | `HTTP_ADAPTER=wiremock` | PR / Daily |
| C | fullreal | `LLM_ADAPTER=openai`（真实调用） | `HTTP_ADAPTER=httpx`（真实出网） | Nightly / 真实验证 |

事实源（配置门禁）：
- `src/config.py`（`e2e_test_mode/llm_adapter/http_adapter`）
- `src/interfaces/api/container.py:AdapterFactory`（模式门禁与错误提示）

## 1. “必须成功 / 必须拒绝 / 条件成功”定义

- **必须成功**：在 deterministic 模式下也应稳定通过（不依赖外部网络/密钥），或能通过 stub/mock 完整闭环。
- **必须拒绝**：无论任何模式都不应接受（违反硬约束/必然执行失败/不可解释）。
- **条件成功**：依赖环境配置、外部系统或数据存在性；当依赖缺失时必须给出可解释失败。

## 2. 能力边界矩阵（按维度拆解）

### 2.1 输入维度

| 输入类型 | 当前支持状态 | 说明/边界 |
| --- | --- | --- |
| 纯文本 | 必须成功 | start/input → prompt/textModel/transform/python → end |
| 结构化 JSON | 必须成功 | 支持模板渲染与 Python/transform 处理（注意 schema/JSON parse） |
| 文件（本地） | 条件成功 | `file` 节点依赖运行环境文件系统权限与路径约束 |
| 数据库（sqlite） | 必须成功 | SaveValidator fail-closed：仅允许 `sqlite:///` |
| 网络（HTTP） | 条件成功 | deterministic 需 `mock_response` 或 HTTP mock；fullreal 需出网 |

### 2.2 控制维度

| 控制能力 | 当前支持状态 | 说明/边界 |
| --- | --- | --- |
| 条件分支（conditional + edge.condition） | 必须成功 | branch gating + `node_skipped` 可解释事件 |
| 循环（loop 节点） | 条件成功 | 循环是“节点内迭代”，不是图层回边；边界需补测（空集合/上限） |
| 图结构（DAG） | 必须成功（无环） | **必须拒绝**有环图（cycle_detected） |
| 组合嵌套（DAG 组合） | 条件成功 | 可组合，但复杂度上升；需要可解释事件与补测矩阵护航 |

### 2.3 依赖维度（关键外部依赖）

| 依赖 | 当前支持状态 | 缺失时的期望行为 |
| --- | --- | --- |
| OpenAI API Key | 条件成功 | fullreal 必需；deterministic/hybrid 应走 stub/replay，不应出网 |
| Tool 数据（DB tools 表） | 条件成功 | tool_id 不存在/已废弃/仓库不可用必须 fail-closed（保存拒绝或执行报错可解释） |
| 通知渠道（webhook/slack/email） | 条件成功 | deterministic 可 stub；fullreal 依赖出网/SMTP 等配置 |

### 2.4 负载维度（性能/稳定性）

| 负载场景 | 当前支持状态 | 说明/边界 |
| --- | --- | --- |
| 大输入（大 JSON/长文本） | 条件成功 | 受 LLM token、内存与模板渲染成本影响；需设上限与超时报错可解释 |
| 长链路（节点数多） | 条件成功 | 受执行时延与事件流量影响；需回归门禁覆盖核心路径 |
| 并发执行（多 run） | 条件成功 | 依赖运行门禁/队列/DB；需压测与隔离策略（不在本轮 P0） |

## 3. 硬约束（必须拒绝清单）

1) `database_url` 非 `sqlite:///`（保存阶段必须拒绝）
2) 模型 provider 非 OpenAI（保存阶段必须拒绝）
3) 明显非 OpenAI 的无前缀模型族（如 `gemini-*`、`claude-*`，保存阶段必须拒绝）
4) 图结构有环（保存阶段必须拒绝）
5) tool 节点缺 `tool_id` / tool_id 不存在或已废弃（保存阶段必须拒绝）

参考：`docs/planning/workflow-usability-test-matrix.md`（P0 覆盖项）
