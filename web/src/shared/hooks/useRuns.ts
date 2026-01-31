/**
 * Run 相关的 React Query Hooks
 *
 * 为什么需要单独的 useRuns？
 * - Run 和 Agent 是不同的资源
 * - Run 有特殊的轮询需求（RUNNING 状态时需要自动刷新）
 * - 方便管理 Run 相关的缓存
 *
 * 使用示例：
 * ```typescript
 * function RunList({ agentId }) {
 *   const { data: runs, isLoading } = useRunsByAgent(agentId);
 *
 *   return <Table dataSource={runs} />;
 * }
 * ```
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import { runsApi } from '@/features/runs/api/runsApi';
import type {
  CreateRunDto,
  RunListParams,
} from '@/shared/types';

type ApiError = {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

const getErrorDetail = (error: unknown, fallback: string) => {
  if (!error || typeof error !== 'object') {
    return fallback;
  }
  const maybe = error as ApiError;
  return maybe.response?.data?.detail || fallback;
};

/**
 * Query Keys
 */
export const runKeys = {
  all: ['runs'] as const,
  lists: () => [...runKeys.all, 'list'] as const,
  list: (agentId: string, params?: RunListParams) =>
    [...runKeys.lists(), agentId, params] as const,
  details: () => [...runKeys.all, 'detail'] as const,
  detail: (id: string) => [...runKeys.details(), id] as const,
  tasks: (runId: string) => [...runKeys.all, 'tasks', runId] as const,
};

/**
 * 获取指定 Agent 的 Run 列表
 *
 * @param agentId - Agent ID
 * @param params - 查询参数（可选）
 * @returns Query 结果
 *
 * 特性：
 * - 自动缓存 1 分钟（Run 数据变化较快）
 * - 只有当 agentId 存在时才发起请求
 */
export const useRunsByAgent = (agentId: string, params?: RunListParams) => {
  return useQuery({
    queryKey: runKeys.list(agentId, params),
    queryFn: () => runsApi.getRunsByAgent(agentId, params),
    enabled: !!agentId,
    staleTime: 1 * 60 * 1000, // 1 分钟
    gcTime: 5 * 60 * 1000, // 5 分钟
  });
};

/**
 * 获取单个 Run 详情
 *
 * @param id - Run ID
 * @param options - 配置选项
 * @returns Query 结果
 *
 * 特性：
 * - 如果 Run 状态是 RUNNING，自动每 3 秒刷新一次
 * - 自动缓存 1 分钟
 *
 * 为什么需要轮询？
 * - Run 执行是异步的，需要实时更新状态
 * - 用户需要看到执行进度
 *
 * 使用示例：
 * ```typescript
 * const { data: run } = useRun(runId);
 *
 * // 如果 run.status === 'RUNNING'，会自动每 3 秒刷新
 * ```
 */
export const useRun = (
  id: string,
  options?: {
    /** 是否启用轮询（默认：当状态为 RUNNING 时启用） */
    enablePolling?: boolean;
    /** 轮询间隔（毫秒，默认 3000） */
    pollingInterval?: number;
  }
) => {
  const query = useQuery({
    queryKey: runKeys.detail(id),
    queryFn: () => runsApi.getRun(id),
    enabled: !!id,
    staleTime: 1 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  // 如果状态是 RUNNING，启用轮询
  const shouldPoll =
    options?.enablePolling !== false &&
    query.data?.status === 'RUNNING';

  // 使用 refetchInterval 实现轮询
  const pollingInterval = shouldPoll
    ? options?.pollingInterval || 3000
    : false;

  return useQuery({
    ...query,
    refetchInterval: pollingInterval,
  });
};

/**
 * 创建并执行 Run
 *
 * @returns Mutation 结果
 *
 * 特性：
 * - 成功后自动刷新 Run 列表
 * - 显示成功/失败提示
 * - 返回创建的 Run 数据
 *
 * 使用示例：
 * ```typescript
 * const createRun = useCreateRun();
 *
 * const handleExecute = async (agentId: string) => {
 *   try {
 *     const run = await createRun.mutateAsync({ agent_id: agentId });
 *     navigate(`/runs/${run.id}`);
 *   } catch (error) {
 *     // 错误已经在 onError 中处理
 *   }
 * };
 * ```
 */
export const useCreateRun = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateRunDto) => runsApi.createRun(data),
    onSuccess: (newRun) => {
      // 刷新对应 Agent 的 Run 列表
      queryClient.invalidateQueries({
        queryKey: runKeys.list(newRun.agent_id),
      });

      // 将新 Run 添加到缓存中
      queryClient.setQueryData(runKeys.detail(newRun.id), newRun);

      message.success('开始执行');
    },
    onError: (error: unknown) => {
      message.error(getErrorDetail(error, '执行失败'));
    },
  });
};

/**
 * 获取 Run 的 Task 列表
 *
 * @param runId - Run ID
 * @returns Query 结果
 *
 * 特性：
 * - 自动缓存 1 分钟
 * - 只有当 runId 存在时才发起请求
 */
export const useTasksByRun = (runId: string) => {
  return useQuery({
    queryKey: runKeys.tasks(runId),
    queryFn: () => runsApi.getTasksByRun(runId),
    enabled: !!runId,
    staleTime: 1 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });
};

/**
 * 为什么 Run 的 staleTime 比 Agent 短？
 *
 * 原因：
 * - Agent 数据相对稳定，不经常变化
 * - Run 数据变化频繁（状态从 PENDING → RUNNING → SUCCEEDED/FAILED）
 * - 需要更频繁地刷新 Run 数据以获取最新状态
 *
 * 配置对比：
 * - Agent: staleTime = 5 分钟
 * - Run: staleTime = 1 分钟
 * - Run (RUNNING): refetchInterval = 3 秒
 */

/**
 * 为什么使用 refetchInterval 而不是 WebSocket？
 *
 * 优点：
 * 1. 简单：不需要额外的 WebSocket 服务器
 * 2. 可靠：HTTP 请求更稳定
 * 3. 兼容性好：所有浏览器都支持
 *
 * 缺点：
 * 1. 延迟：最多 3 秒的延迟
 * 2. 资源消耗：频繁的 HTTP 请求
 *
 * 后续优化：
 * - 可以使用 Server-Sent Events (SSE) 实现实时推送
 * - 或者使用 WebSocket 实现双向通信
 */
