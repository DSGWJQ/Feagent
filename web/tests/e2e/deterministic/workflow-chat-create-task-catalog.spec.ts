/**
 * Deterministic UI E2E: Chat-create Task Catalog (S-01/S-05/S-08)
 *
 * Goal:
 * - Simulate real user operations (explicit create -> editor -> save -> run)
 * - Verify the deterministic chat-create templates can generate/save/execute workflows
 *
 * Scope:
 * - S-01: httpRequest(mock) -> file(write)
 * - S-05: loop(range) -> end
 * - S-08: structuredOutput(schema) -> end
 */

import { test, expect } from '../fixtures/workflowFixtures';
import type { Page } from '@playwright/test';

async function approveSideEffectsUntilSettled(page: Page): Promise<void> {
  const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
  const confirmModal = page.locator('[data-testid="side-effect-confirm-modal"]');
  const allowButton = page.locator('[data-testid="confirm-allow-button"]');
  const confirmIdHidden = page.locator('[data-testid="confirm-id-hidden"]');

  let allowClicks = 0;
  const MAX_ALLOW_CLICKS = 10;

  const approveSideEffectsIfNeeded = async (): Promise<boolean> => {
    if (!(await confirmModal.isVisible().catch(() => false))) return false;

    const previousConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
    await allowButton.waitFor({ state: 'visible', timeout: 5_000 });
    await expect(allowButton).toBeEnabled();
    await allowButton.click();

    allowClicks += 1;
    if (allowClicks > MAX_ALLOW_CLICKS) {
      throw new Error(`[workflow-chat-create-task-catalog] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`);
    }

    await expect(async () => {
      const visible = await confirmModal.isVisible().catch(() => false);
      const currentConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
      expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
    }).toPass({ timeout: 15_000 });

    return true;
  };

  // Red-team guard: a side-effect gated run may stay `idle` until the user approves the first modal.
  // Ensure the run actually started (either running status or confirm modal shown) before waiting
  // for terminal status.
  await expect(async () => {
    const modalVisible = await confirmModal.isVisible().catch(() => false);
    const status = await statusIndicator.getAttribute('data-status');
    expect(modalVisible || status === 'running').toBeTruthy();
  }).toPass({ timeout: 15_000 });

  await expect(async () => {
    await approveSideEffectsIfNeeded();
    const status = await statusIndicator.getAttribute('data-status');
    expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
  }).toPass({ timeout: 60_000 });
}

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

  await page.waitForSelector('[data-testid="workflow-canvas"]', { state: 'visible', timeout: 30_000 });
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

  await approveSideEffectsUntilSettled(page);

  const finalResultLocator = page.locator('[data-testid="workflow-final-result"]');
  await expect(finalResultLocator).not.toHaveText('', { timeout: 60_000 });

  const finalText = (await finalResultLocator.textContent())?.trim() ?? '';
  try {
    return JSON.parse(finalText);
  } catch (err) {
    throw new Error(
      `[workflow-chat-create-task-catalog] final result is not valid JSON: ${String(err)} text=${finalText}`,
    );
  }
}

test.describe('Workflow Chat-Create Task Catalog (UI, deterministic)', () => {
  test('S-01: should chat-create httpRequest(mock) -> file(write) and run to file result', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      "S-01 请生成一个工作流：调用订单 API（deterministic 使用 mock_response，不出网），把响应保存到文件，并输出文件写入结果。",
    );

    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      operation?: string;
      bytes_written?: number;
      path?: string;
    };

    expect(finalResult.operation).toBe('write');
    expect(Number(finalResult.bytes_written ?? 0)).toBeGreaterThan(0);
    expect(String(finalResult.path ?? '')).toContain(`http_file_${workflowId}`);
  });

  test('S-05: should chat-create loop(range) squares and run to list output', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-05 请生成一个工作流：用 loop(range) 从 0 到 4 生成对象列表（包含 i 与 square=i*i），并输出列表。',
    );

    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as Array<{ i?: number; square?: number }>;
    expect(Array.isArray(finalResult)).toBeTruthy();
    expect(finalResult).toHaveLength(5);
    expect(finalResult[0]).toEqual({ i: 0, square: 0 });
    expect(finalResult[4]).toEqual({ i: 4, square: 16 });
  });

  test('S-08: should chat-create structuredOutput(schema) and run to deterministic stub JSON', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-08 请生成一个工作流：使用 structuredOutput 做结构化抽取（schemaName=Ticket，schema 包含 name/phone/issue/priority），并输出结果。',
    );

    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      stub?: boolean;
      mode?: string;
      schemaName?: string;
      output?: { message?: string };
    };
    expect(finalResult.stub).toBeTruthy();
    expect(finalResult.mode).toBe('deterministic');
    expect(finalResult.schemaName).toBe('Ticket');
    expect(finalResult.output?.message).toBe('deterministic stub');
  });
});
