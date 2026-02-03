/**
 * Deterministic UI E2E: Chat-create Task Catalog (S-03/S-04/S-06)
 *
 * Flow:
 * 1) Chat-create a workflow on the explicit create page (/workflows/new)
 * 2) Enter editor, save
 * 3) (optional) Configure execution input (JSON)
 * 4) Run and assert output semantics
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

async function setInitialInput(page: Page, initialInput: unknown): Promise<void> {
  const inputButton = page.locator('[data-testid="workflow-input-button"]');
  await expect(inputButton).toBeEnabled();
  await inputButton.click();

  const inputTextarea = page.locator('[data-testid="workflow-input-textarea"]');
  await expect(inputTextarea).toBeVisible({ timeout: 10_000 });
  await inputTextarea.fill(JSON.stringify(initialInput, null, 2));

  const inputDoneButton = page.locator('[data-testid="workflow-input-modal-done"]');
  await expect(inputDoneButton).toBeEnabled();
  await inputDoneButton.click();
  await expect(inputTextarea).not.toBeVisible({ timeout: 10_000 });
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
  const MAX_ALLOW_CLICKS = 10;
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
          `[workflow-chat-create-task-catalog-2] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`,
        );
      }

      // Modal may close and re-open quickly; treat either as progress.
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
          `[workflow-chat-create-task-catalog-2] final result is not valid JSON: ${String(err)} text=${finalText}`,
        );
      }
    }

    await page.waitForTimeout(200);
  }

  throw new Error('[workflow-chat-create-task-catalog-2] timed out waiting for final result');
}

test.describe('Workflow Chat-Create Task Catalog 2 (UI, deterministic)', () => {
  test('S-03: should chat-create sqlite write -> conditional -> notification and run to notification stub', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-03 请生成一个工作流：向 sqlite 写入一条数据，然后判断 rows_affected 是否大于 0；成功则发送 webhook 通知并结束。',
    );

    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      stub?: boolean;
      mode?: string;
      type?: string;
      subject?: string;
      message?: string;
    };

    expect(finalResult.stub).toBeTruthy();
    expect(finalResult.mode).toBe('deterministic');
    expect(finalResult.type).toBe('webhook');
    expect(finalResult.subject).toBe('Insert Done');
    expect(finalResult.message).toBe('insert ok');
  });

  test('S-04: should chat-create conditional branching and return A when input is \"test\"', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      "S-04 请生成一个工作流：输入字符串，若等于 test 走 A 分支输出 'A'，否则走 B 分支输出 'B'。",
    );

    await saveWorkflow(page, workflowId);
    await setInitialInput(page, 'test');

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as string;
    expect(finalResult).toBe('A');
  });

  test('S-04: should chat-create conditional branching and return B when input is not \"test\"', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      "S-04 请生成一个工作流：输入字符串，若等于 test 走 A 分支输出 'A'，否则走 B 分支输出 'B'。",
    );

    await saveWorkflow(page, workflowId);
    await setInitialInput(page, 'nope');

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as string;
    expect(finalResult).toBe('B');
  });

  test('S-06: should chat-create transform(field_mapping) and return mapped {id,name}', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-06 请生成一个工作流：输入是一个 JSON（含 user.profile.name 与 user.id），用 transform 做字段映射输出 {id, name}。',
    );

    await saveWorkflow(page, workflowId);
    await setInitialInput(page, { user: { id: 42, profile: { name: 'Alice' } } });

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as { id?: number; name?: string };
    expect(finalResult).toEqual({ id: 42, name: 'Alice' });
  });
});
