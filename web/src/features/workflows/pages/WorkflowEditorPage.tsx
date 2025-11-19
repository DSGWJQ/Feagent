/**
 * 工作流编辑器页面
 *
 * 功能：
 * - 拖拽编辑工作流节点和连线
 * - 保存工作流到后端
 * - 执行工作流（SSE 流式返回）
 *
 * 基于 V0 模板简化实现
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  ReactFlow,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button, message } from 'antd';
import { PlayCircleOutlined, SaveOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { updateWorkflow } from '../api/workflowsApi';
import { useWorkflowExecution } from '../hooks/useWorkflowExecution';
import type { WorkflowNode, WorkflowEdge } from '../types/workflow';

/**
 * 初始节点（示例）
 */
const initialNodes: Node[] = [
  {
    id: '1',
    type: 'input',
    position: { x: 50, y: 250 },
    data: { label: 'Start' },
  },
  {
    id: '2',
    type: 'default',
    position: { x: 350, y: 250 },
    data: { label: 'HTTP Request' },
  },
  {
    id: '3',
    type: 'output',
    position: { x: 650, y: 250 },
    data: { label: 'End' },
  },
];

/**
 * 初始边（示例）
 */
const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2' },
  { id: 'e2-3', source: '2', target: '3' },
];

/**
 * 工作流编辑器页面
 */
export function WorkflowEditorPage() {
  const { id: workflowId } = useParams<{ id: string }>();
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // 工作流执行 Hook
  const {
    isExecuting,
    executionLog,
    error: executionError,
    currentNodeId,
    nodeStatusMap,
    execute,
  } = useWorkflowExecution();

  /**
   * 节点变化处理
   */
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  /**
   * 边变化处理
   */
  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  /**
   * 连线处理
   */
  const onConnect: OnConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), []);

  /**
   * 保存工作流
   */
  const handleSave = useCallback(async () => {
    if (!workflowId) {
      message.error('工作流 ID 不存在');
      return;
    }

    setIsSaving(true);
    try {
      // 转换为后端格式
      const workflowNodes: WorkflowNode[] = nodes.map((node) => ({
        id: node.id,
        type: node.type || 'default',
        position: node.position,
        data: node.data || {},
      }));

      const workflowEdges: WorkflowEdge[] = edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        label: edge.label as string | undefined,
      }));

      await updateWorkflow(workflowId, {
        nodes: workflowNodes,
        edges: workflowEdges,
      });

      message.success('工作流保存成功');
    } catch (error: any) {
      console.error('Failed to save workflow:', error);
      message.error(`保存失败: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  }, [workflowId, nodes, edges]);

  /**
   * 执行工作流
   */
  const handleExecute = useCallback(() => {
    if (!workflowId) {
      message.error('工作流 ID 不存在');
      return;
    }

    execute(workflowId, {
      initial_input: { message: 'test' },
    });
  }, [workflowId, execute]);

  /**
   * 显示执行错误
   */
  useEffect(() => {
    if (executionError) {
      message.error(`执行失败: ${executionError}`);
    }
  }, [executionError]);

  /**
   * 更新节点状态（根据执行状态）
   */
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const status = nodeStatusMap[node.id];
        if (status) {
          return {
            ...node,
            data: {
              ...node.data,
              status,
            },
            style: {
              ...node.style,
              backgroundColor:
                status === 'running'
                  ? '#1890ff'
                  : status === 'completed'
                    ? '#52c41a'
                    : status === 'error'
                      ? '#ff4d4f'
                      : undefined,
            },
          };
        }
        return node;
      })
    );
  }, [nodeStatusMap]);

  return (
    <div style={{ width: '100%', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 头部工具栏 */}
      <div
        style={{
          padding: '16px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h1 style={{ margin: 0 }}>工作流编辑器</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button icon={<SaveOutlined />} onClick={handleSave} loading={isSaving}>
            保存
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleExecute}
            loading={isExecuting}
          >
            执行
          </Button>
        </div>
      </div>

      {/* React Flow 画布 */}
      <div style={{ flex: 1 }} ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onInit={setReactFlowInstance}
          fitView
        >
          <Background gap={16} size={1} />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>

      {/* 执行日志面板 */}
      {isExecuting || executionLog.length > 0 ? (
        <div
          style={{
            position: 'absolute',
            right: 0,
            top: 64,
            width: '400px',
            height: 'calc(100vh - 64px)',
            backgroundColor: '#fff',
            borderLeft: '1px solid #f0f0f0',
            padding: '16px',
            overflowY: 'auto',
          }}
        >
          <h3>执行日志</h3>
          {currentNodeId && (
            <div style={{ marginBottom: '8px', color: '#1890ff' }}>
              正在执行节点: {currentNodeId}
            </div>
          )}
          <div>
            {executionLog.map((entry, index) => (
              <div
                key={index}
                style={{
                  marginBottom: '8px',
                  padding: '8px',
                  backgroundColor: '#f5f5f5',
                  borderRadius: '4px',
                }}
              >
                <div style={{ fontWeight: 'bold' }}>
                  {entry.node_type} ({entry.node_id})
                </div>
                <pre style={{ margin: 0, fontSize: '12px' }}>
                  {JSON.stringify(entry.output, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

