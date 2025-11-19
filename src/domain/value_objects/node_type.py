"""NodeType 枚举 - 节点类型

业务定义：
- NodeType 定义工作流中支持的节点类型
- 每种类型对应不同的执行逻辑

设计原则：
- 使用枚举确保类型安全
- 继承 str 方便序列化
"""

from enum import Enum


class NodeType(str, Enum):
    """节点类型枚举

    为什么继承 str？
    1. 序列化友好：可以直接转换为 JSON
    2. 数据库友好：可以直接存储为字符串
    3. 兼容性好：可以和字符串比较

    支持的节点类型：
    - START: 开始节点（工作流入口）
    - END: 结束节点（工作流出口）
    - HTTP: HTTP 请求节点（GET/POST/PUT/DELETE）
    - TRANSFORM: 数据转换节点（格式化、映射等）
    - DATABASE: 数据库操作节点（查询、插入等）
    - CONDITIONAL: 条件判断节点（if/else，支持分支）
    - LOOP: 循环节点（for/while）
    - PYTHON: Python 代码执行节点
    - LLM: LLM 调用节点（OpenAI、Claude 等）
    - PROMPT: 提示词节点（构造 LLM 输入）
    - IMAGE: 图像生成节点
    - AUDIO: 音频生成节点
    """

    # React Flow 默认节点类型（兼容）
    INPUT = "input"  # React Flow 默认输入节点
    DEFAULT = "default"  # React Flow 默认节点
    OUTPUT = "output"  # React Flow 默认输出节点

    # 基础节点类型
    START = "start"
    END = "end"

    # HTTP 请求节点
    HTTP = "http"
    HTTP_REQUEST = "httpRequest"  # V0 前端使用的名称

    # 数据转换节点
    TRANSFORM = "transform"

    # 数据库节点
    DATABASE = "database"

    # 条件分支节点
    CONDITIONAL = "conditional"
    CONDITION = "condition"  # 保留向后兼容

    # 循环节点
    LOOP = "loop"

    # Python 代码节点
    PYTHON = "python"
    JAVASCRIPT = "javascript"  # V0 前端使用的名称

    # LLM 节点
    LLM = "llm"
    TEXT_MODEL = "textModel"  # V0 前端使用的名称
    PROMPT = "prompt"

    # 图像生成节点
    IMAGE = "imageGeneration"  # V0 前端使用的名称

    # 音频节点
    AUDIO = "audio"

    # 其他节点
    EMBEDDING = "embeddingModel"  # V0 前端使用的名称
    TOOL = "tool"
    STRUCTURED_OUTPUT = "structuredOutput"  # V0 前端使用的名称
