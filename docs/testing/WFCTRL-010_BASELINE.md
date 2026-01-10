# CFLOW-010 基线：必跑命令清单与本机结果

目标：固化“完整真实测试”的必跑命令集（命令 + 退出码），并记录本机基线结果，作为后续变更的对照与回归入口。

> 说明：本文件名历史上沿用 `WFCTRL-010_*`，但内容以当前 issue `CFLOW-010` 为准。

## 必跑命令清单（命令 + 退出码）

### Tier 1：PR 必跑（必须 exit 0）

- `python scripts/validate_node_definitions.py --strict`
  - 期望：退出码 `0`
- `python scripts/validate_tool_configs.py`
  - 期望：退出码 `0`
- `python -m pytest -q --collect-only`
  - 期望：退出码 `0`
- `pnpm -C web type-check`
  - 期望：退出码 `0`
- `pnpm -C web test`
  - 期望：退出码 `0`

### Tier 2：基线巡检（必须执行并记录；允许既有失败）

- `python scripts/validate_prompt_templates.py`
  - 期望：退出码 `0`
- `python -m ruff check .`
  - 期望：退出码 `0`
- `pnpm -C web lint`
  - 期望：退出码 `0`
- `pwsh -NoProfile -File scripts/workflow_core_checks.ps1`
  - 期望：退出码 `0`
  - 说明：依赖 `lint-imports`（import-linter）存在；如缺失应先安装后端 dev 依赖后再跑。

### Tier 3：E2E（deterministic/hybrid/fullreal）

> 说明：E2E 依赖后端与前端服务已启动（本清单不要求“首次安装依赖”联网；首次安装属于环境准备阶段）。
>
> 口径：`deterministic` 目标是不依赖外网；`hybrid/fullreal` 可能涉及外部依赖（例如真实 LLM/外部 HTTP），需按用例约束执行。

- 后端：`python -m uvicorn src.interfaces.api.main:app --reload --port 8000`
- 前端：`pnpm -C web dev -- --host 127.0.0.1 --port 5173`
- 环境变量：
  - `PLAYWRIGHT_API_URL=http://127.0.0.1:8000`
  - `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173`
- 运行：
  - `pnpm -C web test:e2e:deterministic`
  - `pnpm -C web test:e2e:hybrid`
  - `pnpm -C web test:e2e:fullreal`

## 本机执行结果（2026-01-10）

证据日志目录：`tmp/baseline_CFLOW-010_2026-01-10_23-29-39/`

### Tier 1 结果

- `python scripts/validate_node_definitions.py --strict`：exit `0`
- `python scripts/validate_tool_configs.py`：exit `0`
- `python -m pytest -q --collect-only`：exit `0`（collected `7342` tests）
- `pnpm -C web type-check`：exit `0`
- `pnpm -C web test`：exit `0`（`182 passed, 4 skipped`）

### Tier 2 结果（既有失败记录）

- `python scripts/validate_prompt_templates.py`：exit `1`
  - 原因：目录不存在 `docs/prompt_templates`
- `python -m ruff check .`：exit `1`
  - 原因：存在 `143` 个 lint errors（见日志）
- `pnpm -C web lint`：exit `1`
  - 原因：存在 `228` 个 lint problems（见日志）
- `pwsh -NoProfile -File scripts/workflow_core_checks.ps1`：exit `0`（修复脚本后可运行）
