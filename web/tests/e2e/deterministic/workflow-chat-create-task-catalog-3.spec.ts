/**
 * Deterministic UI E2E: Chat-create Task Catalog (S-02/S-09/S-10)
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
  const MAX_ALLOW_CLICKS = 15;
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
          `[workflow-chat-create-task-catalog-3] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`,
        );
      }

      await expect(async () => {
        const visible = await confirmModal.isVisible().catch(() => false);
        const currentConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
        expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
      }).toPass({ timeout: 15_000 });
    }

    const finalText = (await finalResultLocator.textContent())?.trim() ?? '';
    if (finalText) {
      try {
        return JSON.parse(finalText);
      } catch (err) {
        throw new Error(
          `[workflow-chat-create-task-catalog-3] final result is not valid JSON: ${String(err)} text=${finalText}`,
        );
      }
    }

    await page.waitForTimeout(200);
  }

  throw new Error('[workflow-chat-create-task-catalog-3] timed out waiting for final result');
}

test.describe('Workflow Chat-Create Task Catalog 3 (UI, deterministic)', () => {
  test('S-02: should create report pipeline and read back aggregated JSON from file', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-02 请生成一个工作流：查询销售数据，统计 count/sum/avg，并将聚合结果写入文件后再读回输出。',
    );
    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      path?: string;
      content?: string;
      size?: number;
    };

    expect(String(finalResult.path ?? '')).toContain(`report_${workflowId}`);
    expect(Number(finalResult.size ?? 0)).toBeGreaterThan(0);

    const content = String(finalResult.content ?? '').trim();
    const parsed = JSON.parse(content) as { count?: number; sum_amount?: number; avg_amount?: number };
    expect(parsed).toEqual({ count: 3, sum_amount: 60, avg_amount: 20 });
  });

  test('S-09: should create embedding -> write file -> read back embedding payload', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-09 请生成一个工作流：对输入文本生成 embedding（deterministic stub），写入文件后再读回输出。',
    );
    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as { content?: string };
    const content = String(finalResult.content ?? '').trim();
    const embed = JSON.parse(content) as {
      stub?: boolean;
      mode?: string;
      model?: string;
      dimensions?: number;
      embeddings?: number[][];
    };
    expect(embed.stub).toBeTruthy();
    expect(embed.mode).toBe('deterministic');
    expect(embed.model).toContain('openai/');
    expect(embed.dimensions).toBe(3);
    expect(Array.isArray(embed.embeddings)).toBeTruthy();
    expect(embed.embeddings?.[0]?.length).toBe(3);
  });

  test('S-10: should create scaffold files and list directory contents', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-10 请生成一个工作流：在 tmp/scaffold 下生成 README.md 与 main.py，然后 list 目录并输出清单（不执行任何命令）。',
    );
    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      operation?: string;
      count?: number;
      items?: Array<{ name?: string }>;
    };

    expect(finalResult.operation).toBe('list');
    expect(Number(finalResult.count ?? 0)).toBeGreaterThanOrEqual(2);

    const names = new Set((finalResult.items ?? []).map((item) => item?.name).filter(Boolean));
    expect(names.has('README.md')).toBeTruthy();
    expect(names.has('main.py')).toBeTruthy();
  });
});
