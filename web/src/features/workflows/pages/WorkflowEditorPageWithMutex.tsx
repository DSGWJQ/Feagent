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
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button, message, Empty, Spin, Modal, Alert, Drawer, Input, Collapse, Typography } from 'antd';
import { PlayCircleOutlined, SaveOutlined, LeftOutlined, RightOutlined, UndoOutlined, RedoOutlined, WarningOutlined, HistoryOutlined, ExperimentOutlined, SearchOutlined, FileTextOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ResearchResultDisplay, type ResearchResult } from '@/components/ResearchResultDisplay';
import { useRunReplay, type RunEvent } from '@/hooks/useRunReplay';
import { useResearchPlan, type ResearchPlanDTO, type CompileResponse } from '@/hooks/useResearchPlan';
import { API_BASE_URL } from '@/services/api';
import { useWorkflowHistory } from '../hooks/useWorkflowHistory';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useConflictResolution, type Conflict } from '../hooks/useConflictResolution';
import { wouldCreateCycle } from '../utils/graphUtils';
import { confirmRunSideEffect, updateWorkflow } from '../api/workflowsApi';
import { useWorkflowExecutionWithCallback } from '../hooks/useWorkflowExecutionWithCallback';
import { useWorkflow } from '@/hooks/useWorkflow';
import type { Workflow, WorkflowNode, WorkflowEdge } from '../types/workflow';
import NodePalette from '../components/NodePalette';
import NodeConfigPanel from '../components/NodeConfigPanel';
import CodeExportModal from '../components/CodeExportModal';
import WorkflowAIChatWithExecution from '@/shared/components/WorkflowAIChatWithExecution';
import { useWorkflowInteraction } from '../contexts/WorkflowInteractionContext';
import { NeoButton } from '@/shared/components/common/NeoButton';
import {
  StartNode,
  EndNode,
  HttpRequestNode,
  TextModelNode,
  ConditionalNode,
  JavaScriptNode,
  PythonNode,
  TransformNode,
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
import { Divider } from 'antd';
import styles from '../styles/sim-editor.module.css';


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
  python: PythonNode,
  transform: TransformNode,
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
 * 初始节点（空白画布）
 */
const initialNodes: Node[] = [];

const initialEdges: Edge[] = [];

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
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isCanvasMode } = useWorkflowInteraction();
  const disableRunPersistence =
    (import.meta.env.VITE_DISABLE_RUN_PERSISTENCE ?? 'false').toString().toLowerCase() === 'true';
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_, setInteractionMode] = useState('idle');

  // Execution input (JSON) is user-configurable so deterministic workflows can run end-to-end.
  const [executionInputModalOpen, setExecutionInputModalOpen] = useState(false);
  const [executionInputJson, setExecutionInputJson] = useState<string>(() =>
    JSON.stringify(
      {
        data: [
          { name: ' Alice ', email: ' alice@example.com ', age: ' 30 ', amount: '12.50' },
          { name: 'Alice', email: 'alice@example.com', age: '30', amount: '12.50' },
          { name: '  Bob', email: '', age: 'not_a_number', amount: '$9' },
          { name: 'Carol', email: null, age: '  42', amount: ' 0 ' },
        ],
      },
      null,
      2
    )
  );

  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [edgeConfigOpen, setEdgeConfigOpen] = useState(false);
  const [edgeConditionDraft, setEdgeConditionDraft] = useState('');
  const [chatPanelCollapsed, setChatPanelCollapsed] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [nodeIdCounter, setNodeIdCounter] = useState(4);

  // Step F.7: ResearchResult 和 Run 状态
  const [researchResult, setResearchResult] = useState<ResearchResult | null>(null);
  const [resultDrawerOpen, setResultDrawerOpen] = useState(false);
  const [lastRunId, setLastRunId] = useState<string | null>(null);

  const runIdStorageKey = useMemo(() => `workflow:lastRunId:${workflowId}`, [workflowId]);

  // MVP Step 2: 刷新后可恢复 run_id（用于 Replay 复原同一成功/失败结论）
  useEffect(() => {
    const stored = localStorage.getItem(runIdStorageKey);
    setLastRunId(stored && stored.trim() ? stored : null);
  }, [runIdStorageKey]);

  useEffect(() => {
    if (!lastRunId) {
      localStorage.removeItem(runIdStorageKey);
      return;
    }
    localStorage.setItem(runIdStorageKey, lastRunId);
  }, [lastRunId, runIdStorageKey]);

  // MVP Step 1: Research Plan 状态
  const [planDrawerOpen, setPlanDrawerOpen] = useState(false);
  const [researchGoal, setResearchGoal] = useState('');
  const [compileWarnings, setCompileWarnings] = useState<string[]>([]);

  /**
   * MVP Step 3: 统一 ResearchResult 提取函数
   * 优先级：RESEARCH_END 输出 > research_result 字段 > result 字段 > 原始对象
   * 用于执行完成回调和 Replay 事件处理
   */
  const extractResearchResult = useCallback((value: unknown): ResearchResult | null => {
    if (!value || typeof value !== 'object') return null;
    const obj = value as Record<string, unknown>;

    // 构建候选列表（按优先级，覆盖常见字段名）
    const candidates: unknown[] = [
      obj.research_result,
      typeof obj.result === 'object' ? (obj.result as Record<string, unknown>)?.research_result : null,
      obj.result,
      obj.final_result,
      obj.output,
      obj.data,
      obj,
    ];

    for (const candidate of candidates) {
      if (!candidate || typeof candidate !== 'object') continue;
      const rr = candidate as Record<string, unknown>;
      // 验证 ResearchResult 结构
      if (typeof rr.question === 'string' && Array.isArray(rr.claims)) {
        return rr as unknown as ResearchResult;
      }
    }
    return null;
  }, []);

  // Step F.8: Replay hook - MVP Step 3: 增强事件处理
  // 使用 ref 防止 workflow_complete + RESEARCH_END 双重触发
  const resultHandledRef = useRef(false);
  const [replayEvents, setReplayEvents] = useState<RunEvent[]>([]);

  const {
    isReplaying,
    startReplay,
    stopReplay,
  } = useRunReplay({
    runId: lastRunId ?? '',
    onEvent: (event: RunEvent) => {
      setReplayEvents((prev) => [...prev, event]);
      // 处理成功完成事件（防止双重触发）
      if ((event.type === 'workflow_complete' || event.type === 'RESEARCH_END') && !resultHandledRef.current) {
        const rr = extractResearchResult(event);
        if (rr) {
          resultHandledRef.current = true;
          setResearchResult(rr);
          setResultDrawerOpen(true);
        }
      }
      // 处理失败事件 - 允许用户查看部分结果或错误
      if (event.type === 'workflow_error') {
        const rr = extractResearchResult(event);
        if (rr) {
          setResearchResult(rr);
          setResultDrawerOpen(true);
          message.warning('Research completed with errors');
        } else {
          // 规范化错误消息
          const errorMsg = typeof event.error === 'string'
            ? event.error
            : (event.detail ?? event.message ?? 'Unknown error');
          message.error(`Workflow failed: ${errorMsg}`);
        }
      }
    },
    onComplete: () => {
      message.success('Replay completed');
      resultHandledRef.current = false; // 重置以便下次 replay
    },
    onError: (err) => {
      message.error(`Replay failed: ${err.message}`);
      resultHandledRef.current = false;
    },
  });

  const handleStartReplay = useCallback(async () => {
    setReplayEvents([]);
    await startReplay();
  }, [startReplay]);

  // 本地草稿模式：不从后端加载数据
  const isLocalDraft = workflowId === 'local-draft' || workflowId === 'demo-draft';

  const { workflowData, isLoadingWorkflow, workflowError } = useWorkflow(
    isLocalDraft ? '' : workflowId
  );

  // MVP Step 1: Research Plan hook
  const workflowProjectId =
    workflowData &&
    typeof (workflowData as Record<string, unknown>).project_id === 'string'
      ? ((workflowData as Record<string, unknown>).project_id as string)
      : undefined;
  const effectiveProjectId = searchParams.get('projectId') ?? workflowProjectId ?? null;

  const {
    createRun: createResearchRun,
    generatePlan,
    compilePlan,
    cancelGeneration,
    reset: resetResearchPlan,
    plan: researchPlan,
    isGenerating,
    isCompiling,
    thinkingContent,
    error: researchError,
  } = useResearchPlan({
    workflowId,
    projectId: effectiveProjectId,
    onPlanGenerated: (plan) => {
      message.success('Research plan generated!');
    },
    onCompiled: (response) => {
      // Update canvas with new nodes/edges
      handleWorkflowUpdate({
        id: response.id,
        name: response.name,
        description: response.description,
        nodes: response.nodes,
        edges: response.edges,
      });
      setCompileWarnings(response.warnings);
      if (response.warnings.length > 0) {
        message.warning(`Plan compiled with ${response.warnings.length} warning(s)`);
      } else {
        message.success('Plan compiled and applied to canvas!');
      }
      setPlanDrawerOpen(false);
    },
    onError: (err) => {
      message.error(`Research plan error: ${err.message}`);
    },
  });

  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);
  const pendingFitViewRef = useRef(false);
  const nodeIdCounterRef = useRef(4);

  const [executionStartTime, setExecutionStartTime] = useState<number | null>(null);

  const requestFitView = useCallback(() => {
    pendingFitViewRef.current = true;
    requestAnimationFrame(() => {
      const instance = reactFlowInstance.current;
      if (!instance?.fitView) return;
      instance.fitView({ padding: 0.2, duration: 300 });
      pendingFitViewRef.current = false;
    });
  }, []);

  // Refs for synchronous access to current state
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);

  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);
  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);

  // Undo/Redo history management
  const {
    pushSnapshot,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
  } = useWorkflowHistory({ maxHistorySize: 50, debounceMs: 300 });

  // Conflict resolution for concurrent editing
  const {
    conflicts,
    hasConflicts,
    detectConflict,
    resolveConflict,
    resolveAllConflicts,
    clearConflicts,
  } = useConflictResolution({
    defaultStrategy: 'ask',
    onConflictDetected: (conflict) => {
      message.warning(`检测到冲突: ${conflict.elementType === 'node' ? '节点' : '连线'} ${conflict.elementId}`);
    },
  });

  // PRD-030: side-effect confirm modal
  const [pendingConfirm, setPendingConfirm] = useState<null | {
    runId: string;
    workflowId?: string;
    nodeId?: string;
    confirmId: string;
  }>(null);
  const [confirmSubmitting, setConfirmSubmitting] = useState(false);

  const submitConfirmDecision = useCallback(
    async (decision: 'allow' | 'deny') => {
      if (!pendingConfirm) return;
      setConfirmSubmitting(true);
      try {
        await confirmRunSideEffect(pendingConfirm.runId, {
          confirm_id: pendingConfirm.confirmId,
          decision,
        });
        setPendingConfirm(null);
        message.success(decision === 'allow' ? '已允许执行外部副作用' : '已拒绝执行外部副作用');
      } catch (err: any) {
        console.warn('confirm side effect failed', err);
        message.error(`确认失败: ${err?.message || '未知错误'}`);
      } finally {
        setConfirmSubmitting(false);
      }
    },
    [pendingConfirm]
  );

  const {
    execute,
    isExecuting,
    currentNodeId,
    executionLog,
    error: executionError,
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

      // Step F.7: 提取并显示 ResearchResult
      const rr = extractResearchResult(finalResult);
      if (rr) {
        setResearchResult(rr);
        setResultDrawerOpen(true);
      }

      message.success(
        summary.success
          ? `工作流执行成功！共执行 ${totalNodes} 个节点`
          : `工作流执行完成！成功 ${successNodes} 个，失败 ${errorNodes} 个`
      );
    },
    onConfirmRequired: ({ runId, workflowId, nodeId, confirmId }) => {
      setPendingConfirm((prev) => {
        if (prev && prev.confirmId === confirmId) return prev;
        return { runId, workflowId, nodeId, confirmId };
      });
    },
  });

  // Memoize edge options to avoid unnecessary re-renders
  const defaultEdgeOptions = useMemo(() => ({
    style: {
      stroke: 'var(--color-neutral-600)',
      strokeWidth: 2,
    },
  }), []);

  // PRD-050: diff baseline = current canvas state (canvas is master)
  const diffBaselineWorkflow = useMemo<Workflow | null>(() => {
    if (!workflowId) return null;
    const wf: Workflow = {
      id: workflowId,
      name: workflowData?.name ?? '',
      description: workflowData?.description ?? '',
      nodes: (nodes ?? []).map((n: any) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data ?? {},
      })),
      edges: (edges ?? []).map((e: any) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        label: e.label,
        condition: e?.data?.condition ?? null,
      })),
      status: (workflowData as any)?.status ?? ('draft' as any),
      created_at: (workflowData as any)?.created_at ?? '',
      updated_at: (workflowData as any)?.updated_at ?? '',
    };
    return wf;
  }, [workflowId, workflowData, nodes, edges]);

  const connectionLineStyle = useMemo(() => ({
    stroke: 'var(--color-primary-400)',
    strokeWidth: 2,
  }), []);

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
      data: {
        ...(node.data || {}),
        // Ensure common fields exist for custom node renderers/config panels.
        name: node.name ?? node.data?.name ?? '',
        label: node.name ?? node.data?.label ?? node.data?.name ?? '',
      },
    }));

    const newEdges: Edge[] = workflow.edges.map((edge: any) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.condition,
      data: {
        condition: edge.condition ?? null,
      },
    }));

    setNodes(newNodes);
    setEdges(newEdges);
    clearHistory();
    pushSnapshot(newNodes, newEdges, { immediate: true });
    onWorkflowUpdate(workflow);

    message.success('工作流已更新');
    requestFitView();
  }, [clearHistory, onWorkflowUpdate, pushSnapshot]);

  /**
   * 映射后端节点类型到前端节点类型
   */
  const mapBackendNodeTypeToFrontend = (backendType: string): string => {
    const trimmed = backendType?.trim();
    if (!trimmed) {
      return 'default';
    }

    // If backend already matches a registered ReactFlow node type, keep it.
    if (trimmed in nodeTypes) {
      return trimmed;
    }

    // Backward-compatible aliases / legacy naming from backend or older frontends.
    const typeMap: Record<string, string> = {
      http: 'httpRequest',
      llm: 'textModel',
      transform: 'javascript',
      python: 'javascript',
      condition: 'conditional',
    };

    return typeMap[trimmed] || 'default';
  };

  /**
   * 节点变化处理（带历史记录）
   */
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      const shouldSnapshot = changes.some(
        (c) => c.type === 'add' || c.type === 'remove' || c.type === 'position'
      );
      setNodes((nds) => {
        const nextNodes = applyNodeChanges(changes, nds);
        if (shouldSnapshot) {
          pushSnapshot(nextNodes, edgesRef.current);
        }
        return nextNodes;
      });
    },
    [pushSnapshot]
  );

  /**
   * 边变化处理（带历史记录）
   */
  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      const shouldSnapshot = changes.some(
        (c) => c.type === 'add' || c.type === 'remove'
      );
      setEdges((eds) => {
        const nextEdges = applyEdgeChanges(changes, eds);
        if (shouldSnapshot) {
          pushSnapshot(nodesRef.current, nextEdges);
        }
        return nextEdges;
      });
    },
    [pushSnapshot]
  );

  /**
   * 连线处理（带循环检测）
   */
  const onConnect: OnConnect = useCallback(
    (params) => {
      const source = params.source;
      const target = params.target;

      if (!source || !target) return;

      // Check for cycle using current edges
      if (wouldCreateCycle(edgesRef.current, source, target)) {
        message.error('无法创建连线：这将导致循环依赖');
        return;
      }

      // Apply change and push snapshot after
      setEdges((eds) => {
        const nextEdges = addEdge(
          {
            ...params,
            data: { condition: null },
          },
          eds
        );
        pushSnapshot(nodesRef.current, nextEdges);
        return nextEdges;
      });
    },
    [pushSnapshot]
  );

  const handleEdgeClick = useCallback(
    (_: unknown, edge: Edge) => {
      setSelectedEdge(edge);
      setEdgeConditionDraft(String((edge as any)?.data?.condition ?? ''));
      setEdgeConfigOpen(true);
      setConfigPanelOpen(false);
    },
    []
  );

  const handleSaveEdgeCondition = useCallback(() => {
    if (!selectedEdge) return;

    const nextCondition = edgeConditionDraft.trim();
    const normalizedCondition = nextCondition ? nextCondition : null;

    setEdges((eds) => {
      const nextEdges = eds.map((edge) => {
        if (edge.id !== selectedEdge.id) return edge;
        return {
          ...edge,
          label: normalizedCondition,
          data: { ...(edge.data ?? {}), condition: normalizedCondition },
        };
      });
      pushSnapshot(nodesRef.current, nextEdges);
      return nextEdges;
    });

    message.success('Edge condition 已更新');
    setEdgeConfigOpen(false);
  }, [edgeConditionDraft, pushSnapshot, selectedEdge]);

  /**
   * Undo handler
   */
  const handleUndo = useCallback(() => {
    const snapshot = undo();
    if (snapshot) {
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
      message.info('已撤销');
    }
  }, [undo]);

  /**
   * Redo handler
   */
  const handleRedo = useCallback(() => {
    const snapshot = redo();
    if (snapshot) {
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
      message.info('已重做');
    }
  }, [redo]);

  /**
   * Delete selected elements handler (for keyboard shortcut)
   * Returns true if something was deleted
   */
  const handleDeleteSelected = useCallback((): boolean => {
    // Get selected nodes and edges using refs
    const selectedNodes = nodesRef.current.filter((n) => n.selected);
    const selectedEdges = edgesRef.current.filter((e) => e.selected);

    if (selectedNodes.length === 0 && selectedEdges.length === 0) return false;

    const nodeIds = new Set(selectedNodes.map((n) => n.id));
    const edgeIds = new Set(selectedEdges.map((e) => e.id));

    // Calculate next state
    const nextNodes = nodesRef.current.filter((n) => !nodeIds.has(n.id));
    const nextEdges = edgesRef.current.filter(
      (e) =>
        !edgeIds.has(e.id) &&
        !nodeIds.has(e.source) &&
        !nodeIds.has(e.target)
    );

    // Apply changes
    setNodes(nextNodes);
    setEdges(nextEdges);
    pushSnapshot(nextNodes, nextEdges);
    return true;
  }, [pushSnapshot]);

  /**
   * Handle conflict resolution modal
   */
  const handleResolveConflict = useCallback(
    (conflictId: string, strategy: 'local' | 'remote' | 'merge') => {
      const conflict = conflicts.find((c) => c.id === conflictId);
      const resolution = resolveConflict(conflictId, strategy);
      if (!resolution || !conflict) return;

      // Handle deletion case (result is null)
      if (resolution.result == null) {
        if (conflict.elementType === 'node') {
          const nextNodes = nodesRef.current.filter((n) => n.id !== conflict.elementId);
          const nextEdges = edgesRef.current.filter(
            (e) => e.source !== conflict.elementId && e.target !== conflict.elementId
          );
          setNodes(nextNodes);
          setEdges(nextEdges);
          pushSnapshot(nextNodes, nextEdges);
        } else {
          const nextEdges = edgesRef.current.filter((e) => e.id !== conflict.elementId);
          setEdges(nextEdges);
          pushSnapshot(nodesRef.current, nextEdges);
        }
        message.success('冲突已解决（已删除）');
        return;
      }

      // Apply the resolution (update case)
      if (conflict.elementType === 'node') {
        const resultNode = resolution.result as Node;
        const nextNodes = nodesRef.current.map((n) => (n.id === resultNode.id ? resultNode : n));
        setNodes(nextNodes);
        pushSnapshot(nextNodes, edgesRef.current);
      } else {
        const resultEdge = resolution.result as Edge;
        const nextEdges = edgesRef.current.map((e) => (e.id === resultEdge.id ? resultEdge : e));
        setEdges(nextEdges);
        pushSnapshot(nodesRef.current, nextEdges);
      }
      message.success('冲突已解决');
    },
    [conflicts, pushSnapshot, resolveConflict]
  );

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

    const nextNodes = nodesRef.current.concat(newNode);
    setNodes(nextNodes);
    pushSnapshot(nextNodes, edgesRef.current);
  }, [isCanvasMode, pushSnapshot, setInteractionMode]);

  /**
   * 保存节点配置
   */
  const handleSaveNodeConfig = useCallback((nodeId: string, config: any) => {
    const nextNodes = nodesRef.current.map((node) =>
      node.id === nodeId
        ? {
          ...node,
          data: {
            ...node.data,
            ...config,
          },
        }
        : node
    );
    setNodes(nextNodes);
    pushSnapshot(nextNodes, edgesRef.current);
    setConfigPanelOpen(false);
  }, [pushSnapshot]);

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

      const nextNodes = nodesRef.current.concat(newNode);
      setNodes(nextNodes);
      pushSnapshot(nextNodes, edgesRef.current);
      setInteractionMode('canvas');
    },
    [pushSnapshot, setInteractionMode]
  );

  /**
   * 保存工作流
   * Returns true on success, false on failure
   */
  const handleSave = useCallback(async (): Promise<boolean> => {
    if (!workflowId) {
      message.error('工作流 ID 不存在');
      return false;
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
        sourceHandle: edge.sourceHandle || undefined,
        label: (edge.label as string | undefined) || null,
        condition:
          (edge as any)?.data?.condition ?? (typeof edge.label === 'string' ? edge.label : null),
      }));

      await updateWorkflow(workflowId, {
        nodes: workflowNodes,
        edges: workflowEdges,
      });

      message.success('工作流保存成功');
      return true;
    } catch (error: any) {
      console.error('Failed to save workflow:', error);

      const detail = error?.response?.data?.detail;
      if (detail && typeof detail === 'object' && Array.isArray((detail as any).errors)) {
        const payload = detail as any;
        Modal.error({
          title: '保存失败：工作流校验未通过',
          width: 760,
          content: (
            <div>
              <div style={{ marginBottom: 8 }}>
                {payload.message || 'Workflow validation failed'}
              </div>
              <div style={{ maxHeight: 360, overflow: 'auto' }}>
                <ul style={{ paddingLeft: 18, margin: 0 }}>
                  {payload.errors.map((errItem: any, idx: number) => (
                    <li key={`${errItem.code ?? 'error'}_${idx}`}>
                      <code>{errItem.code ?? 'error'}</code>
                      {errItem.path ? <span> @ {errItem.path}</span> : null}
                      {errItem.message ? <span>: {errItem.message}</span> : null}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ),
        });
        message.error('保存失败：工作流校验未通过');
      } else if (typeof detail === 'string' && detail.trim()) {
        message.error(`保存失败: ${detail}`);
      } else {
        message.error(`保存失败: ${error?.message || '未知错误'}`);
      }
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [workflowId, nodes, edges]);

  // Keyboard shortcuts
  useKeyboardShortcuts(
    {
      onSave: handleSave,
      onUndo: handleUndo,
      onRedo: handleRedo,
      onDelete: handleDeleteSelected,
    },
    {
      enabled: !isExecuting && isCanvasMode,
      containerRef: reactFlowWrapper,
    }
  );

  /**
   * MVP Step 1: 生成 Research Plan
   */
  const handleGenerateResearchPlan = useCallback(async () => {
    if (!researchGoal.trim()) {
      message.warning('Please enter a research goal');
      return;
    }

    // Create run for unified session tracking
    let runIdForSession: string | null = null;
    if (!disableRunPersistence && effectiveProjectId) {
      runIdForSession = await createResearchRun();
      if (runIdForSession) {
        setLastRunId(runIdForSession);
        message.info(`Session started (${runIdForSession.slice(0, 8)}...)`);
      }
    }

    await generatePlan(researchGoal, runIdForSession);
  }, [researchGoal, effectiveProjectId, disableRunPersistence, createResearchRun, generatePlan]);

  /**
   * MVP Step 1: 编译 Plan 到画布
   * 强化：如果没有 run 则先创建，确保 compile 事件落库
   */
  const handleCompilePlan = useCallback(async () => {
    if (!researchPlan) {
      message.warning('No research plan to compile');
      return;
    }

    // 确保有 run_id（如果没有则创建）
    let runIdForCompile = lastRunId;
    if (!disableRunPersistence && !runIdForCompile && effectiveProjectId) {
      runIdForCompile = await createResearchRun();
      if (runIdForCompile) {
        setLastRunId(runIdForCompile);
        message.info(`Session started (${runIdForCompile.slice(0, 8)}...)`);
      }
    }

    await compilePlan(researchPlan, runIdForCompile);
  }, [researchPlan, compilePlan, lastRunId, effectiveProjectId, disableRunPersistence, createResearchRun]);

  /**
   * 执行工作流 (Step F.7: 创建 Run 后执行)
   * MVP Step 2: 复用 lastRunId 保证 plan/compile/execute 全链路一致
   */
  const handleExecute = useCallback(async () => {
    if (!workflowId) {
      message.error('工作流 ID 不存在');
      return;
    }

    // 先保存工作流
    const saveSuccess = await handleSave();
    if (!saveSuccess) {
      message.error('保存失败，无法执行');
      return;
    }

    let initialInput: any = {};
    const trimmed = executionInputJson.trim();
    if (trimmed) {
      try {
        initialInput = JSON.parse(trimmed);
      } catch {
        message.error('Execution Input 必须是合法 JSON');
        return;
      }
    }

    // 记录开始时间
    setExecutionStartTime(Date.now());

    // MVP Step 2: 优先复用 lastRunId (来自 plan/compile 流程)
    let runId: string | undefined = lastRunId ?? undefined;

    // 如果没有 lastRunId，且启用 run 持久化且有 projectId，则尝试创建新的 Run。
    // 否则降级为 legacy execute（不带 run_id），保证 demo 可跑通。
    if (!runId && !disableRunPersistence && effectiveProjectId) {
      try {
        const token = localStorage.getItem('authToken');
        const headers: HeadersInit = { 'Content-Type': 'application/json' };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        const runRes = await fetch(
          `${API_BASE_URL}/projects/${effectiveProjectId}/workflows/${workflowId}/runs`,
          { method: 'POST', headers, body: JSON.stringify({}) }
        );
        if (runRes.ok) {
          const runData = await runRes.json();
          runId = runData.id;
          setLastRunId(runId);
          message.info(`Session started (${runId?.slice(0, 8) ?? '?'}...)`);
        } else {
          const errData = await runRes.json().catch(() => ({}));
          console.warn('Failed to create run:', { status: runRes.status, errData });
          message.warning('无法创建 Run：将以 legacy 模式执行（无 run session）');
        }
      } catch (err) {
        console.warn('Failed to create run:', err);
        message.warning('无法创建 Run：将以 legacy 模式执行（无 run session）');
      }
    }

    // 执行工作流
    execute(
      workflowId,
      runId && !disableRunPersistence
        ? { initial_input: initialInput, run_id: runId }
        : { initial_input: initialInput }
    );
  }, [workflowId, execute, handleSave, effectiveProjectId, lastRunId, disableRunPersistence, executionInputJson]);

  // 初始化时加载工作流
  useEffect(() => {
    if (isLocalDraft && !isInitialized) {
      setIsInitialized(true);
      return;
    }

    if (workflowData && !isInitialized) {
      console.log('Loading workflow:', workflowData.id, workflowData.name);

      // 转换后端数据到前端格式
      const loadedNodes: Node[] = workflowData.nodes.map((node: any) => ({
        id: node.id,
        type: mapBackendNodeTypeToFrontend(node.type),
        position: { x: node.position.x, y: node.position.y },
        data: {
          ...(node.data || {}),
          name: node.name ?? node.data?.name ?? '',
          label: node.name ?? node.data?.label ?? node.data?.name ?? '',
        },
      }));

      const loadedEdges: Edge[] = workflowData.edges.map((edge: any) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.condition,
        data: {
          condition: edge.condition ?? null,
        },
      }));

      setNodes(loadedNodes);
      setEdges(loadedEdges);
      clearHistory();
      pushSnapshot(loadedNodes, loadedEdges, { immediate: true });
      setIsInitialized(true);

      console.log(`Workflow loaded: ${loadedNodes.length} nodes, ${loadedEdges.length} edges`);
      requestFitView();
    }
  }, [clearHistory, pushSnapshot, workflowData, isInitialized]);

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
            sim
          </div>
          <div className={styles.titleGroup}>
            <span className={styles.title}>Workflow Studio</span>
            <span className={styles.subtitle}>v1.0.0</span>
          </div>
        </div>

        <div className={styles.actionsArea}>
          {/* Undo/Redo Buttons */}
          <Button
            type="text"
            icon={<UndoOutlined />}
            onClick={handleUndo}
            disabled={!canUndo || isExecuting}
            title="撤销 (Ctrl+Z)"
          />
          <Button
            type="text"
            icon={<RedoOutlined />}
            onClick={handleRedo}
            disabled={!canRedo || isExecuting}
            title="重做 (Ctrl+Y)"
          />

          <Divider type="vertical" style={{ borderColor: '#e5e7eb', height: '20px' }} />

          <NeoButton
            variant="secondary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={isSaving}
            disabled={isExecuting || isGenerating || isCompiling}
            data-testid="workflow-save-button"
          >
            Save
          </NeoButton>
          <NeoButton
            variant="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleExecute}
            loading={isExecuting}
            disabled={isGenerating || isCompiling}
            data-testid="workflow-run-button"
          >
            Run
          </NeoButton>

          <NeoButton
            variant="secondary"
            icon={<FileTextOutlined />}
            onClick={() => setExecutionInputModalOpen(true)}
            disabled={isExecuting || isGenerating || isCompiling}
            data-testid="workflow-input-button"
            title="Configure execution input (JSON)"
          >
            Input
          </NeoButton>

          {/* MVP Step 1: Research Plan 按钮 */}
          <NeoButton
            variant="secondary"
            icon={<SearchOutlined />}
            onClick={() => setPlanDrawerOpen(true)}
            disabled={isExecuting || isGenerating || isCompiling}
          >
            Research
          </NeoButton>

          {/* Step F.8: Replay 按钮 - 始终显示，无 run 时禁用 */}
          <NeoButton
            variant="secondary"
            icon={<HistoryOutlined />}
            onClick={() => (isReplaying ? stopReplay() : handleStartReplay())}
            loading={isReplaying}
            disabled={!lastRunId || isExecuting || isGenerating || isCompiling}
            title={!lastRunId ? 'No run session to replay' : `Replay run ${lastRunId.slice(0, 8)}`}
            data-testid="replay-run-button"
          >
            {isReplaying ? 'Stop' : 'Replay'}
          </NeoButton>

          {/* MVP Step 2: Run ID 显示 */}
          {lastRunId && (
            <span
              style={{
                fontSize: 11,
                color: 'var(--neo-text-2)',
                marginLeft: 8,
                padding: '2px 6px',
                background: 'var(--neo-surface-alt)',
                borderRadius: 4,
                fontFamily: 'monospace',
              }}
              title={`Current Run: ${lastRunId}`}
            >
              {lastRunId.slice(0, 12)}
            </span>
          )}

          {/* E2E Test: Execution Status Indicator */}
           <span
             data-testid="workflow-execution-status"
             data-status={isExecuting ? 'running' : (executionError ? 'idle' : (lastRunId ? 'completed' : 'idle'))}
             style={{ display: 'none' }}
           />
        </div>
      </div>

      <Modal
        title="Execution Input (JSON)"
        open={executionInputModalOpen}
        onCancel={() => setExecutionInputModalOpen(false)}
        onOk={() => setExecutionInputModalOpen(false)}
        okText="Done"
        cancelText="Cancel"
        width={760}
        destroyOnClose={false}
      >
        <Alert
          type="info"
          showIcon
          message="该 JSON 会作为 workflow initial_input 传入 Start 节点，并流入后续节点（input1）。"
          style={{ marginBottom: 12 }}
        />
        <Input.TextArea
          data-testid="workflow-input-textarea"
          value={executionInputJson}
          onChange={(e) => setExecutionInputJson(e.target.value)}
          autoSize={{ minRows: 12, maxRows: 28 }}
          placeholder='例如：{ \"data\": [ { \"name\": \" Alice \", \"age\": \"30\" } ] }'
        />
      </Modal>

      {replayEvents.length > 0 && (
        <div
          data-testid="replay-event-list"
          style={{
            position: 'fixed',
            right: 16,
            bottom: 16,
            width: 360,
            maxHeight: 240,
            overflow: 'auto',
            background: 'rgba(10, 10, 10, 0.85)',
            color: '#fff',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 8,
            padding: 8,
            zIndex: 1000,
            pointerEvents: 'none',
            fontFamily: 'monospace',
            fontSize: 12,
          }}
        >
          {replayEvents.slice(-200).map((event, index) => (
            <div
              key={`${index}-${event.type}`}
              data-testid={`execution-log-entry-${index}`}
              style={{ padding: '2px 0' }}
            >
              {event.type}
              {event.node_id ? `:${String(event.node_id).slice(0, 8)}` : ''}
            </div>
          ))}
        </div>
      )}

      {/* Main Drafting Table */}
      <div className={styles.draftingTable}>
        {/* Left: Palette */}
        <NodePalette onAddNode={handleAddNode} />

        {/* Center: Canvas */}
        <div className={styles.canvasArea} ref={reactFlowWrapper} data-testid="workflow-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onEdgeClick={handleEdgeClick}
            onNodeDragStart={onNodeDragStart}
            onMoveStart={onMoveStart}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onInit={(instance) => {
              reactFlowInstance.current = instance;
              if (pendingFitViewRef.current) {
                requestAnimationFrame(() => {
                  reactFlowInstance.current?.fitView?.({ padding: 0.2, duration: 300 });
                  pendingFitViewRef.current = false;
                });
              }
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
            <NeoButton
              variant="ghost"
              size="small"
              icon={chatPanelCollapsed ? <RightOutlined /> : <LeftOutlined />}
              onClick={() => setChatPanelCollapsed(!chatPanelCollapsed)}
            />

          </div>

          {!chatPanelCollapsed && (
            <div className={styles.chatContent}>
              {workflowId ? (
                <WorkflowAIChatWithExecution
                  workflowId={workflowId}
                  onWorkflowUpdate={handleWorkflowUpdate}
                  showWelcome={true}
                  diffBaselineWorkflow={diffBaselineWorkflow}
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

      {/* Edge Condition Drawer */}
      <Drawer
        title="Edge Condition"
        open={edgeConfigOpen}
        onClose={() => setEdgeConfigOpen(false)}
        width={420}
      >
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          条件表达式用于控制目标节点是否执行（空值表示无条件通过）。示例：
          <Typography.Text code style={{ marginLeft: 6 }}>
            score &gt; 0.8
          </Typography.Text>
        </Typography.Paragraph>
        <Input
          value={edgeConditionDraft}
          onChange={(e) => setEdgeConditionDraft(e.target.value)}
          placeholder="(empty = unconditional)"
          data-testid="edge-condition-input"
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
          <Button onClick={() => setEdgeConfigOpen(false)}>Cancel</Button>
          <Button type="primary" onClick={handleSaveEdgeCondition} data-testid="edge-condition-save">
            Save
          </Button>
        </div>
      </Drawer>

      {/* Code Export Modal - Keep as is for now or refactor later */}
      <CodeExportModal
        open={exportModalOpen}
        nodes={nodes}
        edges={edges}
        onClose={() => setExportModalOpen(false)}
      />

      {/* PRD-030: Side-effect Confirm Modal */}
      <Modal
        title="需要确认外部副作用"
        open={!!pendingConfirm}
        onCancel={() => submitConfirmDecision('deny')}
        maskClosable={false}
        closable={!confirmSubmitting}
        footer={[
          <Button
            key="deny"
            danger
            onClick={() => submitConfirmDecision('deny')}
            loading={confirmSubmitting}
            data-testid="confirm-deny-button"
          >
            Deny
          </Button>,
          <Button
            key="allow"
            type="primary"
            onClick={() => submitConfirmDecision('allow')}
            loading={confirmSubmitting}
            data-testid="confirm-allow-button"
          >
            Allow
          </Button>,
        ]}
      >
        <div data-testid="side-effect-confirm-modal">
          <span style={{ display: 'none' }}>需要确认外部副作用</span>
          <Alert
            type="warning"
            showIcon
            message="该工作流将执行外部副作用操作（默认 deny）"
            description="请选择 allow/deny 后才能继续同一 run 执行。"
            style={{ marginBottom: 12 }}
          />
          {/* Hidden element for E2E test to access confirm_id */}
          <input
            type="hidden"
            data-testid="confirm-id-hidden"
            value={pendingConfirm?.confirmId || ''}
          />
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            <Typography.Text type="secondary">run_id:</Typography.Text>{' '}
            <Typography.Text code>{pendingConfirm?.runId}</Typography.Text>
          </Typography.Paragraph>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            <Typography.Text type="secondary">workflow_id:</Typography.Text>{' '}
            <Typography.Text code>{pendingConfirm?.workflowId || '-'}</Typography.Text>
          </Typography.Paragraph>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            <Typography.Text type="secondary">node_id:</Typography.Text>{' '}
            <Typography.Text code>{pendingConfirm?.nodeId || '-'}</Typography.Text>
          </Typography.Paragraph>
        </div>
      </Modal>

      {/* Conflict Resolution Modal */}
      <Modal
        title={
          <span>
            <WarningOutlined style={{ color: '#faad14', marginRight: 8 }} />
            检测到编辑冲突
          </span>
        }
        open={hasConflicts}
        footer={null}
        onCancel={() => resolveAllConflicts('local')}
        width={500}
      >
        <Alert
          message="其他用户同时编辑了相同的元素"
          description="请选择如何解决冲突"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
        {conflicts.map((conflict) => (
          <div
            key={conflict.id}
            style={{
              padding: 12,
              marginBottom: 8,
              border: '1px solid #d9d9d9',
              borderRadius: 4,
            }}
          >
            <div style={{ marginBottom: 8 }}>
              <strong>
                {conflict.elementType === 'node' ? '节点' : '连线'}:
              </strong>{' '}
              {conflict.elementId}
              <span
                style={{ marginLeft: 8, color: '#999', fontSize: 12 }}
              >
                ({conflict.type === 'node_modified' || conflict.type === 'edge_modified'
                  ? '已修改'
                  : '已删除'})
              </span>
            </div>
            <Button.Group size="small">
              <Button onClick={() => handleResolveConflict(conflict.id, 'local')}>
                保留本地
              </Button>
              <Button onClick={() => handleResolveConflict(conflict.id, 'remote')}>
                使用远程
              </Button>
              <Button
                type="primary"
                onClick={() => handleResolveConflict(conflict.id, 'merge')}
              >
                合并
              </Button>
            </Button.Group>
          </div>
        ))}
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Button
            onClick={() => resolveAllConflicts('local')}
            style={{ marginRight: 8 }}
          >
            全部保留本地
          </Button>
          <Button type="primary" onClick={() => resolveAllConflicts('merge')}>
            全部合并
          </Button>
        </div>
      </Modal>

      {/* Step F.7: ResearchResult Drawer */}
      <Drawer
        title={
          <span>
            <ExperimentOutlined style={{ marginRight: 8 }} />
            Research Results
          </span>
        }
        placement="right"
        width={600}
        open={resultDrawerOpen}
        onClose={() => setResultDrawerOpen(false)}
        destroyOnClose
      >
        {researchResult && <ResearchResultDisplay result={researchResult} />}
      </Drawer>

      {/* MVP Step 1: Research Plan Drawer */}
      <Drawer
        title={
          <span>
            <SearchOutlined style={{ marginRight: 8 }} />
            Generate Research Plan
          </span>
        }
        placement="right"
        width={600}
        open={planDrawerOpen}
        onClose={() => {
          if (!isGenerating && !isCompiling) {
            setPlanDrawerOpen(false);
            resetResearchPlan();
            setResearchGoal('');
            setCompileWarnings([]);
          }
        }}
        destroyOnClose={false}
        extra={
          isGenerating ? (
            <Button size="small" onClick={cancelGeneration} danger>
              Cancel
            </Button>
          ) : null
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Input Section */}
          <div>
            <Typography.Text strong>Research Goal</Typography.Text>
            <Input.TextArea
              value={researchGoal}
              onChange={(e) => setResearchGoal(e.target.value)}
              placeholder="Describe what you want to research... e.g., 'Analyze user authentication patterns in the codebase'"
              rows={3}
              disabled={isGenerating || isCompiling}
              style={{ marginTop: 8 }}
            />
            <Button
              type="primary"
              onClick={handleGenerateResearchPlan}
              loading={isGenerating}
              disabled={!researchGoal.trim() || isCompiling}
              style={{ marginTop: 12 }}
              block
            >
              {isGenerating ? 'Generating...' : 'Generate Plan'}
            </Button>
          </div>

          {/* Thinking Content (streaming) */}
          {thinkingContent && (
            <Collapse
              items={[
                {
                  key: 'thinking',
                  label: 'AI Thinking...',
                  children: (
                    <pre style={{
                      whiteSpace: 'pre-wrap',
                      fontSize: 12,
                      maxHeight: 200,
                      overflow: 'auto',
                      background: '#f5f5f5',
                      padding: 8,
                      borderRadius: 4,
                    }}>
                      {thinkingContent}
                    </pre>
                  ),
                },
              ]}
              defaultActiveKey={['thinking']}
              size="small"
            />
          )}

          {/* Error Display */}
          {researchError && (
            <Alert
              type="error"
              message="Generation Failed"
              description={researchError.message}
              showIcon
            />
          )}

          {/* Plan Preview */}
          {researchPlan && (
            <div>
              <Typography.Text strong>Generated Plan</Typography.Text>
              <Collapse
                style={{ marginTop: 8 }}
                items={[
                  {
                    key: 'overview',
                    label: `${researchPlan.tasks.length} Tasks`,
                    children: (
                      <div>
                        {researchPlan.tasks.map((task, idx) => (
                          <div
                            key={task.id}
                            style={{
                              padding: '8px 12px',
                              background: idx % 2 === 0 ? '#fafafa' : '#fff',
                              borderRadius: 4,
                              marginBottom: 4,
                            }}
                          >
                            <Typography.Text strong>{task.id}</Typography.Text>
                            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                              [{task.type}]
                            </Typography.Text>
                            {task.dependencies.length > 0 && (
                              <div style={{ fontSize: 11, color: '#888' }}>
                                Depends on: {task.dependencies.join(', ')}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ),
                  },
                  {
                    key: 'parallel',
                    label: `Parallel Points (${researchPlan.parallel_points.length})`,
                    children: (
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {researchPlan.parallel_points.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                        {researchPlan.parallel_points.length === 0 && (
                          <Typography.Text type="secondary">None</Typography.Text>
                        )}
                      </ul>
                    ),
                  },
                  {
                    key: 'risks',
                    label: `Risk Points (${researchPlan.risk_points.length})`,
                    children: (
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {researchPlan.risk_points.map((r, i) => (
                          <li key={i} style={{ color: '#fa8c16' }}>{r}</li>
                        ))}
                        {researchPlan.risk_points.length === 0 && (
                          <Typography.Text type="secondary">None identified</Typography.Text>
                        )}
                      </ul>
                    ),
                  },
                  {
                    key: 'raw',
                    label: 'Raw JSON',
                    children: (
                      <pre style={{
                        fontSize: 11,
                        maxHeight: 200,
                        overflow: 'auto',
                        background: '#f5f5f5',
                        padding: 8,
                        borderRadius: 4,
                      }}>
                        {JSON.stringify(researchPlan, null, 2)}
                      </pre>
                    ),
                  },
                ]}
                defaultActiveKey={['overview']}
              />

              {/* Compile Button */}
              <Button
                type="primary"
                onClick={handleCompilePlan}
                loading={isCompiling}
                disabled={isGenerating}
                style={{ marginTop: 16 }}
                block
                icon={<PlayCircleOutlined />}
              >
                {isCompiling ? 'Compiling...' : 'Apply to Canvas'}
              </Button>
            </div>
          )}

          {/* Compile Warnings */}
          {compileWarnings.length > 0 && (
            <Alert
              type="warning"
              message="Compile Warnings"
              description={
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {compileWarnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              }
              showIcon
            />
          )}
        </div>
      </Drawer>
    </div>
  );
};

export default WorkflowEditorPageWithMutex;
