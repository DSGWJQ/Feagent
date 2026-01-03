# ADR: LangGraph Workflow Execution Alignment (WF-050)

## Context

The repository contains two workflow-execution implementations:

- Domain kernel: `WorkflowEngine` / `ExecuteWorkflowUseCase` (single source of truth).
- Infrastructure LangGraph prototype: `langgraph_workflow_executor*`.

At the same time, `WorkflowExecutorAdapter` historically injected a
`LangGraphWorkflowExecutorAdapter` that raised `NotImplementedError`, creating
an architecture drift risk (“wired but not runnable”).

## Decision

Choose **Option B (disable workflow LangGraph execution)**:

- Workflow execution remains **Domain-kernel only** (WorkflowEngine v1).
- `WorkflowExecutorAdapter` no longer injects a LangGraph workflow executor.
- `LangGraphWorkflowExecutorAdapter` is explicitly **feature-disabled** and
  raises a clear `DomainError` instead of `NotImplementedError` if called.

## Consequences

- No runtime path can reach a `NotImplementedError` for workflow execution via
  adapter injection.
- If we later decide to enable workflow LangGraph execution, it must be done as
  a complete implementation behind an explicit feature flag + rollback plan.

## References

- `src/domain/services/workflow_engine.py`
- `src/application/services/workflow_execution_facade.py`
- `src/interfaces/api/services/workflow_executor_adapter.py`
- `src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py`
