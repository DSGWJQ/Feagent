# Phase 3.2 详细规划：格式约束层 - 系统基础的坚实建设

## 🎯 目标陈述

构建**严格的格式约束系统**，确保：
1. **结构化数据**：所有 LLM 输出遵循明确的 Pydantic 模型
2. **字段级验证**：必填字段、类型、枚举值的完整验证
3. **系统提示工程**：精确约束 LLM 输出格式
4. **智能重试机制**：LLM 输出失败时的自动恢复
5. **完整文档**：不再有"待实现"的标记

---

## 📋 详细设计方案

### 第一部分：Pydantic Models 设计（Domain 层）

#### 1.1 核心数据模型

```python
# src/domain/value_objects/workflow_action.py

from enum import Enum
from typing import Literal, Any
from pydantic import BaseModel, Field, validator

class ActionType(str, Enum):
    """工作流动作类型枚举"""
    REASON = "reason"           # LLM 进行推理
    EXECUTE_NODE = "execute_node"  # 执行某个节点
    WAIT = "wait"               # 等待用户输入
    FINISH = "finish"           # 工作流完成
    ERROR_RECOVERY = "error_recovery"  # 错误恢复

class WorkflowAction(BaseModel):
    """工作流执行动作的结构化表示

    这是 LLM 与执行引擎之间的**契约**：
    - LLM 必须返回这个格式
    - 系统必须验证这个格式
    - 文档明确定义了所有可能的值
    """

    type: ActionType = Field(
        ...,
        description="动作类型（必填）"
    )

    node_id: str | None = Field(
        default=None,
        description="执行的节点 ID（execute_node 时必填）"
    )

    reasoning: str | None = Field(
        default=None,
        description="推理过程或说明（reason 时必填）"
    )

    params: dict[str, Any] = Field(
        default_factory=dict,
        description="执行参数"
    )

    retry_count: int = Field(
        default=0,
        ge=0,  # >= 0
        description="重试次数"
    )

    @validator("node_id")
    def validate_node_id_for_execute(cls, v, values):
        """确保 execute_node 时必须有 node_id"""
        if values.get("type") == ActionType.EXECUTE_NODE and not v:
            raise ValueError("execute_node 必须提供 node_id")
        return v

    @validator("reasoning")
    def validate_reasoning_for_reason(cls, v, values):
        """确保 reason 时必须有推理内容"""
        if values.get("type") == ActionType.REASON and not v:
            raise ValueError("reason 必须提供 reasoning 内容")
        return v

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "type": "reason",
                "reasoning": "当前工作流需要...",
                "params": {},
                "retry_count": 0
            }
        }


class LLMResponse(BaseModel):
    """LLM 原始响应的解析结果"""

    raw_content: str = Field(
        ...,
        description="LLM 的原始文本输出"
    )

    action: WorkflowAction | None = Field(
        default=None,
        description="解析后的结构化动作"
    )

    is_valid: bool = Field(
        default=False,
        description="是否成功解析和验证"
    )

    error_message: str | None = Field(
        default=None,
        description="验证失败的错误信息"
    )

    parse_attempt: int = Field(
        default=1,
        ge=1,
        description="解析尝试次数"
    )


class WorkflowExecutionContext(BaseModel):
    """工作流执行上下文

    在执行过程中维护的状态信息
    """

    workflow_id: str
    workflow_name: str
    available_nodes: list[str]  # 当前工作流中的节点列表
    executed_nodes: dict[str, Any] = Field(default_factory=dict)  # {node_id: result}
    current_step: int = Field(default=0, ge=0)
    max_steps: int = Field(default=50, ge=1)  # 防止无限循环
    messages_count: int = Field(default=0, ge=0)
```

#### 1.2 验证规则定义

```python
# src/domain/services/workflow_action_validator.py

from typing import Type
from pydantic import ValidationError
from src.domain.value_objects.workflow_action import (
    WorkflowAction, ActionType, WorkflowExecutionContext
)

class WorkflowActionValidator:
    """工作流动作验证器

    职责：
    1. 验证 JSON 格式
    2. 验证字段完整性
    3. 验证字段值的有效性
    4. 生成清晰的错误信息
    """

    @staticmethod
    def validate(
        action_dict: dict,
        context: WorkflowExecutionContext
    ) -> tuple[WorkflowAction | None, str | None]:
        """验证动作字典

        返回：
            (action: WorkflowAction | None, error_message: str | None)
        """
        try:
            # 1. Pydantic 基础验证
            action = WorkflowAction(**action_dict)

            # 2. 业务规则验证
            error = WorkflowActionValidator._validate_business_rules(
                action, context
            )

            if error:
                return None, error

            return action, None

        except ValidationError as e:
            # 格式化 Pydantic 错误
            error_msg = WorkflowActionValidator._format_validation_error(e)
            return None, error_msg
        except Exception as e:
            return None, f"未预期的错误: {str(e)}"

    @staticmethod
    def _validate_business_rules(
        action: WorkflowAction,
        context: WorkflowExecutionContext
    ) -> str | None:
        """验证业务规则"""

        # 规则 1: execute_node 时节点必须存在
        if action.type == ActionType.EXECUTE_NODE:
            if action.node_id not in context.available_nodes:
                return f"节点 {action.node_id} 不存在于工作流中"

            if action.node_id in context.executed_nodes:
                return f"节点 {action.node_id} 已执行过"

        # 规则 2: 防止无限循环
        if context.current_step >= context.max_steps:
            return f"已达最大步骤数 ({context.max_steps})"

        # 规则 3: 节点 ID 格式验证
        if action.node_id and not action.node_id.startswith("node_"):
            return f"节点 ID 格式错误: {action.node_id}"

        return None

    @staticmethod
    def _format_validation_error(e: ValidationError) -> str:
        """将 Pydantic 错误格式化为用户可读的信息"""
        errors = []
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"字段 '{field}': {msg}")
        return "验证失败: " + " | ".join(errors)
```

---

### 第二部分：System Prompt 工程（精确约束）

#### 2.1 结构化 System Prompt

```python
# src/lc/prompts/workflow_chat_system_prompt.py

from src.domain.value_objects.workflow_action import ActionType, WorkflowExecutionContext

def get_workflow_chat_system_prompt(context: WorkflowExecutionContext) -> str:
    """生成精确的系统提示

    关键点：
    1. 明确列出所有可能的动作
    2. 给出每个动作的必填字段
    3. 给出真实的示例
    4. 强调 JSON 格式的重要性
    5. 说明失败时的后果
    """

    available_nodes = ", ".join(context.available_nodes)

    prompt = f"""你是一个工作流编排助手。你的职责是决定执行什么操作。

## 重要：必须返回 JSON 格式

你的每一个响应都必须是有效的 JSON，包含以下结构：

{{
  "type": "<动作类型>",
  "reasoning": "<可选：你的推理过程>",
  "node_id": "<可选：节点 ID>",
  "params": {{}},
  "retry_count": 0
}}

## 可用的动作类型

### 1. reason（进行推理）
当你需要分析情况时使用。
- 必填字段: type, reasoning
- 示例：
{{"type": "reason", "reasoning": "当前工作流有以下节点：{available_nodes}。我需要决定执行哪一个..."}}

### 2. execute_node（执行节点）
当你决定执行一个节点时使用。
- 必填字段: type, node_id
- node_id 必须是以下之一: {available_nodes}
- 示例：
{{"type": "execute_node", "node_id": "node_123", "params": {{"timeout": 30}}}}

### 3. wait（等待用户输入）
当你需要用户提供信息时使用。
- 必填字段: type, reasoning
- 示例：
{{"type": "wait", "reasoning": "需要用户确认执行参数"}}

### 4. finish（完成工作流）
当工作流应该结束时使用。
- 必填字段: type, reasoning
- 示例：
{{"type": "finish", "reasoning": "所有节点已成功执行"}}

### 5. error_recovery（错误恢复）
当前一个节点失败时使用。
- 必填字段: type, reasoning
- 示例：
{{"type": "error_recovery", "reasoning": "节点执行失败，尝试替代方案..."}}

## 当前工作流状态

- 工作流 ID: {context.workflow_id}
- 工作流名称: {context.workflow_name}
- 已执行节点: {list(context.executed_nodes.keys())}
- 当前步骤: {context.current_step} / {context.max_steps}
- 可用节点: {available_nodes}

## 验证规则

1. **JSON 必须有效**：如果返回的不是有效 JSON，系统会拒绝并要求重试
2. **必填字段完整**：根据动作类型，必须提供对应的必填字段
3. **node_id 必须存在**：如果类型是 execute_node，node_id 必须在可用节点列表中
4. **不能重复执行**：已执行过的节点不能再执行
5. **防止无限循环**：最多执行 {context.max_steps} 步

## 如果验证失败

- 系统会返回具体的错误信息
- 你应该分析错误，调整你的响应
- 最多重试 3 次（使用 "retry_count" 字段）
- 第 4 次失败后，工作流会中止

## 示例对话

用户：执行"获取数据"节点
你的思考：
1. 检查工作流中是否有这样的节点
2. 检查节点 ID
3. 准备执行

你的响应：
{{"type": "execute_node", "node_id": "node_get_data", "params": {{}}, "retry_count": 0}}

---

现在，请根据工作流状态，决定你的下一步操作。
返回 JSON 格式的动作。不要返回任何其他文本。"""

    return prompt
```

---

### 第三部分：智能重试机制（Application 层）

#### 3.1 重试策略

```python
# src/application/services/workflow_action_parser.py

from typing import Optional
from pydantic import ValidationError
import json
from src.domain.value_objects.workflow_action import (
    WorkflowAction, LLMResponse, WorkflowExecutionContext
)
from src.domain.services.workflow_action_validator import WorkflowActionValidator

class WorkflowActionParser:
    """工作流动作解析器

    职责：
    1. 解析 LLM 输出
    2. 验证格式和业务规则
    3. 实施重试策略
    4. 生成清晰的错误恢复提示
    """

    MAX_PARSE_ATTEMPTS = 3

    @staticmethod
    async def parse_and_validate(
        llm_output: str,
        context: WorkflowExecutionContext,
        attempt: int = 1
    ) -> LLMResponse:
        """解析和验证 LLM 输出

        参数：
            llm_output: LLM 的文本输出
            context: 执行上下文
            attempt: 当前尝试次数

        返回：
            LLMResponse，包含解析结果和错误信息
        """

        # 第 1 步：尝试 JSON 解析
        try:
            action_dict = json.loads(llm_output)
        except json.JSONDecodeError as e:
            if attempt < WorkflowActionParser.MAX_PARSE_ATTEMPTS:
                # 返回错误响应，让上层决定是否重试
                return LLMResponse(
                    raw_content=llm_output,
                    is_valid=False,
                    error_message=f"JSON 格式错误 (第 {attempt} 次尝试): {str(e)}",
                    parse_attempt=attempt
                )
            else:
                # 达到最大尝试次数
                return LLMResponse(
                    raw_content=llm_output,
                    is_valid=False,
                    error_message=f"JSON 格式错误，已重试 {attempt} 次，放弃解析",
                    parse_attempt=attempt
                )

        # 第 2 步：字段级验证
        action, error = WorkflowActionValidator.validate(action_dict, context)

        if error:
            return LLMResponse(
                raw_content=llm_output,
                action=None,
                is_valid=False,
                error_message=f"{error} (第 {attempt} 次尝试)",
                parse_attempt=attempt
            )

        # 第 3 步：验证成功
        return LLMResponse(
            raw_content=llm_output,
            action=action,
            is_valid=True,
            error_message=None,
            parse_attempt=attempt
        )

    @staticmethod
    def generate_retry_prompt(
        error_response: LLMResponse,
        context: WorkflowExecutionContext
    ) -> str:
        """生成重试提示

        当 LLM 输出验证失败时，使用这个提示让 LLM 重新尝试
        """

        prompt = f"""你的上一个响应无法被系统解析。错误信息：

{error_response.error_message}

你的上一个响应：
{error_response.raw_content}

请重新分析，确保：
1. 返回有效的 JSON
2. 必填字段完整（根据动作类型）
3. node_id（如有）在允许的列表中：{context.available_nodes}

现在请重新尝试（第 {error_response.parse_attempt + 1} 次）："""

        return prompt
```

---

### 第四部分：集成到 UseCase（Application 层）

#### 4.1 增强的 UpdateWorkflowByChatUseCase

```python
# src/application/use_cases/update_workflow_by_chat_enhanced.py

from typing import AsyncGenerator
from src.domain.value_objects.workflow_action import (
    WorkflowAction, ActionType, WorkflowExecutionContext
)
from src.application.services.workflow_action_parser import WorkflowActionParser
from src.lc.prompts.workflow_chat_system_prompt import get_workflow_chat_system_prompt

class UpdateWorkflowByChatEnhancedUseCase:
    """增强版工作流聊天 UseCase

    与原版相比，额外提供：
    1. 结构化的动作验证
    2. 智能重试机制
    3. 清晰的错误恢复流程
    4. 完整的执行日志
    """

    async def execute_streaming_with_validation(
        self,
        workflow_id: str,
        user_message: str
    ) -> AsyncGenerator[dict, None]:
        """流式执行，带完整的格式验证

        事件流：
        1. user_input
        2. llm_reasoning (流式）
        3. action_parsing
        4. action_validation (失败时重试)
        5. action_execution
        6. node_execution (流式)
        7. completion
        """

        # 初始化执行上下文
        workflow = await self.workflow_repo.find_by_id(workflow_id)
        context = WorkflowExecutionContext(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            available_nodes=[node.id for node in workflow.nodes]
        )

        messages = [
            {"role": "system", "content": get_workflow_chat_system_prompt(context)},
            {"role": "user", "content": user_message}
        ]

        # ReAct 循环
        while context.current_step < context.max_steps:
            # 第 1 步：LLM 推理（流式）
            yield {
                "type": "reasoning_start",
                "step": context.current_step
            }

            llm_output = ""
            async for chunk in self.llm_service.stream_invoke(messages):
                llm_output += chunk
                yield {
                    "type": "reasoning_chunk",
                    "content": chunk
                }

            yield {
                "type": "reasoning_complete",
                "full_output": llm_output
            }

            # 第 2 步：解析和验证（带重试）
            parse_response = await WorkflowActionParser.parse_and_validate(
                llm_output, context, attempt=1
            )

            # 重试循环
            while (not parse_response.is_valid and
                   parse_response.parse_attempt < WorkflowActionParser.MAX_PARSE_ATTEMPTS):

                yield {
                    "type": "validation_error",
                    "error": parse_response.error_message,
                    "attempt": parse_response.parse_attempt
                }

                # 生成重试提示
                retry_prompt = WorkflowActionParser.generate_retry_prompt(
                    parse_response, context
                )
                messages.append({"role": "user", "content": retry_prompt})

                # 重新请求 LLM
                llm_output = ""
                async for chunk in self.llm_service.stream_invoke(messages):
                    llm_output += chunk

                # 重新验证
                parse_response = await WorkflowActionParser.parse_and_validate(
                    llm_output, context,
                    attempt=parse_response.parse_attempt + 1
                )

            # 如果最终验证失败
            if not parse_response.is_valid:
                yield {
                    "type": "fatal_error",
                    "error": f"无法解析 LLM 输出，已重试 {parse_response.parse_attempt} 次",
                    "last_error": parse_response.error_message
                }
                break

            # 第 3 步：执行动作
            action = parse_response.action

            yield {
                "type": "action_parsed",
                "action": action.dict()
            }

            # 处理不同的动作类型
            if action.type == ActionType.REASON:
                # 继续推理，添加到消息历史
                messages.append({
                    "role": "assistant",
                    "content": action.reasoning
                })
                context.current_step += 1

            elif action.type == ActionType.EXECUTE_NODE:
                # 执行节点
                try:
                    result = await self.execute_node(
                        action.node_id, action.params
                    )
                    context.executed_nodes[action.node_id] = result

                    yield {
                        "type": "node_execution_complete",
                        "node_id": action.node_id,
                        "result": result
                    }

                    # 添加到消息历史
                    messages.append({
                        "role": "assistant",
                        "content": f"已执行节点 {action.node_id}，结果：{result}"
                    })

                except Exception as e:
                    yield {
                        "type": "node_execution_error",
                        "node_id": action.node_id,
                        "error": str(e)
                    }

                    # 触发错误恢复
                    messages.append({
                        "role": "user",
                        "content": f"节点 {action.node_id} 执行失败：{str(e)}。请决定如何处理。"
                    })

                context.current_step += 1

            elif action.type == ActionType.WAIT:
                yield {"type": "waiting_for_user", "message": action.reasoning}
                # 等待用户输入（在外部处理）
                break

            elif action.type == ActionType.FINISH:
                yield {
                    "type": "workflow_completed",
                    "reasoning": action.reasoning,
                    "executed_nodes": context.executed_nodes
                }
                break

            elif action.type == ActionType.ERROR_RECOVERY:
                # 错误恢复
                messages.append({
                    "role": "assistant",
                    "content": action.reasoning
                })
                context.current_step += 1

            # 安全检查
            if context.current_step >= context.max_steps:
                yield {
                    "type": "max_steps_reached",
                    "max_steps": context.max_steps
                }
                break
```

---

### 第五部分：测试策略（TDD 的核心）

#### 5.1 测试分层

```
单元测试（Unit）:
├─ Pydantic Models 验证
│  ├─ 必填字段检查
│  ├─ 字段类型验证
│  ├─ Enum 值验证
│  └─ 自定义验证器
│
├─ WorkflowActionValidator
│  ├─ 业务规则验证
│  ├─ 节点存在性检查
│  ├─ 执行状态检查
│  └─ 错误消息格式
│
└─ WorkflowActionParser
   ├─ JSON 解析错误处理
   ├─ 验证失败处理
   ├─ 重试逻辑
   └─ 重试提示生成

集成测试（Integration）:
├─ System Prompt 生成正确性
├─ 单轮 LLM 调用 → 验证流程
├─ 多轮重试流程
└─ 完整的 ReAct 循环

真实场景测试（Real-world）:
├─ 真实 LLM（如 GPT-4）的输出处理
├─ 边界情况（故意给 LLM 错误的输入）
├─ 错误恢复能力测试
└─ 性能和延迟测试
```

#### 5.2 关键测试场景

```python
测试场景列表：

1. 格式验证测试
   - ✅ 正确的 JSON 格式
   - ❌ 无效的 JSON
   - ❌ 缺少必填字段
   - ❌ 字段类型错误
   - ❌ Enum 值不在列表中

2. 业务规则测试
   - ❌ node_id 不存在
   - ❌ 节点已执行过
   - ❌ 超过最大步骤数
   - ❌ 节点 ID 格式错误

3. 重试逻辑测试
   - ✅ 第 1 次失败 → 自动重试
   - ✅ 第 2 次失败 → 再次重试
   - ❌ 第 4 次失败 → 中止

4. 真实 LLM 测试
   - 用 GPT-4 调用，故意给错误的上下文
   - 验证系统是否能引导 LLM 纠正
   - 测试边界情况的处理

5. 端到端测试
   - 完整的工作流执行流程
   - 从用户输入 → 最终输出
   - 验证整个约束系统的有效性
```

---

## 🏗️ 实施顺序

### Phase 3.2a：基础模型和验证（1-2 天）
```
RED:
  1. 编写 Pydantic Models 的单元测试
  2. 编写 WorkflowActionValidator 的测试
  3. 编写 WorkflowActionParser 的测试

GREEN:
  1. 实现 Pydantic Models（WorkflowAction, LLMResponse）
  2. 实现 WorkflowActionValidator
  3. 实现 WorkflowActionParser（带重试逻辑）

REFACTOR:
  1. 优化验证错误消息
  2. 优化重试策略
  3. 添加日志记录
```

### Phase 3.2b：System Prompt 和集成（1-2 天）
```
RED:
  1. 编写 System Prompt 生成的测试
  2. 编写 UpdateWorkflowByChatEnhancedUseCase 的集成测试
  3. 编写真实 LLM 场景测试

GREEN:
  1. 实现 get_workflow_chat_system_prompt()
  2. 实现增强版 UseCase
  3. 集成验证系统

REFACTOR:
  1. 微调 System Prompt
  2. 优化流式响应格式
  3. 真实场景验证
```

### Phase 3.2c：真实场景验证（1 天）
```
测试场景：
1. 正常流程：LLM 输出正确格式 → 执行
2. 格式错误：LLM 返回无效 JSON → 自动重试 → 成功
3. 业务规则错误：节点 ID 错误 → 重试提示 → 纠正
4. 恢复能力：故意给 LLM 错误的上下文 → 系统是否能恢复

验收标准：
✅ 所有测试通过
✅ 文档完整（不再有 "待实现"）
✅ 真实 LLM 测试成功
✅ 错误恢复流程清晰
```

---

## 🚨 关键假设和风险

### 假设
1. ✅ Pydantic v2 可以处理复杂的嵌套验证
2. ✅ LLM 能够理解 JSON 约束（通过良好的 Prompt）
3. ✅ 重试 3 次足以解决大多数格式错误
4. ✅ 流式响应和验证可以并行处理

### 风险
1. ⚠️ LLM 有时无法遵守 JSON 约束 → 需要更好的 Prompt 工程
2. ⚠️ 验证错误消息不够清晰 → 需要迭代改进
3. ⚠️ 重试策略可能造成延迟 → 需要性能测试
4. ⚠️ 真实 LLM 的行为难以预测 → 需要广泛的真实场景测试

---

## 📊 预期成果

### 完成后的系统状态
```
格式约束层：✅ 完整
├─ Pydantic Models：✅
├─ 字段级验证：✅
├─ System Prompt 工程：✅
├─ 智能重试：✅
└─ 文档完整：✅

测试覆盖：✅
├─ 单元测试：✅ 15+ 个
├─ 集成测试：✅ 10+ 个
└─ 真实场景：✅ 5+ 个

文档：✅
├─ 不再有 "待实现"
├─ 清晰的 API 定义
└─ 完整的示例
```

### 代码质量指标
```
- 类型覆盖：100%
- 文档字符串：100%
- 单元测试覆盖率：>80%
- 集成测试覆盖率：>70%
```

---

## 总结：为什么这样设计

1. **DDD 原则**：格式约束属于 Domain 层（WorkflowAction）
2. **分层清晰**：Domain (Model) → Application (Parser) → Interface (UseCase)
3. **易于测试**：每一层都可以独立测试
4. **易于扩展**：新增动作类型只需修改 Enum，验证器自动适应
5. **文档同步**：System Prompt 就是文档，代码和文档永不分离
6. **真实可靠**：在真实 LLM 场景下验证，而非仅依赖 Mock

---

**下一步：** 按照上述计划，从 RED 测试开始实施 Phase 3.2a
