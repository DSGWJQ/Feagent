/**
 * UX-WF-000: Explicit Create Header
 *
 * Contract:
 * - `/workflows/new` is the explicit workflow creation entry
 * - Creating a workflow must send header `X-Workflow-Create: explicit`
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('UX-WF-000: Explicit Create Header', () => {
  test('should send x-workflow-create: explicit when creating workflow', async ({ page, cleanupTokens }) => {
    test.setTimeout(60_000);

    let headerValue: string | undefined;
    let requestUrl: string | undefined;

    page.on('request', (request) => {
      if (request.method() !== 'POST') return;
      const url = request.url();
      if (!url.includes('/api/workflows/chat-create/stream')) return;

      const headers = request.headers();
      headerValue = headers['x-workflow-create'];
      requestUrl = url;
    });

    await page.goto('/workflows/new');

    const createTextarea = page.locator('[data-testid="workflow-chat-create-textarea"]');
    await expect(createTextarea).toBeVisible({ timeout: 15_000 });
    await createTextarea.fill(
      'S-05 请生成一个最小工作流：用 loop(range) 从 0 到 0 生成列表，并输出该列表。',
    );

    const createButton = page.locator('[data-testid="workflow-chat-create-submit"]');
    await expect(createButton).toBeEnabled();
    await createButton.click();

    await page.waitForURL(/\/workflows\/[^/]+\/edit/, { timeout: 60_000 });

    expect(
      headerValue,
      `missing x-workflow-create header on request: ${requestUrl ?? '<unknown>'}`,
    ).toBe('explicit');

    const editorUrl = page.url();
    const workflowIdMatch = editorUrl.match(/\/workflows\/([^/]+)\/edit/);
    const workflowId = workflowIdMatch?.[1] ?? '';
    expect(workflowId, `missing workflow id from url: ${editorUrl}`).toBeTruthy();
    if (workflowId) cleanupTokens.push(`cleanup_${workflowId}`);
  });
});
