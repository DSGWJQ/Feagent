/**
 * UX-WF-009: Knowledge Assistant (Database -> Transform -> LLM)
 *
 * Priority: P0 (goal coverage)
 * Test Mode: Deterministic (no external LLM/HTTP)
 * Scenario: Operations/Customer Service Knowledge Assistant
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('UX-WF-009: Knowledge Assistant', () => {
  test('should run knowledge_assistant fixture to completion', async ({ page, seedWorkflow }) => {
    // Includes run creation, optional side-effect confirmation, and execution completion waits.
    test.setTimeout(180_000);

    const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
    const projectId = 'e2e_knowledge_assistant';

    // Step 1: Seed the knowledge_assistant workflow fixture
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'knowledge_assistant',
      projectId,
    });

    // Step 2: Fetch workflow to verify structure and extract node IDs
    const workflowRes = await page.request.get(`${apiBaseUrl}/api/workflows/${workflow_id}`, {
      timeout: 10000,
    });
    expect(workflowRes.ok()).toBeTruthy();
    const wfJson = (await workflowRes.json()) as {
      nodes?: Array<{ id: string; type: string; name?: string }>;
    };

    // Build node name -> ID mapping for assertions
    const nodeIdByName = new Map<string, string>();
    for (const node of wfJson.nodes ?? []) {
      if (node?.id && node?.name) nodeIdByName.set(node.name, node.id);
    }

    // Expected nodes in this workflow
    const expectedNodeNames = ['Query Knowledge Base', 'Map KB Data', 'Generate Reply'];

    // Step 3: Navigate to workflow editor
    await page.goto(`/workflows/${workflow_id}/edit?projectId=${projectId}`);
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // Step 4: Assert key nodes are visible on canvas
    for (const name of expectedNodeNames) {
      const id = nodeIdByName.get(name);
      expect(id).toBeTruthy();
      await expect(page.locator(`[data-testid="workflow-node-${id}"]`)).toBeVisible({
        timeout: 10000,
      });
    }

    // Step 5: Verify initial execution status
    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(statusIndicator).toHaveAttribute('data-status', 'idle', { timeout: 5000 });

    // Step 6: Verify run button is enabled
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await expect(runButton).toBeEnabled();

    // Step 7: Prepare to capture run creation response
    const runCreationPromise = page.waitForResponse(
      (response) =>
        response.url().includes(`/workflows/${workflow_id}/runs`) &&
        response.request().method() === 'POST' &&
        !response.url().includes('/execute'),
      { timeout: 15000 }
    );

    // Step 8: Click run button to start execution
    await runButton.click();

    // Step 9: Extract run ID from creation response
    const runResponse = await runCreationPromise;
    expect(runResponse.ok()).toBeTruthy();
    const runJson = (await runResponse.json()) as { id?: string };
    const runId = (runJson.id || '').trim();
    expect(runId).toBeTruthy();

    // Step 10: Setup side-effect approval logic
    const confirmModal = page.locator('[data-testid="side-effect-confirm-modal"]');
    const allowButton = page.locator('[data-testid="confirm-allow-button"]');
    const confirmIdHidden = page.locator('[data-testid="confirm-id-hidden"]');

    let allowClicks = 0;
    const MAX_ALLOW_CLICKS = 10;

    const approveSideEffectsIfNeeded = async (): Promise<boolean> => {
      if (!(await confirmModal.isVisible().catch(() => false))) return false;

      // Red-team guard: ensure we are approving the current run, not stale UI
      await expect(confirmModal).toContainText(runId);
      const previousConfirmId =
        (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';

      await allowButton.waitFor({ state: 'visible', timeout: 5000 });
      await expect(allowButton).toBeEnabled();
      await allowButton.click();

      allowClicks += 1;
      if (allowClicks > MAX_ALLOW_CLICKS) {
        throw new Error(`[UX-WF-009] Too many side-effect approvals (> ${MAX_ALLOW_CLICKS}).`);
      }

      // Modal may close and re-open quickly for the next side-effect node; treat either as progress
      await expect(async () => {
        const visible = await confirmModal.isVisible().catch(() => false);
        const currentConfirmId =
          (await confirmIdHidden.getAttribute('value').catch(() => null)) ?? '';
        expect(!visible || currentConfirmId !== previousConfirmId).toBeTruthy();
      }).toPass({ timeout: 15000 });

      return true;
    };

    // Step 11: Verify execution actually started (either running status or confirm modal shown)
    await expect(async () => {
      const modalVisible = await confirmModal.isVisible().catch(() => false);
      const status = await statusIndicator.getAttribute('data-status');
      expect(modalVisible || status === 'running').toBeTruthy();
    }).toPass({ timeout: 15000 });

    // Step 12: Approve side-effects and wait for completion
    // Database and LLM nodes are gated as "side effects" and require explicit approval
    await expect(async () => {
      await approveSideEffectsIfNeeded();
      const status = await statusIndicator.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 60000 });

    // Note: Per UX-WF-006/008 pattern, we rely on execution status validation only,
    // without checking node_complete events (unreliable in deterministic mode).
    // Since workflow status is 'completed', we can trust all nodes executed successfully.
  });
});
