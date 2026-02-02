/**
 * Deterministic UI E2E: Workflow Data Cleaning
 *
 * Flow (user-facing):
 * 1) Chat-create a workflow on the home page
 * 2) Enter editor, save
 * 3) Configure execution input (JSON)
 * 4) Run and assert output semantics (dedupe + drop-empty + type conversion)
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('Workflow Data Cleaning (UI, deterministic)', () => {
  test('should chat-create -> save -> run -> produce cleaned output', async ({ page, cleanupTokens }) => {
    test.setTimeout(120_000);

    const chatCreatePrompt =
      '请通过 Chat-create 创建一个“数据清洗”工作流：类型转换、去重、去空。输入数据在 initial_input.data 数组里，输出清洗后的 data。';

    await page.goto('/');

    const createTextarea = page.locator('[data-testid="workflow-chat-create-textarea"]');
    await expect(createTextarea).toBeVisible({ timeout: 15_000 });
    await createTextarea.fill(chatCreatePrompt);

    const createButton = page.locator('[data-testid="workflow-chat-create-submit"]');
    await expect(createButton).toBeEnabled();
    await createButton.click();

    // Wait for navigation to the newly created workflow editor.
    await page.waitForURL(/\/workflows\/[^/]+\/edit/, { timeout: 30_000 });

    const editorUrl = page.url();
    const workflowIdMatch = editorUrl.match(/\/workflows\/([^/]+)\/edit/);
    const workflowId = workflowIdMatch?.[1] ?? '';
    expect(workflowId, `missing workflow id from url: ${editorUrl}`).toBeTruthy();
    if (workflowId) {
      // The cleanup API accepts "cleanup_{workflow_id}" tokens (same convention as seed workflows).
      cleanupTokens.push(`cleanup_${workflowId}`);
    }

    // The editor route should include projectId (chat-create defaults workflow.project_id),
    // so Runs API paths work without extra querystring hacks.
    await page.waitForSelector('[data-testid="workflow-canvas"]', { state: 'visible', timeout: 30_000 });

    // Save (explicit step to match UX contract; also ensures server-side validation runs).
    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await expect(saveButton).toBeEnabled();
    const saveResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'PATCH' &&
        response.url().includes(`/api/workflows/${workflowId}`),
      { timeout: 30_000 }
    );
    await saveButton.click();
    const saveResponse = await saveResponsePromise;
    expect(saveResponse.ok(), `save failed: HTTP ${saveResponse.status()} url=${saveResponse.url()}`).toBeTruthy();

    // Configure execution input.
    const initialInput = {
      data: [
        { user_id: '1', age: '20', email: 'a@example.com' },
        { user_id: '1', age: '20', email: 'a@example.com' }, // duplicate row
        { user_id: '', age: null, email: '   ' }, // empty row (should be dropped)
        { user_id: '2', age: '30', email: 'b@example.com' },
      ],
    };

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

    // Run.
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await expect(runButton).toBeEnabled();
    await runButton.click();

    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(async () => {
      const status = await statusIndicator.getAttribute('data-status');
      // Some workflows may complete quickly; treat completed/idle as terminal-ish.
      expect(['running', 'completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 15_000 });

    // If a side-effect confirm modal appears, allow it (with a strict cap to avoid infinite loops).
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
        throw new Error(`[workflow-data-cleaning] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`);
      }

      await expect(async () => {
        const visible = await confirmModal.isVisible().catch(() => false);
        const currentConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
        expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
      }).toPass({ timeout: 15_000 });

      return true;
    };

    await expect(async () => {
      await approveSideEffectsIfNeeded();
      const status = await statusIndicator.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 60_000 });

    // Assert semantic output (fail-closed: we require a parseable JSON final result).
    const finalResultLocator = page.locator('[data-testid="workflow-final-result"]');
    await expect(finalResultLocator).not.toHaveText('', { timeout: 60_000 });

    const finalText = (await finalResultLocator.textContent())?.trim() ?? '';
    let finalResult: unknown;
    try {
      finalResult = JSON.parse(finalText);
    } catch (err) {
      throw new Error(`[workflow-data-cleaning] final result is not valid JSON: ${String(err)} text=${finalText}`);
    }

    const resultObj = finalResult as { data?: Array<Record<string, unknown>> };
    expect(Array.isArray(resultObj.data)).toBeTruthy();

    const rows = (resultObj.data ?? []).slice();
    rows.sort((a, b) => Number(a.user_id ?? 0) - Number(b.user_id ?? 0));

    expect(rows).toEqual([
      { user_id: 1, age: 20, email: 'a@example.com' },
      { user_id: 2, age: 30, email: 'b@example.com' },
    ]);
  });
});
