/**
 * Workflow-related TypeScript types
 * These match the backend DTOs and entities
 */

// Workflow status
export type WorkflowStatus = 'draft' | 'published' | 'archived';

// Node types in workflow
export type NodeType = 'http' | 'llm' | 'javascript' | 'condition' | 'start' | 'end';

// Task types for classification
export type TaskType = 'data_analysis' | 'content_creation' | 'research' | 'problem_solving' | 'automation' | 'unknown';

// Task status
export type TaskStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';

// Run status
export type RunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';

// Scheduled workflow status
export type ScheduledWorkflowStatus = 'active' | 'disabled' | 'paused';

// Workflow entity
export interface Workflow {
  id: string;
  name: string;
  description?: string;
  status: WorkflowStatus;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  createdAt?: string;
  updatedAt?: string;
}

// Workflow node
export interface WorkflowNode {
  id: string;
  type: NodeType;
  label: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
  config?: Record<string, unknown>;
}

// Workflow edge
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  data?: Record<string, unknown>;
}

// Task entity
export interface Task {
  id: string;
  runId: string;
  type: string;
  status: TaskStatus;
  inputData: Record<string, unknown>;
  outputData?: Record<string, unknown>;
  error?: string;
  createdAt?: string;
  updatedAt?: string;
}

// Run entity
export interface Run {
  id: string;
  agentId: string;
  status: RunStatus;
  tasks: Task[];
  createdAt?: string;
  updatedAt?: string;
  completedAt?: string;
}

// Task Classification result
export interface ClassificationResult {
  taskType: TaskType;
  confidence: number;
  reasoning: string;
  suggestedTools: string[];
}

// Scheduled Workflow entity
export interface ScheduledWorkflow {
  id: string;
  workflowId: string;
  cronExpression: string;
  status: ScheduledWorkflowStatus;
  maxRetries: number;
  consecutiveFailures: number;
  lastExecutionStatus?: string;
  lastExecutionAt?: string;
  lastErrorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

// Tool entity
export interface Tool {
  id: string;
  name: string;
  description?: string;
  category?: string;
  version?: string;
  status?: 'draft' | 'published' | 'deprecated';
  createdAt?: string;
  updatedAt?: string;
}

// LLM Provider entity
export interface LLMProvider {
  id: string;
  name: string;
  apiKey?: string;
  apiKeyMasked?: string;
  baseUrl?: string;
  model?: string;
  enabled?: boolean;
  createdAt?: string;
  updatedAt?: string;
}

// Scheduler status information
export interface SchedulerStatus {
  schedulerRunning: boolean;
  totalJobsInScheduler: number;
  jobDetails: JobDetail[];
  message: string;
}

// Job detail information
export interface JobDetail {
  id: string;
  name: string;
  trigger: string;
  nextRunTime?: string;
}

// Scheduler jobs information
export interface SchedulerJobs {
  jobsInScheduler: JobDetail[];
  activeScheduledWorkflows: ScheduledWorkflowInfo[];
  summary: SchedulerSummary;
  message: string;
}

// Scheduled workflow info in scheduler
export interface ScheduledWorkflowInfo extends ScheduledWorkflow {
  isInScheduler: boolean;
}

// Scheduler summary
export interface SchedulerSummary {
  totalJobsInScheduler: number;
  totalActiveWorkflows: number;
  workflowsNotInScheduler: number;
}

// API Response wrapper for list endpoints
export interface ListResponse<T> {
  items: T[];
  total?: number;
  page?: number;
  pageSize?: number;
}

// API Error response
export interface ApiError {
  detail: string;
  statusCode?: number;
}
