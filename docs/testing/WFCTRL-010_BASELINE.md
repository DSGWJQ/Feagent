# WFCTRL-010 基线：必跑命令清单与本机结果

目标：固化“完整真实测试”的必跑命令集（命令 + 退出码），并记录本机基线结果。

## 必跑命令清单（命令 + 退出码）

### 后端 / 校验脚本

- `python scripts/validate_node_definitions.py --strict`
  - 期望：退出码 `0`

### 前端

- `pnpm -C web type-check`
  - 期望：退出码 `0`
- `pnpm -C web test`
  - 期望：退出码 `0`

## 本机执行结果（2026-01-08）

- ✅ `python scripts/validate_node_definitions.py --strict`：exit `0`
- ✅ `pnpm -C web type-check`：exit `0`
- ✅ `pnpm -C web test`：exit `0`

## 备注：pytest 全量收集现状（非本需求阻塞修复范围）

执行 `pytest -q --collect-only` 当前会在收集阶段失败（exit `1`），共 `11` 个 collection errors：

- `ModuleNotFoundError: No module named 'src.lc'`
  - 影响：`tests/integration/task_executor/*`、`tests/integration/api/workflow_chat/*` 等多处测试模块
- `ImportError: cannot import name 'ShortTermSaturatedEvent' from 'src.domain.services.context_manager'`
  - 影响：`tests/integration/test_memory_distillation_pipeline.py`、`tests/integration/test_saturation_flow_integration.py`

判定：上述失败与本次 workflow 条件门控 / 对话增量编辑 / 配置模板化能力的实现无直接因果关系；后续如需推进全量 `pytest -q`，应单独立项处理缺失模块与集成链路。
