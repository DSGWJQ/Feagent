# 三高测试总结报告（执行版）

版本：v1.6（执行版 - 第八轮）
状态：已执行（JS/Conditional 线程化 + Legacy 心跳仍未改善 timeout；Runs 基线达标）
关联规划：`docs/three-high-test-plan.md`

---

## A. 测试环境

- 硬件：CPU 16 逻辑核（`os.cpu_count()`），内存 15.22 GB（`GlobalMemoryStatusEx`），磁盘类型未知（权限受限）
- OS：Windows 11 10.0.26100
- 后端启动参数：
  - Profile A（Runs）：`python -m uvicorn src.interfaces.api.main:app --port 8025`
    - `E2E_TEST_MODE=deterministic`, `LLM_ADAPTER=stub`, `HTTP_ADAPTER=mock`, `DISABLE_RUN_PERSISTENCE=false`, `ENABLE_TEST_SEED_API=true`, `MAX_CONCURRENT_TASKS=20`
  - Profile B（Legacy）：`python -m uvicorn src.interfaces.api.main:app --port 8026`
    - `E2E_TEST_MODE=deterministic`, `LLM_ADAPTER=stub`, `HTTP_ADAPTER=mock`, `DISABLE_RUN_PERSISTENCE=true`, `ENABLE_TEST_SEED_API=true`, `MAX_CONCURRENT_TASKS=20`
- DB：SQLite，`C:/Users/23225/AppData/Local/Temp/agent_platform_demo_v2.db`
  - 执行期修复：W4 `reconcile_sync` 改为 OS 临时目录 per-run DB（`{context.initial_input.db_dir}/reconcile_sync_{run_id}.db`），`disk I/O error` 已消失
- Stub/Mock/Replay：
  - deterministic 模式：LLM/Notification 走内置 stub；HTTP 走 mock
  - Runs 自动确认：压测脚本在 SSE 收到 `workflow_confirm_required` 后自动 `allow`
  - W3 长尾：Python 节点 CPU busy-loop（30,000,000 次迭代）
  - PythonExecutor：改为 `asyncio.to_thread` 执行（避免阻塞事件循环）
  - JavaScript/Conditional Executor：改为 `asyncio.to_thread` 执行
  - Legacy SSE：实时队列 + 启动心跳事件（仍未改善 timeout）
  - 压测初始输入：`initial_input.run_id` 与 `initial_input.db_dir` 始终传入
  - stub 延迟分布/失败率档位：当前未提供可配置能力（视为缺口）

## B. 口径与方法（必须可复现）

- attempt 定义：一次 execute/stream 从发起到终态（complete/error）或超时/断连为止
- error_rate 定义：HTTP 5xx、timeout、disconnect 未终态、workflow_error（4xx 单列不计入）
- baseline 方法：并发 10，持续 720s；Profile A attempts=266（达标），Profile B attempts=32（未达标）
- 验收阈值：error_rate < 1%，且 P95[class] <= 2 * baseline_P95[class]
- 压测工具与版本：自研脚本 `scripts/three_high_load_test.py`（httpx+asyncio）
- max_wait_s：180
- VU 行为模型：
  - Profile A：先 `POST /api/projects/{project_id}/workflows/{workflow_id}/runs` 再携带 run_id 执行 stream
  - Profile B：直接 `POST /api/workflows/{workflow_id}/execute/stream`
- Workload Mix：W1 30%、W2 40%、W3 20%、W4 10%
  - W1：`main_subgraph_only`（wf_d63e074d）
  - W2：`report_pipeline`（wf_bd0ea003）
  - W3：`code_assistant`（wf_b8b02e10）
  - W4：`reconcile_sync`（wf_daddf5b1）

## C. Baseline 结果（目标来源）

> 注意：Profile A baseline error_rate 为 0 且 attempts 达标；Profile B baseline 受 timeout/5xx 影响不可用。

| workload | baseline_P95(ms) | target(2x) |
|---|---:|---:|
| W1（短 CPU） | 28694.10 | 57388.20 |
| W2（中 CPU） | 40748.00 | 81496.00 |
| W3（长尾占用） | 38341.11 | 76682.22 |
| W4（高事件密度） | 37163.47 | 74326.94 |

## D. 并发爬坡结果（主结论）

### D.1 Profile A（Runs）
- 最大稳定并发（Stable）：10（baseline）
- 拐点并发（Knee）：25（P95 超 2x baseline）
- 极限并发（Limit，可选）：未定义

| stage | concurrency | attempts | error_rate | P95 W1 | P95 W2 | P95 W3 | P95 W4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 10 | 266 | 0.00% | 28694.10 | 40748.00 | 38341.11 | 37163.47 |
| c25 | 25 | 72 | 0.00% | 128097.31 | 190339.99 | 209783.47 | 128002.56 |
| c40 | 40 | 50 | 0.00% | 268337.91 | 325170.75 | 289840.28 | 252227.89 |

### D.2 Profile B（Legacy）
- 最大稳定并发（Stable）：无（baseline timeout）
- 拐点并发（Knee）：10（baseline）
- 极限并发（Limit，可选）：未定义

| stage | concurrency | attempts | error_rate | P95 W1 | P95 W2 | P95 W3 | P95 W4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 10 | 32 | 56.25% | 180015.10 | 169209.84 | 180009.80 | 180013.04 |
| c25 | 25 | 42 | 100% | 180016.35 | 180012.36 | 180015.74 | 180010.70 |
| c40 | 40 | 57 | 100% | 234795.62 | 205724.81 | 218866.99 | 247485.13 |

### D.3 A/B 对照（用于归因）
- P95 放大比：Profile B 长时间 timeout，P95 贴近 `max_wait`，A/B 比例无意义（需先修复 Legacy 超时）
- error_rate 差异：A baseline 0.00% vs B baseline 56.25%（Legacy 超时显著）
- 资源差异：已采集（`process_*` 有值），尚未做深入对比分析

### D.4 图表与表格（必须）

并发 vs error_rate（ASCII 图表）：

```
Profile A
10 | 0.00%
25 | 0.00%
40 | 0.00%

Profile B
10 | ############################ 56.25%
25 | ################################################## 100%
40 | ################################################## 100%
```

并发 vs P95（表格见 D.1 / D.2）。原始数据：
- `data/three_high_profileA.json`
- `data/three_high_profileB.json`

## E. 高可用验证结果

- SSE 断连与资源释放：本轮未重复验证（上一轮在 Profile A 执行 10 次“首事件后断连”，`/health` 仍为 200）
- 断连后的可追溯性（Runs）：本轮未重复验证；W4 `disk I/O error` 已消失（见 F）
- 故障注入（stub 延迟升高/失败率）：未执行（缺少可配置能力）
- 重启恢复（RTO）：未执行（受限于进程终止权限）

## F. 瓶颈归因（证据驱动）

- 主要瓶颈（Runs）：W4 `disk I/O error` 已消失，当前瓶颈转向 P95 延迟在 c25/c40 明显抬升（CPU/长尾占用）
  - 证据：Profile A baseline error_rate 0% 且达标，但 c25/c40 的 P95 > 2x baseline（见 D.1）
- 主要瓶颈（Legacy）：高并发下 SSE 执行超时（P95 ~ max_wait），影响所有 workload
  - 证据：Profile B 基线与爬坡大量 timeout，error_rate >= 56.25%

## G. 优化建议（按 ROI 排序）

### G.1 立即可做（低风险）
- W4 SQLite I/O：已通过 OS 临时目录 per-run DB 解决，可保留为测试默认配置
- Legacy SSE 连接超时诊断：增加队列长度、活跃执行数、事件发送延迟指标
- Runs 延迟抬升诊断：聚焦 W3 长尾节点与 CPU 使用率，考虑降低单节点计算量或隔离到线程池
- Legacy 复核：Python/JavaScript/Conditional 线程化 + SSE 实时队列/心跳已启用但超时未改善，需排查 SSE 写入/队列阻塞

### G.2 中期优化
- Stub 延迟/失败率能力补齐：支持延迟分布与失败档位（用于可用性测试）
- 执行路径降噪：将 CPU-heavy 节点隔离到独立线程/进程池
- SSE 端到端快失败：区分排队超时与执行超时，避免误判

### G.3 长期优化
- SQLite → Postgres（并发写与锁竞争优化）
- 事件写入异步化与落盘策略优化
- 持续压测门禁：基线+单档爬坡作为发布门禁

## H. 风险与局限（必须写清）

- 本机单实例结论不可直接外推到生产；生产需在同构环境复测
- SQLite 锁与文件 IO 可能导致结果偏保守且抖动大（本次使用 SQLite）
- stub/mock 模拟仅近似真实延迟分布；本次 deterministic stub 无失败率/延迟分布配置
- Profile A baseline attempts 已达 200（error_rate=0），但 c25/c40 仍超阈
- Profile B baseline attempts 未达 200 且 timeout 显著，Legacy 结论不可用
- 图表为 ASCII 形式，未生成图片

## I. 一句话摘要（用于汇报）

在 Windows 11（16 逻辑核/15.22GB）本机单实例下，Runs baseline 并发 10 达到 266 attempts 且 error_rate 0（W4 disk I/O 已消失），但 c25/c40 P95 超过 2x baseline；Legacy 路径在并发 10 仍大量 timeout，稳定并发未达标，优先修复 Legacy SSE 超时并继续回归。
