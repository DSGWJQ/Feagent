/**
 * 工作流编辑器页面（带互斥锁）
 *
 * 功能：
 * - 拖拽编辑工作流节点和连线
 * - 保存工作流到后端
 * - 执行工作流（SSE 流式返回）
 * - 聊天/拖拽互斥锁
 */

import { useState, useCallback, useRef, useEffect, useMemo, type DragEvent } from 'react';
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
  type NodeDragHandler,
  type NodeChange,
  type EdgeChange,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button, message, Empty, Spin } from 'antd';
import { PlayCircleOutlined, SaveOutlined, LeftOutlined, RightOutlined, WifiOutlined, DisconnectOutlined } from '@ant-design/icons';
import { updateWorkflow } from '../api/workflowsApi';
import { useWorkflowExecutionWithCallback } from '../hooks/useWorkflowExecutionWithCallback';
import { useWorkflow } from '@/hooks/useWorkflow';
import { useCanvasSync } from '../hooks/useCanvasSync';
import type { WorkflowNode, WorkflowEdge } from '../types/workflow';
import NodePalette from '../components/NodePalette';
import NodeConfigPanel from '../components/NodeConfigPanel';
import CodeExportModal from '../components/CodeExportModal';
import WorkflowAIChatWithExecution from '@/shared/components/WorkflowAIChatWithExecution';
import { useWorkflowInteraction } from '../contexts/WorkflowInteractionContext';
import {
  StartNode,
  EndNode,
  HttpRequestNode,
  TextModelNode,
  ConditionalNode,
  JavaScriptNode,
  PromptNode,
  ImageGenerationNode,
  AudioNode,
  ToolNode,
  EmbeddingModelNode,
  StructuredOutputNode,
  DatabaseNode,
  FileNode,
  NotificationNode,
  LoopNode,
} from '../components/nodes';
import { ExecutionOverlay } from '../components/ExecutionOverlay';
import { getDefaultNodeData } from '../utils/nodeUtils';
import { ThemeToggle } from '@/shared/components/ThemeToggle';
import { Divider } from 'antd';
import styles from '../styles/drafting.module.css';

/**
 * 节点类型映射
 */
const nodeTypes = {
  start: StartNode,
  end: EndNode,
  httpRequest: HttpRequestNode,
  textModel: TextModelNode,
  conditional: ConditionalNode,
  javascript: JavaScriptNode,
  prompt: PromptNode,
  imageGeneration: ImageGenerationNode,
  audio: AudioNode,
  tool: ToolNode,
  embeddingModel: EmbeddingModelNode,
  structuredOutput: StructuredOutputNode,
  database: DatabaseNode,
  file: FileNode,
  notification: NotificationNode,
  loop: LoopNode,
};

/**
 * 初始节点（示例）
 */
const initialNodes: Node[] = [
  {
    id: '1',
    type: 'start',
    position: { x: 50, y: 250 },
    data: {},
  },
  {
    id: '2',
    type: 'httpRequest',
    position: { x: 350, y: 250 },
    data: {
      url: 'https://api.example.com',
      method: 'GET',
    },
  },
  {
    id: '3',
    type: 'end',
    position: { x: 650, y: 250 },
    data: {},
  },
];

const initialEdges: Edge[] = [
  {
    id: 'e1-2',
    source: '1',
    target: '2',
  },
  {
    id: 'e2-3',
    source: '2',
    target: '3',
  },
];

interface WorkflowEditorPageWithMutexProps {
  workflowId: string;
  onWorkflowUpdate: (workflow: any) => void;
}

/**
 * 工作流编辑器内部组件（使用 Context）
 */
const WorkflowEditorPageWithMutex: React.FC<WorkflowEditorPageWithMutexProps> = ({
  workflowId,
  onWorkflowUpdate,
}) => {
  const { isCanvasMode } = useWorkflowInteraction();
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_, setInteractionMode] = useState('idle');

  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [chatPanelCollapsed, setChatPanelCollapsed] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [nodeIdCounter, setNodeIdCounter] = useState(4);

  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);
  const nodeIdCounterRef = useRef(4);

  const [executionStartTime, setExecutionStartTime] = useState<number | null>(null);

  const {
    execute,
    isExecuting,
    currentNodeId,
    executionLog,
    executionError,
    nodeStatusMap,
    nodeOutputMap,
  } = useWorkflowExecutionWithCallback({
    onWorkflowComplete: ({ finalResult, executionLog, nodeStatusMap, nodeOutputMap }) => {
      // 计算执行统计
      const totalNodes = Object.keys(nodeStatusMap).length;
      const successNodes = Object.values(nodeStatusMap).filter(s => s === 'completed').length;
      const errorNodes = Object.values(nodeStatusMap).filter(s => s === 'error').length;
      const duration = executionStartTime ? Date.now() - executionStartTime : undefined;

      // 准备执行总结
      const summary = {
        success: errorNodes === 0,
        totalNodes,
        successNodes,
        errorNodes,
        duration,
        result: finalResult,
      };

      // 调用全局方法添加执行总结到聊天
      if (window.addExecutionSummary) {
        window.addExecutionSummary(summary);
      }

      message.success(
        summary.success
          ? `工作流执行成功！共执行 ${totalNodes} 个节点`
          : `工作流执行完成！成功 ${successNodes} 个，失败 ${errorNodes} 个`
      );
    },
  });

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { workflowData, isLoadingWorkflow, workflowError } = useWorkflow(workflowId);

  /**
   * WebSocket 画布同步
   */
  const handleRemoteNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

  const handleRemoteEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const handleExecutionStatus = useCallback((status: {
    nodeId: string;
    status: 'running' | 'completed' | 'error';
    outputs: Record<string, any>;
    error: string | null;
  }) => {
    // 执行状态由 WebSocket 实时同步
    console.log('Execution status from WebSocket:', status);
  }, []);

  const handleWorkflowStarted = useCallback(() => {
    console.log('Workflow started (WebSocket)');
    setExecutionStartTime(Date.now());
  }, []);

  const handleWorkflowCompletedWS = useCallback((status: {
    status: string;
    outputs: Record<string, any>;
  }) => {
    console.log('Workflow completed (WebSocket):', status);
  }, []);

  const handleWSError = useCallback((error: string) => {
    console.error('WebSocket error:', error);
  }, []);

  // Memoize edge options to avoid unnecessary re-renders
  const defaultEdgeOptions = useMemo(() => ({
    style: {
      stroke: 'var(--color-neutral-600)',
      strokeWidth: 2,
    },
  }), []);

  const connectionLineStyle = useMemo(() => ({
    stroke: 'var(--color-primary-400)',
    strokeWidth: 2,
  }), []);

  const {
    isConnected: wsConnected,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    error: wsError,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    createNode: wsCreateNode,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    updateNode: wsUpdateNode,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    deleteNode: wsDeleteNode,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    moveNode: wsMoveNode,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    createEdge: wsCreateEdge,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    deleteEdge: wsDeleteEdge,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    startExecution: wsStartExecution,
  } = useCanvasSync({
    workflowId,
    enabled: !!workflowId && isInitialized,
    onNodesChange: handleRemoteNodesChange,
    onEdgesChange: handleRemoteEdgesChange,
    onExecutionStatus: handleExecutionStatus,
    onWorkflowStarted: handleWorkflowStarted,
    onWorkflowCompleted: handleWorkflowCompletedWS,
    onError: handleWSError,
  });

  /**
   * 处理工作流更新（从AI聊天返回）
   */
  const handleWorkflowUpdate = useCallback((workflow: any) => {
    console.log('收到工作流更新:', workflow);

    // 转换后端工作流格式到 React Flow 格式
    const newNodes: Node[] = workflow.nodes.map((node: any) => ({
      id: node.id,
      type: mapBackendNodeTypeToFrontend(node.type),
      position: { x: node.position.x, y: node.position.y },
      data: node.data || {},
    }));

    const newEdges: Edge[] = workflow.edges.map((edge: any) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.condition,
    }));

    setNodes(newNodes);
    setEdges(newEdges);
    onWorkflowUpdate(workflow);

    message.success('工作流已更新');
  }, [onWorkflowUpdate]);

  /**
   * 映射后端节点类型到前端节点类型
   */
  const mapBackendNodeTypeToFrontend = (backendType: string): string => {
    const typeMap: Record<string, string> = {
      'start': 'start',
      'end': 'end',
      'http': 'httpRequest',
      'llm': 'textModel',
      'transform': 'javascript',
      'database': 'httpRequest',
      'python': 'javascript',
      'condition': 'conditional',
    };
    return typeMap[backendType] || 'httpRequest';
  };

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
   * 节点选择处理
   */
  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (!isCanvasMode) return;
    setSelectedNode(node);
    setConfigPanelOpen(true);
  }, [isCanvasMode]);

  /**
   * 节点拖拽开始处理
   */
  const onNodeDragStart: NodeDragHandler = useCallback(() => {
    if (!isCanvasMode) {
      setInteractionMode('canvas');
    }
  }, [isCanvasMode, setInteractionMode]);

  /**
   * 视图移动开始时切换为画布模式
   */
  const onMoveStart = useCallback(() => {
    if (!isCanvasMode) {
      setInteractionMode('canvas');
    }
  }, [isCanvasMode, setInteractionMode]);

  /**
   * 添加节点
   */
  const handleAddNode = useCallback((type: string) => {
    if (!isCanvasMode) {
      setInteractionMode('canvas');
      return;
    }

    const newNode: Node = {
      id: `node-${nodeIdCounterRef.current++}`,
      type,
      position: { x: Math.random() * 400, y: Math.random() * 400 },
      data: getDefaultNodeData(type),
    };

    setNodes((nds) => [...nds, newNode]);
  }, [isCanvasMode, setInteractionMode]);

  /**
   * 保存节点配置
   */
  const handleSaveNodeConfig = useCallback((nodeId: string, config: any) => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === nodeId
          ? {
            ...node,
            data: {
              ...node.data,
              ...config,
            },
          }
          : node
      )
    );
    setConfigPanelOpen(false);
  }, []);

  /**
   * 处理拖拽经过画布
   */
  const handleDragOver = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      if (!isCanvasMode) {
        setInteractionMode('canvas');
      }
    },
    [isCanvasMode, setInteractionMode]
  );

  /**
   * 处理将节点拖拽到画布
   */
  const handleDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();

      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect();
      const instance = reactFlowInstance.current;
      const type = event.dataTransfer.getData('application/reactflow');

      if (!reactFlowBounds || !instance || !type) {
        return;
      }

      const instanceAny = instance as {
        screenToFlowPosition?: (pos: { x: number; y: number }) => { x: number; y: number };
        project?: (pos: { x: number; y: number }) => { x: number; y: number };
      };

      const position =
        typeof instanceAny.screenToFlowPosition === 'function'
          ? instanceAny.screenToFlowPosition({ x: event.clientX, y: event.clientY })
          : typeof instanceAny.project === 'function'
            ? instanceAny.project({
              x: event.clientX - reactFlowBounds.left,
              y: event.clientY - reactFlowBounds.top,
            })
            : {
              x: event.clientX - reactFlowBounds.left,
              y: event.clientY - reactFlowBounds.top,
            };

      const newNode: Node = {
        id: `node-${nodeIdCounterRef.current++}`,
        type,
        position,
        data: getDefaultNodeData(type),
      };

      setNodes((nds) => nds.concat(newNode));
      setInteractionMode('canvas');
    },
    [setInteractionMode]
  );

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
      const workflowNodes = nodes.map((node) => ({
        id: node.id,
        type: node.type || 'default',
        name: node.data?.name || node.type || '',
        position: {
          x: node.position.x,
          y: node.position.y,
        },
        data: node.data || {},
      }));

      const workflowEdges = edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        target: edge.target,
        sourceHandle: edge.sourceHandle || undefined,
        label: (edge.label as string | undefined) || null,
        condition: null,
        label: (edge.label as string | undefined) || null,
        condition: null,
      }));

      await updateWorkflow(workflowId, {
        nodes: workflowNodes,
        edges: workflowEdges,
      });

      message.success('工作流保存成功');
    } catch (error: any) {
      console.error('Failed to save workflow:', error);
      message.error(`保存失败: ${error.message}`);
      throw error;
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

    // 先保存工作流
    handleSave().then(() => {
      // 记录开始时间
      setExecutionStartTime(Date.now());

      // 保存成功后执行
      execute(workflowId, {
        initial_input: { message: 'test' },
      });
    }).catch((error) => {
      message.error(`保存失败，无法执行: ${error.message}`);
    });
  }, [workflowId, execute, handleSave]);

  // 初始化时加载工作流
  useEffect(() => {
    if (workflowData && !isInitialized) {
      console.log('Loading workflow:', workflowData.id, workflowData.name);

      // 转换后端数据到前端格式
      const loadedNodes: Node[] = workflowData.nodes.map((node: any) => ({
        id: node.id,
        type: mapBackendNodeTypeToFrontend(node.type),
        position: { x: node.position.x, y: node.position.y },
        data: node.data || {},
      }));

      const loadedEdges: Edge[] = workflowData.edges.map((edge: any) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.condition,
      }));

      setNodes(loadedNodes);
      setEdges(loadedEdges);
      setIsInitialized(true);

      console.log(`Workflow loaded: ${loadedNodes.length} nodes, ${loadedEdges.length} edges`);
    }
  }, [workflowData, isInitialized]);

  // 显示加载状态
  if (isLoadingWorkflow) {
    return (
      <div className={styles.loadingContainer}>
        <Spin size="large" tip="Loading Drafting Room...">
          <div style={{ width: 0, height: 0 }} />
        </Spin>
      </div>
    );
  }

  return (
    <div className={styles.pageContainer}>
      {/* Control Bar */}
      <div className={styles.controlBar}>
        <div className={styles.logoArea}>
          <div className={styles.logoIcon}>
            <span>🏛️</span>
          </div>
          <div className={styles.titleGroup}>
            <span className={styles.title}>Drafting Room</span>
            <span className={styles.subtitle}>Neoclassical Workflow Architect</span>
          </div>
        </div>

        <div className={styles.actionsArea}>
          {/* Status Indicator */}
          <div className={`${styles.statusIndicator} ${wsConnected ? styles.statusConnected : styles.statusDisconnected}`}>
            {wsConnected ? <WifiOutlined /> : <DisconnectOutlined />}
            {wsConnected ? 'SYNC ACTIVE' : 'OFFLINE'}
          </div>

          <Divider type="vertical" style={{ borderColor: 'var(--neo-border)', height: '24px' }} />

          <Button
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={isSaving}
            style={{
              background: 'transparent',
              border: '1px solid var(--neo-border)',
              color: 'var(--neo-text)'
            }}
          >
            Save Blueprint
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleExecute}
            loading={isExecuting}
            style={{
              background: 'var(--neo-gold)',
              borderColor: 'var(--neo-gold)',
              color: '#000',
              fontWeight: 600
            }}
          >
            Execute Protocol
          </Button>
          <ThemeToggle showTooltip />
        </div>
      </div>

      {/* Main Drafting Table */}
      <div className={styles.draftingTable}>
        {/* Left: Palette */}
        <NodePalette onAddNode={handleAddNode} />

        {/* Center: Canvas */}
        <div className={styles.canvasArea} ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onNodeDragStart={onNodeDragStart}
            onMoveStart={onMoveStart}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onInit={(instance) => {
              reactFlowInstance.current = instance;
            }}
            // @ts-ignore - NodeType signature mismatch
            nodeTypes={nodeTypes}
            fitView
            style={{ backgroundColor: 'transparent' }}
            defaultEdgeOptions={defaultEdgeOptions}
            connectionLineStyle={connectionLineStyle}
            nodesDraggable={isCanvasMode}
            nodesConnectable={isCanvasMode}
            elementsSelectable={isCanvasMode}
            panOnDrag={isCanvasMode}
            zoomOnScroll={true}
            zoomOnPinch={true}
            panOnScroll={false}
          >
            <Background color="#333" gap={20} size={1} />
            <Controls />
            <MiniMap
              nodeColor={(node) => {
                // Keep original logic or simplify
                return 'var(--neo-gold)';
              }}
              maskColor="rgba(0, 0, 0, 0.6)"
              style={{
                backgroundColor: 'var(--neo-surface)',
                border: '1px solid var(--neo-border)',
                borderRadius: '4px',
              }}
            />
          </ReactFlow>

          {/* Execution Overlay */}
          <ExecutionOverlay
            nodeStatusMap={nodeStatusMap}
            nodeOutputMap={nodeOutputMap}
            currentNodeId={currentNodeId}
            isExecuting={isExecuting}
            nodes={nodes}
          />
        </div>

        {/* Right: AI Chat */}
        <div className={`${styles.chatPanel} ${chatPanelCollapsed ? styles.chatPanelCollapsed : ''}`}>
          <div className={styles.chatHeader}>
            {!chatPanelCollapsed && <h3 className={styles.chatTitle}>Architect's Log</h3>}
            <Button
              type="text"
              size="small"
              icon={chatPanelCollapsed ? <RightOutlined /> : <LeftOutlined />}
              onClick={() => setChatPanelCollapsed(!chatPanelCollapsed)}
              style={{ color: 'var(--neo-text-2)' }}
            />
          </div>

          {!chatPanelCollapsed && (
            <div className={styles.chatContent}>
              {workflowId ? (
                <WorkflowAIChatWithExecution
                  workflowId={workflowId}
                  onWorkflowUpdate={handleWorkflowUpdate}
                  showWelcome={true}
                />
              ) : (
                <Empty
                  description="Begin by engaging the Architect."
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  style={{ color: 'var(--neo-text-2)', marginTop: '40px' }}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Node Config Drawer */}
      <NodeConfigPanel
        open={configPanelOpen}
        node={selectedNode}
        onClose={() => setConfigPanelOpen(false)}
        onSave={handleSaveNodeConfig}
      />

      {/* Code Export Modal - Keep as is for now or refactor later */}
      <CodeExportModal
        open={exportModalOpen}
        nodes={nodes}
        edges={edges}
        onClose={() => setExportModalOpen(false)}
      />
    </div>
  );
};

export default WorkflowEditorPageWithMutex;
