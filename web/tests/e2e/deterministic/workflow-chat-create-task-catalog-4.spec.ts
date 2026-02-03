/**
 * Deterministic UI E2E: Chat-create Task Catalog (S-07)
 */

import { test, expect } from '../fixtures/workflowFixtures';
import type { Page } from '@playwright/test';

async function chatCreateToEditor(
  page: Page,
  cleanupTokens: string[],
  prompt: string,
): Promise<string> {
  await page.goto('/workflows/new');

  const createTextarea = page.locator('[data-testid="workflow-chat-create-textarea"]');
  await expect(createTextarea).toBeVisible({ timeout: 15_000 });
  await createTextarea.fill(prompt);

  const createButton = page.locator('[data-testid="workflow-chat-create-submit"]');
  await expect(createButton).toBeEnabled();
  await createButton.click();

  await page.waitForURL(/\/workflows\/[^/]+\/edit/, { timeout: 30_000 });

  const editorUrl = page.url();
  const workflowIdMatch = editorUrl.match(/\/workflows\/([^/]+)\/edit/);
  const workflowId = workflowIdMatch?.[1] ?? '';
  expect(workflowId, `missing workflow id from url: ${editorUrl}`).toBeTruthy();
  if (workflowId) cleanupTokens.push(`cleanup_${workflowId}`);

  await page.waitForSelector('[data-testid="workflow-canvas"]', {
    state: 'visible',
    timeout: 30_000,
  });
  return workflowId;
}

async function saveWorkflow(page: Page, workflowId: string): Promise<void> {
  const saveButton = page.locator('[data-testid="workflow-save-button"]');
  await expect(saveButton).toBeEnabled();

  const saveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      response.url().includes(`/api/workflows/${workflowId}`),
    { timeout: 30_000 },
  );

  await saveButton.click();
  const saveResponse = await saveResponsePromise;
  expect(saveResponse.ok(), `save failed: HTTP ${saveResponse.status()} url=${saveResponse.url()}`).toBeTruthy();
}

async function runWorkflowAndReadFinalJson(page: Page): Promise<unknown> {
  const runButton = page.locator('[data-testid="workflow-run-button"]');
  await expect(runButton).toBeEnabled();
  await runButton.click();

  const confirmModal = page.locator('[data-testid="side-effect-confirm-modal"]');
  const allowButton = page.locator('[data-testid="confirm-allow-button"]');
  const confirmIdHidden = page.locator('[data-testid="confirm-id-hidden"]');
  const finalResultLocator = page.locator('[data-testid="workflow-final-result"]');

  let allowClicks = 0;
  const MAX_ALLOW_CLICKS = 20; // S-07 includes multiple file ops.
  const started = Date.now();

  while (Date.now() - started < 60_000) {
    if (await confirmModal.isVisible().catch(() => false)) {
      const previousConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
      await allowButton.waitFor({ state: 'visible', timeout: 5_000 });
      await expect(allowButton).toBeEnabled();
      await allowButton.click();

      allowClicks += 1;
      if (allowClicks > MAX_ALLOW_CLICKS) {
        throw new Error(
          `[workflow-chat-create-task-catalog-4] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`,
        );
      }

      await expect(async () => {
        const visible = await confirmModal.isVisible().catch(() => false);
        const currentConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
        expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
      }).toPass({ timeout: 15_000 });
    }

    const finalText = (await finalResultLocator.textContent())?.trim() ?? '';
    if (finalText) return JSON.parse(finalText);

    await page.waitForTimeout(200);
  }

  throw new Error('[workflow-chat-create-task-catalog-4] timed out waiting for final result');
}

test.describe('Workflow Chat-Create Task Catalog 4 (UI, deterministic)', () => {
  test('S-07: should create file list/read/delete workflow and end with empty directory listing', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-07 请生成一个工作流：列出 tmp 目录内容；读取指定文件；然后删除该文件并返回删除后的目录清单。',
    );
    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      operation?: string;
      count?: number;
      items?: unknown[];
      path?: string;
    };

    expect(finalResult.operation).toBe('list');
    expect(Number(finalResult.count ?? -1)).toBe(0);
    expect(Array.isArray(finalResult.items)).toBeTruthy();
    expect(finalResult.items).toHaveLength(0);
    expect(String(finalResult.path ?? '')).toContain(`s07_${workflowId}`);
  });
});
