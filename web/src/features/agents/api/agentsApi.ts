/**
 * Agent API 客户端
 *
 * 为什么需要这个文件？
 * - 封装所有 Agent 相关的 API 调用
 * - 提供类型安全的 API 接口
 * - 集中管理 API 端点，方便维护
 *
 * 使用示例：
 * ```typescript
 * import { agentsApi } from '@/features/agents/api/agentsApi';
 *
 * // 获取 Agent 列表
 * const agents = await agentsApi.getAgents();
 *
 * // 创建 Agent
 * const newAgent = await agentsApi.createAgent({
 *   name: '数据分析助手',
 *   start: '有一个 CSV 文件',
 *   goal: '生成数据分析报告',
 * });
 * ```
 */

import request from '@/shared/utils/request';
import type {
  Agent,
  CreateAgentDto,
  UpdateAgentDto,
  AgentListParams,
} from '@/shared/types';

/**
 * Agent API 客户端
 */
export const agentsApi = {
  /**
   * 获取 Agent 列表
   *
   * @param params - 查询参数
   * @returns Agent 列表
   *
   * API: GET /api/agents
   */
  getAgents: (params?: AgentListParams): Promise<Agent[]> => {
    return request.get<Agent[]>('/api/agents', { params });
  },

  /**
   * 获取单个 Agent 详情
   *
   * @param id - Agent ID
   * @returns Agent 详情
   *
   * API: GET /api/agents/{id}
   */
  getAgent: (id: string): Promise<Agent> => {
    return request.get<Agent>(`/api/agents/${id}`);
  },

  /**
   * 创建 Agent
   *
   * @param data - 创建 Agent 的数据
   * @returns 创建的 Agent
   *
   * API: POST /api/agents
   */
  createAgent: (data: CreateAgentDto): Promise<Agent> => {
    return request.post<Agent>('/api/agents', data);
  },

  /**
   * 更新 Agent
   *
   * @param id - Agent ID
   * @param data - 更新的数据
   * @returns 更新后的 Agent
   *
   * API: PUT /api/agents/{id}
   *
   * 注意：目前后端可能还没有实现此接口
   */
  updateAgent: (id: string, data: UpdateAgentDto): Promise<Agent> => {
    return request.put<Agent>(`/api/agents/${id}`, data);
  },

  /**
   * 删除 Agent
   *
   * @param id - Agent ID
   *
   * API: DELETE /api/agents/{id}
   */
  deleteAgent: (id: string): Promise<void> => {
    return request.delete(`/api/agents/${id}`);
  },
};

/**
 * 为什么使用对象而不是单独的函数？
 *
 * 优点：
 * 1. 命名空间：避免函数名冲突（agentsApi.getAgents vs getAgents）
 * 2. 组织性：所有 Agent 相关的 API 都在一个对象中
 * 3. 可测试性：方便 Mock 整个 API 对象
 * 4. 可扩展性：方便添加新的 API 方法
 *
 * 示例：
 * ```typescript
 * // 好的做法
 * import { agentsApi } from '@/features/agents/api/agentsApi';
 * agentsApi.getAgents();
 *
 * // 不好的做法（容易冲突）
 * import { getAgents } from '@/features/agents/api/agentsApi';
 * import { getAgents } from '@/features/runs/api/runsApi'; // 冲突！
 * ```
 */
