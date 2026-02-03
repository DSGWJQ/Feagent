/**
 * Deterministic UI E2E: Chat-create Task Catalog (S-17)
 *
 * Goal:
 * - Simulate real user operations (home chat-create -> editor -> save -> run)
 * - Cover the success path for `tool` nodes (requires a real tool_id)
 *
 * Strategy (KISS):
 * - Create a builtin tool via Tools API with implementation_config.handler="echo"
 * - Chat-create a deterministic workflow template using `S-17 tool_id=<id>` marker
 * - Save and run, asserting the final output is echoed back deterministically
 */

import { test, expect } from '../fixtures/workflowFixtures';
import type { APIRequestContext, Page } from '@playwright/test';

type ToolResponse = { id?: string };

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
      throw new Error(`[workflow-chat-create-task-catalog-7] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`);
    }

    await expect(async () => {
      const visible = await confirmModal.isVisible().catch(() => false);
      const currentConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
      expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
    }).toPass({ timeout: 15_000 });

    return true;
  };

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
      `[workflow-chat-create-task-catalog-7] final result is not valid JSON: ${String(err)} text=${finalText}`,
    );
  }
}

async function createEchoTool(request: APIRequestContext): Promise<string> {
  const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
  const suffix = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const name = `e2e_echo_${suffix}`;

  const response = await request.post(`${apiBaseUrl}/api/tools`, {
    data: {
      name,
      description: 'E2E echo tool (deterministic)',
      category: 'custom',
      author: 'e2e',
      parameters: [
        {
          name: 'message',
          type: 'string',
          description: 'Echo payload',
          required: false,
        },
      ],
      returns: { type: 'object' },
      implementation_type: 'builtin',
      implementation_config: { handler: 'echo' },
      tags: ['e2e', 'echo'],
    },
    headers: { 'Content-Type': 'application/json' },
  });

  expect(
    response.ok(),
    `tool create failed: HTTP ${response.status()} body=${await response.text().catch(() => '')}`,
  ).toBeTruthy();

  const payload = (await response.json().catch(() => ({}))) as ToolResponse;
  const toolId = String(payload.id ?? '');
  expect(toolId, `missing tool id from create response: ${JSON.stringify(payload)}`).toBeTruthy();
  return toolId;
}

async function deleteToolBestEffort(request: APIRequestContext, toolId: string): Promise<void> {
  if (!toolId) return;
  const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
  await request.delete(`${apiBaseUrl}/api/tools/${toolId}`).catch(() => null);
}

test.describe('Workflow Chat-Create Task Catalog (UI, deterministic)', () => {
  test('S-17: should chat-create tool(echo) workflow and run to echoed output', async ({
    page,
    request,
    cleanupTokens,
  }) => {
    test.setTimeout(120_000);

    const toolId = await createEchoTool(request);
    try {
      const workflowId = await chatCreateToEditor(
        page,
        cleanupTokens,
        `S-17 tool_id=${toolId} 请生成一个工作流：调用该 tool 回显 message，并输出 echoed 字段用于验证。`,
      );

      await saveWorkflow(page, workflowId);

      const finalResult = (await runWorkflowAndReadFinalJson(page)) as { echoed?: string };
      expect(finalResult.echoed).toBe(`tool_echo_${workflowId}`);
    } finally {
      await deleteToolBestEffort(request, toolId);
    }
  });
});
