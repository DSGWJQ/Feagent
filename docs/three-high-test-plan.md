# 三高测试规划文档（本机单实例 / 基线派生目标 / 不走真实外部调用）

版本：v1.0（规划版）
状态：规划已确认，可进入落地执行（脚本/采集/压测/修复/回归）
关联交付物：`docs/three-high-test-report.md`（执行完成后必须生成）

---

## 0. 背景与目标

### 0.1 背景
本项目包含 Workflow 执行与编排能力，核心执行入口为 SSE 流式接口。目标是在**本机单实例**部署形态下，评估系统高并发能力（“能同时运行多少个工作流”），并覆盖“三高”：
- 高性能（Performance）
- 高并发（Concurrency）
- 高可用（Availability）

约束：
- 不走真实外部调用：LLM/HTTP/RAG 等必须 stub/mock/replay（不触网）
- 执行阶段若遇到 bug：必须循环修复并回归，直到压测能跑通并得到结论
- 验收口径：错误率 < 1%，且 P95 不超过目标 2 倍；目标采用**基线派生**。

### 0.2 本次测试要回答的问题
1) 本机单实例下的“最大稳定并发”（Stable Concurrency）是多少？
2) “拐点并发”（Knee Point）在哪里？（错误率/延迟/资源开始显著恶化）
3) 瓶颈归因是什么？（CPU/内存/SSE/DB/事件落库/执行器）
4) Runs 模式（可追溯）与 legacy 模式（不落 run）之间的额外开销差异是多少？

### 0.3 Charter（目标 / 问题 / 约束）
目标：评估本机单实例下 Workflow 执行的三高能力，并为后续压测与修复提供统一合同。
必答问题：见 0.2 的四个问题（不可增删）。
约束/边界：本机单实例（结论不可外推到多实例/集群）；不走真实外部调用（LLM/HTTP/RAG 必须 stub/mock/replay）；SSE 必须消费到终态（complete/workflow_error/timeout/disconnect），否则结论无效。

---

## 1. 范围与非范围

### 1.1 范围（必须覆盖）
- Workflow 执行主链路（SSE 长连接）
  - `POST /api/workflows/{workflow_id}/execute/stream`
- Runs 链路（用于“真实场景可追溯”与可用性验证）
  - `POST /api/projects/{project_id}/workflows/{workflow_id}/runs`（创建 run）
  - `GET /api/runs/{run_id}/events`（回放/完整性抽检）
- Workflow 读写（真实用户行为叠加）
  - `GET /api/workflows/{id}`、`PATCH /api/workflows/{id}`
- 调度叠加（scheduler 与人工执行并发叠加）
  - 以现有调度触发接口为准（执行阶段落地）

### 1.2 非范围（本轮不做）
- 多实例/集群/负载均衡（本次固定单实例）
- 真实外部依赖调用（全部 stub/mock/replay）
- 安全渗透测试（不在本轮目标内）

---

## 2. 验收口径（强制统一口径，保证可复现）

### 2.1 “一次尝试”的定义（Attempt）
一次 attempt 指：一个虚拟用户发起一次 workflow 执行（execute/stream），并持续消费 SSE 直到：
- 收到 `workflow_complete`（成功），或
- 收到 `workflow_error`（失败），或
- 超时/断连未收到终态（失败）

### 2.2 错误率定义（Error Rate）
统计窗口建议：1 分钟窗口 + 5 分钟滚动窗口。

计入 error：
- HTTP 5xx
- 客户端超时（`max_wait_ms` 内未收到终态）
- SSE 断连且未收到终态
- 收到 `workflow_error` 终态

不计入 error_rate（但必须单列统计；出现占比高视为阻断性缺陷，需修复后再测）：
- HTTP 4xx（契约/参数/校验错误）

计算：
- `error_rate = errors / total_attempts`
- `incomplete_rate = incompletes / total_attempts`（超时/断连未终态）

### 2.3 P95 目标（基线派生）
对每类 workload（见 3.1）分别计算 baseline：
- baseline 并发：`baseline_concurrency = 10`（如机器较弱可改 5，但必须记录）
- baseline 时长：>= 5 分钟 且 >= 200 attempts（取更严格者）
- baseline 指标：`baseline_P95[class]`

派生目标：
- `target_P95[class] = baseline_P95[class]`

验收阈值：
- `P95[class] <= 2 * target_P95[class]` 且 `error_rate < 1%`

---

## 3. 负载设计（真实行为模拟 + 不走真实外部）

### 3.1 Workload Mix（至少四类）
为避免“只测短流程高估并发”，必须至少包含四类 workflow，并在混合压测中按权重抽样：

- W1：短 CPU（框架开销型）
  - 1–2 节点，<200ms
  - 目的：测路由/SSE/序列化最小开销与吞吐上限
- W2：中 CPU（常规处理型）
  - 5–10 节点，1–3s
  - 目的：贴近真实数据处理/转换/校验
- W3：长尾占用（连接占用型）
  - 10–60s（用 stub sleep 模拟外部依赖延迟）
  - 目的：最能体现“同时运行多少”上限（并发≈连接占用）
- W4：高事件密度（事件/落库压力型）
  - 同等时长下事件更多或 payload 更大
  - 目的：压测 run_events/队列/DB 写放大/网络吞吐

默认权重（可调）：W1 30%、W2 40%、W3 20%、W4 10%。

### 3.2 外部调用禁止真实（Stub/Mock/Replay）
要求：LLM/HTTP/RAG 等节点执行不触网。

stub 必须支持两项能力（执行阶段若缺失则作为 bug 修复项补齐）：
- 模拟延迟分布（可配置）：建议 P50=50ms，P95=300ms，P99=800ms
- 失败率档位（可配置）：0% / 1% / 5% / 20%（仅在可用性阶段启用）

---

## 4. 测试模式：Profile A/B 双轨对照（用于归因）

### 4.1 Profile A：Runs 模式（主结论）
虚拟用户流程：
1) 选择 workflow_id（按 W1~W4 权重抽样）
2) 创建 run：`POST /projects/{project_id}/workflows/{workflow_id}/runs`（可带 Idempotency-Key 测幂等）
3) 执行：`POST /workflows/{workflow_id}/execute/stream`（携带 run_id），持续消费 SSE 直到终态
4) 抽样回放：`GET /runs/{run_id}/events` 验证事件完整性与可回放

目的：反映“真实可追溯”执行成本，为高可用验证提供证据。

### 4.2 Profile B：Legacy 模式（对照线）
虚拟用户流程：
1) 直接执行：`POST /workflows/{workflow_id}/execute/stream`（不创建 run 或 runs disabled）
2) 持续消费 SSE 直到终态

目的：量化 Runs/事件落库的额外开销，定位 DB/事件是否是拐点主因。

对照输出：
- 延迟放大比：`P95_A / P95_B`
- 可用性差异：`error_rate_A - error_rate_B`
- CPU/内存/IO 差异

---

## 5. 并发爬坡策略（找拐点）

### 5.1 Step Load（推荐）
- Warmup：10 并发，3–5 分钟
- Ramp：10 → 25 → 50 → 75 → 100 → 150 → 200 → 300 → 400…（按机器能力扩展）
- 每档持续：>= 10 分钟，且 W3（长尾）在该档位至少完整跑完多个周期
- Spike（可选）：接近拐点并发时瞬间翻倍 60 秒，观察雪崩与恢复
- Soak（可选）：拐点下方 1 档持续 1–8 小时，观察泄漏与堆积

### 5.2 拐点判定（满足任一视为超过稳定上限）
- `error_rate >= 1%` 且持续 2 个窗口
- 任一 workload 类别 `P95 > 2 * baseline_P95[class]` 且持续 2 个窗口
- 资源饱和且伴随劣化：CPU 持续 > 85% 或内存持续上升无回落
- `incomplete_rate` 明显上升（例如 > 0.5%）或 SSE 断连率显著上升

输出结论：
- 最大稳定并发（Stable）：满足验收口径的最高并发档位
- 拐点并发（Knee）：首次持续违反口径的并发档位
- 极限并发（Limit，可选）：系统尚能响应但指标明显失控的档位（仅风险参考）

---

## 6. 必采集指标（保证可归因）

### 6.1 客户端侧（每个 attempt 必须记录）
- workflow_class（W1/W2/W3/W4）
- start_ts/end_ts、duration_ms
- TTFB_ms（首个 SSE event 到达时间）
- events_count、bytes_count
- terminal_type（complete / workflow_error / timeout / disconnect）
- HTTP status（非 200 时）
- Profile A：run_id、（可选）events_replay_ok（抽样回放一致性）

### 6.2 系统侧（本机）
- 后端进程：CPU%、内存 RSS、线程/句柄数
- 网络：ESTABLISHED 连接数、端口占用趋势
- DB：写入速率、锁等待（SQLite 时特别关注锁与 I/O 抖动；报告必须标注局限）

### 6.3 执行完成后必须产出图表
- 并发 vs error_rate（总/分类型：5xx、timeout、disconnect、workflow_error）
- 并发 vs P95（按 W1~W4 分开）
- 并发 vs CPU/内存/连接数
- Profile A vs B 对照（同 workload、同并发）

---

## 7. 高可用（单实例也必须做的稳定性验证）

### 7.1 SSE 断连与资源释放
- 压测中随机断开一部分 SSE 连接（客户端侧），验证服务端不会积压资源导致崩溃
- 指标：断连后句柄/连接数是否回落、error_rate 是否异常抬升

### 7.2 断连后的可追溯性（Runs 模式）
- 对断连的 run_id 抽样调用 replay（`GET /runs/{run_id}/events`）
- 验证：是否能回放到终态、事件是否缺失、顺序是否稳定

### 7.3 故障注入（不走真实外部）
- 对 stub/mock 注入延迟升高与失败率（1%/5%/20%）
- 验证：是否触发重试风暴、是否出现级联失败、在压力下降后是否能自恢复

### 7.4 重启恢复（执行阶段做）
- 在中等并发运行时重启后端进程
- 指标：恢复到健康端点可用的时间（RTO），未完成 attempt 的终态分布变化

---

## 8. Bug 修复与回归闭环（执行阶段强制）

当压测出现阻断（4xx 占比高、5xx、卡死、断连暴涨、DB 锁死等），必须按以下流程迭代直到跑通：

1) 最小化复现
- 固定 workflow_id + 小并发（5~10）仍可复现
- 固定 stub 延迟/失败配置

2) 定位归因
- 分类：SSE 写流/读流、序列化、DB 锁/约束、协程饥饿、队列堆积、超时/重试放大
- 关联 run_id/trace_id（若启用）

3) 外科手术式修复（KISS/SOLID）
- 优先修边界：资源释放、背压/限流、timeout、重试上限、幂等一致性
- 避免引入隐式耦合（SRP/OCP）

4) 回归验证
- 重跑 baseline 档 + 一个中等并发档 + 接近拐点档
- 确认 error_rate/P95 口径满足，再继续爬坡

---

## 9. 风险与局限（必须写入最终总结报告）
- 单实例结论不可外推到生产（硬件/DB/多副本差异）
- SQLite（若使用）对并发写入与锁竞争非常敏感，结果可能偏保守且抖动大（必须注明）
- 不走真实外部调用会低估真实延迟，但通过 stub 延迟分布可部分模拟；必须记录 stub 配置
- SSE 压测若不完整消费流会产生“假高并发结论”，脚本必须强制读到终态

---

## 10. 交付物（执行完成后必须生成）

### 10.1 执行期产物（原始数据）
- 压测原始结果（每 attempt：duration/TTFB/events/bytes/terminal_type）
- 系统资源采样数据（CPU/内存/连接数/句柄）
- 关键日志样本（用于归因）

### 10.2 最终总结文档（必须）
文件：`docs/three-high-test-report.md`
必须包含：
- 环境与配置（含 stub 延迟/失败率）
- baseline 表（W1~W4 的 baseline_P95 与 2x 阈值）
- 并发爬坡结果（最大稳定并发、拐点并发、Profile A/B 对照）
- 高可用验证结果（断连、故障注入、重启恢复）
- 瓶颈归因（证据驱动：曲线/日志/指标）
- 优化建议（按 ROI 排序：立即可做 / 中期 / 长期）
- 一句话结论摘要（可用于汇报）
