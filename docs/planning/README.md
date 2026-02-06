# 技术规划总揽文档

**文档版本**: 1.0.0
**创建日期**: 2026-01-12
**最后更新**: 2026-01-12
**所有者**: Architecture Team

---

## 📋 规划文档索引

本文档汇总了项目中期和长期的技术规划，所有规划文档均已完成并可供参考实施。

| # | 规划名称 | 优先级 | 工期 | 状态 | 文档路径 |
|---|---------|--------|------|------|---------|
| 0 | **项目精简与去冗余总规划（一次性收敛版）** | P0 (近期) | 1-2周 | 🚧 进行中 | [PROJECT_SIMPLIFICATION_DEDUP_PLAN.md](./PROJECT_SIMPLIFICATION_DEDUP_PLAN.md) |
| 1 | **事件系统修复** | P1 (中期) | 2-3周 | ✅ 已收敛（EventBus 单轨） | [EVENT_SYSTEM_FIX_PLAN.md](./EVENT_SYSTEM_FIX_PLAN.md) |
| 2 | **Human 节点实现** | P2 (中期) | 2-3周 | 📋 待启动 | [HUMAN_NODE_IMPLEMENTATION_PLAN.md](./HUMAN_NODE_IMPLEMENTATION_PLAN.md) |
| 3 | **EventBus 架构升级** | P3 (长期) | 2-3月 | 🧊 暂缓（长期备选） | [EVENTBUS_ARCHITECTURE_UPGRADE_PLAN.md](./EVENTBUS_ARCHITECTURE_UPGRADE_PLAN.md) |

---

## 🎯 战略路线图

### 阶段划分

```
┌─────────────────────────────────────────────────────────────┐
│                    项目演进路线图                            │
└─────────────────────────────────────────────────────────────┘

Phase 1: 当前阶段 (已完成)
├─ ✅ 四场景 E2E 测试通过
├─ ✅ 事件缺失根因调查
└─ ✅ 知识助理 Fixture 创建

Phase 2: 中期优化 (2-3周 × 2)
├─ 🔧 事件系统修复 (P1)
│   ├─ Week 1: 基础设施 (BaseExecutor + 事件定义)
│   ├─ Week 2: 执行器改造 (7个执行器)
│   └─ Week 3: 依赖注入 + 测试验证
│
└─ 📊 Human 节点实现 (P2)
    ├─ Week 1: 基础设施 (YAML + 数据模型)
    ├─ Week 2: 执行器 + 工作流集成
    └─ Week 3: 前端 + E2E 测试

Phase 3: 长期架构升级 (2-3月)
└─ 🏗️ EventBus 统一架构
    ├─ Month 1: Event Store + EventBus 升级
    ├─ Month 2: CQRS 实现
    └─ Month 3: Saga 编排 + 全面迁移
```

---

## 📊 优先级矩阵

### 价值 vs 成本分析

```
高价值 │
      │  ┌─────────────┐
      │  │ 事件系统修复 │ ← P1 推荐优先
      │  │  (快速收益)  │
      │  └─────────────┘
      │         │
      │         │  ┌─────────────┐
      │         │  │Human节点实现│ ← P2 业务需求
      │         │  │  (用户体验)  │
价    │         │  └─────────────┘
值    │         │
      │         │
      │         │         ┌─────────────┐
      │         │         │EventBus升级│ ← P3 长期投资
      │         │         │(架构重构)  │
      │         │         └─────────────┘
低价值│─────────┼──────────────────────────▶
      低成本            成本                高成本
```

**推荐顺序**:
1. **事件系统修复** (P1) - 快速见效，解决技术债务
2. **Human 节点实现** (P2) - 业务价值高，完善核心功能
3. **EventBus 架构升级** (P3) - 长期投资，战略布局

---

## 🔧 规划 1: 事件系统修复

### 核心问题
- 执行器不发布事件，依赖脆弱的 callback 机制
- UX-WF-007/008 无法从 execution channel 获取 node_complete 事件

### 解决方案
**方案 A**: 执行器发布事件（推荐）
- 让每个执行器注入 EventBus
- 在执行前后发布标准事件（node_start/complete/error）
- 符合 DDD 原则，架构解耦

### 实施计划
| Phase | 时间 | 关键交付物 |
|-------|------|-----------|
| Phase 1 | Week 1 | `BaseNodeExecutor` 基类 + 事件定义 |
| Phase 2 | Week 2 | 7个执行器改造完成 |
| Phase 3 | Week 2-3 | 依赖注入 + E2E 测试通过 |

### 验收标准
- ✅ UX-WF-007/008 测试恢复事件验证并通过
- ✅ 所有节点执行发布完整事件
- ✅ 性能影响 < 5%

### 预期收益
- **可观测性**: +100% (完整事件日志)
- **调试效率**: +30% (快速定位问题)
- **架构质量**: 消除技术债务

**详细文档**: [EVENT_SYSTEM_FIX_PLAN.md](./EVENT_SYSTEM_FIX_PLAN.md)

---

## 📊 规划 2: Human 节点实现

### 业务场景
1. **客服知识助理**: DB → LLM → **Human (审核)** → Notification
2. **财务审批**: File → Python → **Human (审批)** → Database
3. **内容审核**: HTTP → LLM → **Human (复核)** → API

### 技术挑战
| 挑战 | 优先级 | 解决方案 |
|------|--------|---------|
| 异步等待 | P0 | 工作流暂停机制 + 状态持久化 |
| 超时处理 | P0 | 定时任务 + Fallback 策略 |
| 权限控制 | P1 | 审批人列表 + 审批日志 |
| 通知机制 | P1 | Email/Webhook/In-App |

### 实施计划
| Phase | 时间 | 关键交付物 |
|-------|------|-----------|
| Phase 1 | Week 1 | `human.yaml` + `HumanApprovalTask` 实体 |
| Phase 2 | Week 1-2 | `HumanExecutor` + 事件定义 |
| Phase 3 | Week 2 | 工作流暂停/恢复机制 |
| Phase 4 | Week 2-3 | `HumanNode.tsx` + `ApprovalPanel.tsx` |

### 验收标准
- ✅ 节点定义 YAML 校验通过
- ✅ 执行器单元测试覆盖率 > 80%
- ✅ UX-WF-009 测试添加 Human 节点并通过
- ✅ 审批流程：提交 → 通过/拒绝 → 工作流继续/停止

### 预期收益
- **业务价值**: 支持人机协作场景
- **用户体验**: 友好的审批界面
- **可扩展性**: 支持多种审批模式（串行/并行/投票）

**详细文档**: [HUMAN_NODE_IMPLEMENTATION_PLAN.md](./HUMAN_NODE_IMPLEMENTATION_PLAN.md)

---

## 🏗️ 规划 3: EventBus 架构升级

### 架构愿景
从 **Callback + EventBus 混合** 演进到 **纯事件驱动架构 (EDA)**

### 核心组件

```
EventBus 统一架构
├─ Event Store (事件存储)
│   ├─ 事件溯源 (Event Sourcing)
│   ├─ 快照优化 (Snapshots)
│   └─ 时间旅行 (Time Travel Debug)
│
├─ CQRS (读写分离)
│   ├─ 命令模型 (Write)
│   └─ 查询模型 (Read via Projections)
│
├─ Saga 编排 (长事务)
│   ├─ 工作流执行 Saga
│   ├─ 补偿机制 (Rollback)
│   └─ 分布式事务
│
└─ 分布式支持
    ├─ RabbitMQ / Kafka
    ├─ 跨实例通信
    └─ 水平扩展
```

### 实施计划
| Month | 关键里程碑 |
|-------|-----------|
| Month 1 | Event Store 实现 + EventBus 升级 |
| Month 2 | CQRS 实现 + API 重构 |
| Month 3 | Saga 编排 + 全面迁移 |

### 迁移策略
1. **Phase 0**: 并行运行（EventBus + Callback 共存）
2. **Phase 1**: 逐步替换（按模块迁移）
3. **Phase 2**: 清理 Callback（删除旧代码）

### 预期收益
| 指标 | 提升幅度 |
|------|---------|
| 可维护性 | +40% |
| 可扩展性 | +100% |
| 可观测性 | +60% |
| 故障诊断时间 | -50% |

**详细文档**: [EVENTBUS_ARCHITECTURE_UPGRADE_PLAN.md](./EVENTBUS_ARCHITECTURE_UPGRADE_PLAN.md)

---

## 🔄 依赖关系图

### 规划之间的依赖

```
┌─────────────────────────────────────┐
│ 规划 3: EventBus 架构升级 (长期)    │
│ - Event Store                       │
│ - CQRS                              │
│ - Saga                              │
└─────────────┬───────────────────────┘
              │ 依赖 ▲
              │      │ 提供基础
┌─────────────▼───────────────────────┐
│ 规划 1: 事件系统修复 (中期 P1)      │
│ - 执行器发布事件                     │
│ - EventBus 统一                     │
└─────────────┬───────────────────────┘
              │ 可选依赖 (建议先完成)
              │
┌─────────────▼───────────────────────┐
│ 规划 2: Human 节点实现 (中期 P2)    │
│ - 审批任务                          │
│ - 暂停/恢复机制                     │
└─────────────────────────────────────┘
```

**推荐路径**:
1. 先完成 **规划 1** (事件系统修复) - 奠定事件基础
2. 再实施 **规划 2** (Human 节点) - 依赖事件系统
3. 最后推进 **规划 3** (EventBus 升级) - 长期演进

---

## 📈 投资回报分析 (ROI)

### 规划 1: 事件系统修复

| 维度 | 投入 | 产出 | ROI |
|------|------|------|-----|
| **人力** | 1人 × 3周 | - | - |
| **可观测性** | - | 完整事件日志 | ⭐⭐⭐⭐⭐ |
| **技术债务** | - | 消除 Callback | ⭐⭐⭐⭐⭐ |
| **调试效率** | - | +30% | ⭐⭐⭐⭐ |
| **总 ROI** | - | - | **⭐⭐⭐⭐⭐** (强烈推荐) |

### 规划 2: Human 节点实现

| 维度 | 投入 | 产出 | ROI |
|------|------|------|-----|
| **人力** | 1-2人 × 3周 | - | - |
| **业务价值** | - | 支持人机协作 | ⭐⭐⭐⭐⭐ |
| **用户体验** | - | 审批界面 | ⭐⭐⭐⭐ |
| **功能完整性** | - | 核心能力补齐 | ⭐⭐⭐⭐ |
| **总 ROI** | - | - | **⭐⭐⭐⭐** (推荐) |

### 规划 3: EventBus 架构升级

| 维度 | 投入 | 产出 | ROI |
|------|------|------|-----|
| **人力** | 2-3人 × 3月 | - | - |
| **架构质量** | - | 事件驱动架构 | ⭐⭐⭐⭐⭐ |
| **可扩展性** | - | +100% | ⭐⭐⭐⭐⭐ |
| **学习曲线** | 陡峭 | 团队提升 | ⭐⭐⭐ |
| **总 ROI** | - | - | **⭐⭐⭐⭐** (长期投资) |

---

## 🚦 启动前检查清单

### 规划 1: 事件系统修复

- [ ] 团队完成 DDD 培训
- [ ] 确认 EventBus 当前实现稳定
- [ ] 预留 1 名后端工程师 × 3周
- [ ] 准备性能测试环境
- [ ] 确定 Code Review 流程

### 规划 2: Human 节点实现

- [ ] 确认规划 1 已完成（建议）
- [ ] 确定审批人权限管理方案
- [ ] 预留 1 名后端 + 1 名前端 × 3周
- [ ] 准备通知服务（Email/Webhook）
- [ ] 设计审批 UI 原型

### 规划 3: EventBus 架构升级

- [ ] 确认规划 1 已完成（必需）
- [ ] 架构评审会议通过
- [ ] 预留 2-3 名工程师 × 3月
- [ ] 准备 PostgreSQL Event Store
- [ ] 制定灰度发布计划

---

## 📚 参考资料

### 内部文档
- [Agent 3 事件调查报告](./AGENT3_EVENT_INVESTIGATION_REPORT.md)
- [DDD 架构规范](../architecture/DDD_ARCHITECTURE.md)
- [EventBus 设计文档](../architecture/EVENTBUS_DESIGN.md)
- [四场景测试总结](../testing/FOUR_SCENARIOS_TEST_SUMMARY.md)

### 外部资源
- [Event Sourcing - Martin Fowler](https://martinfowler.com/eaaDev/EventSourcing.html)
- [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html)
- [Saga Pattern](https://microservices.io/patterns/data/saga.html)
- [Domain-Driven Design Book](https://www.oreilly.com/library/view/domain-driven-design-tackling/0321125215/)

---

## 🎯 下一步行动

### 立即行动 (This Week)
1. ✅ 规划文档已完成，等待审查
2. 📅 组织技术评审会议（讨论三个规划）
3. 🗳️ 投票决定优先启动哪个规划

### 近期计划 (Next Month)
1. 启动 **规划 1** (事件系统修复) - 推荐优先
2. 组建实施团队
3. 设置项目 Milestone 和 Kanban

### 长期愿景 (Next Quarter)
1. 完成中期规划 (1 + 2)
2. 启动长期规划 (3)
3. 持续优化和演进

---

## 📞 联系方式

**技术咨询**: Architecture Team
**问题反馈**: [项目 Issue Tracker]
**文档维护**: 每季度更新一次

---

**文档状态**: ✅ 完成
**审查状态**: 📋 待审查
**最后更新**: 2026-01-12
