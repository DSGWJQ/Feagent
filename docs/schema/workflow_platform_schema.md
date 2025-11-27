# 工作流平台 Schema 概览

> 本文是后端/数据团队设计表结构、索引和约束时的基准文档。请与 Alembic 迁移保持一致，任何数据库变更先更新此处。

## 1. 数据库分层
- **业务数据库**（`agent_platform.db` / PostgreSQL）：存储 agents、workflows、runs、tasks 等核心实体。
- **日志/队列**：运行日志写入 JSONB 字段并同步到结构化日志系统（ELK/ClickHouse）。
- **外部配置**：API Key、Coze 凭证等存于 secrets 表并加密。

## 2. 核心表设计

### 2.1 `agents`
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | TEXT(36) | PK | UUID |
| `start` | TEXT | NOT NULL | 起点描述 |
| `goal` | TEXT | NOT NULL | 目标描述 |
| `status` | VARCHAR(20) | NOT NULL, default `active` | active/archived |
| `name` | VARCHAR(255) | NOT NULL | 展示名称 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| **索引** | `idx_agents_status`, `idx_agents_created_at` |

### 2.2 `workflows`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK | 内部 workflow id |
| `name` VARCHAR(255) NOT NULL |
| `description` TEXT |
| `status` VARCHAR(20) NOT NULL (`draft/published`) |
| `source` VARCHAR(32) default `native` (`coze`, `imported`) |
| `source_id` TEXT | 外部 workflow id |
| `created_at`, `updated_at` DATETIME NOT NULL |
| 关系 | nodes/edges 级联删除 |

### 2.3 `nodes`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK |
| `workflow_id` TEXT FK → workflows(id) ON DELETE CASCADE |
| `type` VARCHAR(50) NOT NULL，如 `httpRequest`, `textModel` |
| `name` VARCHAR(255) NOT NULL |
| `config` JSON NOT NULL | 节点配置 |
| `position_x`, `position_y` FLOAT | 画布位置 |

### 2.4 `edges`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK |
| `workflow_id` TEXT FK → workflows(id) |
| `source_node_id` TEXT | 必须存在于 nodes |
| `target_node_id` TEXT | 必须存在于 nodes |
| `condition` TEXT 可空 |

### 2.5 `runs`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK |
| `agent_id` TEXT FK → agents(id) |
| `status` VARCHAR(20) NOT NULL (`pending/running/succeeded/failed`) |
| `created_at`, `started_at`, `finished_at` DATETIME |
| `error` TEXT |
| 索引 | `idx_runs_agent_id`, `idx_runs_status`, `idx_runs_created_at` |

### 2.6 `tasks`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK |
| `agent_id` TEXT FK → agents |
| `run_id` TEXT FK → runs，可空 |
| `name` VARCHAR(255) NOT NULL |
| `description` TEXT |
| `status` VARCHAR(20) NOT NULL |
| `input_data` JSON | 可空 |
| `output_data` JSON | 可空 |
| `error` TEXT |
| `retry_count` INT default 0 |
| `events` JSON | TaskEvent 数组（timestamp, message） |
| `created_at`, `started_at`, `finished_at` DATETIME |

### 2.7 `scheduled_workflows`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK |
| `workflow_id` TEXT FK → workflows |
| `cron_expression` TEXT NOT NULL |
| `status` VARCHAR(20) default `active` |
| `max_retries`, `consecutive_failures` INT |
| `last_execution_at` DATETIME |
| `last_execution_status` VARCHAR(20) |
| `last_error_message` TEXT |
| `created_at`, `updated_at` DATETIME |

### 2.8 `tools`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK |
| `name` VARCHAR(255) UNIQUE |
| `category` VARCHAR(50) |
| `config` JSON | 沙箱/入口等配置 |
| `owner_id` TEXT | 上传者 |
| `visibility` VARCHAR(20) (`private/shared`) |
| 审批字段 | `status` (`pending/approved/rejected`) |

### 2.9 `llm_providers`
| 字段 | 类型 | 约束 |
|------|------|------|
| `id` TEXT PK |
| `name` VARCHAR(50) |
| `base_url` TEXT |
| `api_key` TEXT（加密存储） |
| `model` VARCHAR(100) |
| `metadata` JSON | 如速率限制 |

## 3. 约束与规则
- **参照完整性**：删除 workflow/run 时 nodes/edges/tasks 级联删除。
- **状态校验**：status 字段使用枚举或 CHECK，限制非法状态。
- **JSON 校验**：`config` 等 JSON 在应用层做 Schema 验证。
- **软删除**：暂未启用，使用 status 表示归档。

## 4. 索引与性能建议
- 大体量 runs/tasks 可按 `created_at` 分区。
- JSON 列如 `events` 需要全文检索时可加 GIN 索引。
- `scheduled_workflows` 对 `status + workflow_id` 建索引便于调度查询。

## 5. 数据保留策略
- 执行日志默认保留 30 天；快照体积小可长期保留。
- LLM trace 可能含敏感信息，写库前需脱敏。

## 6. 规划中的表
- `workflow_snapshots`：`id, workflow_id, diff, created_by, label`。
- `audit_logs`：记录用户、操作、对象、时间、payload。
- `usage_metrics`：用于限流与计费。
