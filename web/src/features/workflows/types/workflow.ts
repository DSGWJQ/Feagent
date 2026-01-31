/**
 * 工作流类型定义
 *
 * 与后端 API 数据格式保持一致（V0 前端格式）
 */

/**
 * 节点位置
 */
export interface Position {
  x: number;
  y: number;
}

/**
 * 工作流节点
 *
 * 数据格式：
 * - id: 节点 ID
 * - type: 节点类型（start, end, httpRequest, textModel, etc.）
 * - position: 节点在画布上的位置
 * - data: 节点配置数据（不同类型节点有不同的配置）
 */
export interface WorkflowNode {
  id: string;
  type: string;
  position: Position;
  data: Record<string, unknown>;
}

/**
 * 工作流边（连线）
 *
 * 数据格式：
 * - id: 边 ID
 * - source: 源节点 ID
 * - target: 目标节点 ID
 * - sourceHandle: 源节点句柄（可选，用于条件分支）
 * - label: 边标签（可选）
 * - condition: 条件表达式（可选）
 */
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  label?: string;
  condition?: string;
}

/**
 * 工作流状态
 */
export enum WorkflowStatus {
  DRAFT = 'draft',
  PUBLISHED = 'published',
  ARCHIVED = 'archived',
}

/**
 * 工作流
 */
export interface Workflow {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  status: WorkflowStatus;
  created_at: string;
  updated_at: string;
}

/**
 * 更新工作流请求
 */
export interface UpdateWorkflowRequest {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

/**
 * 执行工作流请求
 */
export interface ExecuteWorkflowRequest {
  initial_input?: unknown;
  run_id?: string;
}

/**
 * 执行工作流响应
 */
export interface ExecuteWorkflowResponse {
  execution_log: ExecutionLogEntry[];
  final_result: unknown;
  execution_summary?: ExecutionSummary;
}

/**
 * 执行日志条目
 */
export interface ExecutionLogEntry {
  node_id: string;
  node_type: string;
  output: unknown;
}

/**
 * 执行统计（由后端权威返回）
 */
export interface ExecutionSummary {
  total_nodes: number;
  success_nodes: number;
  failed_nodes: number;
  duration_ms?: number;
}

/**
 * SSE 事件类型
 */
export type SSEEventType =
  | 'node_start'
  | 'node_complete'
  | 'node_error'
  | 'workflow_complete'
  | 'workflow_error'
  | 'workflow_confirm_required'
  | 'workflow_confirmed';

/**
 * SSE 事件
 */
export interface SSEEvent {
  type: SSEEventType;
  run_id?: string;
  workflow_id?: string;
  node_id?: string;
  node_type?: string;
  node_name?: string;
  output?: unknown;
  error?: string;
  reason?: string;
  result?: unknown;
  execution_log?: ExecutionLogEntry[];
  execution_summary?: ExecutionSummary;
  confirm_id?: string;
  default_decision?: 'deny';
  decision?: 'allow' | 'deny';
}

/**
 * 节点执行状态
 */
export type NodeExecutionStatus = 'idle' | 'running' | 'completed' | 'error';
