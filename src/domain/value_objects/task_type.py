"""TaskType 枚举 - 任务类型分类

V2新功能：智能任务分类系统

业务定义：
- TaskType 定义任务的类型分类
- 用于区分不同的任务处理方式
- 支持 AI 模型智能分类

设计原则：
- 使用枚举确保分类的一致性
- 继承 str 方便序列化和数据库存储
- 设计原则遵循 OODA 决策循环

任务类型说明：
- DATA_ANALYSIS: 数据分析任务（需要处理结构化数据）
- CONTENT_CREATION: 内容创建任务（生成、编写、翻译等）
- RESEARCH: 研究任务（搜索、分析、总结信息）
- PROBLEM_SOLVING: 问题解决任务（代码调试、排障等）
- AUTOMATION: 自动化任务（重复操作、工作流执行）
- UNKNOWN: 未分类（初始状态或无法分类）
"""

from enum import Enum


class TaskType(str, Enum):
    """任务类型枚举

    为什么继承 str？
    1. 序列化友好：可以直接转换为 JSON
    2. 数据库友好：可以直接存储为字符串
    3. 兼容性好：可以和字符串比较

    分类系统设计：
    基于 OODA 循环（Observe-Orient-Decide-Act）的任务分类
    """

    # 数据分析任务
    # 特点：处理结构化数据，需要进行统计、聚合、计算
    # 例子："分析去年的销售数据，找出增长趋势"
    DATA_ANALYSIS = "data_analysis"

    # 内容创建任务
    # 特点：生成新的文本内容（写作、翻译、总结等）
    # 例子："写一篇关于人工智能的博客文章"
    CONTENT_CREATION = "content_creation"

    # 研究任务
    # 特点：搜索信息、分析资料、总结知识
    # 例子："研究最新的深度学习框架"
    RESEARCH = "research"

    # 问题解决任务
    # 特点：排查问题、调试代码、修复错误
    # 例子："为什么我的API返回500错误？"
    PROBLEM_SOLVING = "problem_solving"

    # 自动化任务
    # 特点：重复执行相同的操作流程
    # 例子："每天自动备份数据库"
    AUTOMATION = "automation"

    # 未分类
    # 特点：初始状态或无法准确分类
    # 说明：需要用户手动确认或由 AI 进一步分析
    UNKNOWN = "unknown"
