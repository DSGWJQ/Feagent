/**
 * Deterministic UI E2E: Chat-create Task Catalog (S-15/S-16)
 *
 * Scope:
 * - S-15: Parameterized project scaffold (template-rendered paths + content) with readback verification.
 * - S-16: Conditional scaffold (cli vs lib) via edge gating; verify correct branch output.
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
      throw new Error(`[workflow-chat-create-task-catalog-6] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`);
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
      `[workflow-chat-create-task-catalog-6] final result is not valid JSON: ${String(err)} text=${finalText}`,
    );
  }
}

type ListedItem = { name?: string; type?: string; path?: string };
type ListResult = { path?: string; items?: ListedItem[]; count?: number };

test.describe('Workflow Chat-Create Task Catalog 6 (UI, deterministic)', () => {
  test('S-15: should generate parameterized scaffold and return files + README readback', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-15 请生成一个工作流：用输入 project.name 参数化生成项目目录与文件（README.md/main.py），并在最后输出目录清单和 README 内容（用于验证模板渲染）。',
    );
    await saveWorkflow(page, workflowId);
    await setInitialInput(page, { project: { name: 'MyApp' } });

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as {
      project_dir?: string;
      files?: ListedItem[];
      readme?: string;
    };

    expect(String(finalResult.project_dir ?? '')).toContain(`scaffold_${workflowId}`);
    expect(String(finalResult.project_dir ?? '')).toContain('MyApp');

    const files = Array.isArray(finalResult.files) ? finalResult.files : [];
    expect(files.some((it) => it?.name === 'README.md')).toBeTruthy();
    expect(files.some((it) => it?.name === 'main.py')).toBeTruthy();

    expect(String(finalResult.readme ?? '')).toContain('# MyApp');
  });

  test('S-16: should scaffold CLI when input.kind == cli', async ({ page, cleanupTokens }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-16 请生成一个工作流：根据 input.kind 选择生成 CLI(main.py) 或 Library(__init__.py) 骨架，并输出目录清单；要求 conditional 分支只执行一个分支。',
    );
    await saveWorkflow(page, workflowId);
    await setInitialInput(page, { kind: 'cli' });

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as ListResult;
    const items = Array.isArray(finalResult.items) ? finalResult.items : [];
    expect(items.some((it) => it?.name === 'main.py')).toBeTruthy();
    expect(items.some((it) => it?.name === '__init__.py')).toBeFalsy();
  });

  test('S-16: should scaffold LIB when input.kind != cli', async ({ page, cleanupTokens }) => {
    test.setTimeout(120_000);

    const workflowId = await chatCreateToEditor(
      page,
      cleanupTokens,
      'S-16 请生成一个工作流：根据 input.kind 选择生成 CLI(main.py) 或 Library(__init__.py) 骨架，并输出目录清单；要求 conditional 分支只执行一个分支。',
    );
    await saveWorkflow(page, workflowId);
    await setInitialInput(page, { kind: 'lib' });

    const finalResult = (await runWorkflowAndReadFinalJson(page)) as ListResult;
    const items = Array.isArray(finalResult.items) ? finalResult.items : [];
    expect(items.some((it) => it?.name === '__init__.py')).toBeTruthy();
    expect(items.some((it) => it?.name === 'main.py')).toBeFalsy();
  });
});
