"""LLM 客户端封装 - 统一管理 LLM 配置和初始化

职责：
1. 创建和配置 LLM 客户端（OpenAI 兼容）
2. 提供工厂函数，便于测试和切换
3. 统一管理 LLM 参数（temperature、max_tokens 等）

为什么需要这个模块？
- 封装 LLM 初始化逻辑，避免在业务代码中重复配置
- 便于测试：可以轻松 Mock LLM
- 便于切换：未来可以轻松切换到其他 LLM（如 Claude、本地模型）
- 单一职责：只负责创建和配置 LLM 客户端

设计原则：
- 依赖注入：通过工厂函数创建 LLM，而不是全局单例
- 配置分离：LLM 配置从 Settings 读取，不硬编码
- 类型安全：使用类型注解，便于 IDE 提示和类型检查

支持的 LLM Provider：
- OpenAI（官方）
- KIMI（Moonshot AI，兼容 OpenAI 协议）
- 其他兼容 OpenAI 协议的 Provider（如 Azure OpenAI、本地模型等）
"""

from langchain_openai import ChatOpenAI

from src.config import settings


def get_llm(
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> ChatOpenAI:
    """创建 LLM 客户端（OpenAI 兼容）

    为什么使用工厂函数？
    - 延迟初始化：只在需要时创建 LLM
    - 配置灵活：可以传入不同的配置
    - 便于测试：可以传入 Mock 配置
    - 便于管理：可以在应用启动时创建，关闭时销毁

    参数说明：
    - model: 模型名称（默认从配置读取）
      - OpenAI: gpt-4o-mini, gpt-4o, gpt-4-turbo 等
      - KIMI: moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k 等
    - temperature: 温度参数（0-2，越高越随机）
      - 0.0: 确定性输出，适合代码生成、数据提取
      - 0.7: 平衡创造性和确定性，适合对话、计划生成
      - 1.0+: 高创造性，适合创意写作
    - max_tokens: 最大输出 token 数（None 表示使用模型默认值）
    - timeout: 请求超时时间（秒，None 表示使用配置默认值）

    返回：
        ChatOpenAI: LLM 客户端实例

    异常：
        ValueError: 当 API Key 未配置时

    示例：
    >>> # 使用默认配置
    >>> llm = get_llm()
    >>>
    >>> # 自定义配置
    >>> llm = get_llm(
    ...     model="moonshot-v1-8k",
    ...     temperature=0.0,
    ...     max_tokens=1000,
    ... )
    >>>
    >>> # 调用 LLM
    >>> response = llm.invoke("你好，请介绍一下自己")
    >>> print(response.content)
    """
    # 验证 API Key
    # 为什么在这里验证？
    # - 提前发现配置错误，避免运行时错误
    # - 提供清晰的错误信息
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY 未配置，请在 .env 文件中设置 OPENAI_API_KEY\n"
            "示例：\n"
            "  OpenAI: OPENAI_API_KEY=sk-...\n"
            "  KIMI: OPENAI_API_KEY=sk-...\n"
        )

    # 使用配置中的模型（如果未指定）
    model_name = model or settings.openai_model

    # 使用配置中的超时时间（如果未指定）
    request_timeout = timeout or settings.request_timeout

    # 创建 LLM 客户端
    # 为什么使用 ChatOpenAI？
    # - LangChain 官方推荐的 OpenAI 客户端
    # - 支持 OpenAI 兼容协议（可以通过 base_url 切换到其他 Provider）
    # - 支持流式输出、函数调用等高级功能
    return ChatOpenAI(  # type: ignore[call-arg]
        model=model_name,
        openai_api_key=settings.openai_api_key,  # type: ignore[arg-type]
        openai_api_base=settings.openai_base_url,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,  # type: ignore[arg-type]
        timeout=request_timeout,
        # 其他可选参数：
        # - streaming: 是否启用流式输出（默认 False）
        # - max_retries: 最大重试次数（默认 2）
        # - request_timeout: 请求超时时间（秒）
    )


def get_llm_for_planning(
    model: str | None = None,
) -> ChatOpenAI:
    """创建用于计划生成的 LLM 客户端

    为什么单独创建？
    - 计划生成需要更确定性的输出（temperature 较低）
    - 计划生成可能需要更多 token（max_tokens 较大）
    - 便于统一管理计划生成的 LLM 配置

    参数：
        model: 模型名称（默认从配置读取）

    返回：
        ChatOpenAI: LLM 客户端实例

    示例：
    >>> llm = get_llm_for_planning()
    >>> response = llm.invoke("起点：CSV 文件，目标：分析销售数据")
    """
    return get_llm(
        model=model,
        temperature=0.3,  # 较低的温度，确保计划的确定性
        max_tokens=2000,  # 计划可能较长，需要更多 token
    )


def get_llm_for_execution(
    model: str | None = None,
) -> ChatOpenAI:
    """创建用于任务执行的 LLM 客户端

    为什么单独创建？
    - 任务执行需要平衡创造性和确定性（temperature 中等）
    - 任务执行可能需要调用工具，需要支持函数调用
    - 便于统一管理任务执行的 LLM 配置

    参数：
        model: 模型名称（默认从配置读取）

    返回：
        ChatOpenAI: LLM 客户端实例

    示例：
    >>> llm = get_llm_for_execution()
    >>> # 配合 Agent 使用
    >>> from langchain.agents import create_openai_functions_agent
    >>> agent = create_openai_functions_agent(llm, tools, prompt)
    """
    return get_llm(
        model=model,
        temperature=0.7,  # 中等温度，平衡创造性和确定性
        max_tokens=1000,  # 任务执行输出通常较短
    )


# 为什么不使用全局单例？
# - 全局单例难以测试（无法 Mock）
# - 全局单例难以切换配置（如不同的 temperature）
# - 工厂函数更灵活，符合依赖注入原则
#
# 如果担心性能问题（每次创建新实例）：
# - ChatOpenAI 内部有连接池，创建实例的开销很小
# - 如果确实需要缓存，可以在上层（如 Use Case）中缓存
# - 或者使用 functools.lru_cache 装饰器
