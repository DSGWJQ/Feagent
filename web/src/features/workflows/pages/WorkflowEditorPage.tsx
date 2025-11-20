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
import { PlayCircleOutlined, SaveOutlined, CodeOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { updateWorkflow } from '../api/workflowsApi';
import { useWorkflowExecution } from '../hooks/useWorkflowExecution';
import type { WorkflowNode, WorkflowEdge } from '../types/workflow';
import NodePalette from '../components/NodePalette';
import NodeConfigPanel from '../components/NodeConfigPanel';
import CodeExportModal from '../components/CodeExportModal';
import { WorkflowAIChat } from '@/shared/components';
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
} from '../components/nodes';
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
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [chatPanelCollapsed, setChatPanelCollapsed] = useState(false);

  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  let nodeIdCounter = useRef(4); // 从 4 开始，因为已有 1, 2, 3

  // 工作流执行 Hook
  const {
    isExecuting,
    executionLog,
    error: executionError,
    currentNodeId,
    nodeStatusMap,
    nodeOutputMap,
    execute,
  } = useWorkflowExecution();

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

    message.success('工作流已更新');
  }, []);

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
      'database': 'httpRequest', // 暂时映射到 httpRequest
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
    setSelectedNode(node);
    setConfigPanelOpen(true);
  }, []);

  /**
   * 拖拽放置节点
   */
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow');
      if (!type || !reactFlowInstance) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNode: Node = {
        id: `node-${nodeIdCounter.current++}`,
        type,
        position,
        data: getDefaultNodeData(type),
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [reactFlowInstance]
  );

  /**
   * 允许拖拽
   */
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  /**
   * 点击添加节点（从调色板）
   */
  const handleAddNode = useCallback(
    (type: string) => {
      if (!reactFlowInstance) return;

      // 在画布中心添加节点
      const center = reactFlowInstance.getViewport();
      const position = {
        x: -center.x / center.zoom + 400,
        y: -center.y / center.zoom + 300,
      };

      const newNode: Node = {
        id: `node-${nodeIdCounter.current++}`,
        type,
        position,
        data: getDefaultNodeData(type),
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [reactFlowInstance]
  );

  /**
   * 保存节点配置
   */
  const handleSaveNodeConfig = useCallback((nodeId: string, data: any) => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, ...data } } : node
      )
    );
  }, []);

  /**
   * 保存工作流
   */
  const handleSave = useCallback(async () => {
    if (!workflowId) {
      message.error('工作流 ID 不存在');
      throw new Error('工作流 ID 不存在');
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
      // 保存成功后执行
      execute(workflowId, {
        initial_input: { message: 'test' },
      });
    }).catch((error) => {
      message.error(`保存失败，无法执行: ${error.message}`);
    });
  }, [workflowId, execute, handleSave]);

  /**
   * 显示执行错误
   */
  useEffect(() => {
    if (executionError) {
      message.error(`执行失败: ${executionError}`);
    }
  }, [executionError]);

  /**
   * 更新节点状态和输出（根据执行状态）
   */
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const status = nodeStatusMap[node.id];
        const output = nodeOutputMap[node.id];

        if (status || output) {
          return {
            ...node,
            data: {
              ...node.data,
              status: status || node.data.status,
              output: output || node.data.output,
            },
          };
        }
        return node;
      })
    );
  }, [nodeStatusMap, nodeOutputMap]);

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      position: 'fixed',
      top: 0,
      left: 0,
      backgroundColor: '#0a0a0a', // 深黑色背景
      color: '#fafafa', // 浅色文字
    }}>
      {/* 头部工具栏 */}
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid #262626',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#141414', // 深色卡片背景
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
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            icon={<CodeOutlined />}
            onClick={() => setExportModalOpen(true)}
            style={{
              backgroundColor: '#262626',
              borderColor: '#434343',
              color: '#fafafa'
            }}
          >
            导出代码
          </Button>
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
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onInit={setReactFlowInstance}
            fitView
            style={{ backgroundColor: '#0a0a0a' }}
          >
            <Background
              gap={16}
              size={1}
              color="#262626"
              style={{ backgroundColor: '#0a0a0a' }}
            />
            <Controls
              style={{
                button: {
                  backgroundColor: '#262626',
                  borderColor: '#434343',
                  color: '#fafafa'
                }
              }}
            />
            <MiniMap
              nodeColor={(node) => {
                switch (node.type) {
                  case 'textModel':
                    return '#8b5cf6'; // 紫色
                  case 'embeddingModel':
                    return '#3b82f6'; // 蓝色
                  case 'tool':
                    return '#eab308'; // 黄色
                  case 'structuredOutput':
                    return '#10b981'; // 绿色
                  case 'prompt':
                    return '#ec4899'; // 粉色
                  case 'imageGeneration':
                    return '#06b6d4'; // 青色
                  case 'audio':
                    return '#f97316'; // 橙色
                  case 'javascript':
                    return '#8b5cf6'; // 紫色
                  case 'start':
                    return '#a855f7'; // 深紫色
                  case 'end':
                    return '#7c3aed'; // 更深紫色
                  case 'conditional':
                    return '#ec4899'; // 粉色
                  case 'httpRequest':
                    return '#3b82f6'; // 蓝色
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
        </div>

        {/* 右侧AI聊天框 */}
        <div
          data-testid="ai-chat-panel"
          style={{
            width: chatPanelCollapsed ? '48px' : '400px',
            height: '100%',
            backgroundColor: '#141414', // 深色背景
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
              aria-label={chatPanelCollapsed ? '展开' : '折叠'}
              style={{
                marginLeft: chatPanelCollapsed ? 0 : 'auto',
                color: '#fafafa'
              }}
            />
          </div>

          {/* 聊天框内容 */}
          {!chatPanelCollapsed && (
            <div style={{ flex: 1, overflow: 'hidden', backgroundColor: '#141414' }}>
              <WorkflowAIChat
                workflowId={workflowId || 'default'}
                onWorkflowUpdate={handleWorkflowUpdate}
                showWelcome={true}
              />
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

      {/* 执行日志面板 */}
      {isExecuting || executionLog.length > 0 ? (
        <div
          style={{
            position: 'absolute',
            right: 0,
            top: 64,
            width: '400px',
            height: 'calc(100vh - 64px)',
            backgroundColor: '#141414',
            borderLeft: '1px solid #262626',
            padding: '16px',
            overflowY: 'auto',
          }}
        >
          <h3 style={{ color: '#fafafa' }}>执行日志</h3>
          {currentNodeId && (
            <div style={{ marginBottom: '8px', color: '#3b82f6' }}>
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
                  backgroundColor: '#1a1a1a',
                  borderRadius: '4px',
                  border: '1px solid #262626',
                }}
              >
                <div style={{ fontWeight: 'bold', color: '#fafafa' }}>
                  {entry.node_type} ({entry.node_id})
                </div>
                <pre style={{ margin: 0, fontSize: '12px', color: '#8c8c8c' }}>
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

