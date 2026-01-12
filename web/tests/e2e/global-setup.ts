/**
 * Playwright 全局 Setup
 * 在所有测试开始前执行，用于清理残留的测试数据
 */

import { FullConfig } from '@playwright/test';
import { batchCleanupTestData } from './fixtures/workflowFixtures';
import { ensureBackendRunning } from './helpers/backend';

async function globalSetup(config: FullConfig) {
  console.log('\n========================================');
  console.log('Playwright Global Setup');
  console.log('========================================\n');

  // 检查环境变量
  const apiUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
  console.log(`API URL: ${apiUrl}`);
  console.log(`Test Mode: ${process.env.E2E_TEST_MODE || 'deterministic'}`);
  console.log(`Preserve on Failure: ${process.env.PRESERVE_ON_FAILURE || 'false'}\n`);

  // Ensure backend is available for Seed API and Runs API before cleanup.
  await ensureBackendRunning();

  // 清理残留的测试数据（从上次测试失败或中断留下的）
  try {
    console.log('[Setup] Cleaning up residual test data from previous runs...');
    const stats = await batchCleanupTestData();
    console.log(`[Setup] Cleanup completed: ${stats.deleted} workflow(s) deleted\n`);
  } catch (error) {
    console.warn('[Setup] Failed to cleanup residual data:', error);
    console.warn('[Setup] Continuing with test execution...\n');
  }

  console.log('========================================');
  console.log('Setup Complete - Starting Tests');
  console.log('========================================\n');
}

export default globalSetup;
