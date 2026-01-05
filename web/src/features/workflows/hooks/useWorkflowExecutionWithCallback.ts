/**
 * 工作流执行 Hook（带回调）
 *
 * 在执行完成后调用回调函数，用于插入执行总结到聊天
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { executeWorkflowStreaming } from '../api/workflowsApi';
import type {
  ExecuteWorkflowRequest,
  SSEEvent,
  ExecutionLogEntry,
  NodeExecutionStatus,
} from '../types/workflow';

export interface UseWorkflowExecutionWithCallbackProps {
  /** 工作流执行完成时的回调 */
  onWorkflowComplete?: (result: {
    finalResult: any;
    executionLog: ExecutionLogEntry[];
    nodeStatusMap: Record<string, NodeExecutionStatus>;
    nodeOutputMap: Record<string, any>;
  }) => void;
  /** PRD-030: 外部副作用确认弹窗触发 */
  onConfirmRequired?: (payload: {
    runId: string;
    workflowId?: string;
    nodeId?: string;
    confirmId: string;
    defaultDecision?: 'deny';
  }) => void;
}

export interface UseWorkflowExecutionWithCallbackReturn {
  /** 是否正在执行 */
  isExecuting: boolean;
  /** 执行日志 */
  executionLog: ExecutionLogEntry[];
  /** 错误信息 */
  error: string | null;
  /** 当前执行的节点 ID */
  currentNodeId: string | null;
  /** 节点状态映射 */
  nodeStatusMap: Record<string, NodeExecutionStatus>;
  /** 节点输出映射 */
  nodeOutputMap: Record<string, any>;
  /** 最终结果 */
  finalResult: any;
  /** 执行工作流 */
  execute: (workflowId: string, request: ExecuteWorkflowRequest) => void;
  /** 取消执行 */
  cancel: () => void;
  /** 重置状态 */
  reset: () => void;
}

/**
 * 工作流执行 Hook（带回调）
 */
export function useWorkflowExecutionWithCallback({
  onWorkflowComplete,
  onConfirmRequired,
}: UseWorkflowExecutionWithCallbackProps = {}): UseWorkflowExecutionWithCallbackReturn {
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionLog, setExecutionLog] = useState<ExecutionLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [nodeStatusMap, setNodeStatusMap] = useState<Record<string, NodeExecutionStatus>>({});
  const [nodeOutputMap, setNodeOutputMap] = useState<Record<string, any>>({});
  const [finalResult, setFinalResult] = useState<any>(null);

  const cancelFnRef = useRef<(() => void) | null>(null);
  const previousNodeStatusMap = useRef<Record<string, NodeExecutionStatus>>({});

  /**
   * 处理 SSE 事件
   */
  const handleEvent = useCallback((event: SSEEvent) => {
    switch (event.type) {
      case 'node_start':
        if (event.node_id) {
          setCurrentNodeId(event.node_id);
          setNodeStatusMap((prev) => ({
            ...prev,
            [event.node_id!]: 'running',
          }));
        }
        break;

      case 'node_complete':
        if (event.node_id) {
          setCurrentNodeId(null);
          setNodeStatusMap((prev) => ({
            ...prev,
            [event.node_id!]: 'completed',
          }));
          setNodeOutputMap((prev) => ({
            ...prev,
            [event.node_id!]: event.output,
          }));
          setExecutionLog((prev) => [
            ...prev,
            {
              node_id: event.node_id!,
              node_type: event.node_type || 'unknown',
              output: event.output,
            },
          ]);
        }
        break;

      case 'node_error':
        if (event.node_id) {
          setCurrentNodeId(null);
          setNodeStatusMap((prev) => ({
            ...prev,
            [event.node_id!]: 'error',
          }));
          setError(event.error || 'Node execution failed');
        }
        break;

      case 'workflow_complete':
        setIsExecuting(false);
        setCurrentNodeId(null);
        setFinalResult(event.result);

        // 保存当前状态
        const currentStatusMap = { ...nodeStatusMap };
        const currentOutputMap = { ...nodeOutputMap };

        if (event.execution_log) {
          setExecutionLog(event.execution_log);
        }

        // 延迟调用回调，确保状态已更新
        setTimeout(() => {
          if (onWorkflowComplete) {
            onWorkflowComplete({
              finalResult: event.result,
              executionLog: event.execution_log || executionLog,
              nodeStatusMap: currentStatusMap,
              nodeOutputMap: currentOutputMap,
            });
          }
        }, 100);
        break;

      case 'workflow_error':
        setIsExecuting(false);
        setCurrentNodeId(null);
        setError(event.error || 'Workflow execution failed');
        break;

      case 'workflow_confirm_required': {
        const runId = event.run_id;
        const confirmId = event.confirm_id;
        if (runId && confirmId && onConfirmRequired) {
          onConfirmRequired({
            runId,
            workflowId: event.workflow_id,
            nodeId: event.node_id,
            confirmId,
            defaultDecision: event.default_decision,
          });
        }
        break;
      }

      case 'workflow_confirmed':
        // no-op: UI can rely on API call resolution; this event is mainly for observability/replay
        break;
    }
  }, [nodeStatusMap, nodeOutputMap, executionLog, onWorkflowComplete, onConfirmRequired]);

  /**
   * 处理错误
   */
  const handleError = useCallback((err: Error) => {
    setIsExecuting(false);
    setCurrentNodeId(null);
    setError(err.message);
  }, []);

  /**
   * 执行工作流
   */
  const execute = useCallback(
    (workflowId: string, request: ExecuteWorkflowRequest) => {
      // 重置状态
      setIsExecuting(true);
      setExecutionLog([]);
      setError(null);
      setCurrentNodeId(null);
      setNodeStatusMap({});
      setNodeOutputMap({});
      setFinalResult(null);

      // 保存之前的状态用于对比
      previousNodeStatusMap.current = {};

      // 取消之前的执行
      if (cancelFnRef.current) {
        cancelFnRef.current();
      }

      // 开始执行
      cancelFnRef.current = executeWorkflowStreaming(
        workflowId,
        request,
        handleEvent,
        handleError
      );
    },
    [handleEvent, handleError]
  );

  /**
   * 取消执行
   */
  const cancel = useCallback(() => {
    if (cancelFnRef.current) {
      cancelFnRef.current();
      cancelFnRef.current = null;
    }
    setIsExecuting(false);
    setCurrentNodeId(null);
  }, []);

  /**
   * 重置状态
   */
  const reset = useCallback(() => {
    setIsExecuting(false);
    setExecutionLog([]);
    setError(null);
    setCurrentNodeId(null);
    setNodeStatusMap({});
    setNodeOutputMap({});
    setFinalResult(null);
    previousNodeStatusMap.current = {};
  }, []);

  return {
    isExecuting,
    executionLog,
    error,
    currentNodeId,
    nodeStatusMap,
    nodeOutputMap,
    finalResult,
    execute,
    cancel,
    reset,
  };
}

export default useWorkflowExecutionWithCallback;
