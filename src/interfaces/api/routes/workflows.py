"""Workflow API 璺敱

瀹氫箟 Workflow 鐩稿叧鐨?API 绔偣
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.application.use_cases.execute_workflow import (
    ExecuteWorkflowInput,
    ExecuteWorkflowUseCase,
)
from src.application.use_cases.generate_workflow_from_form import (
    GenerateWorkflowFromFormUseCase,
    GenerateWorkflowInput,
)
from src.application.use_cases.import_workflow import (
    ImportWorkflowInput,
    ImportWorkflowUseCase,
)
from src.application.use_cases.update_workflow_by_chat import (
    UpdateWorkflowByChatInput,
    UpdateWorkflowByChatUseCase,
)
from src.application.use_cases.update_workflow_by_drag import (
    UpdateWorkflowByDragInput,
    UpdateWorkflowByDragUseCase,
)
from src.config import settings
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.ports.workflow_chat_llm import WorkflowChatLLM
from src.domain.services.workflow_chat_service import WorkflowChatService
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry
from src.infrastructure.llm import LangChainWorkflowChatLLM
from src.interfaces.api.dependencies.current_user import get_current_user_optional
from src.interfaces.api.dto.workflow_dto import (
    ChatRequest,
    ChatResponse,
    CreateWorkflowRequest,
    ImportWorkflowRequest,
    ImportWorkflowResponse,
    UpdateWorkflowRequest,
    WorkflowResponse,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


# 鍒涘缓鍏ㄥ眬鎵ц鍣ㄦ敞鍐岃〃
_executor_registry = create_executor_registry(
    openai_api_key=settings.openai_api_key or None,
    anthropic_api_key=getattr(settings, "anthropic_api_key", None),
)


def get_workflow_repository(
    db: Session = Depends(get_db_session),
) -> SQLAlchemyWorkflowRepository:
    """Provide a workflow repository bound to the current request session."""

    return SQLAlchemyWorkflowRepository(db)


def get_workflow_chat_llm() -> WorkflowChatLLM:
    """Resolve the LLM implementation for workflow chat features."""

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured for workflow chat.",
        )

    try:
        return LangChainWorkflowChatLLM(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            temperature=0,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def get_workflow_chat_service(
    llm: WorkflowChatLLM = Depends(get_workflow_chat_llm),
) -> WorkflowChatService:
    """Create the domain service that orchestrates chat-driven workflow edits."""

    return WorkflowChatService(llm=llm)


def get_update_workflow_by_chat_use_case(
    workflow_repository: SQLAlchemyWorkflowRepository = Depends(get_workflow_repository),
    chat_service: WorkflowChatService = Depends(get_workflow_chat_service),
) -> UpdateWorkflowByChatUseCase:
    """Assemble the use case with its required dependencies."""

    return UpdateWorkflowByChatUseCase(
        workflow_repository=workflow_repository,
        chat_service=chat_service,
    )


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    request: CreateWorkflowRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user_optional),  # 可选认证
) -> WorkflowResponse:
    """创建新工作流

    业务场景：
    - 登录用户：创建工作流并关联到用户账户（可长期保存）
    - 非登录用户：创建工作流但不关联用户（仅体验，刷新后丢失）
    - 可以提供初始节点和边

    认证：
    - 可选认证（Authorization: Bearer <token>）
    - 登录用户的工作流会关联user_id
    - 非登录用户的工作流user_id为None

    请求参数：
    - request: 创建请求（包含name, description, nodes, edges）

    返回：
    - 创建后的工作流

    错误：
    - 422: 请求参数验证失败
    - 400: 业务规则验证失败
    - 500: 服务器内部错误
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(
            f"[POST] 开始创建工作流: name={request.name}, user_id={current_user.id if current_user else 'anonymous'}"
        )
        logger.info(f"[POST] 请求数据: nodes={len(request.nodes)}, edges={len(request.edges)}")

        # 1. 创建 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)

        # 2. 转换 DTO 到 Domain 实体
        from src.domain.entities.workflow import Workflow

        nodes = [node_dto.to_entity() for node_dto in request.nodes]
        edges = [edge_dto.to_entity() for edge_dto in request.edges]

        workflow = Workflow.create(
            name=request.name,
            description=request.description,
            nodes=nodes,
            edges=edges,
        )

        # 3. 关联用户（如果已登录）
        if current_user:
            workflow.user_id = current_user.id
            logger.info(f"[POST] 工作流关联到用户: user_id={current_user.id}")
        else:
            logger.info("[POST] 非登录用户创建工作流（体验模式）")

        # 4. 保存到数据库
        workflow_repository.save(workflow)
        db.commit()

        logger.info(f"[POST] 工作流创建成功: workflow_id={workflow.id}")

        # 5. 转换为 DTO 返回
        return WorkflowResponse.from_entity(workflow)

    except DomainError as e:
        logger.error(f"[POST] 领域错误: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"[POST] 服务器内部错误: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """Get workflow details"""
    import logging

    logger = logging.getLogger(__name__)

    logger.info(f"[GET] Fetching workflow: {workflow_id}")

    try:
        # 1. 鍒涘缓 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)
        logger.info("[GET] Repository created")

        # 2. 鑾峰彇宸ヤ綔娴?        logger.info("[GET] Calling get_by_id...")
        workflow = workflow_repository.get_by_id(workflow_id)
        logger.info(f"[GET] get_by_id returned: {workflow is not None}")

        if not workflow:
            logger.warning(f"[GET] Workflow {workflow_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        logger.info(f"[GET] Workflow found: id={workflow.id}, name={workflow.name}")
        logger.info("[GET] Converting to DTO...")

        # 3. 杞崲涓?DTO
        response = WorkflowResponse.from_entity(workflow)
        logger.info("[GET] DTO created successfully")
        return response

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str,
    request: UpdateWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """鏇存柊宸ヤ綔娴侊紙鎷栨嫿璋冩暣锛?
    涓氬姟鍦烘櫙锛?    - 鐢ㄦ埛鍦ㄥ墠绔嫋鎷界紪杈戝櫒涓皟鏁村伐浣滄祦
    - 娣诲姞/鍒犻櫎/鏇存柊鑺傜偣
    - 娣诲姞/鍒犻櫎杈?
    璇锋眰鍙傛暟锛?    - workflow_id: 宸ヤ綔娴?ID锛堣矾寰勫弬鏁帮級
    - request: 鏇存柊璇锋眰锛堝寘鍚妭鐐瑰拰杈瑰垪琛級

    杩斿洖锛?    - 鏇存柊鍚庣殑宸ヤ綔娴?
    閿欒锛?    - 404: Workflow 涓嶅瓨鍦?    - 422: 璇锋眰鍙傛暟楠岃瘉澶辫触
    - 400: 涓氬姟瑙勫垯楠岃瘉澶辫触锛堝杈瑰紩鐢ㄧ殑鑺傜偣涓嶅瓨鍦級
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(
            f"[PATCH] 寮€濮嬫洿鏂板伐浣滄祦: workflow_id={workflow_id!r} (type={type(workflow_id).__name__})"
        )
        logger.info(f"[PATCH] 璇锋眰鏁版嵁: nodes={len(request.nodes)}, edges={len(request.edges)}")

        # 1. 鍒涘缓 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)
        logger.info("[PATCH] Repository 鍒涘缓鎴愬姛")

        # 2. 鍏堟祴璇曡兘鍚︽壘鍒板伐浣滄祦
        test_find = workflow_repository.find_by_id(workflow_id)
        logger.info(f"[PATCH] find_by_id 缁撴灉: {test_find is not None}")
        if test_find:
            logger.info(f"[PATCH] 鎵惧埌宸ヤ綔娴? id={test_find.id}, name={test_find.name}")

        # 3. 杞崲 DTO 鈫?Entity
        nodes = [node_dto.to_entity() for node_dto in request.nodes]
        edges = [edge_dto.to_entity() for edge_dto in request.edges]
        logger.info(f"[PATCH] DTO 杞崲瀹屾垚: nodes={len(nodes)}, edges={len(edges)}")

        # 4. 鍒涘缓 Use Case
        use_case = UpdateWorkflowByDragUseCase(workflow_repository=workflow_repository)
        logger.info("[PATCH] Use Case 鍒涘缓鎴愬姛")

        # 5. 鎵ц Use Case
        input_data = UpdateWorkflowByDragInput(
            workflow_id=workflow_id,
            nodes=nodes,
            edges=edges,
        )
        logger.info("[PATCH] 寮€濮嬫墽琛?Use Case...")
        workflow = use_case.execute(input_data)
        logger.info(f"[PATCH] Use Case 鎵ц鎴愬姛: workflow_id={workflow.id}")

        # 5. 鎻愪氦浜嬪姟
        db.commit()

        # 6. 杞崲 Entity 鈫?DTO
        return WorkflowResponse.from_entity(workflow)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{e.entity_type} 不存在: {e.entity_id}",
        )
    except DomainError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


class ExecuteWorkflowRequest(BaseModel):
    """鎵ц宸ヤ綔娴佽姹?
    瀛楁锛?    - initial_input: 鍒濆杈撳叆锛堜紶閫掔粰 Start 鑺傜偣锛?"""

    initial_input: Any = None


class ExecuteWorkflowResponse(BaseModel):
    """鎵ц宸ヤ綔娴佸搷搴?
    瀛楁锛?    - execution_log: 鎵ц鏃ュ織锛堟瘡涓妭鐐圭殑鎵ц璁板綍锛?    - final_result: 鏈€缁堢粨鏋滐紙End 鑺傜偣鐨勮緭鍑猴級
    """

    execution_log: list[dict[str, Any]]
    final_result: Any


@router.post("/{workflow_id}/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> ExecuteWorkflowResponse:
    """鎵ц宸ヤ綔娴侊紙闈炴祦寮忥級

    涓氬姟鍦烘櫙锛?    - 鐢ㄦ埛瑙﹀彂宸ヤ綔娴佹墽琛?    - 鎸夋嫇鎵戦『搴忔墽琛岃妭鐐?    - 杩斿洖鎵ц缁撴灉

    璇锋眰鍙傛暟锛?    - workflow_id: 宸ヤ綔娴?ID锛堣矾寰勫弬鏁帮級
    - request: 鎵ц璇锋眰锛堝寘鍚垵濮嬭緭鍏ワ級

    杩斿洖锛?    - 鎵ц鏃ュ織鍜屾渶缁堢粨鏋?
    閿欒锛?    - 404: Workflow 涓嶅瓨鍦?    - 400: 宸ヤ綔娴佹墽琛屽け璐ワ紙濡傚寘鍚幆锛?"""
    try:
        # 1. 鍒涘缓 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)

        # 2. 鍒涘缓 Use Case
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=workflow_repository,
            executor_registry=_executor_registry,
        )

        # 3. 鎵ц Use Case
        input_data = ExecuteWorkflowInput(
            workflow_id=workflow_id,
            initial_input=request.initial_input,
        )
        result = await use_case.execute(input_data)

        # 4. 杩斿洖缁撴灉
        return ExecuteWorkflowResponse(
            execution_log=result["execution_log"],
            final_result=result["final_result"],
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{e.entity_type} 不存在: {e.entity_id}",
        )
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


@router.post("/{workflow_id}/execute/stream")
async def execute_workflow_streaming(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """鎵ц宸ヤ綔娴侊紙娴佸紡杩斿洖 SSE锛?
    涓氬姟鍦烘櫙锛?    - 鐢ㄦ埛瑙﹀彂宸ヤ綔娴佹墽琛?    - 瀹炴椂鎺ㄩ€佽妭鐐规墽琛岀姸鎬?    - 浣跨敤 Server-Sent Events (SSE) 鍗忚

    璇锋眰鍙傛暟锛?    - workflow_id: 宸ヤ綔娴?ID锛堣矾寰勫弬鏁帮級
    - request: 鎵ц璇锋眰锛堝寘鍚垵濮嬭緭鍏ワ級

    杩斿洖锛?    - SSE 浜嬩欢娴侊紙text/event-stream锛?
    浜嬩欢绫诲瀷锛?    - node_start: 鑺傜偣寮€濮嬫墽琛?    - node_complete: 鑺傜偣鎵ц瀹屾垚
    - node_error: 鑺傜偣鎵ц澶辫触
    - workflow_complete: 宸ヤ綔娴佹墽琛屽畬鎴?    - workflow_error: 宸ヤ綔娴佹墽琛屽け璐?
    閿欒锛?    - 404: Workflow 涓嶅瓨鍦?"""
    import json

    async def event_generator():
        """鐢熸垚 SSE 浜嬩欢"""
        try:
            # 1. 鍒涘缓 Repository
            workflow_repository = SQLAlchemyWorkflowRepository(db)

            # 2. 鍒涘缓 Use Case
            use_case = ExecuteWorkflowUseCase(
                workflow_repository=workflow_repository,
                executor_registry=_executor_registry,
            )

            # 3. 鎵ц Use Case锛堟祦寮忥級
            input_data = ExecuteWorkflowInput(
                workflow_id=workflow_id,
                initial_input=request.initial_input,
            )

            # 4. 鐢熸垚 SSE 浜嬩欢
            async for event in use_case.execute_streaming(input_data):
                yield f"data: {json.dumps(event)}\n\n"

        except NotFoundError as e:
            # 鐢熸垚閿欒浜嬩欢
            error_event = {
                "type": "workflow_error",
                "error": f"{e.entity_type} 涓嶅瓨鍦? {e.entity_id}",
            }
            yield f"data: {json.dumps(error_event)}\n\n"

        except Exception as e:
            # 鐢熸垚閿欒浜嬩欢
            error_event = {
                "type": "workflow_error",
                "error": f"鏈嶅姟鍣ㄥ唴閮ㄩ敊璇? {str(e)}",
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/{workflow_id}/chat", response_model=ChatResponse)
def chat_with_workflow(
    workflow_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db_session),
    use_case: UpdateWorkflowByChatUseCase = Depends(get_update_workflow_by_chat_use_case),
) -> ChatResponse:
    """瀵硅瘽寮忎慨鏀瑰伐浣滄祦

    鍙傛暟锛?        workflow_id: 宸ヤ綔娴?ID
        request: 瀵硅瘽璇锋眰锛堝寘鍚敤鎴锋秷鎭級

    杩斿洖锛?        ChatResponse: 鍖呭惈淇敼鍚庣殑宸ヤ綔娴佸拰AI鍥炲娑堟伅

    閿欒锛?    - 404: Workflow 涓嶅瓨鍦?    - 400: 娑堟伅涓虹┖鎴栧鐞嗗け璐?    - 500: 鏈嶅姟鍣ㄥ唴閮ㄩ敊璇?"""
    try:
        # 鎵ц Use Case
        input_data = UpdateWorkflowByChatInput(
            workflow_id=workflow_id,
            user_message=request.message,
        )
        modified_workflow, ai_message = use_case.execute(input_data)

        # 鎻愪氦浜嬪姟
        db.commit()

        # 杩斿洖缁撴灉
        return ChatResponse(
            workflow=WorkflowResponse.from_entity(modified_workflow),
            ai_message=ai_message,
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{e.entity_type} 不存在: {e.entity_id}",
        )
    except DomainError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


class GenerateWorkflowRequest(BaseModel):
    """Generate workflow request DTO."""

    description: str
    goal: str


class GenerateWorkflowResponse(BaseModel):
    """Generate workflow response DTO."""

    workflow_id: str
    name: str
    description: str
    node_count: int
    edge_count: int


class SimpleWorkflowLLMClient:
    """Simple workflow generation LLM client."""

    def __init__(self, llm_model: ChatOpenAI):
        self.llm = llm_model

    async def generate_workflow(self, description: str, goal: str) -> dict[str, Any]:
        """浣跨敤 LLM 鐢熸垚宸ヤ綔娴佺粨鏋?
        鍙傛暟锛?            description: 宸ヤ綔娴佹弿杩?            goal: 宸ヤ綔娴佺洰鏍?
        杩斿洖锛?            鍖呭惈鑺傜偣鍜岃竟鐨勫伐浣滄祦缁撴瀯
        """
        # 鏋勫缓 LLM 鎻愮ず璇?
        prompt = f"""
You are a workflow designer. Based on the following requirements, create a JSON workflow specification.

Requirements:
- Description: {description}
- Goal: {goal}

The JSON must include:
{{
  "name": "Workflow name",
  "description": "Workflow description",
  "nodes": [
    {{
      "type": "start|end|httpRequest|textModel|database|conditional|loop|python|transform|file|notification",
      "name": "Node name",
      "config": {{}} ,
      "position": {{"x": 100, "y": 100}}
    }}
  ],
  "edges": [
    {{"source": "node_1", "target": "node_2"}}
  ]
}}

Rules:
1. Include at least one start node and one end node.
2. Node types must be selected from the supported list.
3. Edge source/target must reference existing nodes.
        4. Return valid JSON only, without extra commentary.

        """

        # 璋冪敤 LLM
        response = await self.llm.ainvoke(prompt)

        # 瑙ｆ瀽鍝嶅簲锛堝亣璁?LLM 杩斿洖鏈夋晥鐨?JSON锛?        import json

        try:
            # 灏濊瘯鎻愬彇 JSON锛堝彲鑳藉湪鍝嶅簲鐨勬煇涓綅缃級
            text = response.content if hasattr(response, "content") else str(response)
            # 鏌ユ壘 JSON 瀵硅薄
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                return json.loads(json_str)
            else:
                raise ValueError("鍝嶅簲涓湭鎵惧埌鏈夋晥鐨?JSON")
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 鍝嶅簲涓嶆槸鏈夋晥鐨?JSON: {str(e)}")


@router.post("/import", response_model=ImportWorkflowResponse, status_code=status.HTTP_201_CREATED)
def import_workflow(
    request: ImportWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> ImportWorkflowResponse:
    """瀵煎叆 Coze 宸ヤ綔娴?
    V2鏂板姛鑳斤細鏀寔浠?Coze 骞冲彴瀵煎叆宸ヤ綔娴?
    涓氬姟鍦烘櫙锛?    鐢ㄦ埛浠?Coze 骞冲彴瀵煎嚭宸ヤ綔娴?JSON锛岄€氳繃姝ゆ帴鍙ｅ鍏ュ埌 Feagent

    鍙傛暟锛?        request: ImportWorkflowRequest 鍖呭惈 Coze JSON 鏁版嵁

    杩斿洖锛?        ImportWorkflowResponse 鍖呭惈瀵煎叆鍚庣殑宸ヤ綔娴佸熀鏈俊鎭?
    閿欒锛?        400: 杈撳叆鏁版嵁鏃犳晥锛圝SON 鏍煎紡閿欒銆佺己灏戝繀闇€瀛楁銆佷笉鏀寔鐨勮妭鐐圭被鍨嬬瓑锛?        500: 鏈嶅姟鍣ㄥ唴閮ㄩ敊璇?"""
    try:
        # 1. 鍒涘缓 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)

        # 2. 鍒涘缓 Use Case
        use_case = ImportWorkflowUseCase(workflow_repository=workflow_repository)

        # 3. 鎵ц Use Case
        input_data = ImportWorkflowInput(coze_json=request.coze_json)
        output = use_case.execute(input_data)

        # 4. 鎻愪氦浜嬪姟
        db.commit()

        # 5. 杩斿洖缁撴灉
        return ImportWorkflowResponse(
            workflow_id=output.workflow_id,
            name=output.name,
            source=output.source,
            source_id=output.source_id,
        )

    except DomainError as e:
        # Domain灞傞獙璇佸け璐ワ紙绌篔SON銆佺己灏戣妭鐐广€佷笉鏀寔鐨勮妭鐐圭被鍨嬨€佽竟寮曠敤閿欒绛夛級
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # 鍏朵粬鏈鏈熺殑閿欒
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


@router.post(
    "/generate-from-form",
    response_model=GenerateWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_workflow_from_form(
    request: GenerateWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> GenerateWorkflowResponse:
    """浠庤〃鍗曠敓鎴愬伐浣滄祦

    V2鏂板姛鑳斤細AI杈呭姪宸ヤ綔娴佸垵濮嬪寲

    涓氬姟鍦烘櫙锛?    鐢ㄦ埛鎻愪緵宸ヤ綔娴佹弿杩板拰鐩爣锛岀郴缁熶娇鐢?LLM 鑷姩鐢熸垚宸ヤ綔娴佺粨鏋?
    鍙傛暟锛?        request: GenerateWorkflowRequest 鍖呭惈宸ヤ綔娴佹弿杩板拰鐩爣

    杩斿洖锛?        GenerateWorkflowResponse 鍖呭惈鐢熸垚鍚庣殑宸ヤ綔娴佷俊鎭?
    閿欒锛?        400: 杈撳叆鏁版嵁鏃犳晥鎴?LLM 鐢熸垚澶辫触
        500: 鏈嶅姟鍣ㄥ唴閮ㄩ敊璇?"""
    try:
        # 1. 鍒涘缓 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)

        # 2. 初始化 LLM 客户端
        openai_api_key = settings.openai_api_key
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

        llm = ChatOpenAI(
            api_key=openai_api_key,
            model=settings.openai_model,
            temperature=0.7,
        )
        llm_client = SimpleWorkflowLLMClient(llm)

        # 3. 鍒涘缓 Use Case
        use_case = GenerateWorkflowFromFormUseCase(
            workflow_repository=workflow_repository,
            llm_client=llm_client,
        )

        # 4. 鎵ц Use Case
        input_data = GenerateWorkflowInput(
            description=request.description,
            goal=request.goal,
        )
        workflow = await use_case.execute(input_data)

        # 5. 鎻愪氦浜嬪姟
        db.commit()

        # 6. 杩斿洖缁撴灉
        return GenerateWorkflowResponse(
            workflow_id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            node_count=len(workflow.nodes),
            edge_count=len(workflow.edges),
        )

    except DomainError as e:
        # Domain灞傞獙璇佸け璐?        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        # 鍊奸敊璇紙濡傜幆澧冨彉閲忕己澶憋級
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # 鍏朵粬鏈鏈熺殑閿欒
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )
