# Feagent 文档导航

> **项目**：Feagent – 企业级 AI 工作流编排平台  
> **阶段**：V2（对话编辑 + Coze 集成）  
> **最后更新**：2025-11-25

---

## 1. 如何快速上手
### 新成员 Checklist
1. 阅读 `docs/需求分析.md`，了解业务背景。  
2. 浏览 `docs/开发规范.md`（总览），熟悉四层 DDD 架构与流程。  
3. 使用 AI 助手前，先查看 `.augment/rules`。

### 开发新功能
1. 在 `docs/prd/` 确认需求范围。  
2. 参考 `docs/schema`、`docs/api`、`docs/security` 获取数据/接口/安全约束。  
3. 研发遵循 `docs/开发规范.md` 与 `.augment/rules`。  
4. 行为变化需同步更新对应文档。

---

## 2. 文档地图

| 分类 | 路径 | 用途 |
|------|------|------|
| **PRD** | `docs/prd/workflow_platform_prd.md` | 产品愿景、画像、旅程、功能与非功能需求 |
| **Schema** | `docs/schema/workflow_platform_schema.md` | 数据表结构、约束、索引建议、保留策略 |
| **安全/RLS** | `docs/security/rls_and_access.md` | 角色权限、行级安全、密钥与审计策略 |
| **API** | `docs/api/workflow_platform_api.md` | Agents/Workflows/Runs/调度/SSE 接口契约 |
| **架构** | `docs/architecture/langchain_guide.md` | LangChain 集成与扩展指南 |
| **需求分析** | `docs/需求分析.md` | 历史需求文档（逐步由 PRD 替换） |
| **开发规范** | `docs/开发规范.md` | 后端/前端/流程规范（00–03） |
| **技术方案** | `docs/技术方案/*.md` | 历史架构决策、方案沉淀 |
| **项目规划** | `docs/项目规划/*.md` | 路线图、风险评估、里程碑 |
| **Archive** | `docs/archive/` | 已归档文档，仅供参考 |

---

## 3. 推荐阅读顺序
1. **业务**：`prd/` → `需求分析.md`
2. **架构**：`开发规范.md` + `architecture/langchain_guide.md`
3. **数据/安全**：`schema/`、`security/`
4. **集成**：`api/`、`技术方案/04-Coze集成方案.md`
5. **流程**：`开发规范` 系列（TDD + 工作流）

---

## 4. 当前 V2 焦点
- Coze 工作流导入与执行适配器
- 对话 + 拖拽协同及版本快照
- 自定义工具 & GitHub 导入
- 调度中心与 SSE 可观测链路

实时进展见 `docs/prd/workflow_platform_prd.md` 的里程碑与风险章节。

---

## 5. 文档贡献流程
- 按类别将新内容放入 `prd/schema/security/api/architecture` 等目录。  
- 新增顶层文档时务必更新本 README。  
- 文件名尽量清晰，可使用 UTF-8 中文。  
- 使用 Markdown 标题/表格/代码块以提升可读性。

---

如需帮助，请在 `#feagent-docs` 频道沟通或在相关 PR 中留言。
