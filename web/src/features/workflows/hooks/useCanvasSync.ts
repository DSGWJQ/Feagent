/**
 * useCanvasSync Hook
 *
 * 提供 WebSocket 画布同步功能，用于：
 * - 管理 WebSocket 连接
 * - 接收画布状态更新
 * - 发送节点/边操作
 * - 同步执行状态
 *
 * 使用示例：
 * ```tsx
 * const {
 *   isConnected,
 *   error,
 *   createNode,
 *   updateNode,
 *   deleteNode,
 *   moveNode,
 *   createEdge,
 *   deleteEdge,
 * } = useCanvasSync({
 *   workflowId: 'wf_123',
 *   enabled: true,
 *   onNodesChange: (changes) => setNodes((nodes) => applyNodeChanges(changes, nodes)),
 *   onEdgesChange: (changes) => setEdges((edges) => applyEdgeChanges(changes, edges)),
 * });
 * ```
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { NodeChange, EdgeChange } from '@xyflow/react';
import type { WorkflowNode, WorkflowEdge, Position } from '../types/workflow';

/**
 * 执行状态
 */
export interface ExecutionStatus {
  nodeId: string;
  status: 'running' | 'completed' | 'error';
  outputs: Record<string, any>;
  error: string | null;
}

/**
 * 工作流完成状态
 */
export interface WorkflowCompletedStatus {
  status: string;
  outputs: Record<string, any>;
}

/**
 * WebSocket 消息类型
 */
interface WSMessage {
  type: string;
  workflow_id?: string;
  node_id?: string;
  node_type?: string;
  position?: Position;
  config?: Record<string, any>;
  changes?: Record<string, any>;
  edge_id?: string;
  source_id?: string;
  target_id?: string;
  status?: string;
  outputs?: Record<string, any>;
  error?: string | null;
  message?: string;
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
  timestamp?: string;
}

/**
 * Hook 配置选项
 */
export interface UseCanvasSyncOptions {
  /** 工作流 ID */
  workflowId: string;
  /** 是否启用连接 */
  enabled?: boolean;
  /** 节点变化回调 */
  onNodesChange?: (changes: NodeChange[]) => void;
  /** 边变化回调 */
  onEdgesChange?: (changes: EdgeChange[]) => void;
  /** 执行状态回调 */
  onExecutionStatus?: (status: ExecutionStatus) => void;
  /** 工作流开始回调 */
  onWorkflowStarted?: () => void;
  /** 工作流完成回调 */
  onWorkflowCompleted?: (status: WorkflowCompletedStatus) => void;
  /** 错误回调 */
  onError?: (error: string) => void;
}

/**
 * Hook 返回值
 */
export interface UseCanvasSyncReturn {
  /** 是否已连接 */
  isConnected: boolean;
  /** 错误信息 */
  error: string | null;
  /** 创建节点 */
  createNode: (node: WorkflowNode) => void;
  /** 更新节点 */
  updateNode: (nodeId: string, changes: Record<string, any>) => void;
  /** 删除节点 */
  deleteNode: (nodeId: string) => void;
  /** 移动节点 */
  moveNode: (nodeId: string, position: Position) => void;
  /** 创建边 */
  createEdge: (edge: WorkflowEdge) => void;
  /** 删除边 */
  deleteEdge: (edgeId: string) => void;
  /** 开始执行 */
  startExecution: () => void;
}

/**
 * 获取 WebSocket URL
 */
function getWebSocketUrl(workflowId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/ws/workflows/${workflowId}`;
}

/**
 * useCanvasSync Hook
 */
export function useCanvasSync(options: UseCanvasSyncOptions): UseCanvasSyncReturn {
  const {
    workflowId,
    enabled = true,
    onNodesChange,
    onEdgesChange,
    onExecutionStatus,
    onWorkflowStarted,
    onWorkflowCompleted,
    onError,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  /**
   * 处理接收到的消息
   */
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data: WSMessage = JSON.parse(event.data);

        switch (data.type) {
          case 'initial_state':
            // 初始状态 - 设置节点和边
            if (data.nodes && onNodesChange) {
              const nodeChanges: NodeChange[] = data.nodes.map((node) => ({
                type: 'add' as const,
                item: {
                  id: node.id,
                  type: node.type,
                  position: node.position,
                  data: node.data,
                },
              }));
              onNodesChange(nodeChanges);
            }
            if (data.edges && onEdgesChange) {
              const edgeChanges: EdgeChange[] = data.edges.map((edge) => ({
                type: 'add' as const,
                item: {
                  id: edge.id,
                  source: edge.source,
                  target: edge.target,
                  sourceHandle: edge.sourceHandle,
                  label: edge.label,
                },
              }));
              onEdgesChange(edgeChanges);
            }
            break;

          case 'node_created':
            if (onNodesChange) {
              onNodesChange([
                {
                  type: 'add',
                  item: {
                    id: data.node_id!,
                    type: data.node_type!,
                    position: data.position || { x: 0, y: 0 },
                    data: data.config || {},
                  },
                },
              ]);
            }
            break;

          case 'node_updated':
            if (onNodesChange && data.node_id) {
              // 使用 'replace' 类型更新节点数据
              onNodesChange([
                {
                  type: 'replace' as any,
                  id: data.node_id,
                  item: {
                    id: data.node_id,
                    data: data.changes,
                  },
                },
              ]);
            }
            break;

          case 'node_deleted':
            if (onNodesChange && data.node_id) {
              onNodesChange([
                {
                  type: 'remove',
                  id: data.node_id,
                },
              ]);
            }
            break;

          case 'node_moved':
            if (onNodesChange && data.node_id && data.position) {
              onNodesChange([
                {
                  type: 'position',
                  id: data.node_id,
                  position: data.position,
                },
              ]);
            }
            break;

          case 'edge_created':
            if (onEdgesChange) {
              onEdgesChange([
                {
                  type: 'add',
                  item: {
                    id: data.edge_id!,
                    source: data.source_id!,
                    target: data.target_id!,
                  },
                },
              ]);
            }
            break;

          case 'edge_deleted':
            if (onEdgesChange && data.edge_id) {
              onEdgesChange([
                {
                  type: 'remove',
                  id: data.edge_id,
                },
              ]);
            }
            break;

          case 'execution_status':
            if (onExecutionStatus && data.node_id) {
              onExecutionStatus({
                nodeId: data.node_id,
                status: data.status as 'running' | 'completed' | 'error',
                outputs: data.outputs || {},
                error: data.error || null,
              });
            }
            break;

          case 'workflow_started':
            if (onWorkflowStarted) {
              onWorkflowStarted();
            }
            break;

          case 'workflow_completed':
            if (onWorkflowCompleted) {
              onWorkflowCompleted({
                status: data.status || 'completed',
                outputs: data.outputs || {},
              });
            }
            break;

          case 'error':
            const errorMessage = data.message || 'Unknown error';
            setError(errorMessage);
            if (onError) {
              onError(errorMessage);
            }
            break;
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    },
    [
      onNodesChange,
      onEdgesChange,
      onExecutionStatus,
      onWorkflowStarted,
      onWorkflowCompleted,
      onError,
    ]
  );

  /**
   * 发送消息
   */
  const sendMessage = useCallback((message: Record<string, any>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  /**
   * 创建节点
   */
  const createNode = useCallback(
    (node: WorkflowNode) => {
      sendMessage({
        action: 'create_node',
        node: {
          id: node.id,
          type: node.type,
          position: node.position,
          config: node.data,
        },
      });
    },
    [sendMessage]
  );

  /**
   * 更新节点
   */
  const updateNode = useCallback(
    (nodeId: string, changes: Record<string, any>) => {
      sendMessage({
        action: 'update_node',
        node_id: nodeId,
        changes,
      });
    },
    [sendMessage]
  );

  /**
   * 删除节点
   */
  const deleteNode = useCallback(
    (nodeId: string) => {
      sendMessage({
        action: 'delete_node',
        node_id: nodeId,
      });
    },
    [sendMessage]
  );

  /**
   * 移动节点
   */
  const moveNode = useCallback(
    (nodeId: string, position: Position) => {
      sendMessage({
        action: 'move_node',
        node_id: nodeId,
        position,
      });
    },
    [sendMessage]
  );

  /**
   * 创建边
   */
  const createEdge = useCallback(
    (edge: WorkflowEdge) => {
      sendMessage({
        action: 'create_edge',
        edge: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
        },
      });
    },
    [sendMessage]
  );

  /**
   * 删除边
   */
  const deleteEdge = useCallback(
    (edgeId: string) => {
      sendMessage({
        action: 'delete_edge',
        edge_id: edgeId,
      });
    },
    [sendMessage]
  );

  /**
   * 开始执行
   */
  const startExecution = useCallback(() => {
    sendMessage({
      action: 'start_execution',
    });
  }, [sendMessage]);

  /**
   * 建立 WebSocket 连接
   */
  useEffect(() => {
    if (!enabled || !workflowId) {
      return;
    }

    const url = getWebSocketUrl(workflowId);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = handleMessage;

    ws.onerror = () => {
      setError('WebSocket connection error');
      if (onError) {
        onError('WebSocket connection error');
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [workflowId, enabled, handleMessage, onError]);

  return {
    isConnected,
    error,
    createNode,
    updateNode,
    deleteNode,
    moveNode,
    createEdge,
    deleteEdge,
    startExecution,
  };
}

export default useCanvasSync;
