/**
 * 统一导出所有 Hooks
 *
 * 为什么需要这个文件？
 * - 提供统一的导入入口
 * - 简化导入语句
 *
 * 使用示例：
 * ```typescript
 * // 好的做法
 * import { useAgents, useCreateAgent, useRuns } from '@/shared/hooks';
 *
 * // 不好的做法（导入路径太长）
 * import { useAgents } from '@/shared/hooks/useAgents';
 * import { useRuns } from '@/shared/hooks/useRuns';
 * ```
 */

// Agent Hooks
export {
  useAgents,
  useAgent,
  useCreateAgent,
  useUpdateAgent,
  useDeleteAgent,
  agentKeys,
} from './useAgents';

// Run Hooks
export {
  useRunsByAgent,
  useRun,
  useCreateRun,
  useTasksByRun,
  runKeys,
} from './useRuns';
