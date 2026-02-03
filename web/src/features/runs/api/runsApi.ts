/**
 * Run API 客户端
 *
 * 为什么需要这个文件？
 * - 封装所有 Run 相关的 API 调用
 * - 提供类型安全的 API 接口
 * - 集中管理 API 端点，方便维护
 *
 * 使用示例：
 * ```typescript
 * import { runsApi } from '@/features/runs/api/runsApi';
 *
 * // 获取 Agent 的 Run 列表
 * const runs = await runsApi.getRunsByAgent('agent-id');
 *
 * // 创建并执行 Run
 * const newRun = await runsApi.createRun({ agent_id: 'agent-id' });
 * ```
 */

import { get, post } from '@/shared/utils/request';
import type {
  Run,
  CreateRunDto,
  RunListParams,
  Task,
} from '@/shared/types';

/**
 * Run API 客户端
 */
export const runsApi = {
  /**
   * 获取指定 Agent 的 Run 列表
   *
   * @param agentId - Agent ID
   * @param params - 查询参数
   * @returns Run 列表
   *
   * API: GET /agents/{agent_id}/runs
   */
  getRunsByAgent: (agentId: string, params?: RunListParams): Promise<Run[]> => {
    return get<Run[]>(`/agents/${agentId}/runs`, { params });
  },

  /**
   * 获取单个 Run 详情
   *
   * @param id - Run ID
   * @returns Run 详情
   *
   * API: GET /runs/{id}
   */
  getRun: (id: string): Promise<Run> => {
    return get<Run>(`/runs/${id}`);
  },

  /**
   * 创建并执行 Run
   *
   * @param data - 创建 Run 的数据
   * @returns 创建的 Run
   *
   * API: POST /agents/{agent_id}/runs
   *
   * 注意：此接口会立即开始执行 Run
   */
  createRun: (data: CreateRunDto): Promise<Run> => {
    return post<Run>(`/agents/${data.agent_id}/runs`, data);
  },

  /**
   * 获取 Run 的 Task 列表
   *
   * @param runId - Run ID
   * @returns Task 列表
   *
   * API: GET /runs/{run_id}/tasks
   *
   * 注意：目前后端可能还没有实现此接口
   */
  getTasksByRun: (runId: string): Promise<Task[]> => {
    return get<Task[]>(`/runs/${runId}/tasks`);
  },
};

/**
 * 为什么 Run 和 Task 的 API 分开？
 *
 * 原因：
 * 1. 职责分离：Run 和 Task 是不同的领域概念
 * 2. 可维护性：每个 API 文件只关注一个资源
 * 3. 可扩展性：方便后续添加 Task 相关的其他 API
 *
 * 但是：
 * - getTasksByRun 放在 runsApi 中，因为它是通过 Run ID 查询的
 * - 如果后续有独立的 Task API（如 GET /tasks/{id}），可以创建 tasksApi.ts
 */
