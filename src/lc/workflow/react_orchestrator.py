"""ReAct 编排器 - 工作流级 ReAct 循环编排

职责：
1. 协调 Reasoning（推理）- Acting（行动）- Observing（观察）循环
2. 与 LLM 交互进行推理
3. 执行 LLM 决定的动作
4. 收集执行结果进行观察
5. 发出事件给前端进行实时反馈
6. 处理错误和重试

ReAct 循环流程：
1. Reasoning：调用 LLM 分析状态并决定下一步
2. Acting：执行 LLM 决定的动作
3. Observing：收集动作的结果
4. Decision：根据结果决定是否继续循环或结束

事件流：
- reasoning_started
- reasoning_completed
- action_executed
- observation_completed
- iteration_completed
- loop_completed
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage

from src.application.services.workflow_action_parser import WorkflowActionParser
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.workflow_action import (
    ActionType,
    WorkflowAction,
    WorkflowExecutionContext,
)
from src.lc.llm_client import get_llm_for_execution
from src.lc.prompts.workflow_chat_system_prompt import WorkflowChatSystemPrompt


class ReActLoopState:
    """ReAct 循环状态

    继承 WorkflowExecutionContext 并添加 ReAct 特定的状态跟踪
    """

    def __init__(
        self,
        workflow_id: str,
        workflow_name: str,
        available_nodes: list[str],
        max_iterations: int = 50,
    ):
        """初始化 ReAct 循环状态"""
        # 基础执行上下文
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.available_nodes = available_nodes
        self.executed_nodes: dict[str, dict] = {}
        self.current_step = 0
        self.max_steps = 50

        # ReAct 特定状态
        self.iteration_count = 0
        self.messages: list[BaseMessage] = []
        self.executed_actions: list[WorkflowAction] = []
        self.loop_status = "running"  # running / completed / failed
        self.max_iterations = max_iterations

    def add_message(self, message: BaseMessage) -> None:
        """添加消息到历史"""
        self.messages.append(message)

    def add_action(self, action: WorkflowAction) -> None:
        """记录执行的动作"""
        self.executed_actions.append(action)

    def increment_iteration(self) -> None:
        """增加迭代计数"""
        self.iteration_count += 1


@dataclass
class ReActEvent:
    """ReAct 事件"""

    event_type: str  # reasoning_started, action_executed, etc.
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


class ReActOrchestrator:
    """ReAct 编排器

    协调 ReAct 循环的核心类，负责：
    - 推理（调用 LLM）
    - 行动（执行节点）
    - 观察（收集结果）
    - 决策（确定下一步）
    """

    def __init__(
        self,
        max_iterations: int = 50,
        llm: BaseChatModel | None = None,
    ):
        """初始化 ReAct 编排器

        参数：
            max_iterations: 最大迭代次数（防止无限循环）
            llm: LLM 实例（可选，为 None 时使用默认配置创建）
        """
        self.max_iterations = max_iterations
        self.llm = llm or get_llm_for_execution()
        self.system_prompt_generator = WorkflowChatSystemPrompt()
        self.action_parser = WorkflowActionParser()
        self.event_callbacks: list[Callable[[ReActEvent], None]] = []
        self._final_state: ReActLoopState | None = None

    def orchestrate(self) -> ReActLoopState | None:
        """编排（将由 run 方法调用）"""
        return self._final_state

    def execute_action(self, action: WorkflowAction) -> dict[str, Any]:
        """执行动作"""
        return {"success": True}

    def on_event(self, callback: Callable[[ReActEvent], None]) -> None:
        """注册事件处理器

        参数：
            callback: 事件回调函数
        """
        self.event_callbacks.append(callback)

    def emit_event(self, event: ReActEvent) -> None:
        """发出事件

        参数：
            event: 要发出的事件
        """
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"事件处理器错误：{e}")

    def emit_event_simple(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """简便方法：发出事件

        参数：
            event_type: 事件类型
            data: 事件数据
        """
        event = ReActEvent(event_type=event_type, data=data or {})
        self.emit_event(event)

    def run(self, workflow: Workflow) -> ReActLoopState:
        """运行完整的 ReAct 循环

        参数：
            workflow: 要执行的工作流

        返回：
            最终的 ReAct 循环状态
        """
        # 初始化状态
        state = ReActLoopState(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            available_nodes=[node.id for node in workflow.nodes],
        )

        # 添加初始消息
        initial_message = HumanMessage(content=f"开始执行工作流：{workflow.name}")
        state.add_message(initial_message)
        self.emit_event_simple("workflow_started", {"workflow_name": workflow.name})

        # 开始 ReAct 循环
        while self._should_continue_loop(state):
            state.increment_iteration()

            # 步骤 1：推理
            self.emit_event_simple(
                "reasoning_started",
                {"iteration": state.iteration_count},
            )

            reasoning_result = self._do_reasoning(state)
            if not reasoning_result:
                state.loop_status = "failed"
                self.emit_event_simple(
                    "reasoning_failed",
                    {"iteration": state.iteration_count},
                )
                break

            # 步骤 2：行动
            self.emit_event_simple(
                "action_started",
                {"iteration": state.iteration_count},
            )

            action = reasoning_result
            action_result = self._do_action(action, state, workflow)
            if not action_result["success"]:
                self.emit_event_simple(
                    "action_failed",
                    {
                        "iteration": state.iteration_count,
                        "error": action_result.get("error"),
                    },
                )

            # 步骤 3：观察
            self.emit_event_simple(
                "observation_started",
                {"iteration": state.iteration_count},
            )

            self._do_observation(state, action, action_result)

            # 步骤 4：决策
            if self._should_finish_loop(action, state):
                state.loop_status = "completed"
                self.emit_event_simple(
                    "loop_completed",
                    {
                        "iterations": state.iteration_count,
                        "status": "completed",
                    },
                )
                break

            self.emit_event_simple(
                "iteration_completed",
                {"iteration": state.iteration_count},
            )

        # 保存最终状态
        self._final_state = state
        return state

    def _should_continue_loop(self, state: ReActLoopState) -> bool:
        """检查是否应该继续循环

        参数：
            state: 当前状态

        返回：
            是否继续
        """
        # 检查迭代次数
        if state.iteration_count >= self.max_iterations:
            return False

        # 检查步骤数
        if state.current_step >= state.max_steps:
            return False

        # 检查状态
        if state.loop_status != "running":
            return False

        return True

    def _do_reasoning(self, state: ReActLoopState) -> WorkflowAction | None:
        """执行推理阶段

        完整的推理流程：
        1. 生成执行上下文
        2. 获取系统提示
        3. 构建消息历史（之前的推理步骤）
        4. 调用 LLM 获取决策
        5. 解析 LLM 输出为 WorkflowAction

        参数：
            state: 当前状态

        返回：
            LLM 决定的动作，或 None 如果推理失败
        """
        try:
            # 第一步：生成执行上下文
            context = WorkflowExecutionContext(
                workflow_id=state.workflow_id,
                workflow_name=state.workflow_name,
                available_nodes=state.available_nodes,
                executed_nodes=state.executed_nodes,
                current_step=state.current_step,
            )

            # 第二步：获取系统提示（包含工作流信息和格式约束）
            system_prompt = self.system_prompt_generator.get_system_prompt(context)

            # 第三步：构建消息历史
            # 将之前保存的消息加入，形成完整的对话上下文
            messages = list(state.messages)  # 已有的消息历史
            # 如果还没有系统消息，添加系统提示
            if not any(msg.type == "system" for msg in messages):
                from langchain_core.messages import SystemMessage

                messages.insert(0, SystemMessage(content=system_prompt))

            # 第四步：调用 LLM 进行推理
            # LLM 会根据系统提示和消息历史，做出下一步决策
            try:
                llm_response = self.llm.invoke(
                    messages,
                    temperature=0.3,  # 较低温度确保确定性
                )
                # 确保 content 是字符串类型
                raw_content = str(llm_response.content)
            except Exception as e:
                self.emit_event_simple(
                    "reasoning_failed",
                    {
                        "iteration": state.iteration_count,
                        "error": f"LLM 调用失败：{str(e)}",
                    },
                )
                return None

            # 第五步：解析 LLM 输出
            # 使用 ActionParser 进行三级验证：JSON → Pydantic → 业务规则
            parse_result = self.action_parser.parse_and_validate(
                raw_content=raw_content,
                context=context,
                parse_attempt=1,
            )

            if not parse_result.is_valid:
                # 解析失败，记录错误
                self.emit_event_simple(
                    "reasoning_failed",
                    {
                        "iteration": state.iteration_count,
                        "error": parse_result.error_message,
                    },
                )
                return None

            # 解析成功，返回 WorkflowAction
            action = parse_result.action
            state.add_message(HumanMessage(content=raw_content))

            self.emit_event_simple(
                "reasoning_completed",
                {
                    "iteration": state.iteration_count,
                    "action_type": action.type if action else "none",
                    "message": raw_content,
                },
            )

            return action

        except Exception as e:
            self.emit_event_simple(
                "reasoning_failed",
                {
                    "iteration": state.iteration_count,
                    "error": f"推理阶段异常：{str(e)}",
                },
            )
            return None

    def _do_action(
        self, action: WorkflowAction, state: ReActLoopState, workflow: Workflow
    ) -> dict[str, Any]:
        """执行行动阶段

        参数：
            action: 要执行的动作
            state: 当前状态
            workflow: 工作流

        返回：
            执行结果
        """
        if action is None:
            return {"success": False, "error": "动作为空"}

        result = {"success": False, "error": None, "action_type": action.type}

        try:
            if action.type == ActionType.REASON:
                result["success"] = True
                result["message"] = "推理动作完成"

            elif action.type == ActionType.EXECUTE_NODE:
                if not action.node_id:
                    result["error"] = "节点 ID 未指定"
                    return result

                # 执行节点
                node = next((n for n in workflow.nodes if n.id == action.node_id), None)
                if not node:
                    result["error"] = f"节点 {action.node_id} 不存在"
                    return result

                result["success"] = True
                result["node_executed"] = action.node_id
                state.executed_nodes[action.node_id] = {
                    "status": "success",
                    "executed_at": datetime.now().isoformat(),
                }

            elif action.type == ActionType.WAIT:
                result["success"] = True
                result["message"] = "等待外部输入"

            elif action.type == ActionType.FINISH:
                result["success"] = True
                result["message"] = "工作流完成"

            elif action.type == ActionType.ERROR_RECOVERY:
                result["success"] = True
                result["message"] = f"尝试恢复节点 {action.node_id}"

            else:
                result["error"] = f"未知的动作类型：{action.type}"

        except Exception as e:
            result["error"] = str(e)

        state.add_action(action)
        return result

    def _do_observation(
        self,
        state: ReActLoopState,
        action: WorkflowAction,
        action_result: dict[str, Any],
    ) -> None:
        """执行观察阶段

        参数：
            state: 当前状态
            action: 执行的动作
            action_result: 动作执行结果
        """
        # 创建观察消息
        if action_result["success"]:
            observation_msg = HumanMessage(
                content=f"动作执行成功：{action.type}。结果：{action_result.get('message', 'OK')}"
            )
        else:
            observation_msg = HumanMessage(
                content=f"动作执行失败：{action.type}。错误：{action_result.get('error', '未知错误')}"
            )

        state.add_message(observation_msg)

        self.emit_event_simple(
            "observation_completed",
            {
                "iteration": state.iteration_count,
                "action_type": action.type,
                "success": action_result["success"],
            },
        )

    def _should_finish_loop(self, action: WorkflowAction, state: ReActLoopState) -> bool:
        """检查是否应该结束循环

        参数：
            action: 最后执行的动作
            state: 当前状态

        返回：
            是否结束循环
        """
        if action is None:
            return False

        if action.type == ActionType.FINISH:
            return True

        if state.iteration_count >= self.max_iterations:
            return True

        return False

    def get_final_state(self) -> ReActLoopState | None:
        """获取最终状态

        返回：
            最终的 ReAct 循环状态
        """
        return self._final_state

    # 以下是辅助方法，在 GREEN 阶段实现

    def call_llm_for_reasoning(self, state: ReActLoopState) -> str | None:
        """调用 LLM 进行推理

        参数：
            state: 当前状态

        返回：
            LLM 的响应
        """
        # 将在 Phase 3.4 实现真实 LLM 调用
        pass

    def get_execution_context(self) -> WorkflowExecutionContext | None:
        """获取执行上下文"""
        pass

    def execute_node(self, node_id: str) -> dict[str, Any]:
        """执行节点"""
        return {}

    def handle_reason_action(self, action: WorkflowAction) -> dict[str, Any]:
        """处理 REASON 动作"""
        return {}

    def handle_wait_action(self, action: WorkflowAction) -> dict[str, Any]:
        """处理 WAIT 动作"""
        return {}

    def handle_finish_action(self, action: WorkflowAction) -> dict[str, Any]:
        """处理 FINISH 动作"""
        return {}

    def observe_execution_result(self) -> dict[str, Any]:
        """观察执行结果"""
        return {}

    def create_observation_message(self) -> BaseMessage:
        """创建观察消息"""
        return HumanMessage(content="")

    def update_execution_state(self, result: dict[str, Any]) -> None:
        """更新执行状态"""
        pass

    def make_decision(self, state: ReActLoopState) -> bool:
        """做出决策"""
        return False

    def should_continue_loop(self) -> bool:
        """检查是否继续循环"""
        return False

    def check_stop_conditions(self) -> bool:
        """检查停止条件"""
        return False

    def is_finish_action(self, action: WorkflowAction) -> bool:
        """检查是否是 FINISH 动作"""
        return action and action.type == ActionType.FINISH

    def check_step_limit(self, state: ReActLoopState) -> bool:
        """检查步骤限制"""
        return state.current_step < state.max_steps

    def handle_llm_failure(self, error: Exception) -> None:
        """处理 LLM 失败"""
        pass

    def handle_node_failure(self, node_id: str, error: Exception) -> None:
        """处理节点执行失败"""
        pass

    def handle_validation_failure(self, error: str) -> None:
        """处理验证失败"""
        pass

    def emit_action_executed_event(self, action: WorkflowAction) -> None:
        """发出动作执行事件"""
        self.emit_event_simple("action_executed", {"action_type": action.type})

    def emit_observation_event(self, observation: str) -> None:
        """发出观察事件"""
        self.emit_event_simple("observation", {"message": observation})

    def emit_loop_completed_event(self, state: ReActLoopState) -> None:
        """发出循环完成事件"""
        self.emit_event_simple(
            "loop_completed",
            {
                "iterations": state.iteration_count,
                "status": state.loop_status,
            },
        )

    def node_executor(self) -> Any | None:
        """获取节点执行器"""
        pass

    def workflow_executor(self) -> Any | None:
        """获取工作流执行器"""
        pass
