/**
 * Deterministic UI E2E: Chat-create Task Catalog (S-11..S-14)
 *
 * Scope:
 * - S-11: prompt -> textModel(det stub) -> file(write/read) -> end
 * - S-12: imageGeneration(det stub) -> end
 * - S-13: audio(det stub) -> end
 * - S-14: file(write) -> file(append) -> file(read) -> end
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
      throw new Error(`[workflow-chat-create-task-catalog-5] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`);
    }

    await expect(async () => {
      const visible = await confirmModal.isVisible().catch(() => false);
      const currentConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
      expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
    }).toPass({ timeout: 15_000 });

    return true;
  };

  // Red-team guard: a side-effect gated run may stay `idle` until the user approves the first modal.
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

  await approveSideEffectsUntilSettled(page);

  const finalResultLocator = page.locator('[data-testid="workflow-final-result"]');
  await expect(finalResultLocator).not.toHaveText('', { timeout: 60_000 });

  const finalText = (await finalResultLocator.textContent())?.trim() ?? '';
  try {
    return JSON.parse(finalText);
  } catch (err) {
    throw new Error(
      `[workflow-chat-create-task-catalog-5] final result is not valid JSON: ${String(err)} text=${finalText}`,
    );
  }
}

test.describe('Workflow Chat-Create Task Catalog 5 (UI, deterministic)', () => {
  test('S-11: should chat-create prompt -> textModel -> file(write/read) and read back stub output', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-11 请生成一个工作流：用 prompt 拼接输入生成提示词，交给 textModel 生成文本（deterministic 下 stub），把输出写入文件并读回，最后输出读回内容。',
    );
    await saveWorkflow(page, workflowId);
    await setInitialInput(page, 'MyApp');

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as { path?: string; content?: string; size?: number };
    expect(String(finalResult.path ?? '')).toContain(`s11_llm_${workflowId}`);
    expect(String(finalResult.content ?? '')).toContain('[deterministic stub:openai/gpt-4]');
    expect(String(finalResult.content ?? '')).toContain('MyApp');
    expect(Number(finalResult.size ?? 0)).toBeGreaterThan(0);
  });

  test('S-12: should chat-create imageGeneration(det stub) and return stub payload', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-12 请生成一个工作流：使用 imageGeneration 生成图片（deterministic 下返回 stub，不出网），输出结果。',
    );
    await saveWorkflow(page, workflowId);
    await setInitialInput(page, 'A red circle');

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      stub?: boolean;
      mode?: string;
      model?: string;
      prompt_preview?: string;
      image_b64?: string;
      outputFormat?: string;
    };

    expect(finalResult.stub).toBeTruthy();
    expect(finalResult.mode).toBe('deterministic');
    expect(finalResult.model).toBe('openai/dall-e-3');
    expect(String(finalResult.prompt_preview ?? '')).toContain('A red circle');
    expect(finalResult.image_b64).toBe('');
    expect(finalResult.outputFormat).toBe('png');
  });

  test('S-13: should chat-create audio(det stub) and return stub payload', async ({ page, cleanupTokens }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-13 请生成一个工作流：使用 audio 生成语音（deterministic 下返回 stub，不出网），输出结果。',
    );
    await saveWorkflow(page, workflowId);
    await setInitialInput(page, 'Hello world');

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      stub?: boolean;
      mode?: string;
      model?: string;
      voice?: string;
      text_preview?: string;
      audio_b64?: string;
      format?: string;
    };

    expect(finalResult.stub).toBeTruthy();
    expect(finalResult.mode).toBe('deterministic');
    expect(finalResult.model).toBe('openai/tts-1');
    expect(finalResult.voice).toBe('alloy');
    expect(String(finalResult.text_preview ?? '')).toContain('Hello world');
    expect(finalResult.audio_b64).toBe('');
    expect(finalResult.format).toBe('mp3');
  });

  test('S-14: should chat-create file(write)->append->read and read back combined content', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-14 请生成一个工作流：先写文件 line1\\n，再 append line2\\n，然后 read 并输出最终内容。',
    );
    await saveWorkflow(page, workflowId);

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as { path?: string; content?: string; size?: number };
    expect(String(finalResult.path ?? '')).toContain(`s14_append_${workflowId}`);
    expect(finalResult.content).toBe('line1\nline2\n');
    expect(Number(finalResult.size ?? 0)).toBeGreaterThan(0);
  });
});
