"""Knowledge Base DTO（Data Transfer Objects）

定义知识库相关的请求和响应模型
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadDocumentRequest(BaseModel):
    """文档上传请求 DTO

    业务场景：用户上传文档到个人知识库或工作流知识库

    字段：
    - title: 文档标题
    - content: 文档内容
    - workflow_id: 工作流 ID（可选，为空则为个人知识库）
    - source: 文档来源（upload|import|crawl）
    - metadata: 元数据（可选）
    - file_path: 文件路径（可选）

    验证规则：
    - title 不能为空
    - content 不能为空
    """

    title: str = Field(..., min_length=1, description="文档标题")
    content: str = Field(..., min_length=1, description="文档内容")
    workflow_id: str | None = Field(default=None, description="工作流 ID（可选）")
    source: str = Field(default="upload", description="文档来源")
    metadata: dict | None = Field(default=None, description="元数据（可选）")
    file_path: str | None = Field(default=None, description="文件路径（可选）")

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """文档响应 DTO

    业务场景：API 返回文档信息给前端

    字段：
    - id: 文档 ID
    - title: 文档标题
    - workflow_id: 工作流 ID（可选）
    - source: 文档来源
    - status: 文档状态
    - chunk_count: 分块数量
    - total_tokens: 总 token 数（估算）
    - created_at: 创建时间
    - updated_at: 更新时间
    """

    id: str
    title: str
    workflow_id: str | None = None
    source: str
    status: str
    chunk_count: int = 0
    total_tokens: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadDocumentResponse(BaseModel):
    """文档上传响应 DTO

    业务场景：返回上传后的文档基本信息

    字段：
    - document_id: 文档 ID
    - title: 文档标题
    - chunk_count: 分块数量
    - total_tokens: 总 token 数（估算）
    - message: 提示消息
    """

    document_id: str = Field(..., description="文档 ID")
    title: str = Field(..., description="文档标题")
    chunk_count: int = Field(..., ge=0, description="分块数量")
    total_tokens: int = Field(..., ge=0, description="总 token 数")
    message: str = Field(default="文档上传成功", description="提示消息")

    model_config = ConfigDict(from_attributes=True)


class ListDocumentsRequest(BaseModel):
    """文档列表查询请求 DTO

    业务场景：用户查询文档列表（支持过滤）

    字段：
    - workflow_id: 工作流 ID（可选，过滤特定工作流的文档）
    - user_id: 用户 ID（可选，过滤特定用户的文档）
    - source: 文档来源（可选，过滤特定来源）
    - limit: 数量限制（默认 50）
    - offset: 偏移量（默认 0）
    """

    workflow_id: str | None = Field(default=None, description="工作流 ID")
    user_id: str | None = Field(default=None, description="用户 ID")
    source: str | None = Field(default=None, description="文档来源")
    limit: int = Field(default=50, ge=1, le=100, description="数量限制")
    offset: int = Field(default=0, ge=0, description="偏移量")

    model_config = ConfigDict(from_attributes=True)


class ListDocumentsResponse(BaseModel):
    """文档列表响应 DTO

    业务场景：返回文档列表和分页信息

    字段：
    - documents: 文档列表
    - total: 总数量
    - limit: 数量限制
    - offset: 偏移量
    """

    documents: list[DocumentResponse] = Field(..., description="文档列表")
    total: int = Field(..., ge=0, description="总数量")
    limit: int = Field(..., ge=1, description="数量限制")
    offset: int = Field(..., ge=0, description="偏移量")

    model_config = ConfigDict(from_attributes=True)


class DeleteDocumentResponse(BaseModel):
    """文档删除响应 DTO

    业务场景：返回删除操作结果

    字段：
    - document_id: 文档 ID
    - status: 删除状态
    - message: 提示消息
    """

    document_id: str = Field(..., description="文档 ID")
    status: str = Field(default="deleted", description="删除状态")
    message: str = Field(default="文档删除成功", description="提示消息")

    model_config = ConfigDict(from_attributes=True)


class KnowledgeStatsResponse(BaseModel):
    """知识库统计响应 DTO

    业务场景：返回知识库统计信息

    字段：
    - total_documents: 总文档数
    - total_chunks: 总分块数
    - total_tokens: 总 token 数（估算）
    - by_workflow: 按工作流分组的统计
    - by_source: 按来源分组的统计
    """

    total_documents: int = Field(..., ge=0, description="总文档数")
    total_chunks: int = Field(..., ge=0, description="总分块数")
    total_tokens: int = Field(..., ge=0, description="总 token 数")
    by_workflow: dict[str, int] = Field(default_factory=dict, description="按工作流统计")
    by_source: dict[str, int] = Field(default_factory=dict, description="按来源统计")

    model_config = ConfigDict(from_attributes=True)
