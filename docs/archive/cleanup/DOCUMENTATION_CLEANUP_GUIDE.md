# 文档整理指引

## 📋 概述

本文档帮助你整理 `docs/` 目录下的所有文档，明确哪些保留、哪些归档、哪些删除。

---

## 🎯 整理原则

1. **保留**：工作流相关的核心文档
2. **归档**：Agent 相关的文档（可能有参考价值）
3. **删除**：过时、重复、不再需要的文档

---

## 📊 文档分类清单

### ✅ 保留（工作流相关）- 7 个文件

这些是新需求相关的核心文档，**必须保留**：

| 文件名 | 说明 | 优先级 |
|--------|------|--------|
| `workflow_requirements.md` | 工作流需求变更说明 | ⭐⭐⭐ |
| `workflow_api_design.md` | 工作流 API 设计 | ⭐⭐⭐ |
| `workflow_frontend_design.md` | 工作流前端设计 | ⭐⭐⭐ |
| `workflow_implementation_plan.md` | 工作流实现计划 | ⭐⭐⭐ |
| `workflow_documentation_index.md` | 工作流文档索引 | ⭐⭐⭐ |
| `backend_changes_for_workflow.md` | 后端修改分析 | ⭐⭐⭐ |
| `需求分析.md` | 原需求分析（参考） | ⭐⭐ |

**建议操作**：
```bash
# 不需要操作，保持原样
```

---

### 📦 归档（Agent 相关）- 创建 `docs/archive/agent/` 目录

这些是旧需求相关的文档，虽然不再使用，但可能有参考价值：

| 文件名 | 说明 | 是否有参考价值 |
|--------|------|---------------|
| `develop_document.md` | 开发规范（DDD + TDD） | ✅ 有（架构设计参考） |
| `api_reference.md` | Agent API 参考 | ⚠️ 部分（API 设计参考） |
| `backend_setup_guide.md` | 后端设置指南 | ✅ 有（环境配置参考） |
| `frontend_setup_guide.md` | 前端设置指南 | ✅ 有（环境配置参考） |
| `llm_setup_guide.md` | LLM 设置指南 | ✅ 有（LLM 配置参考） |
| `plan_generator_usage_guide.md` | 计划生成器使用指南 | ⚠️ 部分（LangChain 参考） |
| `tools_usage_guide.md` | 工具使用指南 | ⚠️ 部分（工具设计参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p docs/archive/agent

# 移动文件
mv docs/develop_document.md docs/archive/agent/
mv docs/api_reference.md docs/archive/agent/
mv docs/backend_setup_guide.md docs/archive/agent/
mv docs/frontend_setup_guide.md docs/archive/agent/
mv docs/llm_setup_guide.md docs/archive/agent/
mv docs/plan_generator_usage_guide.md docs/archive/agent/
mv docs/tools_usage_guide.md docs/archive/agent/
```

---

### 📦 归档（实现总结）- 创建 `docs/archive/summaries/` 目录

这些是之前开发过程中的总结文档，记录了实现细节：

| 文件名 | 说明 | 是否有参考价值 |
|--------|------|---------------|
| `api_layer_implementation_summary.md` | API 层实现总结 | ✅ 有（API 设计参考） |
| `application_layer_implementation_summary.md` | Application 层实现总结 | ✅ 有（Use Case 设计参考） |
| `execution_summary.md` | 执行总结 | ⚠️ 部分 |
| `langchain_integration_step1_summary.md` | LangChain 集成步骤 1 | ✅ 有（LangChain 参考） |
| `langchain_integration_step3_summary.md` | LangChain 集成步骤 3 | ✅ 有（LangChain 参考） |
| `langchain_integration_step4_summary.md` | LangChain 集成步骤 4 | ✅ 有（LangChain 参考） |
| `langchain_integration_step5_summary.md` | LangChain 集成步骤 5 | ✅ 有（LangChain 参考） |
| `llm_configuration_summary.md` | LLM 配置总结 | ✅ 有（LLM 配置参考） |
| `plan_generator_implementation_summary.md` | 计划生成器实现总结 | ✅ 有（LangChain 参考） |
| `tools_implementation_summary.md` | 工具实现总结 | ✅ 有（工具设计参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p docs/archive/summaries

# 移动文件
mv docs/api_layer_implementation_summary.md docs/archive/summaries/
mv docs/application_layer_implementation_summary.md docs/archive/summaries/
mv docs/execution_summary.md docs/archive/summaries/
mv docs/langchain_integration_step1_summary.md docs/archive/summaries/
mv docs/langchain_integration_step3_summary.md docs/archive/summaries/
mv docs/langchain_integration_step4_summary.md docs/archive/summaries/
mv docs/langchain_integration_step5_summary.md docs/archive/summaries/
mv docs/llm_configuration_summary.md docs/archive/summaries/
mv docs/plan_generator_implementation_summary.md docs/archive/summaries/
mv docs/tools_implementation_summary.md docs/archive/summaries/
```

---

### 📦 归档（前端相关）- 创建 `docs/archive/frontend/` 目录

这些是之前前端开发的文档：

| 文件名 | 说明 | 是否有参考价值 |
|--------|------|---------------|
| `frontend_architecture_summary.md` | 前端架构总结 | ✅ 有（架构参考） |
| `frontend_complete_summary.md` | 前端完整总结 | ✅ 有（整体参考） |
| `frontend_infrastructure_implementation.md` | 前端基础设施实现 | ✅ 有（基础设施参考） |
| `frontend_infrastructure_summary_cn.md` | 前端基础设施总结（中文） | ✅ 有（基础设施参考） |
| `frontend_testing_guide.md` | 前端测试指南 | ✅ 有（测试参考） |
| `how_to_use_v0_template.md` | V0 使用指南 | ✅ 有（V0 参考） |
| `v0_development_guide.md` | V0 开发指南 | ✅ 有（V0 参考） |
| `v0_workflow_summary.md` | V0 工作流总结 | ✅ 有（V0 参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p docs/archive/frontend

# 移动文件
mv docs/frontend_architecture_summary.md docs/archive/frontend/
mv docs/frontend_complete_summary.md docs/archive/frontend/
mv docs/frontend_infrastructure_implementation.md docs/archive/frontend/
mv docs/frontend_infrastructure_summary_cn.md docs/archive/frontend/
mv docs/frontend_testing_guide.md docs/archive/frontend/
mv docs/how_to_use_v0_template.md docs/archive/frontend/
mv docs/v0_development_guide.md docs/archive/frontend/
mv docs/v0_workflow_summary.md docs/archive/frontend/
```

---

### 📦 归档（其他）- 创建 `docs/archive/misc/` 目录

| 文件名 | 说明 | 是否有参考价值 |
|--------|------|---------------|
| `person_record.md` | 个人记录 | ⚠️ 看你自己 |
| `基本流程md` | 基本流程 | ⚠️ 部分 |
| `项目时间规划.md` | 项目时间规划 | ⚠️ 部分 |

**建议操作**：
```bash
# 创建归档目录
mkdir -p docs/archive/misc

# 移动文件
mv docs/person_record.md docs/archive/misc/
mv docs/基本流程md docs/archive/misc/
mv docs/项目时间规划.md docs/archive/misc/
```

---

## 📁 整理后的目录结构

```
docs/
├── workflow_requirements.md                    ← 工作流需求
├── workflow_api_design.md                      ← 工作流 API 设计
├── workflow_frontend_design.md                 ← 工作流前端设计
├── workflow_implementation_plan.md             ← 工作流实现计划
├── workflow_documentation_index.md             ← 工作流文档索引
├── backend_changes_for_workflow.md             ← 后端修改分析
├── 需求分析.md                                  ← 原需求分析
│
└── archive/                                    ← 归档目录
    ├── agent/                                  ← Agent 相关
    │   ├── develop_document.md
    │   ├── api_reference.md
    │   ├── backend_setup_guide.md
    │   ├── frontend_setup_guide.md
    │   ├── llm_setup_guide.md
    │   ├── plan_generator_usage_guide.md
    │   └── tools_usage_guide.md
    │
    ├── summaries/                              ← 实现总结
    │   ├── api_layer_implementation_summary.md
    │   ├── application_layer_implementation_summary.md
    │   ├── execution_summary.md
    │   ├── langchain_integration_step1_summary.md
    │   ├── langchain_integration_step3_summary.md
    │   ├── langchain_integration_step4_summary.md
    │   ├── langchain_integration_step5_summary.md
    │   ├── llm_configuration_summary.md
    │   ├── plan_generator_implementation_summary.md
    │   └── tools_implementation_summary.md
    │
    ├── frontend/                               ← 前端相关
    │   ├── frontend_architecture_summary.md
    │   ├── frontend_complete_summary.md
    │   ├── frontend_infrastructure_implementation.md
    │   ├── frontend_infrastructure_summary_cn.md
    │   ├── frontend_testing_guide.md
    │   ├── how_to_use_v0_template.md
    │   ├── v0_development_guide.md
    │   └── v0_workflow_summary.md
    │
    └── misc/                                   ← 其他
        ├── person_record.md
        ├── 基本流程md
        └── 项目时间规划.md
```

---

## 🚀 快速整理脚本

### Windows PowerShell

```powershell
# 创建归档目录
New-Item -ItemType Directory -Force -Path "docs/archive/agent"
New-Item -ItemType Directory -Force -Path "docs/archive/summaries"
New-Item -ItemType Directory -Force -Path "docs/archive/frontend"
New-Item -ItemType Directory -Force -Path "docs/archive/misc"

# 移动 Agent 相关文档
Move-Item -Path "docs/develop_document.md" -Destination "docs/archive/agent/"
Move-Item -Path "docs/api_reference.md" -Destination "docs/archive/agent/"
Move-Item -Path "docs/backend_setup_guide.md" -Destination "docs/archive/agent/"
Move-Item -Path "docs/frontend_setup_guide.md" -Destination "docs/archive/agent/"
Move-Item -Path "docs/llm_setup_guide.md" -Destination "docs/archive/agent/"
Move-Item -Path "docs/plan_generator_usage_guide.md" -Destination "docs/archive/agent/"
Move-Item -Path "docs/tools_usage_guide.md" -Destination "docs/archive/agent/"

# 移动实现总结文档
Move-Item -Path "docs/api_layer_implementation_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/application_layer_implementation_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/execution_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/langchain_integration_step1_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/langchain_integration_step3_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/langchain_integration_step4_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/langchain_integration_step5_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/llm_configuration_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/plan_generator_implementation_summary.md" -Destination "docs/archive/summaries/"
Move-Item -Path "docs/tools_implementation_summary.md" -Destination "docs/archive/summaries/"

# 移动前端相关文档
Move-Item -Path "docs/frontend_architecture_summary.md" -Destination "docs/archive/frontend/"
Move-Item -Path "docs/frontend_complete_summary.md" -Destination "docs/archive/frontend/"
Move-Item -Path "docs/frontend_infrastructure_implementation.md" -Destination "docs/archive/frontend/"
Move-Item -Path "docs/frontend_infrastructure_summary_cn.md" -Destination "docs/archive/frontend/"
Move-Item -Path "docs/frontend_testing_guide.md" -Destination "docs/archive/frontend/"
Move-Item -Path "docs/how_to_use_v0_template.md" -Destination "docs/archive/frontend/"
Move-Item -Path "docs/v0_development_guide.md" -Destination "docs/archive/frontend/"
Move-Item -Path "docs/v0_workflow_summary.md" -Destination "docs/archive/frontend/"

# 移动其他文档
Move-Item -Path "docs/person_record.md" -Destination "docs/archive/misc/"
Move-Item -Path "docs/基本流程md" -Destination "docs/archive/misc/"
Move-Item -Path "docs/项目时间规划.md" -Destination "docs/archive/misc/"

Write-Host "文档整理完成！" -ForegroundColor Green
```

---

## 📝 整理后的核心文档

整理后，`docs/` 目录下只剩下 **7 个核心文档**：

1. ✅ `workflow_requirements.md` - 工作流需求变更说明
2. ✅ `workflow_api_design.md` - 工作流 API 设计
3. ✅ `workflow_frontend_design.md` - 工作流前端设计
4. ✅ `workflow_implementation_plan.md` - 工作流实现计划
5. ✅ `workflow_documentation_index.md` - 工作流文档索引
6. ✅ `backend_changes_for_workflow.md` - 后端修改分析
7. ✅ `需求分析.md` - 原需求分析（参考）

---

## 🎯 下一步

整理完文档后，你可以：

1. **阅读核心文档**：从 `workflow_documentation_index.md` 开始
2. **开始开发**：按照 `workflow_implementation_plan.md` 的步骤
3. **需要参考时**：查看 `docs/archive/` 目录下的归档文档

---

## ✅ 总结

- **保留**：7 个核心文档（工作流相关）
- **归档**：28 个文档（Agent 相关、实现总结、前端相关、其他）
- **删除**：0 个（全部归档，以防万一）

**建议**：先归档，不要删除。如果后续确认不需要，再删除归档目录。
