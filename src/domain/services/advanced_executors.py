"""高级执行器（Advanced Executors）

条件/循环/并行执行器，支持复杂控��流。

组件：
- ConditionExecutor: 条件执行器
- LoopExecutor: 循环执行器
- ParallelExecutor: 并行执行器
- ExecutorFactory: 执行器工厂

功能：
- 条件分支：简单条件、复杂表达式、多分支
- 循环控制：for_each、range、while、break
- 并行执行：全部完成、超时控制、错误处理、首个完成

设计原则：
- 安全执行：表达式在受限环境中执行
- 错误隔离：单个分支失败不影响其他
- 灵活配置：支持多种执行模式

"""

import asyncio
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# 安全的内置函数白名单
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
}


class NodeExecutorProtocol(Protocol):
    """节点执行器协议"""

    async def execute(self, node_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """执行节点"""
        ...


def safe_eval(expression: str, variables: dict[str, Any]) -> Any:
    """安全执行表达式

    参数：
        expression: 要执行的表达式
        variables: 变量字典

    返回：
        表达式结果
    """
    # 构建安全的执行环境
    safe_globals = {"__builtins__": SAFE_BUILTINS}
    safe_locals = variables.copy()

    try:
        return eval(expression, safe_globals, safe_locals)
    except Exception as e:
        logger.error(f"表达式执行失败: {expression}, 错误: {e}")
        raise ValueError(f"表达式执行失败: {e}") from e


class ConditionExecutor:
    """条件执行器

    支持简单条件、复杂表达式和多分支条件。

    使用示���：
        executor = ConditionExecutor()
        result = await executor.execute(config, inputs)
    """

    async def execute(self, config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        """执行条件判断

        参数：
            config: 条件配置
            inputs: 输入数据

        返回：
            包含分支信息和下一节点的结果
        """
        condition_type = config.get("type", "simple")

        if condition_type == "multi_branch":
            return await self._execute_multi_branch(config, inputs)
        else:
            return await self._execute_simple(config, inputs)

    async def _execute_simple(
        self, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行简单条件

        参数：
            config: 条件配置（expression, true_branch, false_branch）
            inputs: 输入数据

        返回：
            分支结果
        """
        expression = config.get("expression", "")
        true_branch = config.get("true_branch", "")
        false_branch = config.get("false_branch", "")

        try:
            result = safe_eval(expression, inputs)
            is_true = bool(result)
        except Exception as e:
            logger.error(f"条件表达式执行失败: {e}")
            is_true = False

        if is_true:
            return {"branch": "true", "next_node": true_branch, "condition_result": True}
        else:
            return {"branch": "false", "next_node": false_branch, "condition_result": False}

    async def _execute_multi_branch(
        self, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行多分支条件

        参数：
            config: 多分支配置
            inputs: 输入数据

        返回：
            匹配的分支结果
        """
        branches = config.get("branches", [])
        default_branch = config.get("default_branch", "")

        for i, branch in enumerate(branches):
            condition = branch.get("condition", "")
            node = branch.get("node", "")

            try:
                result = safe_eval(condition, inputs)
                if bool(result):
                    return {
                        "branch": f"branch_{i}",
                        "next_node": node,
                        "condition_result": True,
                        "matched_condition": condition,
                    }
            except Exception as e:
                logger.warning(f"分支条件执行失败: {condition}, 错误: {e}")
                continue

        # 没有匹配的分支，使用默认
        return {
            "branch": "default",
            "next_node": default_branch,
            "condition_result": False,
            "matched_condition": None,
        }


class LoopExecutor:
    """循环执行器

    支持for_each、range、while循环，以及break中断。

    使用示例：
        executor = LoopExecutor(node_executor=my_executor)
        result = await executor.execute(config, inputs)
    """

    def __init__(self, node_executor: NodeExecutorProtocol):
        """初始化

        参数：
            node_executor: 节点执行器
        """
        self.node_executor = node_executor

    async def execute(self, config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        """执行循环

        参数：
            config: 循环配置
            inputs: 输入数据

        返回：
            循环执行结果
        """
        loop_type = config.get("type", "for_each")

        if loop_type == "for_each":
            return await self._execute_for_each(config, inputs)
        elif loop_type == "range":
            return await self._execute_range(config, inputs)
        elif loop_type == "while":
            return await self._execute_while(config, inputs)
        else:
            raise ValueError(f"不支持的循环类型: {loop_type}")

    async def _execute_for_each(
        self, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行for_each循环

        参数：
            config: 循环配置
            inputs: 输入数据

        返回：
            所有迭代结果
        """
        array_input = config.get("array_input", "items")
        item_variable = config.get("item_variable", "item")
        body_node = config.get("body_node", "")
        break_on = config.get("break_on", None)

        items = inputs.get(array_input, [])
        iterations = []
        exit_reason = "completed"

        for i, item in enumerate(items):
            # 构建迭代输入
            iter_inputs = inputs.copy()
            iter_inputs[item_variable] = item
            iter_inputs["_index"] = i

            # 执行循环体
            result = await self.node_executor.execute(body_node, iter_inputs)
            iterations.append(result)

            # 检查break条件
            if break_on and result.get(break_on):
                exit_reason = "break"
                break

        return {
            "iterations": iterations,
            "iteration_count": len(iterations),
            "exit_reason": exit_reason,
        }

    async def _execute_range(
        self, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行range循环

        参数：
            config: 循环配置
            inputs: 输入数据

        返回：
            所有迭代结果
        """
        start = config.get("start", 0)
        end = config.get("end", 10)
        step = config.get("step", 1)
        index_variable = config.get("index_variable", "i")
        body_node = config.get("body_node", "")

        iterations = []

        for i in range(start, end, step):
            iter_inputs = inputs.copy()
            iter_inputs[index_variable] = i

            result = await self.node_executor.execute(body_node, iter_inputs)
            iterations.append(result)

        return {
            "iterations": iterations,
            "iteration_count": len(iterations),
            "exit_reason": "completed",
        }

    async def _execute_while(
        self, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行while循环

        参数：
            config: 循环配置
            inputs: 输入数据

        返回：
            循环执行结果
        """
        condition = config.get("condition", "True")
        max_iterations = config.get("max_iterations", 100)
        body_node = config.get("body_node", "")
        retry_config = config.get("retry_config", {})

        iterations = []
        current_inputs = inputs.copy()
        exit_reason = "completed"
        iteration_count = 0

        # 重试配置
        base_delay = retry_config.get("base_delay", 0) if retry_config.get("enabled") else 0
        exponential = retry_config.get("exponential", False)

        while iteration_count < max_iterations:
            # 检查条件
            try:
                should_continue = safe_eval(condition, current_inputs)
                if not should_continue:
                    exit_reason = "condition_false"
                    break
            except Exception as e:
                logger.error(f"循环条件执行失败: {e}")
                exit_reason = "condition_error"
                break

            # 执行循环体
            result = await self.node_executor.execute(body_node, current_inputs)
            iterations.append(result)
            iteration_count += 1

            # 更新输入（使用结果更新状态）
            current_inputs.update(result)

            # 检查重试条件
            if retry_config.get("enabled") and result.get("_retry"):
                delay = base_delay
                if exponential:
                    delay = base_delay * (2 ** (iteration_count - 1))
                    max_delay = retry_config.get("max_delay", 10)
                    delay = min(delay, max_delay)
                await asyncio.sleep(delay)

        if iteration_count >= max_iterations:
            exit_reason = "max_iterations"

        return {
            "iterations": iterations,
            "iteration_count": iteration_count,
            "exit_reason": exit_reason,
            "final_result": iterations[-1] if iterations else {},
        }


class ParallelExecutor:
    """并行执行器

    支持并行执行多个分支，支持超时、错误处理和首个完成模式。

    使用示例：
        executor = ParallelExecutor(node_executor=my_executor)
        result = await executor.execute(config, inputs)
    """

    def __init__(self, node_executor: NodeExecutorProtocol):
        """初始化

        参数：
            node_executor: 节点执行器
        """
        self.node_executor = node_executor

    async def execute(self, config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        """执行并行分支

        参数：
            config: 并行配置
            inputs: 输入数据

        返回：
            所有分支的结果
        """
        branches = config.get("branches", [])
        timeout = config.get("timeout", None)
        fail_fast = config.get("fail_fast", True)
        wait_for = config.get("wait_for", "all")

        if wait_for == "first":
            return await self._execute_wait_for_first(branches, inputs, timeout)
        else:
            return await self._execute_all(branches, inputs, timeout, fail_fast)

    async def _execute_all(
        self,
        branches: list[dict[str, Any]],
        inputs: dict[str, Any],
        timeout: float | None,
        fail_fast: bool,
    ) -> dict[str, Any]:
        """执行所有分支

        参数：
            branches: 分支列表
            inputs: 输入数据
            timeout: 超时时间
            fail_fast: 是否快速失败

        返回：
            所有分支结果
        """
        results = {}

        async def execute_branch(branch: dict[str, Any]) -> tuple:
            node = branch.get("node", "")
            output_key = branch.get("output_key", node)

            try:
                if timeout:
                    result = await asyncio.wait_for(
                        self.node_executor.execute(node, inputs), timeout=timeout
                    )
                else:
                    result = await self.node_executor.execute(node, inputs)
                return output_key, result
            except TimeoutError:
                return output_key, {"error": "timeout"}
            except Exception as e:
                return output_key, {"error": str(e)}

        # 创建所有任务
        tasks = [execute_branch(branch) for branch in branches]

        # 并行执行
        completed = await asyncio.gather(*tasks, return_exceptions=not fail_fast)

        # 收集结果
        for item in completed:
            if isinstance(item, Exception):
                continue
            if isinstance(item, tuple):
                key, result = item
                results[key] = result

        return results

    async def _execute_wait_for_first(
        self, branches: list[dict[str, Any]], inputs: dict[str, Any], timeout: float | None
    ) -> dict[str, Any]:
        """等待第一个完成

        参数：
            branches: 分支列表
            inputs: 输入数据
            timeout: 超时时间

        返回：
            第一个完成的结果
        """

        async def execute_branch(branch: dict[str, Any]) -> dict[str, Any]:
            node = branch.get("node", "")
            result = await self.node_executor.execute(node, inputs)
            return result

        # 创建所有任务
        tasks = [asyncio.create_task(execute_branch(branch)) for branch in branches]

        try:
            # 等待第一个完成
            done, pending = await asyncio.wait(
                tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )

            # 取消其他任务
            for task in pending:
                task.cancel()

            # 获取第一个完成的结果
            if done:
                winner_task = done.pop()
                winner_result = winner_task.result()
                return {"winner": winner_result}
            else:
                return {"error": "no_result"}

        except TimeoutError:
            # 取消所有任务
            for task in tasks:
                task.cancel()
            return {"error": "timeout"}


class ExecutorFactory:
    """执行器工厂

    创建各种类型的执行器实例。
    """

    @staticmethod
    def create(executor_type: str, node_executor: NodeExecutorProtocol | None = None, **kwargs):
        """创建执行器

        参数：
            executor_type: 执行器类型（condition, loop, parallel）
            node_executor: 节点执行器（循环和并行需要）
            **kwargs: 其他参数

        返回：
            执行器实例

        异常：
            ValueError: 未知的执行器类型
        """
        if executor_type == "condition":
            return ConditionExecutor()
        elif executor_type == "loop":
            if not node_executor:
                raise ValueError("循环执行器需要node_executor")
            return LoopExecutor(node_executor=node_executor)
        elif executor_type == "parallel":
            if not node_executor:
                raise ValueError("并行执行器需要node_executor")
            return ParallelExecutor(node_executor=node_executor)
        else:
            raise ValueError(f"未知的执行器类型: {executor_type}")


# 导出
__all__ = [
    "ConditionExecutor",
    "LoopExecutor",
    "ParallelExecutor",
    "ExecutorFactory",
    "NodeExecutorProtocol",
    "safe_eval",
    "SAFE_BUILTINS",
]
