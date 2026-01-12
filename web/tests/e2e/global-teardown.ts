/**
 * Playwright 全局 Teardown
 * 在所有测试结束后执行，用于最终清理和验证
 */

import { FullConfig } from '@playwright/test';
import { batchCleanupTestData } from './fixtures/workflowFixtures';
import { stopManagedBackend } from './helpers/backend';

async function globalTeardown(config: FullConfig) {
  console.log('\n========================================');
  console.log('Playwright Global Teardown');
  console.log('========================================\n');

  const preserveOnFailure = process.env.PRESERVE_ON_FAILURE === 'true';

  if (preserveOnFailure) {
    console.log('[Teardown] PRESERVE_ON_FAILURE=true, skipping final cleanup');
    console.log('[Teardown] Failed test data preserved for debugging\n');
  } else {
    // 执行最终清理（清理所有测试数据）
    try {
      console.log('[Teardown] Performing final cleanup...');
      const stats = await batchCleanupTestData();
      console.log(`[Teardown] Final cleanup completed: ${stats.deleted} workflow(s) deleted\n`);

      // 验证清理效果
      if (stats.deleted > 0) {
        console.log('[Teardown] ⚠️  Warning: Detected residual test data');
        console.log('[Teardown] This may indicate cleanup failures during tests');
      } else {
        console.log('[Teardown] ✅ No residual test data detected');
      }
    } catch (error) {
      console.error('[Teardown] Failed to perform final cleanup:', error);
    }
  }

  console.log('\n========================================');
  console.log('Teardown Complete');
  console.log('========================================\n');

  await stopManagedBackend();
}

export default globalTeardown;
