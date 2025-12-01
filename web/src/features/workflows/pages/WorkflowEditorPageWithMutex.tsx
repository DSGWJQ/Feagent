/**
 * 工作流编辑器页面（带互斥锁）
 *
 * 功能：
 * - 拖拽编辑工作流节点和连线
 * - 保存工作流到后端
 * - 执行工作流（SSE 流式返回）
 * - 聊天/拖拽互斥锁
 */

import { useState, useCallback, useRef, useEffect, type DragEvent } from 'react';
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
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button, message, Empty, Spin } from 'antd';
import { PlayCircleOutlined, SaveOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import { updateWorkflow } from '../api/workflowsApi';
import { useWorkflowExecutionWithCallback } from '../hooks/useWorkflowExecutionWithCallback';
import { useWorkflow } from '@/hooks/useWorkflow';
import type { WorkflowNode, WorkflowEdge } from '../types/workflow';
import NodePalette from '../components/NodePalette';
import NodeConfigPanel from '../components/NodeConfigPanel';
import CodeExportModal from '../components/CodeExportModal';
import WorkflowAIChatWithRAG from '@/shared/components/WorkflowAIChatWithRAG';
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
  const { interactionMode, setInteractionMode, isCanvasMode, isChatMode } = useWorkflowInteraction();

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

  const { workflowData, isLoadingWorkflow, workflowError } = useWorkflow(workflowId);

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
        sourceHandle: edge.sourceHandle || null,
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
      <div style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0a0a0a',
        color: '#fafafa',
      }}>
        <Spin size="large" tip="加载工作流中...">
          <div style={{ width: 0, height: 0 }} />
        </Spin>
      </div>
    );
  }

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      position: 'fixed',
      top: 0,
      left: 0,
      backgroundColor: '#0a0a0a',
      color: '#fafafa',
    }}>
      {/* 头部工具栏 */}
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid #262626',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#141414',
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          }}>
            <span style={{ fontSize: '20px' }}>✨</span>
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#fafafa' }}>
              AI 工作流构建器
            </h1>
            <p style={{ margin: 0, fontSize: '12px', color: '#8c8c8c' }}>
              可视化工作流设计器
              {interactionMode !== 'idle' && (
                <span style={{ marginLeft: 8, color: isChatMode ? '#8b5cf6' : '#3b82f6' }}>
                  ({isChatMode ? '聊天模式' : '画布模式'})
                </span>
              )}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={isSaving}
            style={{
              backgroundColor: '#262626',
              borderColor: '#434343',
              color: '#fafafa'
            }}
          >
            保存
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleExecute}
            loading={isExecuting}
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderColor: 'transparent',
            }}
          >
            运行
          </Button>
        </div>
      </div>

      {/* 主内容区域 */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* 左侧节点调色板 */}
        <NodePalette onAddNode={handleAddNode} />

        {/* React Flow 画布 */}
        <div style={{ flex: 1, position: 'relative', backgroundColor: '#0a0a0a' }} ref={reactFlowWrapper}>
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
            nodeTypes={nodeTypes}
            fitView
            style={{ backgroundColor: '#0a0a0a' }}
            nodesDraggable={isCanvasMode}
            nodesConnectable={isCanvasMode}
            elementsSelectable={isCanvasMode}
            panOnDrag={isCanvasMode}
            zoomOnScroll={true}
            zoomOnPinch={true}
            panOnScroll={false}
          >
            <Background color="#262626" gap={20} />
            <Controls
              style={{
                backgroundColor: '#262626',
                borderColor: '#434343',
                color: '#fafafa'
              }}
            />
            <MiniMap
              nodeColor={(node) => {
                switch (node.type) {
                  case 'textModel':
                    return '#8b5cf6';
                  case 'httpRequest':
                    return '#3b82f6';
                  default:
                    return '#8b5cf6';
                }
              }}
              maskColor="rgba(0, 0, 0, 0.6)"
              style={{
                backgroundColor: '#141414',
                border: '1px solid #262626'
              }}
            />
          </ReactFlow>

          {/* 执行进度覆盖层 */}
          <ExecutionOverlay
            nodeStatusMap={nodeStatusMap}
            nodeOutputMap={nodeOutputMap}
            currentNodeId={currentNodeId}
            isExecuting={isExecuting}
            nodes={nodes}
          />
        </div>

        {/* 右侧AI聊天框 */}
        <div
          data-testid="ai-chat-panel"
          style={{
            width: chatPanelCollapsed ? '48px' : '400px',
            height: '100%',
            backgroundColor: '#141414',
            borderLeft: '1px solid #262626',
            display: 'flex',
            flexDirection: 'column',
            transition: 'width 0.3s ease',
            overflow: 'hidden',
          }}
        >
          {/* 聊天框标题栏 */}
          <div
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid #262626',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: '#1a1a1a',
              minHeight: '48px',
            }}
          >
            {!chatPanelCollapsed && (
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#fafafa' }}>AI 助手</h3>
            )}
            <Button
              type="text"
              size="small"
              icon={chatPanelCollapsed ? <RightOutlined /> : <LeftOutlined />}
              onClick={() => setChatPanelCollapsed(!chatPanelCollapsed)}
              style={{
                marginLeft: chatPanelCollapsed ? 0 : 'auto',
                color: '#fafafa'
              }}
            />
          </div>

          {/* 聊天框内容 */}
          {!chatPanelCollapsed && (
            <div style={{ flex: 1, overflow: 'hidden', backgroundColor: '#141414' }}>
              {workflowId ? (
                <WorkflowAIChatWithRAG
                  workflowId={workflowId}
                  onWorkflowUpdate={handleWorkflowUpdate}
                  showWelcome={true}
                />
              ) : (
                <Empty
                  description="请选择或创建工作流后再使用 AI 对话改写"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* 节点配置面板 */}
      <NodeConfigPanel
        open={configPanelOpen}
        node={selectedNode}
        onClose={() => setConfigPanelOpen(false)}
        onSave={handleSaveNodeConfig}
      />

      {/* 代码导出对话框 */}
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
