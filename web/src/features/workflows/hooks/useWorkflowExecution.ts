/**
 * 工作流执行 Hook
 *
 * 提供工作流执行功能（SSE 流式返回）
 */

import { useState, useCallback, useRef } from 'react';
import { executeWorkflowStreaming } from '../api/workflowsApi';
import type {
  ExecuteWorkflowRequest,
  SSEEvent,
  ExecutionLogEntry,
  NodeExecutionStatus,
} from '../types/workflow';

/**
 * 节点状态映射
 */
export interface NodeStatusMap {
  [nodeId: string]: NodeExecutionStatus;
}

/**
 * 节点输出映射
 */
export interface NodeOutputMap {
  [nodeId: string]: any;
}

/**
 * 工作流执行 Hook 返回值
 */
export interface UseWorkflowExecutionReturn {
  /** 是否正在执行 */
  isExecuting: boolean;
  /** 执行日志 */
  executionLog: ExecutionLogEntry[];
  /** 错误信息 */
  error: string | null;
  /** 当前执行的节点 ID */
  currentNodeId: string | null;
  /** 节点状态映射 */
  nodeStatusMap: NodeStatusMap;
  /** 节点输出映射 */
  nodeOutputMap: NodeOutputMap;
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
 * 工作流执行 Hook
 *
 * 使用示例：
 * ```tsx
 * const { isExecuting, executionLog, execute, nodeStatusMap } = useWorkflowExecution();
 *
 * // 执行工作流
 * execute('workflow_id', { initial_input: { message: 'test' } });
 * ```
 */
export function useWorkflowExecution(): UseWorkflowExecutionReturn {
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionLog, setExecutionLog] = useState<ExecutionLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [nodeStatusMap, setNodeStatusMap] = useState<NodeStatusMap>({});
  const [nodeOutputMap, setNodeOutputMap] = useState<NodeOutputMap>({});
  const [finalResult, setFinalResult] = useState<any>(null);

  const cancelFnRef = useRef<(() => void) | null>(null);

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
        if (event.execution_log) {
          setExecutionLog(event.execution_log);
        }
        break;

      case 'workflow_error':
        setIsExecuting(false);
        setCurrentNodeId(null);
        setError(event.error || 'Workflow execution failed');
        break;
    }
  }, []);

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
