/**
 * Agent 相关的 React Query Hooks
 *
 * 为什么使用 TanStack Query（React Query）？
 * 1. 自动缓存：避免重复请求
 * 2. 自动重新获取：数据过期时自动刷新
 * 3. 乐观更新：提升用户体验
 * 4. 加载和错误状态：自动管理 loading 和 error
 * 5. 请求去重：多个组件同时请求相同数据时，只发送一次请求
 *
 * 使用示例：
 * ```typescript
 * function AgentList() {
 *   const { data: agents, isLoading, error } = useAgents();
 *
 *   if (isLoading) return <Spin />;
 *   if (error) return <div>加载失败</div>;
 *
 *   return <Table dataSource={agents} />;
 * }
 * ```
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import { agentsApi } from '@/features/agents/api/agentsApi';
import type {
  Agent,
  CreateAgentDto,
  UpdateAgentDto,
  AgentListParams,
} from '@/shared/types';

/**
 * Query Keys
 *
 * 为什么需要统一的 Query Keys？
 * - 避免 key 冲突
 * - 方便缓存失效（invalidateQueries）
 * - 类型安全
 */
export const agentKeys = {
  all: ['agents'] as const,
  lists: () => [...agentKeys.all, 'list'] as const,
  list: (params?: AgentListParams) => [...agentKeys.lists(), params] as const,
  details: () => [...agentKeys.all, 'detail'] as const,
  detail: (id: string) => [...agentKeys.details(), id] as const,
};

/**
 * 获取 Agent 列表
 *
 * @param params - 查询参数（可选）
 * @returns Query 结果
 *
 * 特性：
 * - 自动缓存 5 分钟
 * - 窗口聚焦时自动重新获取
 */
export const useAgents = (params?: AgentListParams) => {
  return useQuery({
    queryKey: agentKeys.list(params),
    queryFn: () => agentsApi.getAgents(params),
    staleTime: 5 * 60 * 1000, // 5 分钟内数据被认为是新鲜的
    gcTime: 10 * 60 * 1000, // 10 分钟后清除缓存（原 cacheTime）
  });
};

/**
 * 获取单个 Agent 详情
 *
 * @param id - Agent ID
 * @returns Query 结果
 *
 * 特性：
 * - 只有当 id 存在时才会发起请求（enabled: !!id）
 * - 自动缓存 5 分钟
 */
export const useAgent = (id: string) => {
  return useQuery({
    queryKey: agentKeys.detail(id),
    queryFn: () => agentsApi.getAgent(id),
    enabled: !!id, // 只有当 id 存在时才发起请求
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
};

/**
 * 创建 Agent
 *
 * @returns Mutation 结果
 *
 * 特性：
 * - 成功后自动刷新 Agent 列表
 * - 显示成功/失败提示
 * - 返回创建的 Agent 数据
 *
 * 使用示例：
 * ```typescript
 * const createAgent = useCreateAgent();
 *
 * const handleSubmit = async (values) => {
 *   try {
 *     const agent = await createAgent.mutateAsync(values);
 *     navigate(`/agents/${agent.id}`);
 *   } catch (error) {
 *     // 错误已经在 onError 中处理
 *   }
 * };
 * ```
 */
export const useCreateAgent = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAgentDto) => agentsApi.createAgent(data),
    onSuccess: (newAgent) => {
      // 刷新 Agent 列表缓存
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });

      // 可选：将新 Agent 添加到缓存中
      queryClient.setQueryData(agentKeys.detail(newAgent.id), newAgent);

      message.success('创建成功');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '创建失败');
    },
  });
};

/**
 * 更新 Agent
 *
 * @returns Mutation 结果
 *
 * 特性：
 * - 成功后自动刷新相关缓存
 * - 显示成功/失败提示
 */
export const useUpdateAgent = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateAgentDto }) =>
      agentsApi.updateAgent(id, data),
    onSuccess: (updatedAgent) => {
      // 刷新列表和详情缓存
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });
      queryClient.setQueryData(agentKeys.detail(updatedAgent.id), updatedAgent);

      message.success('更新成功');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '更新失败');
    },
  });
};

/**
 * 删除 Agent
 *
 * @returns Mutation 结果
 *
 * 特性：
 * - 成功后自动刷新 Agent 列表
 * - 显示成功/失败提示
 * - 乐观更新（可选）
 *
 * 使用示例：
 * ```typescript
 * const deleteAgent = useDeleteAgent();
 *
 * const handleDelete = (id: string) => {
 *   Modal.confirm({
 *     title: '确认删除？',
 *     onOk: () => deleteAgent.mutate(id),
 *   });
 * };
 * ```
 */
export const useDeleteAgent = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => agentsApi.deleteAgent(id),
    onSuccess: (_, deletedId) => {
      // 刷新 Agent 列表缓存
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });

      // 移除详情缓存
      queryClient.removeQueries({ queryKey: agentKeys.detail(deletedId) });

      message.success('删除成功');
    },
    onError: (error: any) => {
      message.error(error?.response?.data?.detail || '删除失败');
    },
  });
};

/**
 * 为什么使用 Mutation 而不是直接调用 API？
 *
 * 优点：
 * 1. 自动管理加载状态：isLoading, isSuccess, isError
 * 2. 自动缓存失效：成功后自动刷新相关数据
 * 3. 乐观更新：可以在请求完成前更新 UI
 * 4. 错误处理：统一的错误处理逻辑
 * 5. 重试机制：失败后自动重试
 *
 * 示例：
 * ```typescript
 * const createAgent = useCreateAgent();
 *
 * // 自动管理状态
 * if (createAgent.isLoading) return <Spin />;
 *
 * // 调用 mutation
 * createAgent.mutate(data);
 * ```
 */
