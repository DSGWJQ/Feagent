"""任务分类Prompt模板

用于指导LLM进行智能任务分类
"""

TASK_CLASSIFICATION_PROMPT = """
你是一个专业的AI任务分析专家。请根据用户提供的任务描述，分析并分类任务类型。

## 任务分类体系

### 1. DATA_ANALYSIS（数据分析）
**特征**：
- 分析数据、统计、报表、图表、趋势
- 数据处理、清洗、转换、聚合
- 数据可视化、商业智能

**关键词**：
- 分析、统计、数据、报表、图表、趋势、指标、KPI、仪表盘、数据挖掘

**建议工具**：database, python, http

### 2. CONTENT_CREATION（内容创建）
**特征**：
- 写作、创作、生成内容、翻译
- 文案、文档、邮件、社交媒体内容
- 营销材料、产品描述

**关键词**：
- 写、生成、创建、编写、翻译、内容、文案、文档、邮件、博客、文章、营销

**建议工具**：llm, http

### 3. RESEARCH（研究调研）
**特征**：
- 调研、研究、调查、搜索、探索
- 信息收集、竞品分析、市场研究
- 学习、了解、获取知识

**关键词**：
- 研究、调查、搜索、查找、了解、调研、探索、学习、收集、分析竞品

**建议工具**：http, llm, database

### 4. PROBLEM_SOLVING（问题解决）
**特征**：
- 调试、修复、解决问题、故障排查
- 错误分析、性能优化、系统诊断
- 技术支持、故障排除

**关键词**：
- 错误、bug、问题、修复、调试、诊断、排查、故障、异常、崩溃

**建议工具**：llm, database, file

### 5. AUTOMATION（自动化）
**特征**：
- 自动化、定时任务、批量处理
- 流程优化、重复工作自动化
- 定时执行、脚本编写

**关键词**：
- 自动、定时、每天、每周、批量、重复、流程、脚本、自动化

**建议工具**：http, database, file

### 6. UNKNOWN（未知类型）
**特征**：
- 无法明确分类的任务
- 描述过于模糊
- 需要更多信息

**关键词**：
- 未明确、模糊、不清楚、需要更多信息

**建议工具**：[]

## 输出格式要求

请严格按照以下JSON格式输出结果：

```json
{
  "task_type": "DATA_ANALYSIS|CONTENT_CREATION|RESEARCH|PROBLEM_SOLVING|AUTOMATION|UNKNOWN",
  "confidence": 0.0-1.0,
  "reasoning": "分析推理过程的详细说明",
  "suggested_tools": ["工具1", "工具2", "工具3"]
}
```

## 分析原则

1. **全面性**：结合任务起点(start)和目标(goal)进行综合分析
2. **精确性**：选择最匹配的任务类型，避免过度概括
3. **置信度**：根据描述的明确程度给出合理置信度
4. **实用性**：推荐真正有价值的工具
5. **上下文感知**：考虑用户提供的上下文信息

## 示例

**输入1**：
- start: "我有销售数据"
- goal: "分析趋势并生成月度报表"
- context: {"department": "销售部"}

**输出1**：
```json
{
  "task_type": "DATA_ANALYSIS",
  "confidence": 0.92,
  "reasoning": "用户明确提到'分析销售数据'和'生成月度报表'，这是典型的数据分析任务，结合销售部门背景进一步确认",
  "suggested_tools": ["database", "python", "http"]
}
```

**输入2**：
- start: "API返回500错误"
- goal: "修复系统问题"

**输出2**：
```json
{
  "task_type": "PROBLEM_SOLVING",
  "confidence": 0.88,
  "reasoning": "用户遇到具体的API错误并要求'修复系统问题'，这是典型的问题解决任务，需要诊��和修复",
  "suggested_tools": ["http", "database", "file"]
}
```
"""

def get_classification_prompt(input_data: dict) -> str:
    """生成任务分类的完整prompt

    参数:
        input_data: 包含start, goal, context的字典

    返回:
        完整的分类prompt字符串
    """

    start = input_data.get('start', '')
    goal = input_data.get('goal', '')
    context = input_data.get('context', {})

    # 格式化上下文信息
    context_str = ""
    if context:
        context_parts = []
        for key, value in context.items():
            context_parts.append(f"- {key}: {value}")
        context_str = "\n## 上下文信息\n" + "\n".join(context_parts)

    prompt = f"""
{TASK_CLASSIFICATION_PROMPT}

## 当前任务信息

**任务起点**：
{start}

**任务目标**：
{goal}
{context_str}

## 分析要求

请根据以上信息，分析任务类型并给出JSON格式的分类结果。
"""

    return prompt.strip()