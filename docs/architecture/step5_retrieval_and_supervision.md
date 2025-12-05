# Step 5: 检索与监督整合 (Retrieval and Supervision Integration)

## 概述

Step 5 实现了知识库检索和偏离监督机制,确保 ConversationAgent 能够获取相关知识并遵循高优先级笔记的指导。

## 核心组件

### 1. VaultRetriever (知识库检索器)

**职责**: 从知识库中检索相关笔记并按优先级排序

**文件位置**: `src/domain/services/knowledge_vault_retriever.py`

#### 加权评分机制

```python
TYPE_WEIGHTS = {
    NoteType.BLOCKER: 3.0,      # 最高优先级 - 阻塞问题
    NoteType.NEXT_ACTION: 2.0,  # 中等优先级 - 计划任务
    NoteType.CONCLUSION: 1.0,   # 基础优先级 - 结论
    NoteType.PROGRESS: 0.8,     # 进展记录
    NoteType.REFERENCE: 0.5,    # 参考资料
}
```

#### 评分公式

```
final_score = relevance_score × type_weight
normalized_score = min(final_score / max_possible_score, 1.0)
```

其中:
- `relevance_score`: 基于内容匹配、标签匹配、词语匹配计算 (0-1)
- `type_weight`: 笔记类型权重
- `max_possible_score`: 最大可能得分 (1.0 × 3.0 = 3.0)

#### 相关性计算

```python
def _calculate_relevance(note, query):
    score = 0.0

    # 内容完全匹配: +0.5
    if query.lower() in note.content.lower():
        score += 0.5

    # 标签匹配: +0.3
    for tag in note.tags:
        if query.lower() in tag.lower():
            score += 0.3
            break

    # 部分词语匹配: 每个词 +0.1
    query_words = query.lower().split()
    for word in query_words:
        if len(word) > 2 and word in note.content.lower():
            score += 0.1

    return min(score, 1.0)
```

#### 注入限制

- **默认最大注入数量**: 6 条笔记
- **原因**: 避免上下文过载,保持 agent 决策的聚焦性
- **可配置**: 通过 `max_total` 参数调整

#### 使用示例

```python
retriever = VaultRetriever(default_max_total=6)

result = retriever.fetch(
    query="database connection",
    notes=all_notes,
    limit_per_type=3,      # 每种类型最多 3 条
    max_total=6,           # 总共最多 6 条
    only_approved=True,    # 只返回已批准的笔记
)

# 结果按得分降序排序
for note in result.notes:
    print(f"{note.type}: {note.content}")
```

---

### 2. DeviationAlert (偏离告警)

**职责**: 检测 ConversationAgent 是否忽视高优先级笔记

**文件位置**: `src/domain/services/knowledge_deviation_alert.py`

#### 告警类型

```python
class AlertType(str, Enum):
    WARNING = "warning"              # 警告 - 建议关注
    REPLAN_REQUIRED = "replan_required"  # 需要重新规划 - 强制干预
```

#### 严重程度

```python
class AlertSeverity(str, Enum):
    LOW = "low"       # 低 - 可忽略
    MEDIUM = "medium" # 中 - 需要关注
    HIGH = "high"     # 高 - 需要立即处理
```

#### 检测规则

| 被忽视笔记类型 | 告警类型 | 严重程度 | 处理建议 |
|--------------|---------|---------|---------|
| BLOCKER | REPLAN_REQUIRED | HIGH | 立即停止当前计划,重新规划 |
| NEXT_ACTION | WARNING | MEDIUM | 提醒 agent 考虑该计划 |
| CONCLUSION | WARNING | LOW | 记录但不强制干预 |
| PROGRESS | WARNING | LOW | 记录但不强制干预 |
| REFERENCE | WARNING | LOW | 记录但不强制干预 |

#### 忽视检测逻辑

```python
def is_note_ignored(note, agent_actions):
    # 1. 检查标签匹配
    for tag in note.tags:
        if tag.lower() in action_content.lower():
            return False  # 找到标签,未被忽视

    # 2. 检查内容关键词匹配 (支持中文)
    # 提取 2-4 字的子串作为关键词
    for substring in extract_substrings(note.content):
        if substring in action_content:
            return False  # 找到内容匹配,未被忽视

    # 3. 检查其他关键词
    for keyword in extract_keywords(note):
        if keyword.lower() in action_content.lower():
            return False

    return True  # 没有找到任何匹配,被忽视
```

#### 使用示例

```python
detector = DeviationDetector()

# 检测偏离
alert = detector.detect_deviation(
    injected_notes=[blocker, next_action],
    agent_actions=[
        {"type": "decision", "content": "实现用户认证功能"},
    ],
)

if alert:
    print(f"告警类型: {alert.alert_type}")
    print(f"严重程度: {alert.severity}")
    print(f"原因: {alert.reason}")
    print(f"被忽视笔记: {len(alert.ignored_notes)} 条")
```

---

### 3. KnowledgeCoordinator (知识协调器)

**职责**: 整合检索和监督功能,提供统一接口

**文件位置**: `src/domain/services/knowledge_coordinator_integration.py`

#### 核心功能

1. **注入笔记** (`inject_notes`)
   - 使用 VaultRetriever 检索相关笔记
   - 记录注入历史 (session_id, query, injected_notes, timestamp)
   - 返回检索结果

2. **检查偏离** (`check_deviation`)
   - 使用 DeviationDetector 检测偏离
   - 记录偏离历史 (session_id, alert, timestamp)
   - 返回告警 (如果有)

3. **查询历史**
   - `get_injection_history(session_id)`: 获取注入历史
   - `get_deviation_history(session_id)`: 获取偏离历史

4. **统计摘要** (`get_session_summary`)
   - 总注入次数
   - 总注入笔记数
   - 总偏离次数
   - 偏离率

#### 完整工作流示例

```python
coordinator = KnowledgeCoordinator(max_injection=6)

# 1. 注入笔记
result = coordinator.inject_notes(
    query="database connection",
    available_notes=all_notes,
    session_id="session_001",
)

print(f"注入了 {len(result.notes)} 条笔记")

# 2. Agent 执行行动
agent_actions = [
    {"type": "decision", "content": "实现用户认证功能"},
    {"type": "tool_call", "content": "调用 HTTP API"},
]

# 3. 检查偏离
alert = coordinator.check_deviation(
    session_id="session_001",
    agent_actions=agent_actions,
)

if alert:
    if alert.alert_type == AlertType.REPLAN_REQUIRED:
        print("⚠️ 检测到严重偏离,需要重新规划!")
        print(f"原因: {alert.reason}")
        # 触发重新规划流程
    else:
        print("ℹ️ 检测到轻微偏离,建议关注")

# 4. 查询历史
injection_history = coordinator.get_injection_history("session_001")
deviation_history = coordinator.get_deviation_history("session_001")

print(f"注入历史: {len(injection_history)} 次")
print(f"偏离历史: {len(deviation_history)} 次")

# 5. 获取统计摘要
summary = coordinator.get_session_summary("session_001")
print(f"偏离率: {summary['deviation_rate']:.2%}")
```

---

## 架构设计

### 组件关系图

```
┌─────────────────────────────────────────────────────────┐
│                  ConversationAgent                      │
│  (执行决策,可能忽视某些笔记)                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ agent_actions
                     ▼
┌─────────────────────────────────────────────────────────┐
│              KnowledgeCoordinator                       │
│  (协调检索和监督)                                         │
├─────────────────────────────────────────────────────────┤
│  • inject_notes()      - 注入笔记                        │
│  • check_deviation()   - 检查偏离                        │
│  • get_*_history()     - 查询历史                        │
│  • get_session_summary() - 统计摘要                      │
└────────┬──────────────────────────┬─────────────────────┘
         │                          │
         │ 使用                      │ 使用
         ▼                          ▼
┌──────────────────────┐   ┌──────────────────────┐
│   VaultRetriever     │   │  DeviationDetector   │
│  (知识库检索器)       │   │   (偏离检测器)        │
├──────────────────────┤   ├──────────────────────┤
│ • fetch()            │   │ • detect_deviation() │
│ • calculate_score()  │   │ • is_note_ignored()  │
│ • limit_injection()  │   │ • calculate_severity()│
└──────────────────────┘   └──────────────────────┘
         │                          │
         │ 读取                      │ 分析
         ▼                          ▼
┌─────────────────────────────────────────────────────────┐
│                    KnowledgeNote                        │
│  (知识笔记 - Step 4)                                     │
├─────────────────────────────────────────────────────────┤
│  • type: blocker/next_action/conclusion/...            │
│  • status: draft/pending_user/approved/archived        │
│  • content, tags, owner, version                       │
└─────────────────────────────────────────────────────────┘
```

### 数据流

```
1. 注入阶段:
   Query → VaultRetriever → 加权评分 → 排序 → 限制数量 → 注入笔记
                                                            ↓
                                                    InjectionRecord
                                                    (记录到历史)

2. 监督阶段:
   Agent Actions + Injected Notes → DeviationDetector → 检测忽视
                                                            ↓
                                                    DeviationAlert?
                                                            ↓
                                                    DeviationRecord
                                                    (记录到历史)

3. 查询阶段:
   Session ID → KnowledgeCoordinator → 查询历史/统计摘要
```

---

## 配置参数

### VaultRetriever 配置

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| `default_max_total` | 6 | 默认最大注入数量 |
| `TYPE_WEIGHTS` | 见上文 | 笔记类型权重 |

### DeviationDetector 配置

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| `RESOLUTION_KEYWORDS` | 见代码 | 解决关键词列表 (用于 Inspector) |
| `TYPE_SEVERITY_MAP` | 见上文 | 笔记类型对应的严重程度 |

### KnowledgeCoordinator 配置

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| `max_injection` | 6 | 最大注入数量 |

---

## 性能考虑

### 时间复杂度

- **VaultRetriever.fetch()**: O(n log n)
  - n 为笔记总数
  - 主要开销在排序

- **DeviationDetector.detect_deviation()**: O(n × m × k)
  - n 为注入笔记数 (≤6)
  - m 为 agent 行动数
  - k 为关键词数
  - 实际开销很小

### 空间复杂度

- **注入历史**: O(s × i × n)
  - s 为会话数
  - i 为每个会话的注入次数
  - n 为每次注入的笔记数 (≤6)

- **偏离历史**: O(s × d)
  - s 为会话数
  - d 为每个会话的偏离次数

### 优化建议

1. **定期清理历史**: 使用 `clear_session()` 清理过期会话数据
2. **批量检索**: 一次检索多个查询,减少重复计算
3. **缓存评分**: 对相同查询缓存评分结果

---

## 测试覆盖

### 单元测试

- **VaultRetriever**: 21 个测试,99% 覆盖率
  - 加权评分测试
  - 排序测试
  - 注入限制测试
  - 状态过滤测试

- **DeviationAlert**: 18 个测试,98% 覆盖率
  - 告警类型测试
  - 严重程度测试
  - 偏离检测测试
  - 关键词匹配测试 (中英文)

- **KnowledgeCoordinator**: 14 个测试,91% 覆盖率
  - 注入记录测试
  - 偏离检测测试
  - 历史查询测试
  - 统计摘要测试

### 集成测试

- 完整工作流测试
- VaultRetriever + DeviationDetector 集成测试
- KnowledgeCoordinator 端到端测试

---

## 使用场景

### 场景 1: 阻塞问题监督

```python
# 1. 创建 blocker 笔记
blocker = KnowledgeNote.create(
    type=NoteType.BLOCKER,
    content="数据库连接失败,需要先修复配置",
    owner="admin",
    tags=["database", "blocker"],
)

# 2. 注入笔记
coordinator.inject_notes(
    query="database",
    available_notes=[blocker],
    session_id="session_001",
)

# 3. Agent 忽视了 blocker,直接实现其他功能
agent_actions = [
    {"type": "decision", "content": "实现用户认证功能"},
]

# 4. 检测到严重偏离
alert = coordinator.check_deviation("session_001", agent_actions)
assert alert.alert_type == AlertType.REPLAN_REQUIRED
assert alert.severity == AlertSeverity.HIGH

# 5. 触发重新规划
trigger_replan(alert)
```

### 场景 2: 计划任务提醒

```python
# 1. 创建 next_action 笔记
next_action = KnowledgeNote.create(
    type=NoteType.NEXT_ACTION,
    content="优化数据库查询性能",
    owner="developer",
    tags=["performance", "database"],
)

# 2. 注入笔记
coordinator.inject_notes(
    query="performance",
    available_notes=[next_action],
    session_id="session_002",
)

# 3. Agent 忽视了计划
agent_actions = [
    {"type": "decision", "content": "添加新功能"},
]

# 4. 检测到轻微偏离
alert = coordinator.check_deviation("session_002", agent_actions)
assert alert.alert_type == AlertType.WARNING
assert alert.severity == AlertSeverity.MEDIUM

# 5. 记录警告,但不强制干预
log_warning(alert)
```

### 场景 3: 多笔记优先级排序

```python
# 1. 创建多种类型的笔记
notes = [
    KnowledgeNote.create(type=NoteType.CONCLUSION, content="结论1", ...),
    KnowledgeNote.create(type=NoteType.BLOCKER, content="阻塞1", ...),
    KnowledgeNote.create(type=NoteType.NEXT_ACTION, content="计划1", ...),
    KnowledgeNote.create(type=NoteType.BLOCKER, content="阻塞2", ...),
]

# 2. 注入笔记 (自动按优先级排序)
result = coordinator.inject_notes(
    query="test",
    available_notes=notes,
    session_id="session_003",
)

# 3. 验证排序: blocker > next_action > conclusion
assert result.notes[0].type == NoteType.BLOCKER
assert result.notes[1].type == NoteType.BLOCKER
assert result.notes[2].type == NoteType.NEXT_ACTION
assert result.notes[3].type == NoteType.CONCLUSION
```

---

## 未来扩展

### 1. 智能相关性计算

- 使用向量嵌入 (embeddings) 计算语义相关性
- 支持多语言相关性匹配
- 学习用户偏好,动态调整权重

### 2. 自适应注入策略

- 根据 agent 历史表现调整注入数量
- 根据任务复杂度动态调整权重
- 支持上下文感知的注入策略

### 3. 增强偏离检测

- 使用 LLM 进行语义理解
- 检测隐式忽视 (表面提到但实际未处理)
- 支持多轮对话的偏离检测

### 4. 实时监督

- 流式检测偏离 (而非事后检测)
- 实时告警和干预
- 支持人工介入决策

---

## 总结

Step 5 实现了完整的知识检索和监督机制:

✅ **VaultRetriever**: 加权评分 + 注入限制 (99% 覆盖率)
✅ **DeviationAlert**: 偏离检测 + 分级告警 (98% 覆盖率)
✅ **KnowledgeCoordinator**: 统一接口 + 历史记录 (91% 覆盖率)

**总测试数**: 53 个测试全部通过

**核心价值**:
- 确保 agent 获取相关知识
- 监督 agent 遵循高优先级指导
- 提供可追溯的历史记录
- 支持统计分析和优化

---

**文档版本**: 1.0
**创建日期**: 2025-01-22
**作者**: Claude Code
