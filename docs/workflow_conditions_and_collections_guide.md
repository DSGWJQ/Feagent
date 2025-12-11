# 工作流条件分支与集合操作使用指南

## 概述

本指南介绍如何在Feagent工作流系统中使用**条件分支**和**集合操作**功能，实现智能化的数据处理流程。

## 功能特性

### 1. 条件分支（Conditional Branching）

根据前置节点的输出结果动态选择执行路径，实现if-else决策逻辑。

**核心特性：**
- ✅ 基于布尔表达式的条件判断
- ✅ 支持多分支路由
- ✅ 访问前置节点输出字段
- ✅ 条件不满足时自动跳过节点
- ✅ 支持复杂的逻辑运算（and、or、not）

### 2. 集合操作（Collection Operations）

对列表、数组等集合数据进行批量处理。

**三种操作类型：**
- **Loop（for_each）**：遍历集合，对每个元素执行子工作流
- **Map**：转换集合元素，映射为新集合
- **Filter**：根据条件过滤集合元素

---

## 一、条件分支使用方法

### 1.1 基本语法

在工作流YAML定义中，通过`edges`的`condition`字段配置条件：

```yaml
edges:
  - source: node_a
    target: node_b
    condition: "score > 0.8"  # 条件表达式
```

### 1.2 支持的表达式

**比较运算符：**
```python
"value > 100"         # 大于
"price < 50"          # 小于
"status == 'active'"  # 等于
"count != 0"          # 不等于
"score >= 0.7"        # 大于等于
"age <= 18"           # 小于等于
```

**逻辑运算符：**
```python
"score > 0.8 and status == 'valid'"           # 与
"priority == 'high' or amount > 10000"        # 或
"not is_processed"                            # 非
"(score > 0.7 and status == 'ready') or force_process"  # 组合
```

**访问对象字段：**
```python
"user.level > 5"                  # 嵌套字段访问
"order.total_amount > 1000"       # 对象属性
"data.quality_score >= threshold" # 使用参数变量
```

### 1.3 完整示例：数据质量检查

```yaml
name: data_quality_pipeline
kind: workflow
description: 根据数据质量分数选择处理路径

parameters:
  - name: quality_threshold
    type: number
    default: 0.7

nodes:
  - id: load_data
    type: generic
    name: 加载数据

  - id: quality_check
    type: generic
    name: 质量检查
    outputs:
      - quality_score  # 输出质量分数

  - id: clean_data
    type: generic
    name: 数据清洗

  - id: process_data
    type: generic
    name: 数据处理

edges:
  - source: load_data
    target: quality_check

  # 条件分支：质量低时执行清洗
  - source: quality_check
    target: clean_data
    condition: "quality_score < quality_threshold"

  # 条件分支：质量高时直接处理
  - source: quality_check
    target: process_data
    condition: "quality_score >= quality_threshold"

  # 清洗后继续处理
  - source: clean_data
    target: process_data
```

**执行流程：**
1. 如果 `quality_score < 0.7`：`load_data → quality_check → clean_data → process_data`
2. 如果 `quality_score >= 0.7`：`load_data → quality_check → process_data`

---

## 二、Loop操作（for_each）

### 2.1 基本语法

```yaml
nodes:
  - id: loop_users
    type: loop
    name: 遍历用户
    config:
      loop_type: for_each
      collection_field: users        # 集合字段名
      item_variable: current_user    # 当前元素变量名
      max_iterations: 1000           # 最大迭代次数（可选）
    outputs:
      - aggregated_results   # 聚合所有迭代结果
      - iteration_count      # 实际迭代次数
```

### 2.2 完整示例：批量用户处理

```yaml
name: batch_user_processing
kind: workflow
description: 批量处理用户列表

nodes:
  # 1. 加载用户列表
  - id: load_users
    type: generic
    config:
      action: load_from_db
      table: users
    outputs:
      - users  # 输出: [{id:1, name:"Alice"}, {id:2, name:"Bob"}, ...]

  # 2. Loop遍历用户
  - id: loop_users
    type: loop
    config:
      loop_type: for_each
      collection_field: users
      item_variable: current_user

  # 3. 处理单个用户（Loop的子节点）
  - id: process_user
    type: generic
    config:
      action: send_email
      user_id: "{{current_user.id}}"      # 访问当前用户ID
      user_name: "{{current_user.name}}"  # 访问当前用户名

edges:
  - source: load_users
    target: loop_users

  # Loop自动为每个元素执行子节点
  - source: loop_users
    target: process_user
```

**执行逻辑：**
- `process_user`会被执行N次（N = len(users)）
- 每次执行时，`current_user`包含当前元素的数据
- 所有结果聚合到`loop_users`的`aggregated_results`输出

---

## 三、Filter操作

### 3.1 基本语法

```yaml
nodes:
  - id: filter_high_value
    type: loop
    config:
      loop_type: filter
      collection_field: orders         # 输入集合
      filter_condition: "amount > 1000"  # 过滤条件
    outputs:
      - filtered_collection  # 过滤后的集合
```

### 3.2 完整示例：订单筛选

```yaml
name: high_value_order_filter
kind: workflow
description: 筛选高价值订单

parameters:
  - name: min_amount
    type: number
    default: 1000

nodes:
  # 1. 加载订单
  - id: load_orders
    type: generic
    outputs:
      - orders  # [{id:1, amount:500}, {id:2, amount:1500}, ...]

  # 2. Filter过滤
  - id: filter_high_value
    type: loop
    config:
      loop_type: filter
      collection_field: orders
      filter_condition: "amount > min_amount"
    outputs:
      - filtered_collection  # 只保留amount > 1000的订单

  # 3. VIP处理
  - id: vip_process
    type: generic
    config:
      action: vip_handling

edges:
  - source: load_orders
    target: filter_high_value
  - source: filter_high_value
    target: vip_process
```

**执行结果：**
```python
# 输入orders: [
#   {"id": 1, "amount": 500},
#   {"id": 2, "amount": 1500},
#   {"id": 3, "amount": 2000}
# ]

# 输出filtered_collection: [
#   {"id": 2, "amount": 1500},
#   {"id": 3, "amount": 2000}
# ]
```

### 3.3 Filter支持的条件表达式

**简单值过滤：**
```python
"x > 100"        # 简单数值比较
"status == 'active'"  # 字符串比较
```

**对象字段过滤：**
```python
"age >= 18"                    # 对象字段
"score > 0.7 and status == 'valid'"  # 多条件
"price < max_price"            # 使用参数变量
```

---

## 四、Map操作

### 4.1 基本语法

```yaml
nodes:
  - id: apply_discount
    type: loop
    config:
      loop_type: map
      collection_field: products
      transform_expression: "price * 0.9"  # 转换表达式
    outputs:
      - transformed_collection  # 转换后的集合
```

### 4.2 完整示例：价格折扣

```yaml
name: price_discount_map
kind: workflow
description: 对商品应用价格折扣

parameters:
  - name: discount_rate
    type: number
    default: 0.1  # 10%折扣

nodes:
  # 1. 加载商品
  - id: load_products
    type: generic
    outputs:
      - products  # [{id:1, price:100}, {id:2, price:200}, ...]

  # 2. Map转换价格
  - id: apply_discount
    type: loop
    config:
      loop_type: map
      collection_field: products
      transform_expression: "price * (1 - discount_rate)"
    outputs:
      - transformed_collection

  # 3. 保存更新
  - id: save_products
    type: generic
    config:
      action: update_db

edges:
  - source: load_products
    target: apply_discount
  - source: apply_discount
    target: save_products
```

**执行结果：**
```python
# 输入products: [
#   {"id": 1, "name": "A", "price": 100},
#   {"id": 2, "name": "B", "price": 200}
# ]

# 输出transformed_collection: [
#   {"id": 1, "name": "A", "price": 90},  # 100 * 0.9
#   {"id": 2, "name": "B", "price": 180}  # 200 * 0.9
# ]
```

---

## 五、高级用法：组合场景

### 5.1 条件分支 + Filter

根据数据量决定是否采样，然后过滤：

```yaml
nodes:
  - id: check_size
    type: generic
    outputs:
      - data_items
      - record_count

  - id: sample_data
    type: generic

  - id: filter_valid
    type: loop
    config:
      loop_type: filter
      collection_field: data_items
      filter_condition: "score >= 0.7"

edges:
  # 大数据集：先采样再过滤
  - source: check_size
    target: sample_data
    condition: "record_count > 10000"

  - source: sample_data
    target: filter_valid

  # 小数据集：直接过滤
  - source: check_size
    target: filter_valid
    condition: "record_count <= 10000"
```

### 5.2 Filter + Map + Loop

完整的数据处理流水线：

```yaml
nodes:
  # 1. 过滤有效订单
  - id: filter_orders
    type: loop
    config:
      loop_type: filter
      collection_field: orders
      filter_condition: "status == 'pending'"

  # 2. 应用折扣
  - id: apply_discount
    type: loop
    config:
      loop_type: map
      collection_field: filtered_collection
      transform_expression: "amount * 0.95"

  # 3. 批量处理
  - id: loop_process
    type: loop
    config:
      loop_type: for_each
      collection_field: transformed_collection
      item_variable: order

  - id: process_order
    type: generic

edges:
  - source: filter_orders
    target: apply_discount
  - source: apply_discount
    target: loop_process
  - source: loop_process
    target: process_order
```

**执行流程：**
1. Filter：`orders` → 只保留`status == 'pending'`的订单
2. Map：对每个订单的`amount`应用5%折扣
3. Loop：遍历处理每个订单

---

## 六、最佳实践

### 6.1 条件表达式设计

**✅ 推荐：**
```python
"quality_score >= threshold"          # 清晰的语义
"user.level > 5 and user.status == 'active'"  # 逻辑清晰
"len(items) > 0"                      # 检查集合非空
```

**❌ 避免：**
```python
"import os"                           # 不支持import
"eval('malicious code')"              # 不支持eval
"__builtins__"                        # 不支持访问内置对象
```

### 6.2 集合操作性能优化

**1. 使用max_iterations限制迭代次数：**
```yaml
config:
  loop_type: for_each
  max_iterations: 1000  # 防止无限循环
```

**2. 先Filter后Loop：**
```yaml
# ✅ 好：先过滤减少数据量
filter (10000 → 100) → loop (100次)

# ❌ 差：全量遍历
loop (10000次)
```

**3. 合理使用Map代替Loop：**
```yaml
# ✅ Map：简单转换，高效
map: "price * 0.9"

# ❌ Loop：复杂度高，仅当需要执行复杂子流程时使用
loop → process_item
```

### 6.3 错误处理策略

```yaml
error_strategy:
  retry:
    max_attempts: 3
    delay_seconds: 5.0
  on_failure: continue  # Loop中单个元素失败不影响其他元素
```

---

## 七、常见问题

### Q1: 条件表达式中的变量从哪里来？

**A:** 变量来自前置节点的输出字段。例如：

```yaml
- id: node_a
  outputs:
    - score      # 定义输出字段
    - status

- id: node_b
  # 可以在条件中使用 score 和 status
edges:
  - source: node_a
    target: node_b
    condition: "score > 0.8 and status == 'ready'"
```

### Q2: Loop的子节点如何访问当前元素？

**A:** 通过`item_variable`配置的变量名访问：

```yaml
config:
  item_variable: current_user  # 定义变量名

# 子节点中使用
config:
  user_id: "{{current_user.id}}"
  user_name: "{{current_user.name}}"
```

### Q3: 如何处理空集合？

**A:** 系统会自动处理：
- Filter返回空列表：`filtered_collection: []`
- Loop迭代0次：`iteration_count: 0`
- 子节点不会被执行

### Q4: 条件分支都不满足会怎样？

**A:** 目标节点会被标记为`skipped`，不会执行，但工作流会继续。

### Q5: 可以嵌套Loop吗？

**A:** 可以。外层Loop的每次迭代会执行内层Loop：

```yaml
- id: outer_loop
  config:
    loop_type: for_each
    collection_field: users

- id: inner_loop
  config:
    loop_type: for_each
    collection_field: orders  # 来自当前用户的订单
```

---

## 八、配置示例文件

完整的YAML配置示例已提供在 `definitions/nodes/` 目录：

1. **`conditional_data_quality_pipeline.yaml`** - 条件分支示例
2. **`loop_batch_user_processing.yaml`** - Loop遍历示例
3. **`filter_high_value_orders.yaml`** - Filter过滤示例
4. **`map_price_discount.yaml`** - Map转换示例
5. **`smart_order_processing_system.yaml`** - 复杂组合示例

---

## 九、API调用方式

### Python代码示例

```python
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.node_registry import NodeFactory, NodeType

# 创建工作流
agent = WorkflowAgent(workflow_context=ctx, node_factory=factory)

# 添加节点
source = factory.create(NodeType.GENERIC, {"name": "source"})
filter_node = factory.create(NodeType.LOOP, {
    "loop_type": "filter",
    "collection_field": "items",
    "filter_condition": "price > 100"
})

agent.add_node(source)
agent.add_node(filter_node)

# 连接节点（带条件）
agent.connect_nodes(source.id, filter_node.id, condition="status == 'active'")

# 执行工作流
result = await agent.execute_workflow_with_collection_operations()

print(result["status"])  # "completed"
print(result["results"])  # 节点执行结果
print(result["skipped_nodes"])  # 被跳过的节点
```

---

## 十、技术支持

如有问题，请参考：
- 源码：`src/domain/agents/workflow_agent.py`
- 单元测试：`tests/unit/domain/agents/test_workflow_collection_operations.py`
- 集成测试：`tests/integration/test_workflow_conditions_and_collections.py`
- 架构文档：`docs/architecture/current_agents.md`

---

**版本**: 1.0.0
**更新日期**: 2025-12-09
**作者**: Feagent Team
