# 部署说明（Deployment）

本文件用于修复 README 的历史链接。

当前仓库以“本地开发 + 测试可重复”为第一优先级；生产部署的标准化方案尚未固化。

## 建议（临时）

- 使用环境变量管理配置（参考 `.env.example`）
- 以 ASGI 方式运行（示例）：
  ```bash
  python -m uvicorn src.interfaces.api.main:app --host 0.0.0.0 --port 8000
  ```
- 数据库迁移：`alembic upgrade head`

如需落地生产部署（Docker/K8s/反向代理/观测），建议先完成：
- `docs/planning/PROJECT_SIMPLIFICATION_DEDUP_PLAN.md`（去冗余收敛）
- `docs/architecture/MONITORING_ARCHITECTURE.md`（监控与指标）
