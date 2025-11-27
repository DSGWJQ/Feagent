"""Runs 路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application import ExecuteRunInput, ExecuteRunUseCase
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyRunRepository,
    SQLAlchemyTaskRepository,
)
from src.interfaces.api.dto import RunResponse

create_router = APIRouter()
query_router = APIRouter()


def get_agent_repository(
    session: Session = Depends(get_db_session),
) -> SQLAlchemyAgentRepository:
    return SQLAlchemyAgentRepository(session)


def get_run_repository(
    session: Session = Depends(get_db_session),
) -> SQLAlchemyRunRepository:
    return SQLAlchemyRunRepository(session)


def get_task_repository(
    session: Session = Depends(get_db_session),
) -> SQLAlchemyTaskRepository:
    return SQLAlchemyTaskRepository(session)


@create_router.post(
    "/{agent_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED
)
def execute_run(
    agent_id: str,
    agent_repository: SQLAlchemyAgentRepository = Depends(get_agent_repository),
    run_repository: SQLAlchemyRunRepository = Depends(get_run_repository),
    task_repository: SQLAlchemyTaskRepository = Depends(get_task_repository),
) -> RunResponse:
    try:
        use_case = ExecuteRunUseCase(
            agent_repository=agent_repository,
            run_repository=run_repository,
            task_repository=task_repository,
        )
        input_data = ExecuteRunInput(agent_id=agent_id)
        run = use_case.execute(input_data)
        return RunResponse.from_entity(run)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行 Run 失败: {str(e)}",
        ) from e


@query_router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    run_repository: SQLAlchemyRunRepository = Depends(get_run_repository),
) -> RunResponse:
    try:
        run = run_repository.get_by_id(run_id)
        return RunResponse.from_entity(run)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Run 失败: {str(e)}",
        ) from e
