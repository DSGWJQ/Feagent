---
name: audit
description: 全面分析项目结构并给出架构建议
argument-hint: "[具体功能或修改目标]"
allowed-tools:
  - bash
---
请按以下两个角色协作处理 **`$ARGUMENTS`**：

**Claude（分析师）- 搜集项目上下文：**
1.  **执行**：`!find . -type f -name "*.json" -o -name "*.py" -o -name "*.js" -o -name "*.md" | head -20`
2.  **分析**：项目结构、关键依赖、架构模式。
3.  **返回**：
    - 核心文件映射
    - 当前架构摘要
    - 与目标相关的代码模式

**Codex（架构师）- 规划修改：**
1.  **基于以上分析**
2.  **返回**：
    - 架构调整建议
    - 关键修改位置与顺序
    - 实施风险提示
