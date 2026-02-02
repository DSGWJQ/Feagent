/**
 * UX-WF-007: Reconcile / Sync Pipeline (HTTP -> Transform -> DB upsert -> Notification)
 *
 * Priority: P0 (goal coverage)
 * Test Mode: Deterministic (no external HTTP/LLM/notifications)
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('UX-WF-007: Reconcile / Sync Pipeline', () => {
  test('should run reconcile_sync fixture to completion', async ({ page, seedWorkflow }) => {
    // Includes run creation, optional side-effect confirmation, and execution completion waits.
    test.setTimeout(180_000);

    const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
    const projectId = 'e2e_reconcile_sync';

    const { workflow_id } = await seedWorkflow({
      fixtureType: 'reconcile_sync',
      projectId,
    });

    const workflowRes = await page.request.get(`${apiBaseUrl}/api/workflows/${workflow_id}`, {
      timeout: 10000,
    });
    expect(workflowRes.ok()).toBeTruthy();
    const wfJson = (await workflowRes.json()) as {
      nodes?: Array<{ id: string; type: string; name?: string }>;
    };

    const nodeIdByName = new Map<string, string>();
    for (const node of wfJson.nodes ?? []) {
      if (node?.id && node?.name) nodeIdByName.set(node.name, node.id);
    }

    const expectedNodeNames = [
      'Fetch External Orders',
      'Map Payload',
      'DB Init',
      'DB Upsert',
      'DB Verify',
      'Notify Ops',
    ];

    await page.goto(`/workflows/${workflow_id}/edit?projectId=${projectId}`);
    await page.waitForSelector('[data-testid="workflow-canvas"]', { state: 'visible', timeout: 15000 });

    for (const name of expectedNodeNames) {
      const id = nodeIdByName.get(name);
      expect(id).toBeTruthy();
      await expect(page.locator(`[data-testid="workflow-node-${id}"]`)).toBeVisible({ timeout: 10000 });
    }

    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(statusIndicator).toHaveAttribute('data-status', 'idle', { timeout: 5000 });

    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await expect(runButton).toBeEnabled();

    const runCreationPromise = page.waitForResponse(
      (response) =>
        response.url().includes(`/workflows/${workflow_id}/runs`) &&
        response.request().method() === 'POST' &&
        !response.url().includes('/execute'),
      { timeout: 15000 },
    );

    await runButton.click();

    const runResponse = await runCreationPromise;
    expect(runResponse.ok()).toBeTruthy();
    const runJson = (await runResponse.json()) as { id?: string };
    const runId = (runJson.id || '').trim();
    expect(runId).toBeTruthy();

    const confirmModal = page.locator('[data-testid="side-effect-confirm-modal"]');
    const allowButton = page.locator('[data-testid="confirm-allow-button"]');
    const confirmIdHidden = page.locator('[data-testid="confirm-id-hidden"]');

    let allowClicks = 0;
    const MAX_ALLOW_CLICKS = 10;

    const approveSideEffectsIfNeeded = async (): Promise<boolean> => {
      if (!(await confirmModal.isVisible().catch(() => false))) return false;

      await expect(confirmModal).toContainText(runId);
      const previousConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';

      await allowButton.waitFor({ state: 'visible', timeout: 5000 });
      await expect(allowButton).toBeEnabled();
      await allowButton.click();

      allowClicks += 1;
      if (allowClicks > MAX_ALLOW_CLICKS) {
        throw new Error(`[UX-WF-007] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`);
      }

      await expect(async () => {
        const visible = await confirmModal.isVisible().catch(() => false);
        const currentConfirmId = (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
        expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
      }).toPass({ timeout: 15000 });

      return true;
    };

    // Ensure execution actually started (either running status or confirm modal shown).
    await expect(async () => {
      const modalVisible = await confirmModal.isVisible().catch(() => false);
      const status = await statusIndicator.getAttribute('data-status');
      expect(modalVisible || status === 'running').toBeTruthy();
    }).toPass({ timeout: 15000 });

    // Some nodes (database/http/notification/etc.) are gated as "side effects" and require explicit allow/deny.
    // A single run may require multiple approvals (one per side-effect node).
    await expect(async () => {
      await approveSideEffectsIfNeeded();
      const status = await statusIndicator.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 60000 });
  });
});
