# 📚 文档索引（docs/）

> **注意**：本文件是 `docs/` 目录的索引，不会覆盖项目根目录的 `README.md`

本目录包含 Agent Platform 项目的所有开发文档。

---

## 🎯 核心文档（开发必读）

### 1. [ARCHITECTURE_GUIDE.md](./ARCHITECTURE_GUIDE.md) ⭐⭐⭐
**四层架构快速参考（开发时必看）**

- **用途**：开发时快速查阅，防止偏离架构规范（精简版，5 分钟读完）
- **核心内容**：
  - ✅ **四层架构图**：Interface → Application → Domain → Infrastructure
  - ✅ **各层职责说明**：每层做什么、不做什么
  - ✅ **DTO 转换机制**：Request → Input → Entity → ORM → Response
  - ✅ **三层校验机制**：API 层 → Application 层 → Domain 层
  - ✅ **聚合根概念**：多实体打包返回（如 Agent + Tasks）
  - ✅ **常见错误**：Domain 层导入框架、先设计数据库等
  - ✅ **快速参考表**：各层路径、职责、命名规范、禁止事项

**何时查看**：
- ❗ **开始任何新功能开发前**（必读，5 分钟）
- ❗ **不确定代码应该放在哪一层时**
- ❗ **不确定 DTO 如何转换时**
- ❗ **不确定如何校验数据时**
- ❗ **代码审查时**

---

### 2. [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md) ⭐⭐
**完整开发规范（详细版）**

- **用途**：完整的开发规范，包含所有细节（929 行，需要时查阅）
- **核心内容**：
  - ✅ **开发模式**：TDD（测试驱动开发）+ DDD（领域驱动设计）
  - ✅ **开发顺序**：需求分析 → Domain 层 → Ports → Infrastructure → Application → API
  - ✅ **编码规范**：命名规范、代码风格、注释规范
  - ✅ **测试规范**：测试覆盖率、测试命名、测试分层
  - ✅ **数据库规范**：事务管理、迁移流程、查询规范
  - ✅ **API 规范**：RESTful 设计、错误码、SSE 流式响应
  - ✅ **稳定性规范**：重试、超时、幂等、限流

**何时查看**：
- ❗ **不确定如何编写测试时**
- ❗ **不确定如何命名变量/函数/类时**
- ❗ **不确定如何处理事务时**
- ❗ **需要了解完整规范时**

---

### 3. [需求分析.md](./需求分析.md)
**项目需求与技术选型**

- **用途**：理解项目定位、核心功能、技术栈选择
- **内容**：
  - ✅ 项目定位：企业内部中台系统
  - ✅ 核心功能：一句话创建 Agent（起点 + 目的）
  - ✅ 技术栈建议：后端、前端、开发工具
  - ✅ Java → Python 组件映射
  - ✅ 方案评估与设计决策

**何时查看**：
- ❗ **项目初期，理解业务需求时**
- ❗ **技术选型时**
- ❗ **与产品讨论需求时**

---

## 🚧 Workflow 相关文档（新功能）

### 4. [workflow_requirements.md](./workflow_requirements.md)
Workflow 功能需求分析

### 5. [workflow_implementation_plan.md](./workflow_implementation_plan.md)
Workflow 实现计划

### 6. [workflow_api_design.md](./workflow_api_design.md)
Workflow API 设计

### 7. [workflow_frontend_design.md](./workflow_frontend_design.md)
Workflow 前端设计

### 8. [backend_changes_for_workflow.md](./backend_changes_for_workflow.md)
Workflow 后端变更

### 9. [workflow_documentation_index.md](./workflow_documentation_index.md)
Workflow 文档索引

---

## 🧹 维护文档

### 10. [CODE_CLEANUP_GUIDE.md](./CODE_CLEANUP_GUIDE.md)
代码清理指南

### 11. [DOCUMENTATION_CLEANUP_GUIDE.md](./DOCUMENTATION_CLEANUP_GUIDE.md)
文档清理指南

---

## 📦 归档文档

### [archive/](./archive/)
已归档的旧文档（不再使用，但保留作为参考）

- **agent/**：Agent 相关的旧文档
  - `backend_setup_guide.md`
  - `frontend_setup_guide.md`
  - `llm_setup_guide.md`
  - `api_reference.md`
  - 等等

- **frontend/**：前端相关的旧文档
  - `frontend_architecture_summary.md`
  - `frontend_complete_summary.md`
  - 等等

- **misc/**：其他杂项文档
  - `person_record.md`

- **summaries/**：各种总结文档

---

## 🎓 开发工作流

### 推荐的开发流程：

1. **阅读需求** → `需求分析.md`
2. **查看架构** → `ARCHITECTURE_GUIDE.md`（5 分钟快速参考）
3. **编写测试** → TDD Red 阶段
4. **实现功能** → TDD Green 阶段
5. **重构优化** → TDD Refactor 阶段
6. **代码审查** → 对照 `ARCHITECTURE_GUIDE.md` 检查

### 开发时的常见问题：

**Q: 这个功能应该放在哪一层？**
→ 查看 `ARCHITECTURE_GUIDE.md` 的"四层架构图"和"各层职责说明"

**Q: DTO 如何转换？**
→ 查看 `ARCHITECTURE_GUIDE.md` 的"DTO 转换机制"

**Q: 如何校验数据？**
→ 查看 `ARCHITECTURE_GUIDE.md` 的"三层校验机制"

**Q: Domain 层可以导入 SQLAlchemy 吗？**
→ ❌ **禁止**！查看 `ARCHITECTURE_GUIDE.md` 的"常见错误"

**Q: 应该先写数据库还是先写 Domain 层？**
→ **先写 Domain 层**！查看 `ARCHITECTURE_GUIDE.md` 的"常见错误"

**Q: 如何编写测试？**
→ 查看 `DEVELOPMENT_GUIDE.md` 第 2.0 节"TDD 开发模式"

**Q: 如何命名变量/函数/类？**
→ 查看 `DEVELOPMENT_GUIDE.md` 第 2.1 节"代码与风格"

---

## 📝 文档维护规则

1. **核心文档不要随意归档**：
   - `DEVELOPMENT_GUIDE.md` 和 `需求分析.md` 必须保留在主目录

2. **新文档命名规范**：
   - 英文大写：`DEVELOPMENT_GUIDE.md`、`README.md`
   - 中文：`需求分析.md`
   - 功能相关：`workflow_*.md`

3. **归档规则**：
   - 过时的文档移到 `archive/` 目录
   - 按类型分类：`agent/`、`frontend/`、`misc/`、`summaries/`

4. **文档引用**：
   - 使用相对路径：`[文档名](./DEVELOPMENT_GUIDE.md)`
   - 更新引用时检查路径是否正确

---

## 🔗 快速链接

- **四层架构**：[ARCHITECTURE_GUIDE.md](./ARCHITECTURE_GUIDE.md) ⭐⭐⭐
- **完整规范**：[DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)
- **需求分析**：[需求分析.md](./需求分析.md)
- **Workflow 索引**：[workflow_documentation_index.md](./workflow_documentation_index.md)
- **代码清理**：[CODE_CLEANUP_GUIDE.md](./CODE_CLEANUP_GUIDE.md)

---

**最后更新**：2025-11-19
**注意**：本文件是 `docs/` 目录的索引，不会覆盖项目根目录的 `README.md`
