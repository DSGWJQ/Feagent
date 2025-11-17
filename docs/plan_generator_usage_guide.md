# PlanGeneratorChain 使用指南

本文档说明如何使用 PlanGeneratorChain 生成执行计划。

---

## 📋 目录

1. [快速开始](#快速开始)
2. [API 说明](#api-说明)
3. [使用示例](#使用示例)
4. [常见问题](#常见问题)

---

## 🚀 快速开始

### 步骤 1：导入模块

```python
from src.lc import create_plan_generator_chain
```

### 步骤 2：创建 Chain

```python
chain = create_plan_generator_chain()
```

### 步骤 3：调用 Chain

```python
result = chain.invoke({
    "start": "我有一个 CSV 文件，包含销售数据",
    "goal": "分析销售数据，生成报告",
})
```

### 步骤 4：查看结果

```python
print(f"生成了 {len(result)} 个任务：")
for i, task in enumerate(result, 1):
    print(f"{i}. {task['name']}")
    print(f"   {task['description']}")
```

**输出示例**：
```
生成了 6 个任务：
1. 导入数据
   使用 pandas 库导入 CSV 文件，将销售数据加载到 DataFrame 中
2. 数据清洗
   检查并处理数据中的缺失值、异常值，删除重复记录
3. 数据探索
   使用描述性统计方法对数据进行探索，了解数据的基本特征
4. 数据分析
   根据业务需求，计算销售总额、平均销售额、增长率等关键指标
5. 数据可视化
   使用图表工具将分析结果以图表形式展示
6. 撰写分析报告
   将分析结果和图表整理成结构化的报告
```

---

## 📖 API 说明

### `create_plan_generator_chain()`

创建计划生成链。

**返回**：
- `Runnable[dict[str, Any], list[dict[str, str]]]` - LCEL Chain

**示例**：
```python
chain = create_plan_generator_chain()
```

---

### `chain.invoke(input)`

调用 Chain 生成计划。

**参数**：
- `input` (dict): 输入参数
  - `start` (str): 起点（用户当前的状态）
  - `goal` (str): 目标（用户想要达到的目标）

**返回**：
- `list[dict[str, str]]`: 任务列表
  - 每个任务包含：
    - `name` (str): 任务名称
    - `description` (str): 任务描述

**异常**：
- `ValueError`: 当 LLM 输出无效 JSON 时
- `Exception`: 当 LLM 调用失败时

**示例**：
```python
result = chain.invoke({
    "start": "我有一个 CSV 文件",
    "goal": "分析数据",
})
```

---

## 💡 使用示例

### 示例 1：分析 CSV 文件

```python
from src.lc import create_plan_generator_chain

# 创建 Chain
chain = create_plan_generator_chain()

# 调用 Chain
result = chain.invoke({
    "start": "我有一个 CSV 文件，包含销售数据",
    "goal": "分析销售数据，生成报告",
})

# 打印结果
for i, task in enumerate(result, 1):
    print(f"{i}. {task['name']}: {task['description']}")
```

---

### 示例 2：爬取网站数据

```python
from src.lc import create_plan_generator_chain

# 创建 Chain
chain = create_plan_generator_chain()

# 调用 Chain
result = chain.invoke({
    "start": "我有一个网站 URL，需要爬取商品信息",
    "goal": "爬取商品数据并存储到数据库",
})

# 打印结果
for i, task in enumerate(result, 1):
    print(f"{i}. {task['name']}")
    print(f"   {task['description']}")
```

---

### 示例 3：在 Use Case 中使用

```python
from src.lc import create_plan_generator_chain
from src.domain.entities import Task

# 创建 Chain
chain = create_plan_generator_chain()

# 调用 Chain
plan = chain.invoke({
    "start": "我有一个 Excel 表格",
    "goal": "统计各部门人数",
})

# 转换为 Domain 实体
tasks = []
for i, task_data in enumerate(plan, 1):
    task = Task.create(
        run_id="run-123",
        name=task_data["name"],
        description=task_data["description"],
        order=i,
    )
    tasks.append(task)

# 保存到数据库
for task in tasks:
    task_repository.save(task)
```

---

### 示例 4：错误处理

```python
from src.lc import create_plan_generator_chain

# 创建 Chain
chain = create_plan_generator_chain()

try:
    # 调用 Chain
    result = chain.invoke({
        "start": "我有一个 CSV 文件",
        "goal": "分析数据",
    })

    # 验证任务数量
    if not (3 <= len(result) <= 7):
        print(f"警告：任务数量不在范围内（{len(result)} 个）")

    # 验证任务格式
    for task in result:
        if "name" not in task or "description" not in task:
            raise ValueError(f"任务格式错误：{task}")

    print(f"✅ 生成了 {len(result)} 个任务")

except ValueError as e:
    print(f"❌ JSON 解析错误：{e}")
    # 可以重试或返回默认计划

except Exception as e:
    print(f"❌ LLM 调用失败：{e}")
    # 可以重试或返回错误信息
```

---

## ❓ 常见问题

### 1. 如何控制任务数量？

**问题**：生成的任务太多或太少

**解决方案**：
- Prompt 中已经要求 3-7 个任务
- 大部分情况下 LLM 会遵守
- 如果需要严格控制，可以在代码中验证和截断：

```python
result = chain.invoke({"start": "...", "goal": "..."})

# 截断到 7 个
if len(result) > 7:
    result = result[:7]

# 如果少于 3 个，可以重试或返回错误
if len(result) < 3:
    raise ValueError("任务数量太少")
```

---

### 2. 如何提高任务质量？

**问题**：生成的任务不够具体或不够清晰

**解决方案**：
1. **优化 Prompt**：在 `src/lc/prompts/plan_generation.py` 中修改 Prompt
2. **提供更详细的输入**：在 `start` 和 `goal` 中提供更多信息
3. **使用更好的模型**：切换到 `moonshot-v1-32k` 或 `gpt-4o`

```python
# 提供更详细的输入
result = chain.invoke({
    "start": "我有一个 CSV 文件，包含 2023 年全年的销售数据，字段包括：日期、产品、销售额、地区",
    "goal": "分析销售数据，找出销售额最高的产品和地区，生成可视化报告",
})
```

---

### 3. 如何处理 JSON 解析错误？

**问题**：LLM 输出无效 JSON

**解决方案**：
1. **JsonOutputParser 自动处理**：大部分情况下会自动提取 JSON
2. **重试**：如果解析失败，可以重试

```python
max_retries = 3
for i in range(max_retries):
    try:
        result = chain.invoke({"start": "...", "goal": "..."})
        break  # 成功，退出循环
    except ValueError as e:
        if i == max_retries - 1:
            raise  # 最后一次重试失败，抛出异常
        print(f"重试 {i+1}/{max_retries}...")
```

---

### 4. 如何切换 LLM 模型？

**问题**：想使用不同的模型

**解决方案**：
修改 `.env` 文件中的 `OPENAI_MODEL`：

```bash
# 使用 KIMI 8k
OPENAI_MODEL=moonshot-v1-8k

# 使用 KIMI 32k（更好的效果）
OPENAI_MODEL=moonshot-v1-32k

# 使用 OpenAI GPT-4o-mini
OPENAI_MODEL=gpt-4o-mini
```

---

### 5. 如何测试 Chain？

**问题**：想测试 Chain 是否工作

**解决方案**：
运行测试脚本：

```bash
# 运行单元测试
python -m pytest tests/unit/lc/test_plan_generator.py -v

# 运行手动测试
python -c "from tests.unit.lc.test_plan_generator import manual_test; manual_test()"
```

---

## 📚 相关文档

- [LLM 配置指南](./llm_setup_guide.md)
- [PlanGeneratorChain 实现总结](./plan_generator_implementation_summary.md)
- [LangChain 官方文档](https://python.langchain.com/)

---

## 🎯 下一步

PlanGeneratorChain 使用完成后，你可以：

1. ✅ 集成到 ExecuteRunUseCase
2. ✅ 实现任务执行（Task Execution）
3. ✅ 添加错误处理和重试
