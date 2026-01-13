import { test as base, TestInfo } from '@playwright/test';
import axios from 'axios';

/**
 * Seed Workflow 响应类型
 */
interface SeedWorkflowResponse {
  workflow_id: string;
  cleanup_token: string;
  fixture_type: string;
  metadata: Record<string, unknown>;
}

/**
 * Seed Workflow 选项
 */
interface SeedWorkflowOptions {
  fixtureType:
    | 'main_subgraph_only'
    | 'with_isolated_nodes'
    | 'side_effect_workflow'
    | 'invalid_config'
    | 'report_pipeline'
    | 'reconcile_sync'
    | 'code_assistant'
    | 'knowledge_assistant';
  projectId?: string;
  customMetadata?: Record<string, unknown>;
}

/**
 * 清理选项
 */
interface CleanupOptions {
  preserveOnFailure?: boolean; // 测试失败时是否保留数据用于调试
  silent?: boolean; // 是否静默模式（不输出日志）
}

/**
 * 清理统计信息
 */
interface CleanupStats {
  total: number;
  deleted: number;
  preserved: number;
  failed: number;
}

/**
 * Workflow Fixtures
 * 提供测试用的 workflow seed 和自动清理功能
 */
export const test = base.extend<{
  seedWorkflow: (options: SeedWorkflowOptions) => Promise<SeedWorkflowResponse>;
  cleanupTokens: string[];
}>({
  // 清理 token 收集器（增强版：支持失败保留）
  cleanupTokens: async ({}, use, testInfo: TestInfo) => {
    const tokens: string[] = [];
    await use(tokens);

    // 测试结束后根据状态决定是否清理
    if (tokens.length > 0) {
      const preserveOnFailure = process.env.PRESERVE_ON_FAILURE === 'true';
      const shouldPreserve = preserveOnFailure && testInfo.status !== 'passed';

      if (shouldPreserve) {
        console.log(
          `[Cleanup] Test ${testInfo.status}, preserving ${tokens.length} workflow(s) for debugging:`,
        );
        tokens.forEach((token) => {
          const workflowId = token.replace('cleanup_', '');
          console.log(`  - workflow_id: ${workflowId} (cleanup_token: ${token})`);
        });
      } else {
        await cleanupWorkflows(tokens, { preserveOnFailure: false });
      }
    }
  },

  // Seed Workflow Fixture
  seedWorkflow: async ({ cleanupTokens }, use) => {
    // Default to IPv4 loopback to avoid Node resolving `localhost` to `::1` on Windows
    // when backend binds to 127.0.0.1 only (causes ECONNREFUSED ::1:8000).
    const baseURL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';

    const seedWorkflow = async (options: SeedWorkflowOptions): Promise<SeedWorkflowResponse> => {
      const { fixtureType, projectId = 'e2e_test_project', customMetadata = {} } = options;

      try {
        const response = await axios.post<SeedWorkflowResponse>(
          `${baseURL}/api/test/workflows/seed`,
          {
            fixture_type: fixtureType,
            project_id: projectId,
            custom_metadata: {
              ...customMetadata,
              test_timestamp: new Date().toISOString(),
            },
          },
          {
            headers: {
              'Content-Type': 'application/json',
              'X-Test-Mode': 'true', // 安全控制: 必须携带此请求头
            },
            timeout: 10000,
          },
        );

        if (response.status !== 201) {
          throw new Error(`Seed API failed with status ${response.status}`);
        }

        const { workflow_id, cleanup_token } = response.data;

        // 收集 cleanup token 用于测试结束后清理
        cleanupTokens.push(cleanup_token);

        console.log(
          `[Seed] Created workflow: ${workflow_id} (fixture: ${fixtureType}, token: ${cleanup_token})`,
        );

        return response.data;
      } catch (error) {
        if (axios.isAxiosError(error)) {
          const status = error.response?.status;
          const message = error.response?.data?.detail || error.message;
          throw new Error(
            `Failed to seed workflow: ${status ? `HTTP ${status}` : 'Network Error'} - ${message}`,
          );
        }
        throw error;
      }
    };

    await use(seedWorkflow);
  },
});

/**
 * 清理测试 workflows（增强版）
 * @param cleanupTokens - 清理 token 列表
 * @param options - 清理选项
 * @returns 清理统计信息
 */
async function cleanupWorkflows(
  cleanupTokens: string[],
  options: CleanupOptions = {},
): Promise<CleanupStats> {
  const baseURL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
  const { silent = false } = options;

  const stats: CleanupStats = {
    total: cleanupTokens.length,
    deleted: 0,
    preserved: 0,
    failed: 0,
  };

  try {
    const response = await axios.delete(`${baseURL}/api/test/workflows/cleanup`, {
      data: {
        cleanup_tokens: cleanupTokens,
      },
      headers: {
        'Content-Type': 'application/json',
        'X-Test-Mode': 'true',
      },
      timeout: 10000,
    });

    if (response.status === 200) {
      stats.deleted = response.data.deleted_count || 0;
      stats.failed = response.data.failed?.length || 0;

      if (!silent) {
        console.log(`[Cleanup] Successfully deleted ${stats.deleted}/${stats.total} workflow(s)`);
        if (stats.failed > 0) {
          console.warn(`[Cleanup] Failed to delete ${stats.failed} workflow(s):`, response.data.failed);
        }
      }
    } else {
      console.warn(`[Cleanup] Cleanup returned status ${response.status}`);
      stats.failed = stats.total;
    }
  } catch (error) {
    // 清理失败不应阻塞测试
    stats.failed = stats.total;
    if (axios.isAxiosError(error)) {
      console.error(
        `[Cleanup] Failed to cleanup workflows: ${error.response?.status || 'Network Error'} - ${error.message}`,
      );
    } else {
      console.error(`[Cleanup] Unexpected error during cleanup:`, error);
    }
  }

  return stats;
}

/**
 * 批量清理所有测试数据（按 source='e2e_test' 标记）
 * 用途：测试套件开始前/结束后清理残留数据
 * @returns 清理统计信息
 */
export async function batchCleanupTestData(): Promise<CleanupStats> {
  const baseURL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';

  const stats: CleanupStats = {
    total: 0,
    deleted: 0,
    preserved: 0,
    failed: 0,
  };

  try {
    const response = await axios.delete(`${baseURL}/api/test/workflows/cleanup`, {
      data: {
        cleanup_tokens: [],
        delete_by_source: true, // 按 source='e2e_test' 批量删除
      },
      headers: {
        'Content-Type': 'application/json',
        'X-Test-Mode': 'true',
      },
      timeout: 30000, // 批量清理可能较慢
    });

    if (response.status === 200) {
      stats.deleted = response.data.deleted_count || 0;
      stats.total = stats.deleted;
      console.log(`[Batch Cleanup] Deleted ${stats.deleted} test workflow(s) by source='e2e_test'`);
    } else {
      console.warn(`[Batch Cleanup] Cleanup returned status ${response.status}`);
    }
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error(
        `[Batch Cleanup] Failed: ${error.response?.status || 'Network Error'} - ${error.message}`,
      );
    } else {
      console.error(`[Batch Cleanup] Unexpected error:`, error);
    }
  }

  return stats;
}

export { expect } from '@playwright/test';
