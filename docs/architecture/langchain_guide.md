# LangChain 集成指南

> 说明 `src/lc/` 层的结构、配置、扩展点，以及与 Domain/Infrastructure 的协作方式。

## 1. 目录结构
```
src/lc/
├── llm_client.py          # OpenAI 兼容客户端工厂
├── chains/
│   └── plan_generator.py  # start+goal → task list
├── agents/
│   └── task_executor.py   # ReAct 风格任务执行 agent
├── tools/                 # http、file、python、database 等
├── prompts/               # Prompt 模板（计划/分类）
└── __init__.py            # 对外导出
```

## 2. 配置
- 所有 LLM 调用读取 `src/config.py`：`openai_api_key/openai_base_url/openai_model/request_timeout`。
- 本地 `.env` 设置 `OPENAI_API_KEY`；生产由 Secrets Manager 注入。
- 提供三类工厂：
  - `get_llm`（通用）
  - `get_llm_for_planning`（低温度、max_tokens=2000）
  - `get_llm_for_execution`（中温度、绑定工具）

## 3. Chains
### Plan Generator
```python
prompt = get_plan_generation_prompt()
llm = get_llm_for_planning()
parser = JsonOutputParser()
chain = prompt | llm | parser
```
- 输入：`{"start": str, "goal": str}`
- 输出：任务字典数组
- 异常：抛出，由 UseCase 捕获并转化为友好提示

## 4. Agents & Tools
- `task_executor.py` 构建简化 Agent：`ChatPromptTemplate` + `llm.bind_tools(tools)`。
- 默认工具：
  - `http_request`
  - `read_file`
  - `execute_python`
  - `query_database`
- 新增工具：实现 `langchain.tools.BaseTool`，在 `src/lc/tools/__init__.py` 注册；需要对应的 workflow 节点时同步更新 `NodeExecutorRegistry`。

## 5. 与 Domain 的边界
- 领域服务（如 `WorkflowChatService`）应依赖接口而非直接 import LangChain。TODO：抽象 `WorkflowChatLLM`，由基础设施注入实现。
- Application 层通过 `src/lc/__init__.py` 提供的函数获取 chain/agent，不允许在 UseCase 内直接实例化 LLM 客户端。

## 6. 错误与日志
- 捕获 LangChain 异常并抛出 `DomainError` 或返回 `错误：...` 字符串（task executor）。
- LLM 调用日志写入执行日志前需脱敏；日志字段统一为 `trace_id/chain/tool/latency_ms/token_usage`。

## 7. 成本控制
- 工厂默认设置 `timeout/max_retries`，避免无限重试。
- 对话或执行操作需记录 token 使用量，用于费用面板。

## 8. 常见扩展
1. **新增模型提供商**：通过 `openai_base_url` 指向 Moonshot/Azure 等，或扩展 `get_llm`。
2. **自定义 Agent**：在 `src/lc/agents/` 新建模块并在 `__init__` 导出，返回 `Runnable`。
3. **结构化输出**：`LlmExecutor` 支持 `node.config.schema`，通过 `response_format` 输出 JSON。

## 9. TODO
- [ ] 抽象 WorkflowChat LLM port，隔离 LangChain 依赖。
- [ ] 统一工具权限，防止 Agent 调用未授权资源。
- [ ] 评估引入 LangGraph 以支持多步计划与回溯。
