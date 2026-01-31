/**
 * Task 相关类型定义
 *
 * Task 是 Run 执行过程中的子任务
 */

/**
 * Task 状态枚举
 *
 * 对应后端 TaskStatus 枚举
 */
export enum TaskStatus {
  /** 等待执行 */
  PENDING = 'PENDING',

  /** 执行中 */
  RUNNING = 'RUNNING',

  /** 执行成功 */
  SUCCEEDED = 'SUCCEEDED',

  /** 执行失败 */
  FAILED = 'FAILED',
}

/**
 * Task 状态显示配置
 */
export const TASK_STATUS_CONFIG = {
  [TaskStatus.PENDING]: {
    text: '等待执行',
    color: 'default',
    badge: 'default',
  },
  [TaskStatus.RUNNING]: {
    text: '执行中',
    color: 'processing',
    badge: 'processing',
  },
  [TaskStatus.SUCCEEDED]: {
    text: '执行成功',
    color: 'success',
    badge: 'success',
  },
  [TaskStatus.FAILED]: {
    text: '执行失败',
    color: 'error',
    badge: 'error',
  },
} as const;

/**
 * AgentTask - Agent 创建时生成的计划任务
 *
 * 对应后端 TaskResponse DTO（创建 Agent 时返回）
 *
 * 与 Task 的区别：
 * - AgentTask 是计划任务，还没有执行（没有 run_id）
 * - Task 是执行任务，关联到具体的 Run
 */
export interface AgentTask {
  /** Task 唯一标识（UUID） */
  id: string;

  /** 关联的 Agent ID */
  agent_id: string;

  /** 任务名称 */
  name: string;

  /** 任务描述（可选） */
  description: string | null;

  /** 任务状态 */
  status: string;

  /** 创建时间（ISO 8601 格式） */
  created_at: string;
}

/**
 * Task 实体 - Run 执行时的任务
 *
 * 对应后端 Task 实体（执行 Run 时）
 */
export interface Task {
  /** Task 唯一标识（UUID） */
  id: string;

  /** 关联的 Run ID */
  run_id: string;

  /** 任务名称 */
  name: string;

  /** 任务状态 */
  status: TaskStatus;

  /** 任务输入数据 */
  input_data: Record<string, unknown> | null;

  /** 任务输出结果 */
  output_data: Record<string, unknown> | null;

  /** 错误信息（失败时） */
  error: string | null;

  /** 创建时间（ISO 8601 格式） */
  created_at: string;

  /** 更新时间（ISO 8601 格式） */
  updated_at: string;
}
