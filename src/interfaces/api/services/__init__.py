"""接口层服务（package init）

避免在包导入时加载重依赖模块；具体服务请显式从子模块导入，例如：
- `from src.interfaces.api.services.sse_emitter_handler import SSEEmitterHandler`
"""

__all__: list[str] = []
