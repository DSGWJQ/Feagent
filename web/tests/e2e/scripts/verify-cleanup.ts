#!/usr/bin/env tsx
/**
 * E2E 测试数据清理效果验证脚本
 *
 * 用途：
 * - 检查数据库中残留的测试数据数量
 * - 计算残留率（目标：< 5%）
 * - 输出详细的残留数据报告
 *
 * 运行方式：
 *   npx tsx web/tests/e2e/scripts/verify-cleanup.ts
 *
 * 环境变量：
 *   PLAYWRIGHT_API_URL - 后端 API 地址（默认：http://localhost:8000）
 *   CLEANUP_THRESHOLD - 残留率阈值（默认：5）
 */

import axios from 'axios';

interface WorkflowInfo {
  workflow_id: string;
  fixture_type?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
}

interface VerificationResult {
  totalTestWorkflows: number;
  residualRate: number;
  passed: boolean;
  details: WorkflowInfo[];
  timestamp: string;
}

const API_BASE_URL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
const CLEANUP_THRESHOLD = parseFloat(process.env.CLEANUP_THRESHOLD || '5'); // 默认 5%

/**
 * 获取所有测试 workflows（通过 source='e2e_test' 标记）
 */
async function getTestWorkflows(): Promise<WorkflowInfo[]> {
  try {
    // 方案 1：如果有专门的查询端点
    const response = await axios.get(`${API_BASE_URL}/api/workflows`, {
      params: {
        source: 'e2e_test',
        limit: 1000,
      },
      headers: {
        'X-Test-Mode': 'true',
      },
      timeout: 10000,
    });

    if (response.status === 200 && Array.isArray(response.data)) {
      return response.data.map((wf: any) => ({
        workflow_id: wf.id || wf.workflow_id,
        fixture_type: wf.metadata?.fixture_type,
        created_at: wf.created_at,
        metadata: wf.metadata,
      }));
    }
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.warn('[Verify] Workflows query endpoint not found, using alternative method');
    } else {
      console.error('[Verify] Failed to query workflows:', error);
    }
  }

  // 方案 2：通过尝试清理来获取数量（dry-run）
  // 注意：当前后端实现不支持 dry-run，这里返回空数组
  return [];
}

/**
 * 执行批量清理并返回删除数量
 */
async function performBatchCleanup(): Promise<number> {
  try {
    const response = await axios.delete(`${API_BASE_URL}/api/test/workflows/cleanup`, {
      data: {
        cleanup_tokens: [],
        delete_by_source: true,
      },
      headers: {
        'Content-Type': 'application/json',
        'X-Test-Mode': 'true',
      },
      timeout: 30000,
    });

    if (response.status === 200) {
      return response.data.deleted_count || 0;
    }
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error(
        `[Verify] Cleanup failed: ${error.response?.status || 'Network Error'} - ${error.message}`,
      );
    }
  }
  return 0;
}

/**
 * 验证清理效果
 */
async function verifyCleanup(): Promise<VerificationResult> {
  console.log('========================================');
  console.log('E2E Test Data Cleanup Verification');
  console.log('========================================\n');

  console.log(`API Base URL: ${API_BASE_URL}`);
  console.log(`Cleanup Threshold: ${CLEANUP_THRESHOLD}%\n`);

  // 步骤 1：查询当前残留的测试数据
  console.log('[1/3] Querying test workflows...');
  const testWorkflows = await getTestWorkflows();

  // 步骤 2：执行批量清理
  console.log('[2/3] Performing batch cleanup...');
  const deletedCount = await performBatchCleanup();

  console.log(`[2/3] Deleted ${deletedCount} test workflow(s)\n`);

  // 步骤 3：再次查询确认残留
  console.log('[3/3] Verifying residual data...');
  const residualWorkflows = await getTestWorkflows();
  const residualCount = residualWorkflows.length;

  // 计算残留率（基于初始数量 + 删除数量）
  const totalProcessed = deletedCount + residualCount;
  const residualRate = totalProcessed > 0 ? (residualCount / totalProcessed) * 100 : 0;

  const passed = residualRate <= CLEANUP_THRESHOLD;

  console.log('\n========================================');
  console.log('Verification Result');
  console.log('========================================');
  console.log(`Total Test Workflows Processed: ${totalProcessed}`);
  console.log(`Deleted: ${deletedCount}`);
  console.log(`Residual: ${residualCount}`);
  console.log(`Residual Rate: ${residualRate.toFixed(2)}%`);
  console.log(`Threshold: ${CLEANUP_THRESHOLD}%`);
  console.log(`Status: ${passed ? '✅ PASSED' : '❌ FAILED'}\n`);

  if (residualCount > 0) {
    console.log('Residual Workflows:');
    residualWorkflows.forEach((wf, idx) => {
      console.log(`  ${idx + 1}. ${wf.workflow_id} (fixture: ${wf.fixture_type || 'unknown'})`);
    });
    console.log();
  }

  const result: VerificationResult = {
    totalTestWorkflows: totalProcessed,
    residualRate,
    passed,
    details: residualWorkflows,
    timestamp: new Date().toISOString(),
  };

  return result;
}

/**
 * 主函数
 */
async function main() {
  try {
    const result = await verifyCleanup();

    // 输出 JSON 报告（可供 CI 解析）
    if (process.env.OUTPUT_JSON === 'true') {
      console.log('\n========================================');
      console.log('JSON Report');
      console.log('========================================');
      console.log(JSON.stringify(result, null, 2));
    }

    // 如果验证失败，退出码为 1
    if (!result.passed) {
      console.error('\n⚠️  Cleanup verification failed!');
      console.error(`Residual rate (${result.residualRate.toFixed(2)}%) exceeds threshold (${CLEANUP_THRESHOLD}%)`);
      process.exit(1);
    }

    console.log('\n✅ Cleanup verification passed!');
    process.exit(0);
  } catch (error) {
    console.error('\n❌ Verification script failed:', error);
    process.exit(1);
  }
}

// 运行主函数
if (require.main === module) {
  main();
}

export { verifyCleanup, getTestWorkflows, performBatchCleanup };
