"""Tool DTO - 工具数据传输对象

定义 Tool 相关的 API 请求和响应格式

设计原则：
1. DTO 只负责数据传输，不包含业务逻辑
2. 使用 Pydantic 进行数据验证
3. 严格的类型提示
4. 与领域模型分离（解耦）

为什么需要 DTO？
- 领域模型和 API 模型分离
- API 版本控制更容易
- 可以隐藏内部实现细节
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolParameterDTO(BaseModel):
    """工具参数 DTO

    描述工具的输入参数要求
    """

    name: str = Field(..., description="参数名称")
    type: str = Field(..., description="参数类型（string, number, boolean, object, array）")
    description: str = Field(..., description="参数描述")
    required: bool = Field(default=False, description="是否必需")
    default: Any | None = Field(default=None, description="默认值")
    enum: list[str] | None = Field(default=None, description="枚举值列表")

    class Config:
        from_attributes = True


class CreateToolRequest(BaseModel):
    """创建工具请求

    用户提供的创建工具所需的数据
    """

    name: str = Field(..., description="工具名称", min_length=1, max_length=255)
    description: str = Field(..., description="工具描述")
    category: str = Field(..., description="工具分类（http, database, file, ai, notification, custom）")
    author: str = Field(..., description="工具创建者", min_length=1)
    parameters: list[ToolParameterDTO] | None = Field(
        default=None, description="工具参数列表"
    )
    returns: dict[str, Any] | None = Field(default=None, description="返回值 schema")
    implementation_type: str | None = Field(
        default="builtin", description="实现类型（builtin, http, javascript, python）"
    )
    implementation_config: dict[str, Any] | None = Field(
        default=None, description="实现配置"
    )
    tags: list[str] | None = Field(default=None, description="工具标签列表")
    icon: str | None = Field(default=None, description="工具图标 URL")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "HTTP请求工具",
                "description": "发送HTTP请求到指定URL",
                "category": "http",
                "author": "admin",
                "parameters": [
                    {
                        "name": "url",
                        "type": "string",
                        "description": "请求URL",
                        "required": True,
                    },
                    {
                        "name": "method",
                        "type": "string",
                        "description": "HTTP方法",
                        "required": False,
                        "default": "GET",
                        "enum": ["GET", "POST", "PUT", "DELETE"],
                    },
                ],
                "implementation_type": "http",
                "tags": ["http", "network"],
            }
        }


class UpdateToolRequest(BaseModel):
    """更新工具请求

    允许更新工具的部分字段
    """

    name: str | None = Field(default=None, description="工具名称")
    description: str | None = Field(default=None, description="工具描述")
    parameters: list[ToolParameterDTO] | None = Field(default=None, description="工具参数列表")
    returns: dict[str, Any] | None = Field(default=None, description="返回值 schema")
    implementation_type: str | None = Field(default=None, description="实现类型")
    implementation_config: dict[str, Any] | None = Field(default=None, description="实现配置")
    tags: list[str] | None = Field(default=None, description="工具标签列表")
    icon: str | None = Field(default=None, description="工具图标 URL")

    class Config:
        json_schema_extra = {
            "example": {
                "description": "更新后的工具描述",
                "tags": ["http", "network", "api"],
            }
        }


class ToolResponse(BaseModel):
    """工具响应

    返回给客户端的工具信息
    """

    id: str = Field(..., description="工具ID")
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    category: str = Field(..., description="工具分类")
    status: str = Field(..., description="工具状态（draft, testing, published, deprecated）")
    version: str = Field(..., description="版本号")
    parameters: list[ToolParameterDTO] = Field(default=[], description="工具参数列表")
    returns: dict[str, Any] = Field(default={}, description="返回值 schema")
    implementation_type: str = Field(..., description="实现类型")
    implementation_config: dict[str, Any] = Field(default={}, description="实现配置")
    author: str = Field(..., description="工具创建者")
    tags: list[str] = Field(default=[], description="工具标签列表")
    icon: str | None = Field(default=None, description="工具图标 URL")
    usage_count: int = Field(..., description="使用次数")
    last_used_at: datetime | None = Field(default=None, description="最后使用时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")
    published_at: datetime | None = Field(default=None, description="发布时间")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "tool_a1b2c3d4",
                "name": "HTTP请求工具",
                "description": "发送HTTP请求到指定URL",
                "category": "http",
                "status": "published",
                "version": "1.0.0",
                "parameters": [
                    {
                        "name": "url",
                        "type": "string",
                        "description": "请求URL",
                        "required": True,
                    }
                ],
                "returns": {"type": "object"},
                "implementation_type": "http",
                "implementation_config": {},
                "author": "admin",
                "tags": ["http", "network"],
                "icon": None,
                "usage_count": 42,
                "last_used_at": "2025-11-22T10:30:00Z",
                "created_at": "2025-11-20T08:00:00Z",
                "updated_at": "2025-11-21T15:00:00Z",
                "published_at": "2025-11-21T15:00:00Z",
            }
        }


class ToolListResponse(BaseModel):
    """工具列表响应"""

    tools: list[ToolResponse] = Field(..., description="工具列表")
    total: int = Field(..., description="总数量")

    class Config:
        json_schema_extra = {
            "example": {
                "tools": [
                    {
                        "id": "tool_a1b2c3d4",
                        "name": "HTTP请求工具",
                        "status": "published",
                        "category": "http",
                    }
                ],
                "total": 1,
            }
        }


class PublishToolRequest(BaseModel):
    """发布工具请求"""

    pass  # 无需额外参数


class DeprecateToolRequest(BaseModel):
    """废弃工具请求"""

    reason: str = Field(..., description="废弃原因", min_length=1)

    class Config:
        json_schema_extra = {"example": {"reason": "已有更好的替代工具"}}
