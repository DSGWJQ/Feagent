# 数据访问与 RLS 策略

> 本文是多租户隔离、密钥管理与审计的权威指引。Schema 或 API 变化时务必同步更新。

## 1. 角色
| 角色 | 能力范围 | 典型使用者 |
|------|----------|------------|
| **Admin** | 完整读写、管理工作区、轮换密钥 | 平台负责人/运维 |
| **Editor** | 创建/编辑工作流、发起执行、上传工具 | 开发者/资深运营 |
| **Viewer** | 工作流、执行、日志只读 | 运营/学习者 |
| **Service** | 调度器、执行器使用的机器角色 | 后台任务 |

## 2. 行级安全（RLS）
- 所有多租户表（agents、workflows、runs、tasks、tools、snapshots）必须包含 `workspace_id` UUID。
- PostgreSQL 策略示例：
  ```sql
  ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
  CREATE POLICY workflows_rw ON workflows
    USING (workspace_id = current_setting('app.workspace_id')::uuid)
    WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);
  ```
- FastAPI 依赖在鉴权后设置 `app.workspace_id`。
- Service 角色可切换到对应 workspace，或使用权限受限的系统工作区。

## 3. API 鉴权
- 所有路由统一依赖返回 `(user_id, workspace_id, role)`。
- SSE 等长连接也需校验 token，并定期保活。
- 高风险操作（工具上传、GitHub 导入、Coze 密钥管理）仅 Editor 及以上可执行。

## 4. 秘钥管理
- `.env` 仅用于本地，生产密钥由 Vault/KMS 注入。
- 敏感字段（如 provider API Key）使用 AES-256 加密，运行时解密。
- Coze 凭证、自定义工具密钥、Webhook Token 均按 workspace 隔离。

## 5. 日志与审计
- 实现 `audit_logs`：记录操作人、工作区、动作、目标、差异、时间戳。
- 执行日志与 LLM 轨迹在写库前需要脱敏处理 PII。
- 原始 LLM Trace 仅 Editor+ 可查看，且需业务场景说明。

## 6. 加固指引
- 强制 HTTPS/TLS1.2+ 与 HSTS。
- 公有接口配置用户级与全局双重限流。
- 自定义工具运行在隔离沙箱（JS/Python），设置 CPU/内存/时间配额。
- 提供密钥吊销、轮换的标准流程。

## 7. 待办事项
- [ ] 全量表新增 `workspace_id` 并完成迁移。
- [ ] 实现 FastAPI `get_current_context` 依赖，统一返回用户+工作区+角色。
- [ ] 上线 `audit_logs` 表及查看界面。
- [ ] 输出企业租户的数据导出与 DPIA 规范。
