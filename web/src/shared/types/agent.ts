/**
 * Agent 相关类型定义
 *
 * 为什么需要这个文件？
 * - 提供类型安全，避免运行时错误
 * - 与后端 API 响应结构保持一致
 * - 为 V0 生成的组件提供类型支持
 */

import type { AgentTask } from './task';

/**
 * Agent 实体
 *
 * 对应后端 Agent 模型
 */
export interface Agent {
  /** Agent 唯一标识（UUID） */
  id: string;

  /** Agent 名称 */
  name: string;

  /** 起始状态描述 */
  start: string;

  /** 目标状态描述 */
  goal: string;

  /** 创建时间（ISO 8601 格式） */
  created_at: string;

  /** 更新时间（ISO 8601 格式） */
  updated_at: string;

  /** 关联的任务列表（可选，创建 Agent 时返回） */
  tasks?: AgentTask[];
}

/**
 * 创建 Agent 的 DTO（Data Transfer Object）
 *
 * 为什么需要单独的 DTO？
 * - 创建时不需要 id、created_at、updated_at（由后端生成）
 * - 提供更清晰的 API 接口定义
 *
 * 字段说明：
 * - start: 必填，10-500 字符，描述当前状态或拥有的资源
 * - goal: 必填，10-500 字符，描述期望达到的目标或结果
 * - name: 可选，最大 100 字符，不提供时后端自动生成
 */
export interface CreateAgentDto {
  /** 起始状态描述（必填，10-500 字符） */
  start: string;

  /** 目标状态描述（必填，10-500 字符） */
  goal: string;

  /** Agent 名称（可选，最大 100 字符，不提供时自动生成） */
  name?: string;
}

/**
 * 更新 Agent 的 DTO
 *
 * 所有字段都是可选的，只更新提供的字段
 */
export interface UpdateAgentDto {
  /** Agent 名称 */
  name?: string;

  /** 起始状态描述 */
  start?: string;

  /** 目标状态描述 */
  goal?: string;
}

/**
 * Agent 列表查询参数
 */
export interface AgentListParams {
  /** 跳过的记录数（用于分页） */
  skip?: number;

  /** 返回的记录数（用于分页） */
  limit?: number;

  /** 搜索关键词（可选） */
  search?: string;
}
