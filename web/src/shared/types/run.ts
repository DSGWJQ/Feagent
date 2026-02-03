/**
 * Run 相关类型定义
 *
 * 为什么需要这个文件？
 * - 定义 Run 的状态和数据结构
 * - 与后端 RunStatus 枚举保持一致
 * - 为前端组件提供类型支持
 */

/**
 * Run 状态枚举
 *
 * 对应后端 RunStatus 枚举
 */
export const RunStatus = {
  /** 等待执行 */
  PENDING: 'PENDING',

  /** 执行中 */
  RUNNING: 'RUNNING',

  /** 执行成功 */
  SUCCEEDED: 'SUCCEEDED',

  /** 执行失败 */
  FAILED: 'FAILED',
} as const;

export type RunStatus = (typeof RunStatus)[keyof typeof RunStatus];

/**
 * Run 状态显示配置
 *
 * 用于在 UI 中显示不同状态的样式
 */
export const RUN_STATUS_CONFIG = {
  [RunStatus.PENDING]: {
    text: '等待执行',
    color: 'default',
    badge: 'default',
  },
  [RunStatus.RUNNING]: {
    text: '执行中',
    color: 'processing',
    badge: 'processing',
  },
  [RunStatus.SUCCEEDED]: {
    text: '执行成功',
    color: 'success',
    badge: 'success',
  },
  [RunStatus.FAILED]: {
    text: '执行失败',
    color: 'error',
    badge: 'error',
  },
} as const;

/**
 * Run 实体
 *
 * 对应后端 Run 模型
 */
export interface Run {
  /** Run 唯一标识（UUID） */
  id: string;

  /** 关联的 Agent ID */
  agent_id: string;

  /** 运行状态 */
  status: RunStatus;

  /** 执行结果（成功时） */
  result: string | null;

  /** 错误信息（失败时） */
  error: string | null;

  /** 创建时间（ISO 8601 格式） */
  created_at: string;

  /** 更新时间（ISO 8601 格式） */
  updated_at: string;
}

/**
 * 创建 Run 的 DTO
 *
 * 为什么只需要 agent_id？
 * - Run 是通过执行 Agent 创建的
 * - 其他字段（status、result、error）由后端自动生成
 */
export interface CreateRunDto {
  /** 要执行的 Agent ID */
  agent_id: string;
}

/**
 * Run 列表查询参数
 */
export interface RunListParams {
  /** 跳过的记录数（用于分页） */
  skip?: number;

  /** 返回的记录数（用于分页） */
  limit?: number;

  /** 按状态筛选 */
  status?: RunStatus;
}
