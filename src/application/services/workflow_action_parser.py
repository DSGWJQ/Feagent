"""WorkflowActionParser 服务 - 工作流动作解析和验证

职责：
1. 解析 LLM 返回的 JSON 字符串
2. 执行三级验证：JSON 格式 → Pydantic 字段 → 业务规则
3. 跟踪解析尝试次数（最多 3 次）
4. 生成自动重试的提示消息

解析流程：
1. JSON 解析：尝试将字符串解析为 JSON 对象
2. 字段验证：使用 Pydantic 验证字段类型和必填项
3. 业务验证：检查节点存在、无重复执行、步骤限制等

如果任何阶段失败，返回详细的错误信息供 LLM 重试。
"""

import json

from pydantic import ValidationError

from src.domain.services.workflow_action_validator import WorkflowActionValidator
from src.domain.value_objects.workflow_action import (
    LLMResponse,
    WorkflowAction,
    WorkflowExecutionContext,
)


class ParsingError(Exception):
    """解析错误"""

    pass


class WorkflowActionParser:
    """工作流动作解析器"""

    def __init__(self):
        """初始化解析器"""
        self.validator = WorkflowActionValidator()
        self.max_retries = 3

    def parse_and_validate(
        self,
        raw_content: str,
        context: WorkflowExecutionContext,
        parse_attempt: int = 1,
    ) -> LLMResponse:
        """解析和验证工作流动作

        参数：
            raw_content: LLM 返回的原始内容
            context: 执行上下文
            parse_attempt: 当前解析尝试次数（1-3）

        返回：
            LLMResponse：包含解析结果和状态
        """
        # 第一步：JSON 解析
        try:
            json_dict = json.loads(raw_content)
            if not isinstance(json_dict, dict):
                return LLMResponse(
                    raw_content=raw_content,
                    is_valid=False,
                    error_message="JSON 必须是一个对象，不能是数组或其他类型",
                    parse_attempt=parse_attempt,
                )
        except json.JSONDecodeError as e:
            return LLMResponse(
                raw_content=raw_content,
                is_valid=False,
                error_message=f"JSON 解析失败：{str(e)}。请确保返回的是有效的 JSON 格式。",
                parse_attempt=parse_attempt,
            )
        except Exception as e:
            return LLMResponse(
                raw_content=raw_content,
                is_valid=False,
                error_message=f"解析错误：{str(e)}",
                parse_attempt=parse_attempt,
            )

        # 第二步：Pydantic 字段验证
        try:
            action = WorkflowAction(**json_dict)
        except ValidationError as e:
            # 提取第一个错误的详细信息
            errors = e.errors()
            error_messages = []
            for error in errors:
                field = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                error_messages.append(f"字段 '{field}'：{msg}")

            error_msg = "字段验证失败：" + "；".join(error_messages)
            return LLMResponse(
                raw_content=raw_content,
                is_valid=False,
                error_message=error_msg,
                parse_attempt=parse_attempt,
            )
        except Exception as e:
            return LLMResponse(
                raw_content=raw_content,
                is_valid=False,
                error_message=f"Pydantic 验证异常：{str(e)}",
                parse_attempt=parse_attempt,
            )

        # 第三步：业务规则验证
        validation_result = self.validator.validate(action, context)
        if not validation_result.is_valid:
            return LLMResponse(
                raw_content=raw_content,
                action=None,  # 业务验证失败，不返回 action
                is_valid=False,
                error_message=validation_result.error_message,
                parse_attempt=parse_attempt,
            )

        # 所有验证都通过
        return LLMResponse(
            raw_content=raw_content,
            action=action,
            is_valid=True,
            error_message=None,
            parse_attempt=parse_attempt,
        )

    def generate_retry_prompt(
        self,
        failed_response: LLMResponse,
        context: WorkflowExecutionContext,
    ) -> str:
        """生成重试提示

        根据失败原因，为 LLM 生成具体的重试指导。

        参数：
            failed_response: 失败的响应
            context: 执行上下文

        返回：
            重试提示字符串
        """
        attempt = failed_response.parse_attempt
        error_msg = failed_response.error_message or "未知错误"

        # 构建重试提示
        retry_prompt = f"第 {attempt} 次尝试失败：{error_msg}\n\n"

        # 如果是最后一次尝试，加入警告
        if attempt == self.max_retries:
            retry_prompt += "⚠️ 这是最后一次尝试机会。如果这次仍然失败，工作流将停止。\n\n"

        # 根据错误类型提供具体建议
        if "JSON" in error_msg:
            retry_prompt += "请确保返回有效的 JSON 格式，例如：\n"
            retry_prompt += '{"type": "reason", "reasoning": "your thinking here"}\n'
        elif "node_id" in error_msg or "节点" in error_msg:
            if context.available_nodes:
                retry_prompt += f"可用的节点有：{', '.join(context.available_nodes)}\n"
                retry_prompt += "请选择其中一个节点来执行。\n"
            else:
                retry_prompt += "工作流中没有可用的节点可执行。\n"
        elif "已" in error_msg and "执行" in error_msg:
            if context.executed_nodes:
                executed = ", ".join(context.executed_nodes.keys())
                retry_prompt += f"已执行的节点：{executed}\n"
                retry_prompt += "请选择一个未执行过的节点。\n"

        # 添加当前执行状态信息
        retry_prompt += "\n当前执行状态：\n"
        retry_prompt += f"- 步骤进度：{context.current_step}/{context.max_steps}\n"
        retry_prompt += f"- 可用节点：{', '.join(context.available_nodes) if context.available_nodes else '无'}\n"
        if context.executed_nodes:
            retry_prompt += f"- 已执行节点：{', '.join(context.executed_nodes.keys())}\n"

        return retry_prompt
