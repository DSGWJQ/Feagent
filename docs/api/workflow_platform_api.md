# API 参考（当前快照）

**Last Updated**: 2025-12-13


> 以下为对外 FastAPI 路由的契约说明，供前端、第三方或测试引用。除 SSE 外全部返回 JSON。

## 1. 鉴权与上下文
- 登录接口待定，目前由外部入口注入 JWT。
- 所有请求需携带 `Authorization: Bearer <token>`，token 中包含 `workspace_id`、`role`。

## 2. Agents
| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/agents` | 创建 Agent（start/goal/name），自动生成任务计划 |
| `GET` | `/api/agents/{agent_id}` | 获取 Agent 详情 |
| `GET` | `/api/agents` | 列出 Agent 列表 |
| `POST` | `/api/agents/{agent_id}/runs` | 触发一次 Run |

## 3. Runs
| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/runs/{run_id}` | 查看 Run 状态与时间戳 |
| `GET` | `/api/runs/{run_id}/logs` *(规划)* | 节点日志/LLM Trace |

## 4. Workflows
| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/workflows/{workflow_id}` | 获取工作流（节点+边） |
| `PATCH` | `/api/workflows/{workflow_id}` | 拖拽编辑更新节点/边 |
| `POST` | `/api/workflows/{workflow_id}/execute` | 同步执行，返回 execution_log + result |
| `POST` | `/api/workflows/{workflow_id}/execute/stream` | SSE 执行流：node_start/node_complete/node_error/workflow_complete |
| `POST` | `/api/workflows/{workflow_id}/chat` | 对话式修改（WorkflowChatService） |
| `POST` | `/api/workflows/import` | 导入 Coze 工作流 |
| `POST` | `/api/workflows/generate-from-form` | 表单生成最小工作流 |

**DTO 速查**
- `UpdateWorkflowRequest`: `nodes[]`, `edges[]`（含 config/position）。
- `ExecuteWorkflowRequest`: `initial_input` 任意 JSON。
- `ChatRequest`: `message` 字符串。
- `ImportWorkflowRequest`: `coze_json` 原始 JSON 字符串。

## 5. Tools / LLM Providers
| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/tools` | 列出工具 |
| `POST` | `/api/tools` | 上传/注册工具（Editor+） |
| `GET` | `/api/llm-providers` | 列出模型提供商 |
| `POST` | `/api/llm-providers` | 注册新 provider |

## 6. Scheduling
| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/workflows/{workflow_id}/schedule` | 创建定时任务 |
| `GET` | `/api/scheduled-workflows` | 列出定时任务 |
| `GET` | `/api/scheduled-workflows/{id}` | 查看定时任务详情 |
| `DELETE` | `/api/scheduled-workflows/{id}` | 删除定时任务 |
| `POST` | `/api/scheduled-workflows/{id}/trigger` | 手动触发执行 |
| `POST` | `/api/scheduled-workflows/{id}/pause` | 暂停 |
| `POST` | `/api/scheduled-workflows/{id}/resume` | 恢复 |
| `GET` | `/api/scheduler/status` | 调度器运行状态 |
| `GET` | `/api/scheduler/jobs` | 列出 APScheduler Job |

## 7. 并发执行
| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/workflows/execute-concurrent` | 提交多个 workflow 并发执行 |
| `GET` | `/api/workflows/concurrent-runs/wait` | 等待所有执行完成 |
| `POST` | `/api/workflows/concurrent-runs/cancel-all` | 取消执行 |

## 8. 增强对话（Chat Workflows）
| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/workflows/{workflow_id}/chat` | 处理用户消息（增强版） |
| `GET` | `/api/workflows/{workflow_id}/chat-history` | 查看对话历史 |
| `GET` | `/api/workflows/{workflow_id}/chat-search` | 搜索历史 |
| `GET` | `/api/workflows/{workflow_id}/suggestions` | 获取建议 |
| `DELETE` | `/api/workflows/{workflow_id}/chat-history` | 清空历史 |
| `GET` | `/api/workflows/{workflow_id}/chat-context` | 获取压缩上下文 |

## 9. 错误码
- `400`：领域校验失败（缺少 start/goal、Schema 无效）
- `401`：鉴权失败或 workspace 不匹配
- `403`：角色权限不足
- `404`：实体不存在
- `409`：并发/版本冲突（规划）
- `500`：服务器未处理错误（附 trace_id）

## 10. SSE 数据格式
```json
data: {
  "type": "node_start",
  "node_id": "node_xxx",
  "node_type": "httpRequest",
  "timestamp": "2025-01-25T10:00:00Z"
}
```
- `workflow_complete` 事件包含 `result` 与 `execution_log`。
- 客户端需自动重连，服务端通过注释或心跳保持连接。

## 11. 版本兼容
- 暂无 `/v1` 前缀，若有 Breaking Change 必须更新本文并同步 `docs/README.md`。
- 建议前端通过 `/openapi.json` 生成客户端。
